from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import InvalidArgumentException
import requests
from bs4 import BeautifulSoup
import random

import json
import time
from src.log_colors import *


class SteamGifts:
    base_url = "https://www.steamgifts.com/"
    base_search_url = base_url + "giveaways/search?"
    search_url = ""
    cookie = {}
    profile = {}

    def __init__(self, config, display):
        # Load the config.
        self.config = config
        self.display = display

        # Setup the driver.
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--user-data-dir={}'.format(config["chrome-profile-path"]))
            self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        except InvalidArgumentException:
            print("Could not open a browser instance, make sure that all other instances of the profile " +
                  "are closed before running the application.")
            exit(-1)

        # Load the profile.
        self.get_profile_info()

        # Generate the search str.
        self.generate_search_url()

        # Retrieve giveaways.
        giveaways = self.retrieve_giveaways()

        # Enter the giveaways.
        self.enter_giveaways(giveaways)

        # Close the driver.
        self.driver.close()

    def get_soup(self, url, sleep=True):
        # Let the request wait a bit, to avoid bot detection.
        if sleep:
            time.sleep(float(random.randint(300, 800)) / 1000)
        self.driver.implicitly_wait(30)

        # Get the page
        self.driver.get(url)

        # Retrieve the html of the page as soup.
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def get_profile_info(self):
        # Get profile soup.
        soup = self.get_soup(self.base_url, sleep=False)

        # Load the required cookie for requests.
        print(self.driver.get_cookie("PHPSESSID")["value"])
        self.cookie = {
            'PHPSESSID': self.driver.get_cookie("PHPSESSID")["value"]
        }

        # Load the profile.
        profile_container = soup.find("a", {"class": "nav__button nav__button--is-dropdown", "href": "/account"})
        profile_spans = profile_container.findAll("span")
        self.profile = dict({
            "points": int(profile_spans[0].text),
            "level": int(profile_spans[1].text.split(" ")[1]),
            "xsrf_token": soup.find("input", {"name": "xsrf_token"})["value"]
        })

        print("profile", self.profile, self.cookie)

    def generate_search_url(self):
        # Create a custom search string.
        search_str = ""
        config_search = self.config["search"]
        if config_search:

            # Check if level min was filled in.
            if config_search["level_min"] is not None:
                search_str += "level_min={}&".format(str(min(self.profile["level"], config_search["level_min"])))

            # Check if level max was filled in.
            if config_search["level_max"] is not None:
                search_str += "level_max={}&".format(str(min(self.profile["level"], config_search["level_max"])))

            # Create a simple add function
            def simple_add(key):
                if config_search[key] is not None:
                    return "{key}={value}&".format(key=key, value=config_search[key])
                return ""

            search_str += simple_add("entry_min")
            search_str += simple_add("entry_max")
            search_str += simple_add("point_min")
            search_str += simple_add("point_max")

        # Create the final search url.
        self.search_url = (self.base_search_url + search_str)[:-1]
        print("Create search string: ", self.search_url)

    def retrieve_giveaways(self):
        soup = self.get_soup(self.search_url)

        # A function to retrieve a tag without an class.
        def has_no_class(tag):
            return not tag.has_attr('class')

        giveaway_list = soup.find("div", "widget-container").findChild(has_no_class, recursive=False).findChild(
            has_no_class, recursive=False)
        giveaway_entries = giveaway_list.findAll("div", "giveaway__row-inner-wrap")

        # Keep track of all the parsed entries.
        parsed_entries = []

        # Print the giveaways
        for giveaway_entry in giveaway_entries:
            # Check if the giveaway is not faded (already enrolled).
            if 'is-faded' in giveaway_entry['class']:
                continue

            # Get the name and set the rating default.
            app_name = giveaway_entry.find("a", {"class": "giveaway__heading__name"}).text
            steam_db_rating = -1

            # The url can either be an app or a bundle, we cannot deal with bundles. TODO: Fix bundles.
            steam_app_url_split = giveaway_entry.find("a", {"class": "giveaway__icon"})['href'].split("/")
            if steam_app_url_split[-3] == "app":

                steam_app_id = steam_app_url_split[-2]

                if self.config["search"]["use_steam_db"]:
                    steam_db_url = "https://steamdb.info/app/" + steam_app_id

                    # Get the app rating from steam db.
                    try:
                        steam_db_soup = self.get_soup(steam_db_url)
                        steam_db_rating = float(
                            steam_db_soup.find("div", {"class": "header-thing-number"}).text.split(" ")[1][:-1])
                    except AttributeError:
                        # TODO: Fix error for packs, can not find packs.
                        print("Could not retrieve data from: ", app_name, steam_db_url)
                        continue

                    # Check if the rating is inside the requested boundaries.
                    if self.config["search"]["rating_min"] and steam_db_rating < self.config["search"]["rating_min"]:
                        # The game did not satisfy the min rating requirements.
                        continue

                    # Check if the rating is inside the requested boundaries.
                    if self.config["search"]["rating_max"] and steam_db_rating > self.config["search"]["rating_max"]:
                        # The game did not satisfy the min rating requirements.
                        continue

            # Append to the entries.
            entry = {
                'name': app_name,
                'points': int(giveaway_entry.find_all("span", {"class": "giveaway__heading__thin"})[-1].text[1:-2]),
                'page': giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'],
                'giveaway_id': giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'].split("/")[2],
                'rating': steam_db_rating
            }
            parsed_entries.append(entry)

            self.display.log_console_text("Adding giveaway: " + str(entry))

        # TODO: If too few entries in here, then mine the next page as well.
        # Sort the entries.
        return sorted(parsed_entries, key=lambda row: (-row['rating'], -row['points']))

    def enter_giveaways(self, giveaways):
        self.display.log_console_text("Start entering giveaways!", config=log_verbose)

        # Loop through each giveaway.
        for giveaway in giveaways:
            self.enter_giveaway(giveaway)

    def enter_giveaway(self, giveaway):

        # Check if we have enough points to enter.
        if giveaway["points"] > self.profile["points"]:
            return False

        # First sleep random amount of time to not get a block.
        time.sleep(float(random.randint(300, 950)) / 1000)

        # Send the server a request to join the giveaway (with some sleep before).
        entry = requests.post(self.base_url + 'ajax.php',
                              data={'xsrf_token': self.profile["xsrf_token"], 'do': 'entry_insert', 'code': giveaway["giveaway_id"]},
                              cookies=self.cookie)

        # Check if the request was successful, so we can lower the points available on the profile.
        json_data = json.loads(entry.text)

        if json_data['type'] == 'success':
            # Lower the total points of the profile
            self.profile["points"] -= giveaway["points"]

            # Print that we entered the give-away.
            print("Entered giveaway: ", giveaway)
            self.display.log_console_text("Entered giveaway: " + str(giveaway), config=log_info)

            return True

        self.display.log_console_text("Could not enter giveaway: " + str(json_data), config=log_error)
        return False
