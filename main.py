from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import random

import json
import time


class SteamGifts:
    base_search_url = "https://www.steamgifts.com/giveaways/search?"
    search_url = ""

    def __init__(self, config):
        # Load the config.
        self.config = config

        # Setup the driver.
        options = webdriver.ChromeOptions()
        options.add_argument('--user-data-dir={}'.format(config["chrome-profile-path"]))
        self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

        # Load the profile.
        self.get_profile_info()

        # Generate the search str.
        self.generate_search_url()

        # Retrieve giveaways.
        self.retrieve_giveaways()

    def get_soup(self, url):
        # Let the request wait a bit, to avoid bot detection.
        time.sleep(random.randint(200, 500) / 1000)
        self.driver.implicitly_wait(30)

        # Get the page
        self.driver.get(url)

        # Retrieve the html of the page as soup.
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def get_profile_info(self):
        # Get profile soup.
        soup = self.get_soup("https://www.steamgifts.com/account/settings/profile")

        profile_container = soup.find("a", {"class": "nav__button nav__button--is-dropdown", "href": "/account"})
        profile_spans = profile_container.findAll("span")

        self.profile = dict({
            "p": int(profile_spans[0].text),
            "level": int(profile_spans[1].text.split(" ")[1])
        })

        print("profile", self.profile)

    def generate_search_url(self):
        # Create a custom search string.
        search_str = ""
        config_search = config["search"]
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

            app_name = giveaway_entry.find("a", {"class": "giveaway__heading__name"}).text

            # Get the steam app id.
            steam_app_id = giveaway_entry.find("a", {"class": "giveaway__icon"})['href'].split("/")[-2]
            steam_db_url = "https://steamdb.info/app/" + steam_app_id

            # Get the app rating from steam db.
            try:
                steam_db_soup = self.get_soup(steam_db_url)
                steam_db_rating = float(
                    steam_db_soup.find("div", {"class": "header-thing-number"}).text.split(" ")[1][:-1])
            except AttributeError:
                print("Could not retrieve data from: ", app_name, steam_db_url)
                continue
            print(steam_db_rating)

            # Check if the rating is inside the requested boundaries.
            if config["search"]["rating_min"] and steam_db_rating < config["search"]["rating_min"]:
                # The game did not satisfy the min rating requirements.
                continue

            # Check if the rating is inside the requested boundaries.
            if config["search"]["rating_max"] and steam_db_rating > config["search"]["rating_max"]:
                # The game did not satisfy the min rating requirements.
                continue

            # Append to the entries.
            parsed_entries.append({
                'name': app_name,
                'points': int(giveaway_entry.find_all("span", {"class": "giveaway__heading__thin"})[-1].text[1:-2]),
                'id': steam_app_id,
                'page': giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'],
                'rating': steam_db_rating
            })

        # Print all the parsed entries
        print(parsed_entries)


if __name__ == '__main__':
    # Load the config
    with open('config.json') as f:
        config = json.load(f)

    # Create the steamGifts class
    sg = SteamGifts(config)
