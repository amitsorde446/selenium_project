from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import time
import uuid
from pprint import pprint
import boto3
from botocore.exceptions import ClientError
from data_base import DB
from selenium.webdriver.common.by import By

from datetime import date,  timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from PIL import Image
import cv2
from selenium.webdriver.support import expected_conditions as EC
import pytesseract as pt
import os
import numpy as np
from pathlib import Path
import socket
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
import calendar
import pytz


class DeutscheStatement:

    def __init__(self, refid, env="quality"):
        self.timeBwPage = 0.5
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.readConfig()
        self.CreateS3()

        self.dbObj = DB(**self.dbConfig)
        self.refid = refid
        self.downloadDir = os.path.join(os.getcwd(), "pdfs")
        self.chromeOptions = Options()
        self.driver = self.createDriver(mode='headless')
        self.wait = WebDriverWait(self.driver, 5)

        self.netbanking_url = "https://login.deutschebank.co.in/"
        self.userid_xp = "/html/body/form/div/div/div[5]/div[2]/p[2]/span/span/input"
        self.password_xp = "/html/body/form/div/div/div[5]/div[4]/p[2]/span[1]/input"
        self.login_xp = "/html/body/form/div/div/div[5]/div[13]/div/p/span[2]/span/input"
        self.login_error_xp = "/html/body/form/div/div/div[5]/div[2]"

        self.acc_xp = "/html/body/form/div/div/div[3]/div[1]/div[4]/div[3]/div/div[2]/div[1]/div/div[1]/div/div[3]/div[1]/div/div/div/div/div[1]/table/tbody/tr/td[1]/a"
        self.account_statement_id = "PageConfigurationMaster_ACCDETW__1:searchHeader"

        self.date_section_name = "TransactionHistoryFG.SELECTED_RADIO_INDEX"
        self.from_date_id = "PageConfigurationMaster_ACCDETW__1:TransactionHistoryFG.FROM_TXN_DATE"
        self.to_date_id = "PageConfigurationMaster_ACCDETW__1:TransactionHistoryFG.TO_TXN_DATE"

        self.search_id = "PageConfigurationMaster_ACCDETW__1:SEARCH"

        self.pdf_id_name = "PageConfigurationMaster_ACCDETW__1:PDF_DOWNLOAD_CUSTOM"
        self.no_transaction_xp = "/html/body/form/div/div/div[3]/div[1]/div[2]/div[3]/div/div[3]/div/div/div[1]/div/div[3]/div[2]"

        self.summary = "HREF_RetailUserDashboardUX3_W85__0:AccountSummaryWidgetFG.ACCOUNT_NUMBER_ARRAY[0]"
        
        self.date_status = "notExist"

        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)

        if not os.path.exists("Screenshots"):
            os.makedirs("Screenshots")

        if not os.path.exists("pdfs"):
            os.makedirs("pdfs")

    def readConfig(self):
        configFileName = f"config_{self.env}.json"
        with open(configFileName, 'r') as confFile:
            config = json.load(confFile)
            self.driverConfig = config['driverConfig']
            self.dbConfig = config['dbConfig']

    def CreateS3(self):
        try:
            self.session = boto3.session.Session(aws_access_key_id=self.driverConfig['s3']['AWS_ACCESS_KEY_ID'],
                                                 aws_secret_access_key=self.driverConfig['s3']['AWS_SECRET_ACCESS_KEY'],
                                                 region_name=self.driverConfig['s3']['REGION_HOST'])
            self.resource = self.session.resource("s3")
            self.bucket = self.resource.Bucket(self.driverConfig["s3"]["AWS_STORAGE_BUCKET_NAME"])
        except ClientError as e:
            self.logStatus("critical", f"could not connect to s3 {e}")
            raise Exception("couldn't connect to s3")
        except Exception as e:
            self.logStatus("critical", f"could not connect to s3 {e}")

            raise Exception("couldn't connect to s3")

    def uploadToS3(self, filename, key):
        self.bucket.upload_file(
            Filename=filename, Key=key)

    def takeScreenshot(self):
        time.sleep(self.timeBwPage)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), 'screenshots/' + self.refid + "/" + sname)

        os.remove(screenshotName)
        return sname

    def savePdf(self):

        time.sleep(self.timeBwPage)

        pname = os.listdir("pdfs/")[0]

        pname1 = str(uuid.uuid1()) + '.pdf'
        #
        os.rename(("pdfs/" + pname), ("pdfs/" + pname1))

        pdfName = os.path.join(self.pdfDir, f"{pname1}")

        self.uploadToS3(os.path.join(pdfName), 'pdfs/' + self.refid + "/" + pname1)

        os.remove("pdfs/" + pname1)

        return pname1

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'DEUTSCHE', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def createDriver(self, mode='local'):

        self.prefs = {
            "download.default_directory": self.downloadDir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "safebrowsing.disable_download_protection": True,
            "plugins.always_open_pdf_externally": True,
            'plugins.plugins_disabled': ["Chrome PDF Viewer"]
        }

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
        self.chromeOptions.add_experimental_option("prefs", self.prefs)
        try:
            driver = webdriver.Chrome('/usr/local/bin/chromedriver',
                                      chrome_options=self.chromeOptions)
            # driver.maximize_window()
        except Exception as e:
            self.logStatus("error", str(e))
        self.params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {
                'behavior': 'allow',
                'downloadPath': self.downloadDir
            }
        }
#         self.logStatus("info", "Driver created")
        return driver

    def check_exists_by_xpath(self, xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True

    def login(self, username, password, seml, smno):

        response_dict = {"referenceId": self.refid}
        try:
            self.driver.get(self.netbanking_url)
        except:
            self.logStatus("info", "website error", self.takeScreenshot())
            response_dict["responseCode"] = "EIS042"
            response_dict["responseMsg"] = "Information Source is Not Working"
            return response_dict

        self.logStatus("info", "open deutsche netbanking webpage", self.takeScreenshot())

        user_input = self.driver.find_element_by_xpath(self.userid_xp)
        user_input.clear()
        user_input.send_keys(username)

        password_input = self.driver.find_element_by_xpath(self.password_xp)
        password_input.clear()
        password_input.send_keys(password)

        self.logStatus("info", "username/password entered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.login_xp).click()
        time.sleep(4)

        try:
            if self.driver.find_element_by_xpath('/html/body/form/div/div/div[5]/div[2]').text == "Please enter valid Login id and password":
                print("wrong credintials")
                self.logStatus("critical", "Incorrect UserName Or Password.", self.takeScreenshot())
                response_dict["responseCode"] = "EWC002"
                response_dict["responseMsg"] = "Incorrect UserName Or Password."
        except:
            self.logStatus("info", "successfully logged in", self.takeScreenshot())
            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"

        return response_dict

    def logout(self):

        try:
            self.driver.find_element_by_id("HREF_Logout").click()
            time.sleep(2)

            self.driver.find_element_by_id("LOG_OUT").click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull",{"referenceId":self.refid,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.refid,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def selectCalenderDate(self, start_date, end_date):
        
        
        time.sleep(3)
        self.driver.find_element_by_id(self.account_statement_id).click()

        time.sleep(1)

        self.driver.find_element_by_name(self.date_section_name).click()
        time.sleep(1)

        fromDateInput = self.driver.find_element_by_id(self.from_date_id)
        fromDateInput.clear()
        fromDateInput.send_keys(start_date)
        time.sleep(1)

        toDateInput = self.driver.find_element_by_id(self.to_date_id)
        toDateInput.clear()
        toDateInput.send_keys(end_date)
        time.sleep(1)

        self.driver.find_element_by_id(self.search_id).click()
        time.sleep(3)

        try:
            self.driver.find_element_by_xpath(self.no_transaction_xp)
            # self.date_status = "notExist"
        except:

            ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)
            your_element = WebDriverWait(self.driver, some_timeout, ignored_exceptions=ignored_exceptions)\
                .until(expected_conditions.presence_of_element_located((By.NAME, self.pdf_id_name)))

        try:
            self.driver.find_element_by_id(self.pdf_id_name).click()
            time.sleep(1)
            self.savePdf()
            self.date_status = "exist"
            self.logStatus("info", "pdf downloaded", self.takeScreenshot())
        except Exception as e:
            print(e)
            pass

    def downloadData(self, fromDate, toDate, accountno, seml, smno):

        response_dict = {"referenceId": self.refid}

        if self.check_exists_by_xpath('/html/body/div[1]/div[3]/table[1]'):
            print('Application error')
            self.logStatus("info", "application error", self.takeScreenshot())
            tab=self.driver.find_element_by_xpath('/html/body/div[1]/div[3]/table[1]')
            tbdy=tab.find_element_by_tag_name('tbody')
            txtlst=tbdy.find_element_by_tag_name('tr')
            print(list(map(lambda x:x.text,txtlst)))
            return {"referenceId":self.refid,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        # self.driver.find_element_by_id(self.summary).click()

        chk_acc = 0

        table1 = self.driver.find_element_by_xpath("/html/body/form/div/div/div[3]/div[1]/div[4]/div[3]/div/div[1]/div[6]/div/div[1]/div/div[3]/div[1]/div/div/div/div/div[1]/table")

        for row in table1.find_elements_by_tag_name("tr"):
            for row1 in row.find_elements_by_tag_name("td"):
                if len(row1.find_elements_by_tag_name("span"))>0:
                    try:
                        if accountno  in row1.find_element_by_tag_name("a").text:
                            row1.find_element_by_tag_name("a").click()
                            print("yes")
                            chk_acc =1
                            break
                    except:
                        pass
            if chk_acc==1:
                break
        else:
            print("no")
            response_dict["responseCode"] = "EAF010"
            response_dict["responseMsg"] = "Authentication Failed"
            return response_dict

        if len(fromDate)==7 and len(toDate)==7:
            tdy=calendar.monthrange(int(toDate[3:]),int(toDate[:2]))[1]
            fromDate='01'+"-"+fromDate
            toDate=str(tdy)+"-"+toDate

        toDate=datetime.strptime(toDate, '%d-%m-%Y')
        if toDate.year>=datetime.now().year and toDate.month>=datetime.now().month:
            toDate=datetime.now()-timedelta(days=1)

        toDate = toDate.strftime('%d-%m-%Y')

        date_list = pd.date_range(start=fromDate, end=toDate,
                                  freq=pd.DateOffset(days=365), closed=None).to_list()

        for ind1 in range(len(date_list)):
            if ind1 > 0:

                st = date_list[ind1-1].strftime('%d/%m/%Y')
                ed = (date_list[ind1] - timedelta(days=1)).strftime('%d/%m/%Y')
                print(st, ed)

                self.selectCalenderDate(st, ed)

        if len(date_list) > 0 and datetime.strptime(toDate, '%d-%m-%Y') > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
            st = (datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')).strftime('%d/%m/%Y')
            ed = (datetime.strptime(toDate, '%d-%m-%Y')).strftime('%d/%m/%Y')
            print(st, ed)

            self.selectCalenderDate(st, ed)

        elif len(date_list) == 0:

            st = (datetime.strptime(fromDate, '%d-%m-%Y')).strftime('%d/%m/%Y')
            ed = (datetime.strptime(toDate, '%d-%m-%Y')).strftime('%d/%m/%Y')
            print(st, ed)

            self.selectCalenderDate(st, ed)
            
        if self.date_status == "notExist":

            response_dict["responseCode"] = "END013"
            response_dict["responseMsg"] = "No Data Available"
            return response_dict
        
        elif self.date_status == "exist" :

            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"
            return response_dict

    def closeDriver(self):
        self.driver.quit()


# if __name__ == '__main__':

#     deutsche1 = DeutscheStatement(refid="deutscheTesting", env='quality')

#     mode = "Both"
#     bankName = "DEUTSCHE"
#     username = "003917758"
#     password = "Jsk(1996)"

#     fromDate = "19-05-2000"
#     toDate = "10-08-2000"

#     if mode == "Login Check":

#         response = deutsche1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             deutsche1.logout()
#         else:
#             deutsche1.driver_quit()

#     elif mode == "Data Download":
#         response = deutsche1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = deutsche1.getStatements(fromDate, toDate)
#             print(response1)
#             time.sleep(5)
#             deutsche1.logout()

#         else:
#             time.sleep(5)
#             deutsche1.driver_quit()

#     elif mode == "Both":
#         response = deutsche1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = deutsche1.getStatements(fromDate, toDate)
#             print(response1)
#             time.sleep(5)
#             deutsche1.logout()

#         else:
#             time.sleep(5)
#             deutsche1.driver_quit()
