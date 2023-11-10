from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import time
import uuid
from pprint import pprint
from selenium.webdriver.common.by import By

from datetime import date, timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import numpy as np
from pathlib import Path
import socket
import calendar
import pytz

from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException


class HdfcStatement:

    def __init__(self):
        self.chromeOptions = Options()
        self.driver = self.createDriver(mode='headless')
       
    def createDriver(self, mode='local'):

        if mode == 'headless':
            # self.chrome_options.add_argument("--disable-infobars")
            self.chromeOptions.add_argument("--disable-popup-blocking")
            self.chromeOptions.add_argument("--disable-dev-shm-usage")
            self.chromeOptions.add_argument("--disable-extensions")
            self.chromeOptions.add_argument("--headless")
            self.chromeOptions.add_argument("--no-sandbox")
            self.chromeOptions.add_argument("--window-size=1920,1080")
            self.chromeOptions.add_argument("--disable-gpu")
            self.chromeOptions.add_argument("--disable-extensions")
            self.chromeOptions.add_argument("--proxy-server='direct://'")
            self.chromeOptions.add_argument("--proxy-bypass-list=*")
            self.chromeOptions.add_argument("--start-maximized")
            self.chromeOptions.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36")
        try:
            driver = webdriver.Chrome(ChromeDriverManager().install(),
                                      chrome_options=self.chromeOptions)
            # driver.maximize_window()
        except Exception as e:
            self.logStatus("error", str(e))
        
        return driver
    def GetTheData(self):
        pass

   