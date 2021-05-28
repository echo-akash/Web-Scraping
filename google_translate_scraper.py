from models.GoogleTranslate import GoogleTranslate
from models.Listener import Listener
from models.TranslationScraper import TranslationScraper
from models.definitions.DefinitionsScraper import DefinitionScraper
from bs4 import BeautifulSoup
from selenium import webdriver

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from models.options.OptionTranslate import OptionTranslate


class GoogleScraper:
    listener: Listener = None

    def __init__(self):
        self.browser = webdriver.PhantomJS()

    def scraping(self, opt: OptionTranslate) -> GoogleTranslate:

        url = opt.get_url()

        self.listener.on_message("I am scraping")
        self.browser.get(url)
        delay = 3  # seconds
        try:
            myElem = WebDriverWait(self.browser, delay).until(EC.presence_of_element_located((By.CLASS_NAME, 'Dwvecf')))
            self.listener.on_message("Page is ready")

        except TimeoutException:
            self.listener.on_error("Loading took too much time!")

        html = self.browser.page_source
        soup = BeautifulSoup(html)

        a = soup.find_all('div', class_="Dwvecf")

        googleTranslate = GoogleTranslate()
        # soup.find_all("div",clashs_="J0lOec") first and last
        principal = soup.find_all("span", class_="VIiyi")
        principal = list(map(lambda t: t.get_text("|"), principal))
        principal = list(map(lambda t: t.split("|")[0], principal))

        googleTranslate.principal = ", ".join(principal)
        if len(principal) > 1:
            self.listener.on_message("I found results")
        for index in range(len(a)):
            option = a[index]
            title = option.h3.get_text()
            if "Translations" in title:
                translation = TranslationScraper.scraping(a[index])
                googleTranslate.translations = translation
                self.listener.on_message("I found Translations")
            if "Definitions" in title:
                definitions = DefinitionScraper.scraping(a[index])
                googleTranslate.definitions = definitions
                self.listener.on_message("I found Definitions")
        return googleTranslate
