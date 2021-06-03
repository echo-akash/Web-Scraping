import unittest
from message_builder import get_message
from weather import Weather

class TestGetMessage(unittest.TestCase):
    def test_GoForIt(self):
        # Test temperatures that produce message 'Too cold to bike'
        weather = Weather('7:00 am', '3:00 pm')
        weather.to_work_temp = 75
        weather.to_work_precip = 0
        weather.from_work_temp = 80
        weather.from_work_precip = 0
        weather.web_scraping_error = ''
        self.assertEqual(get_message(weather), '\nShould I Bike says: Go for it!\n7:00 am; temp = 75 F; precip = 0 %\n3:00 pm; temp = 80 F; precip = 0 %\n')

    def test_TooColdToBikeToday(self):
        # Test temperatures that produce message 'Too cold to bike today'
        weather = Weather('7:00 am', '3:00 pm')
        weather.to_work_temp = 55
        weather.to_work_precip = 0
        weather.from_work_temp = 60
        weather.from_work_precip = 0
        weather.web_scraping_error = ''
        self.assertEqual(get_message(weather), '\nShould I Bike says: Too cold to bike today\n7:00 am; temp = 55 F; precip = 0 %\n3:00 pm; temp = 60 F; precip = 0 %\n')

    def test_TooRainyToBikeToday(self):
        # Test precipitations that produce message 'Too rainy to bike today'
        weather = Weather('7:00 am', '3:00 pm')
        weather.to_work_temp = 75
        weather.to_work_precip = 30
        weather.from_work_temp = 80
        weather.from_work_precip = 100
        weather.web_scraping_error = ''
        self.assertEqual(get_message(weather), '\nShould I Bike says: Too rainy to bike today\n7:00 am; temp = 75 F; precip = 30 %\n3:00 pm; temp = 80 F; precip = 100 %\n')

    def test_TooColdAndWetToBikeToday(self):
        # Test temperatures and precipitations that produce message 'Too cold and wet to bike today'
        weather = Weather('7:00 am', '3:00 pm')
        weather.to_work_temp = 32
        weather.to_work_precip = 80
        weather.from_work_temp = 37
        weather.from_work_precip = 80
        weather.web_scraping_error = ''
        self.assertEqual(get_message(weather), '\nShould I Bike says: Too cold and wet to bike today\n7:00 am; temp = 32 F; precip = 80 %\n3:00 pm; temp = 37 F; precip = 80 %\n')

    def test_WebScrapingError(self):
        # Test web scraping error'
        weather = Weather('7:00 am', '3:00 pm')
        weather.to_work_temp = 'error'
        weather.to_work_precip = 'error'
        weather.from_work_temp = 'error'
        weather.from_work_precip = 'error'
        weather.web_scraping_error = 'There was an error web scraping'
        self.assertEqual(get_message(weather), '\nShould I Bike says: There was an error\n7:00 am; temp = error F; precip = error %\n3:00 pm; temp = error F; precip = error %\nError: There was an error web scraping')
