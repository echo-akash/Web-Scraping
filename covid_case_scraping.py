import requests
import pandas as pd
from bs4 import BeautifulSoup
import seaborn as sns
from matplotlib.pyplot import figure
import matplotlib.pyplot as plt
import datetime
import numpy as np

ABSOLUTE_PATH_TO_CSV = "/Users/aleksandr/Desktop/Programm/java/lesson_kpfu_3/CoronavirusStatistic/src/main/webapp/WEB-INF/python/csv/"
ABSOLUTE_PATH_TO_TXT = "/Users/aleksandr/Desktop/Programm/java/lesson_kpfu_3/CoronavirusStatistic/src/main/webapp/WEB-INF/python/txt/"
ABSOLUTE_PATH_TO_IMAGE = "/Users/aleksandr/Desktop/Programm/java/lesson_kpfu_3/CoronavirusStatistic/src/main/webapp/template/plots_images/"


class Scraping:
    def __init__(self, url_for_df, url_for_case):
        self.url_for_df = url_for_df
        self.url_for_case = url_for_case
        self.time = datetime.date.today()

    def df_day_statistic(self):
        page = requests.get(self.url_for_df)
        soup = BeautifulSoup(page.text, 'html.parser')

        data = []

        data_iterator = iter(soup.find_all('td'))

        while True:
            try:
                country = next(data_iterator).text
                confirmed = next(data_iterator).text
                deaths = next(data_iterator).text
                continent = next(data_iterator).text

                # For 'confirmed' and 'deaths', make sure to remove the commas and convert to int
                data.append((
                    country,
                    (int(confirmed.replace(',', ''))),
                    (int(deaths.replace(',', ''))),
                    continent
                ))
                # StopIteration error is raised when there are no more elements left to iterate through
            except StopIteration:
                break

        data.sort(key=lambda row: row[1], reverse=True)

        df = pd.DataFrame(data, columns=['Country', 'Number of cases', 'Deaths', 'Continent'], dtype=float)
        df_corona = df.sort_values(by='Number of cases', ascending=False)

        # df_corona['Death_rate'] = (df['Deaths'] / df['Number of cases']) * 100
        return df_corona

    def generic_case(self):
        page = requests.get(self.url_for_case)
        soup = BeautifulSoup(page.text, 'html.parser')
        case = {'case': soup.select('#maincounter-wrap>div>span')[0].text,
                'death': soup.select('#maincounter-wrap>div>span')[1].text,
                'recover': soup.select('#maincounter-wrap>div>span')[2].text}

        return case


    def save_generic_case(self):
        page = requests.get(self.url_for_case)
        soup = BeautifulSoup(page.text, 'html.parser')
        case = f"Case: {soup.select('#maincounter-wrap>div>span')[0].text} \n" \
               f"Death: {soup.select('#maincounter-wrap>div>span')[1].text} \n" \
               f"Recovery: {soup.select('#maincounter-wrap>div>span')[2].text}"

        with open(f"{ABSOLUTE_PATH_TO_TXT}{self.time}.txt", "w") as f:
            f.write(case)


    def save_file(self):
        df = self.df_day_statistic()
        df.to_csv(f"{ABSOLUTE_PATH_TO_CSV}{self.time}.csv", header=False, index=False)


def death_rate(df_corona):
    figure(num=None, figsize=(20, 6), dpi=80, facecolor='w', edgecolor='k')
    df_corona = df_corona[~df_corona.Continent.isin([''])]
    sns.barplot(x='Continent', y='Death_rate', data=df_corona.sort_values(by='Death_rate', ascending=False))
    plt.show()


def main_statistic_contint(df_corona):
    figure(num=None, figsize=(10, 10), dpi=80, facecolor='w', edgecolor='k')
    sns_plot = sns.pairplot(df_corona, hue='Continent')
    figure_plot = sns_plot
    figure_plot.savefig(f"{ABSOLUTE_PATH_TO_IMAGE}FullStat.png")
    # plt.show()


def case_statistic(df_corona):
    figure(num=None, figsize=(10, 10),  facecolor='w', edgecolor='k')
    sns_plot = sns.barplot(x='Country', y='Number of cases', data=df_corona.head(10))
    figure_plot = sns_plot.get_figure()
    figure_plot.savefig(f"{ABSOLUTE_PATH_TO_IMAGE}CaseStat.png")
    # plt.show()

def error_helper():
    for i in range(10):
     with open(f"{ABSOLUTE_PATH_TO_CSV}helper_{i}.csv", "w") as f:
                f.write("")


if __name__ == "__main__":
    url_df = 'https://www.worldometers.info/coronavirus/countries-where-coronavirus-has-spread/'
    url_case = 'https://www.worldometers.info/coronavirus/'

    scraping = Scraping(url_df, url_case)
    df = scraping.df_day_statistic()
    scraping.save_file()
    scraping.save_generic_case()
    case_statistic(df)
#     error_helper()
    main_statistic_contint(df)
