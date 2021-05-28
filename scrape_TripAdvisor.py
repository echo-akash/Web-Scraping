from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dirs import ROOT_DIR
from time import sleep
from datetime import datetime
from web_scraping.wongnai_scraping import write_restaurant_link_to_file
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web_scraping.db_models import Base, RestaurantT


DOMAIN_URL = 'https://www.tripadvisor.com'
THIS_DIR = ROOT_DIR / 'web_scraping/'


def create_table(engine):
    Base.metadata.create_all(engine)


def get_soup_using_selenium(url: str, driver: webdriver, timeout) -> BeautifulSoup:
    driver.get(url)
    WebDriverWait(driver, timeout)
    return BeautifulSoup(driver.page_source, 'html.parser')


def write_to_file(text: str, output_file: str):
    with open(output_file, 'w', encoding='utf8') as f:
        f.write(text)


def get_restaurant_links_from_a_page(soup: BeautifulSoup) -> list:
    divs = soup.find('div', attrs={'data-test-target': 'restaurants-list'})
    a_tags = divs.find_all('a', class_='_2uEVo25r _3tdrXOp7', target='_blank', href=True)

    r_links = []
    for a in a_tags:
        link = DOMAIN_URL + a['href']
        r_links.append(link)
    return r_links


def get_restaurant_links_from_all_pages(driver: webdriver, start_url: str):
    print(f"Started at {datetime.now().strftime('%H:%M:%S')}")
    r_links = []
    url = start_url
    page_num = 1
    while page_num <= 408:
        soup = get_soup_using_selenium(url, driver, 15)
        try:
            r_links = get_restaurant_links_from_a_page(soup)
            write_restaurant_link_to_file(r_links, THIS_DIR / 'data/tripadvisor/restaurant_links_t.txt')
            print(f"Finished page {page_num}")
            page_num += 1
            url = driver.find_element_by_link_text('Next').get_attribute('href')
            if page_num >= 80:
                sleep(30)
            elif page_num >= 40:
                sleep(15)
            else:
                sleep(10)
        except AttributeError:
            print(r_links)
            print(f"Stopped at {datetime.now().strftime('%H:%M:%S')}")
            raise Exception(f"Is suspected to be a robot at page {page_num}. Try again.")
    print(f"Finished at {datetime.now().strftime('%H:%M:%S')} (page {page_num})")
    return r_links


def get_number_of_reviews(num_review: str) -> int:
    """
    >>> get_number_of_reviews('172 reviews')
    172
    >>> get_number_of_reviews('1,822 reviews')
    1822
    """
    num_str = num_review.split(' ')[0]
    num_str = ''.join([n for n in num_str if n != ','])
    return int(num_str)


def get_ratings(ratings: str) -> float:
    # 5.0\xa0
    return float(ratings.split("\\")[0])


def get_restaurant_details_from_a_page(driver: webdriver, r_url: str) -> dict:
    restaurant = {}
    soup = get_soup_using_selenium(r_url, driver, 15)

    # get restaurant's name
    r_name = soup.find('h1', attrs={'data-test-target': 'top-info-header'})
    restaurant['name'] = r_name.string

    try:
        div_rating_review = soup.find('div', class_='Ct2OcWS4')
        rating_str = div_rating_review.find('span', class_='r2Cf69qf').text
        restaurant['rating'] = get_ratings(rating_str)

        num_review_str = div_rating_review.find('a', class_='_10Iv7dOs').string
        restaurant['num_reviews'] = get_number_of_reviews(num_review_str)
    except AttributeError:
        # no ratings and reviews
        restaurant['rating'] = -1
        restaurant['num_reviews'] = -1
        
    cuisine_str = ''
    try:
        # 'https://www.tripadvisor.com/Restaurant_Review-g293916-d15776288-Reviews-1826_Mixology_Rooftop_Bar-Bangkok.html'
        div_details = soup.find('div', class_='_3UjHBXYa').find_all('div', class_='_1XLfiSsv')
        if 'THB' in str(div_details[0]):
            cuisine_str = div_details[1].string
        else:
            cuisine_str = div_details[0].string
    except AttributeError:
        try:
            # 'https://www.tripadvisor.com/Restaurant_Review-g293916-d3715466-Reviews-Calderazzo_On_31-Bangkok.html'
            div_detail = soup.find('div', attrs={'data-tab': 'TABS_DETAILS'})
            div_cuisines = div_detail.find_all('div', class_='ui_column')
            for d in div_cuisines:
                if 'CUISINES' in str(d):
                    cuisine_str = d.find('div', class_='_2170bBgV').string
                    # print(cuisine_str)
        except AttributeError:
            # div details doesn't show
            # https://www.tripadvisor.com/Restaurant_Review-g293916-d873174-Reviews-Le_Normandie-Bangkok.html
            sub_heading = soup.find('span', class_='_13OzAOXO _34GKdBMV')
            a_cuisines = list(sub_heading)[1:-1]
            cuisine_str = ','.join([a.string for a in a_cuisines])
            # print(cuisine_str)

    cuisines = ','.join([c.strip() for c in cuisine_str.split(',')])
    restaurant['cuisines'] = cuisines

    span_address = soup.find('span', class_='_2saB_OSe')
    restaurant['address'] = span_address.string

    span_opening_hrs = soup.find('span', class_='_1h0LGVD2').find_all('span')
    for s in span_opening_hrs:
        if 18 <= len(s.text) < 20:
            opening_hrs_str = s.text.replace(u'\xa0', u' ')
            restaurant['opening_hour'] = opening_hrs_str

    try:
        hr = restaurant['opening_hour']
    except KeyError:
        see_all_hours = driver.find_element_by_class_name('ct1ZIzQ6')
        see_all_hours.click()
        sun_hrs = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, '_2W4n9Mwo'))
        )
        restaurant['opening_hour'] = sun_hrs.text

    return restaurant


def dump_restaurant_details_from_all_pages(driver: webdriver, db_session, r_urls: list):
    # r_urls = [
    #     'https://www.tripadvisor.com/Restaurant_Review-g293916-d15776288-Reviews-1826_Mixology_Rooftop_Bar-Bangkok.html',
    #     'https://www.tripadvisor.com/Restaurant_Review-g293916-d3715466-Reviews-Calderazzo_On_31-Bangkok.html',
    #     'https://www.tripadvisor.com/Restaurant_Review-g293916-d2087255-Reviews-BarSu-Bangkok.html',
    #     'https://www.tripadvisor.com/Restaurant_Review-g293916-d873174-Reviews-Le_Normandie-Bangkok.html'
    # ]
    print(f"Started at {datetime.now().strftime('%H:%M:%S')}")
    for i in range(len(r_urls)):
        restaurant = get_restaurant_details_from_a_page(driver, r_urls[i])
        add_restaurant_to_session(restaurant, db_session)
        db_session.commit()
        print(f"Committed {i + 1} restaurant(s)")
        sleep(15)
    print(f"Finished at {datetime.now().strftime('%H:%M:%S')}")


def add_restaurant_to_session(restaurant: dict, session):
    r_instance = RestaurantT(
        name=restaurant['name'],
        rating=restaurant['rating'],
        num_reviews=restaurant['num_reviews'],
        cuisines=restaurant['cuisines'],
        address=restaurant['address'],
        opening_hour=restaurant['opening_hour']
    )
    session.add(r_instance)


def read_restaurant_links(file: str, start=0, stop=None) -> list:
    links = []
    with open(file, 'r', encoding='utf8') as f:
        for i, link in enumerate(f):
            if stop is None:
                links.append(link)
            else:
                if start <= i + 1 <= stop:
                    links.append(link)
    return links


if __name__ == '__main__':
    # import doctest
    # doctest.testmod(verbose=True)

    driver = webdriver.Chrome(f"{THIS_DIR}/chromedriver.exe")
    # BASE_URL = "https://www.tripadvisor.com/Restaurants-g293916-Bangkok.html"
    # get_restaurant_links_from_all_pages(driver, BASE_URL)

    engine = create_engine(f"sqlite:///{ROOT_DIR / 'web_scraping/data/tripadvisor/restaurants_t2.sqlite3'}")
    Session = sessionmaker(bind=engine)
    session = Session()
    # create_table(engine)

    r_urls = read_restaurant_links(THIS_DIR / 'data/tripadvisor/restaurant_links_t_p1-194.txt', 1, 5)
    dump_restaurant_details_from_all_pages(driver, session, r_urls)

    # r_url = 'https://www.tripadvisor.com/Restaurant_Review-g293916-d18919695-Reviews-Chez_Shibata365-Bangkok.html'
    # print(get_restaurant_details_from_a_page(driver, r_url))
    # driver.close()
