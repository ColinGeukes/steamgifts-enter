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
    search_params = []
    cookie = {}
    profile = {}
    min_entries = 10

    def __init__(self, config, display):
        # Load the config.
        self.config = config
        self.display = display

        # Setup the driver, exit if the setup was not successful.
        self.driver = self.setup_driver()
        if self.driver is None:
            return

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

    def setup_driver(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--user-data-dir={}'.format(self.config["chrome-profile-path"]))
            return webdriver.Chrome(ChromeDriverManager().install(), options=options)
        except InvalidArgumentException:
            self.display.log_console_text(
                "Could not open a browser instance, make sure that all other chrome instances of the profile " +
                "are closed before running the application.", log_error)
            return None

    def get_soup(self, url, sleep=True):
        # Do a random sleep before access.
        random_sleep(sleep)
        self.driver.implicitly_wait(30 + random.randint(0, 15))

        # Get profile soup.
        self.driver.get(url)

        # Retrieve the html of the page as soup.
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def get_request_soup(self, url, sleep=True):
        random_sleep(sleep)

        page = requests.get(url, cookies=self.cookie)
        return BeautifulSoup(page.text, "html.parser")

    def get_profile_info(self):
        # Get soup of main page.
        soup = self.get_soup(self.base_url, sleep=False)

        # Load the required cookie for requests.
        print(self.driver.get_cookie("PHPSESSID")["value"])
        self.cookie = {
            'PHPSESSID': self.driver.get_cookie("PHPSESSID")["value"]
        }

        # Load the profile.
        profile_container = soup.find("a", {"class": "nav__button nav__button--is-dropdown", "href": "/account"})
        profile_spans = profile_container.findAll("span")
        self.profile = dict(
            points=int(profile_spans[0].text),
            level=int(profile_spans[1].text.split(" ")[1]),
            xsrf_token=soup.find("input", {"name": "xsrf_token"})["value"],
            name=soup.find("a", {"class": "nav__avatar-outer-wrap"})["href"].split("/")[-1]
        )

        # Create the profile display.
        self.display.create_profile_display(self.profile)

        # Log the profile to the GUI.
        self.display.log_console_text("\nUser Profile:", log_verbose)
        self.display.log_console_text(" - PHPSESSID: %s\n - xsrf_token: %s\n - Level: %i\n - Points: %i" % (
            self.cookie["PHPSESSID"], self.profile["xsrf_token"], self.profile["level"], self.profile["points"]))

    def generate_search_url(self):
        # Log to the GUI console.
        self.display.log_console_text("\nGenerating search string.", log_verbose)

        # Create a custom search string.
        self.search_params = []
        config_search = self.config["search"]
        if config_search:

            # Check if level min was filled in.
            if config_search["level_min"] is not None:
                self.search_params.append(
                    "level_min={}".format(str(min(self.profile["level"], config_search["level_min"]))))

            # Check if level max was filled in.
            if config_search["level_max"] is not None:
                self.search_params.append(
                    "level_max={}".format(str(min(self.profile["level"], config_search["level_max"]))))

            # Create a simple add function
            def create_simple_param(key):
                if config_search[key] is not None:
                    return "{key}={value}".format(key=key, value=config_search[key])
                return ""

            self.search_params.append(create_simple_param("entry_min"))
            self.search_params.append(create_simple_param("entry_max"))
            self.search_params.append(create_simple_param("point_min"))
            self.search_params.append(create_simple_param("point_max"))

        # Create the final search url.
        self.display.log_console_text("Search params: %s" % str(self.search_params))

    def retrieve_giveaways(self):
        # Keep track of all the parsed entries.
        parsed_entries = []

        # Log the retrieval of giveaways to the console.
        self.display.log_console_text("\nRetrieving the giveaways to possible enter.", log_verbose)

        # Keep looping till we found enough entries.
        current_page = 1
        while len(parsed_entries) < self.min_entries:
            # Start the search for the given page.
            entries_found = self.retrieve_giveaways_page(parsed_entries, current_page)

            # Stop if we mined all the pages possible.
            if not entries_found:
                self.display.log_console_text("There were no more entries matching your search criteria.", log_warning)
                break

            # Increment the page.
            current_page += 1

        # Sort the entries and return them to enter.
        return sorted(parsed_entries, key=lambda row: (-row['rating'], -row['points']))

    def retrieve_paged_search_string(self, page):
        # Create copy of search params and add page search param.
        search_params_copy = self.search_params.copy()
        search_params_copy.append("page=%s" % str(page))

        # Return the final search url.
        return self.base_search_url + "&".join(search_params_copy)

    def retrieve_giveaways_page(self, parsed_entries, page):
        # Retrieve the soup of the current search with the given page
        soup = self.get_request_soup(self.retrieve_paged_search_string(page))
        self.display.log_console_text("Retrieving giveaways for page %i." % page)

        # Check if the site give a no-results page, if no-results then return false.
        if soup.find("div", {"class": "pagination pagination--no-results"}) is not None:
            self.display.log_console_text("There were no entries at page %i." % page, log_error)
            return False

        # Retrieve all the entries.
        giveaway_list = soup.find("div", "widget-container").findChild(has_no_class, recursive=False).findChild(
            has_no_class, recursive=False)
        giveaway_entries = giveaway_list.findAll("div", "giveaway__row-inner-wrap")

        # Print the giveaways
        for giveaway_entry in giveaway_entries:
            # Check if the giveaway is not faded (already enrolled).
            if 'is-faded' in giveaway_entry['class']:
                continue

            # Get the name and set the rating default.
            app_name = giveaway_entry.find("a", {"class": "giveaway__heading__name"}).text

            # Retrieve the steamDB rating.
            sdb_rating = self.get_giveaway_score(giveaway_entry.find("a", {"class": "giveaway__icon"})['href'])

            # Check if the minimal rating filter passed.
            if not self.filter_giveaway_sdb_rating(sdb_rating):
                # Show a warning error that it had insufficient rating, thus was not added.
                self.display.log_console_text("Passing giveaway: %s, insufficient rating on steamDB." % app_name)
                continue

            # Append to the entries.
            entry = dict(
                name=app_name,
                points=int(giveaway_entry.find_all("span", {"class": "giveaway__heading__thin"})[-1].text[1:-2]),
                page=giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'],
                giveaway_id=giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'].split("/")[2],
                rating=sdb_rating
            )
            parsed_entries.append(entry)

            # Log the addition of the give-away.
            self.display.log_console_text("Adding giveaway: " + str(entry))

        return True

    def filter_giveaway_sdb_rating(self, sdb_rating):
        # Check if db is not active, if so always let it pass.
        if not self.config["search"]["use_steam_db"]:
            return True

        # Check if the rating is inside the requested boundaries.
        if self.config["search"]["rating_min"] and sdb_rating < self.config["search"]["rating_min"]:
            # The game did not satisfy the min rating requirements.
            return False

        # Check if the rating is inside the requested boundaries.
        if self.config["search"]["rating_max"] and sdb_rating > self.config["search"]["rating_max"]:
            # The game did not satisfy the min rating requirements.
            return False

        # Filter passed successfully.
        return True

    def get_giveaway_score(self, steam_url):
        # Return perfect score if we are not using the steam db score calculating.
        if not self.config["search"]["use_steam_db"]:
            return 100

        # Split the url to check if the giveaway is a bundle or an app.
        steam_app_url_split = steam_url.split("/")

        steam_type = steam_app_url_split[-3]
        steam_id = steam_app_url_split[-2]

        # Return the game score if the entry is a single game.
        if steam_type == "app":
            return self.get_game_score(steam_id)

        # Return the bundle score if the entry is a bundle (multiple games).
        if steam_type == "sub":
            return self.get_bundle_score(steam_id)

        # Return a not implemented error, negative function.
        self.display.log_console_text("Giveaway-type (%s) not implemented!" % steam_type, log_error)
        return -1

    def get_bundle_score(self, steam_bundle_id):
        # Get the soup of the bundle page.
        soup = self.get_soup("https://store.steampowered.com/sub/%s" % steam_bundle_id)

        # Retrieve all the entries of the bundle.
        bundle_entries = soup.find_all("div", {"class": ["tab_item", "app_impression_tracked"]})

        # Get the rating of the games inside the bundle.
        total_bundle_score = 0
        for bundle_entry in bundle_entries:
            total_bundle_score += self.get_game_score(bundle_entry["data-ds-appid"])

        # Return avg game score.
        return total_bundle_score / len(bundle_entries)

    def get_game_score(self, steam_game_id):
        # Get the steamDB soup.
        steam_db_soup = self.get_soup("https://steamdb.info/app/%s" % steam_game_id)

        # Retrieve the rating of the game.
        rating_str = steam_db_soup.find("div", {"class": "header-thing-number"})

        # Check if the rating is visible, else the bot was temporary banned from steamDB.
        if rating_str is not None:
            return float(rating_str.text.split(" ")[1][:-1])

        # We got temporary banned, return 0, the next time the game could be added.
        self.display.log_console_text("Got temporary banned from steamDB by number of requests...", log_warning)
        return 0

    def enter_giveaways(self, giveaways):
        self.display.log_console_text("\nStart entering giveaways!", config=log_verbose)

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
                              data={'xsrf_token': self.profile["xsrf_token"], 'do': 'entry_insert',
                                    'code': giveaway["giveaway_id"]},
                              cookies=self.cookie)

        # Check if the request was successful, so we can lower the points available on the profile.
        json_data = json.loads(entry.text)

        if json_data['type'] == 'success':
            # Lower the total points of the profile
            self.profile["points"] -= giveaway["points"]

            # Update the profile display, by recreating it.
            self.display.create_profile_display(self.profile)

            # Print that we entered the give-away.
            print("Entered giveaway: ", giveaway)
            self.display.log_console_text("Entered giveaway: " + str(giveaway), config=log_info)

            return True

        self.display.log_console_text("Could not enter giveaway: " + str(json_data), config=log_error)
        return False


# A function to retrieve a tag without an class.
def has_no_class(tag):
    return not tag.has_attr('class')


def random_sleep(sleep):
    if sleep:
        time.sleep(float(random.randint(500, 1200)) / 1000)
