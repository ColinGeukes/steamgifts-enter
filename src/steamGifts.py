import math

import steamspypi
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
    points_threshold_no_query_search = 30

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

        # Show a completion message in the log.
        self.display.log_console_text("\nDone entering giveaways!", config=log_verbose)

        # Close the driver.
        self.driver.close()

        # Auto-close if option enabled.
        if self.config["settings"]["auto_quit"] == 1:
            self.display.quit_application()

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

    def get_soup(self, url):
        # Do a random sleep before access.
        time.sleep(float(random.randint(500, 1200)) / 1000)
        self.driver.implicitly_wait(30)

        # Get profile soup.
        self.driver.get(url)

        # Retrieve the html of the page as soup.
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def get_request_soup(self, url):
        time.sleep(float(random.randint(500, 1200)) / 1000)

        page = requests.get(url, cookies=self.cookie)
        return BeautifulSoup(page.text, "html.parser")

    def get_profile_info(self):
        # Get soup of main page.
        soup = self.get_soup(self.base_url)

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
        self.display.update_profile_display(self.profile)

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

    def retrieve_giveaways(self, use_query=True):
        # Keep track of all the parsed entries.
        parsed_entries = dict(entries=[], totalPoints=0)
        self.display.update_current_mining_display(0, 0)
        self.display.current_session_entered.set("0")

        # Log the retrieval of giveaways to the console.
        self.display.log_console_text("\nRetrieving the giveaways to possible enter.", log_verbose)
        # Keep looping till we found enough entries.
        current_page = 1
        current_level = self.profile["level"]
        min_retrieved_giveaway_total_points = max(200, self.profile["points"] * 3)

        while current_level >= 0 and parsed_entries["totalPoints"] < min_retrieved_giveaway_total_points:  # TODO: Also do a min amount of page scrap.
            # Start the search for the given page.
            entries_found = self.retrieve_giveaways_page(parsed_entries, current_level, current_page, use_query)

            # Stop if we mined all the pages, thus we lower the level we are querying.
            if not entries_found:
                self.display.log_console_text("There were no more entries matching your search criteria for level %d, lower level for more results." % current_level, log_warning)
                current_page = 0
                current_level -= 1
                continue

            # Increment the page.
            current_page += 1

        # Sort the entries and return them to enter.
        return sorted(parsed_entries['entries'], key=lambda row: (-row['rating'], -row['points']))

    def retrieve_paged_search_string(self, level, page, use_query):
        # Check if we use the search params.
        if use_query:
            # Create copy of search params and add page search param.
            search_params_copy = self.search_params.copy()
        else:
            search_params_copy = []

        # Add the page search params.
        search_params_copy.append("level_min=%s" % str(level))
        search_params_copy.append("level_max=%s" % str(level))
        search_params_copy.append("page=%s" % str(page))

        # Return the final search url.
        return self.base_search_url + "&".join(search_params_copy)

    def retrieve_giveaways_page(self, parsed_entries, level, page, use_query):
        # Retrieve the soup of the current search with the given page
        soup = self.get_request_soup(self.retrieve_paged_search_string(level, page, use_query))
        self.display.log_console_text("Retrieving giveaways for (level, page)=(%i, %i)." % (level, page))

        # Check if the site give a no-results page, if no-results then return false.
        if soup.find("div", {"class": "pagination pagination--no-results"}) is not None:
            self.display.log_console_text("There were no entries at (level, page)=(%i, %i)." % (level, page), log_error)
            return False

        # Retrieve all the entries.
        giveaway_list = soup.find("div", "widget-container").findChild(has_no_class, recursive=False).findChild(
            has_no_class, recursive=False)
        giveaway_entries = giveaway_list.findAll("div", "giveaway__row-inner-wrap")

        # Print the giveaways TODO: Keep mining giveaways until we got enough to spend 3x the total amount of points, this gives a good set of games.
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
                self.display.log_console_text(
                    "Passing giveaway: %s, insufficient rating: %0.2f" % (app_name, sdb_rating))
                continue

            # Append to the entries.
            entry = dict(
                name=app_name,
                points=int(giveaway_entry.find_all("span", {"class": "giveaway__heading__thin"})[-1].text[1:-2]),
                page=giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'],
                giveaway_id=giveaway_entry.find("a", {"class": "giveaway__heading__name"})['href'].split("/")[2],
                rating=sdb_rating
            )
            parsed_entries['entries'].append(entry)
            parsed_entries['totalPoints'] += entry['points']

            self.display.update_current_mining_display(len(parsed_entries['entries']), parsed_entries['totalPoints'])

            # Log the addition of the give-away.
            self.display.log_console_text("Adding giveaway: " + str(entry))

        return True

    def filter_giveaway_sdb_rating(self, sdb_rating):

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
        # if not self.config["search"]["use_steam_db"]:
        #    return 100

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
        soup = self.get_request_soup("https://store.steampowered.com/sub/%s" % steam_bundle_id)

        # Retrieve all the entries of the bundle.
        bundle_entries = soup.find_all("div", {"class": ["tab_item", "app_impression_tracked"]})

        # Get the rating of the games inside the bundle.
        total_bundle_score = 0
        for bundle_entry in bundle_entries:
            total_bundle_score += self.get_game_score(bundle_entry["data-ds-appid"])

        # Return avg game score.
        if total_bundle_score != 0:
            return total_bundle_score / len(bundle_entries)
        return 0

    def get_game_score(self, steam_game_id):
        # Get the app details.
        try:
            app_details = steamspypi.download(dict(request="appdetails", appid=str(steam_game_id)))
        except json.decoder.JSONDecodeError:
            # Could not load the app.
            self.display.log_console_text("Could not retrieve steam information for app %s" % steam_game_id, log_error)
            return 0
        # Check if the game has any reviews.
        if "positive" not in app_details or "negative" not in app_details:
            return 0
        # Get the positive and negative reviews.
        reviews_positive = int(app_details["positive"])
        reviews_negative = int(app_details["negative"])
        reviews_total = reviews_positive + reviews_negative

        # Check if there are any reviews for the algorithm.
        if reviews_total > 0:
            reviews_score = reviews_positive / reviews_total
            return (reviews_score - (reviews_score - 0.5) * 2 ** -math.log10(reviews_total + 1)) * 100

        # Return 0, as there were no reviews found.
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
            self.display.update_profile_display(self.profile)

            # Print that we entered the give-away.
            print("Entered giveaway: ", giveaway)
            self.display.log_console_text("Entered giveaway: " + str(giveaway), config=log_info)
            self.display.current_session_entered.set(str(int(self.display.current_session_entered.get()) + 1))
            return True

        self.display.log_console_text("Could not enter giveaway: " + str(json_data), config=log_error)
        return False


# A function to retrieve a tag without an class.
def has_no_class(tag):
    return not tag.has_attr('class')


def random_sleep(sleep):
    if sleep:
        time.sleep(float(random.randint(500, 1200)) / 1000)
