import json
import logging
import re
import time

import dateutil.parser
import facebook
import requests
import selenium
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import FirefoxProfile
from selenium.webdriver.common import keys
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary

from donight.errors import EventScrapingError
from donight.event_finder.scrapers.base_scraper import Scraper
from donight.events import Event
from donight.utils import to_local_timezone
from donight.utils.web_drivers import EnhancedWebDriver, By

assert __name__ != "facebook", "conflict with the facebook-sdk package name"


# TODO a more descriptive return value for self.get_scraping_source (including scraped page).
class FacebookEventsScraper(Scraper):
    __scraped_access_tokens = {}  # A dict mapping (email, password) to the lastly scraped access token

    def __init__(self, **kwargs):
        """
        :param page_url: The page to be scraped.
        :type page_url: basestring
        :param email: The email address with which the scraped facebook user is registered to facebook.
        :type email: basestring
        :param password: The user's facebook password.
        :type password: basestring
        :param halt_condition: A condition that, once it applies to a scraped event, will cause the scraper to stop
                               scraping.
        :type halt_condition: ScrapingHaltCondition
        :param driver: A selenium web driver to interact with facebook.
        :type driver: FacebookScrapingWebDriver
        :type logger: logging.Logger|None
        """
        super(FacebookEventsScraper, self).__init__(kwargs.pop('logger', None))

        self.__email = kwargs.pop('email')
        self.__password = kwargs.pop('password')
        self.__access_token = None

        self.__page_url = kwargs.pop('page_url')
        self.__halt_condition = kwargs.pop('halt_condition')
        self.__driver = kwargs.pop('driver', None)

        if kwargs:
            raise ValueError('Received some unexpected arguments: {}'.format(', '.join(kwargs.keys())))

        self.__event_id_regex_in_url = re.compile(r'/events/(?P<id>\d+)($|/|\?).*')
        self.__graph_api_explorer_url = 'https://developers.facebook.com/tools/explorer'
        self.__is_already_refreshed = False

    def scrape(self):
        event_scraper = FacebookEventScraper(self._access_token or self.__scrape_access_token(self.__driver))
        self.__driver.get(self.__page_url)

        for event_id in self.__iterate_unique_events_ids(self.__driver):
            try:
                event = event_scraper.scrape(event_id)

            except AuthError:
                self.logger.warn("Encountered an authentication error. Access token might have expired. "
                                 "Scraping another access token and retrying.")

                self._access_token = None
                event_scraper = FacebookEventScraper(self.__scrape_access_token(self.__driver))

                try:
                    event = event_scraper.scrape(event_id)

                except EventScrapingError:
                    self.logger.exception('Error scraping facebook event with id {}.'.format(event_id))
                    continue

            except EventScrapingError:
                self.logger.exception('Error scraping facebook event with id {}.'.format(event_id))
                continue

            yield event

            should_stop_scraping = self.__halt_condition.should_stop_scraping(event)
            if should_stop_scraping:
                self.logger.warn("Reached events threshold: " + should_stop_scraping.why)
                break

    def __iterate_unique_events_ids(self, driver):
        scraped_events_ids = set()

        for event_anchor in self.__iterate_events_anchors(driver):
            event_url = event_anchor.get_attribute('href')

            event_id = self.__parse_event_id(event_url)

            if event_id in scraped_events_ids:
                continue
            else:
                # ASSUMPTION: if the scraping later fails, it will always fail for this id.
                scraped_events_ids.add(event_id)

            yield event_id

    def __parse_event_id(self, event_url):
        match = self.__event_id_regex_in_url.search(event_url)
        if match is not None:
            return match.group('id')

        raise EventScrapingError("Unable to parse facebook event id from url: {}".format(event_url))

    def __iterate_events_anchors(self, driver):
        while True:
            try:
                event_anchor = driver.find_element_by_css_selector('a[href*="/events/"]:not([data-already-handled])')

            except NoSuchElementException:
                if self.__load_more_posts(driver):
                    continue
                else:
                    break

            driver.execute_script('arguments[0].setAttribute("data-already-handled", "true");',
                                  event_anchor)

            if self.__event_id_regex_in_url.search(event_anchor.get_attribute('href')) is None:
                # That's not really an event anchor
                continue

            yield event_anchor

    def __load_more_posts(self, driver):
        """
        :returns: Whether there were new posts to load. NOTE: returns a false negative if there's no internet connection
        :rtype: bool
        """
        driver.scroll_to_bottom()

        got_confused_error_message = 'Sorry, we got confused'
        try_refreshing_error_message = 'Please try refreshing the page'

        # wait up to 10 seconds for new posts to load
        for i in xrange(40):
            if driver.is_scrolled_to_bottom():
                time.sleep(0.25)
            else:
                return True

        if driver.has_element(By.XPATH,
                              '//*[@role="dialog"][//*[contains(text(),{})]][//*[contains(text(),{})]]'.format(
                                  json.dumps(got_confused_error_message), json.dumps(try_refreshing_error_message))):
            if self.__is_already_refreshed:
                raise EventScrapingError('Facebook is not reacting properly: received "{}" error twice.'.format(
                    try_refreshing_error_message))

            driver.refresh()
            self.__is_already_refreshed = True
            self.logger.warn('Received an error from facebook: "{}". Refreshing and retrying.'.format(
                try_refreshing_error_message))
            # We're returning a possibly incorrect value without loading new posts.
            # ASSUMPTION: other parts of the code in this class will handle this.
            return True

        self.logger.info("It seems no there are no more events to scrape from the page {}".format(self.__page_url))
        return False

    @property
    def _access_token(self):
        if self.__access_token is not None:
            return self.__access_token

        scraped_access_token = self.__scraped_access_tokens.get((self.__email, self.__password), None)
        return scraped_access_token

    @_access_token.setter
    def _access_token(self, value):
        if self.__email:
            self.__scraped_access_tokens[(self.__email, self.__password)] = value

        self.__access_token = value

    def __scrape_access_token(self, driver):
        with driver.new_tab(self.__graph_api_explorer_url):
            self.__ensure_logged_in(driver)

            # TODO: try to make ALT+T work, maybe in phantomJs, or try to refresh page
            # refresh access token:
            # ASSUMPTION: the 'user_events' permission has already been given to the GraphApi Explorer by that user.
            get_token_button = driver.find_element_by_link_text('Get Token')
            get_token_button.click()
            get_user_access_token_button = driver.find_element_by_link_text('Get User Access Token')
            get_user_access_token_button.click()

            possible_get_access_token_submit_buttons = driver.find_elements_by_css_selector('button[type="submit"]')
            for button in possible_get_access_token_submit_buttons:
                if button.get_attribute('textContent') == 'Get Access Token':
                    break
            else:
                raise NoSuchElementException("Can't find the 'Get Access Token' submit button.")

            button.click()

            access_token_output = driver.find_element_by_css_selector(
                "input[placeholder='Paste in an existing Access Token or click \"Get User Access Token\"']")
            access_token = access_token_output.get_attribute('value')

            self._access_token = access_token
            return access_token

    def __ensure_logged_in(self, driver):
        # ASSUMPTION: the lastly requested page requires the user to be logged in

        if not self.__is_driver_on_login_page(driver):
            return

        email_input = driver.find_element_by_id('email')
        email_input.send_keys(self.__email)

        password_input = driver.find_element_by_id('pass')
        password_input.send_keys(self.__password)
        password_input.send_keys(keys.Keys.ENTER)

        if self.__is_driver_on_login_page(driver):
            raise EventScrapingError('Email or password seem to be incorrect.')

    # noinspection PyMethodMayBeStatic
    def __is_driver_on_login_page(self, driver):
        return driver.has_element(By.XPATH, '//*[contains(text(), "Log into Facebook")]') or \
               driver.has_element(By.XPATH, '//*[contains(text(), "You must log in to continue")]')


class FacebookEventScraper(object):
    """docs at https://developers.facebook.com/docs/graph-api/reference/v2.5/event"""

    def __init__(self, access_token):
        requests.packages.urllib3.disable_warnings()
        self.__graph = facebook.GraphAPI(access_token, version='2.5')

    def scrape(self, event_id):
        try:
            event_dict = self.__graph.get_object(
                event_id,
                fields="place,name,description,start_time,end_time,ticket_uri,cover,owner,is_canceled")
        except facebook.GraphAPIError as e:
            if e.type == 'OAuthException':
                raise AuthError(e)

            raise EventScrapingError("Could not access facebook event with id {}.".format(event_id), e)

        if event_dict.get('is_canceled', False):
            raise EventScrapingError("Event has been canceled.")

        # if not event_dict.get("can_guests_invite"):
        #     raise EventScrapingError("Event does not allow inviting guests")

        description = event_dict.get("description", '')
        ticket_url = event_dict.get("ticket_uri", '')
        if not description and ticket_url:
            description = u'Ticket: ' + ticket_url

        owner_id = event_dict.get("owner", {}).get("id")
        if owner_id:
            owner_url = "https://www.facebook.com/" + event_dict.get("owner", {}).get("id")
        else:
            owner_url = None

        start_time = event_dict.get("start_time")
        end_time = event_dict.get("end_time")
        event = Event(title=event_dict.get("name"),
                      start_time=self.__parse_datetime(start_time),
                      end_time=self.__parse_datetime(end_time),
                      location=event_dict.get("place", {}).get("name"),  # coordinates and id also available
                      price=None,  # TODO parse
                      url="https://www.facebook.com/events/" + event_dict.get("id", event_id),
                      description=description,
                      image=event_dict.get("cover", {}).get("source"),
                      owner=event_dict.get("owner", {}).get("name"),
                      owner_url=owner_url,
                      ticket_url=ticket_url)
        return event

    def __parse_datetime(self, string):
        if string is None:
            return None

        return to_local_timezone(dateutil.parser.parse(string))


class AuthError(Exception):
    pass


class FacebookScrapingWebDriver(EnhancedWebDriver):
    def __init__(self, should_hide_window, installation_path):
        # ASSUMPTION: installation_path refers to a valid firefox executable.
        firefox_binary = None if installation_path is None else FirefoxBinary(installation_path)

        profile = FirefoxProfile()
        profile.set_preference("intl.accept_languages", "en-us,en")
        # do not load images:
        profile.set_preference('browser.migration.version', 9001)
        profile.set_preference('permissions.default.image', 2)
        profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')

        driver = selenium.webdriver.Firefox(firefox_profile=profile, firefox_binary=firefox_binary)
        web_driver = EnhancedWebDriver(driver, should_hide_window)

        super(FacebookScrapingWebDriver, self).__init__(web_driver, should_hide_window)
        self.implicitly_wait(5)
