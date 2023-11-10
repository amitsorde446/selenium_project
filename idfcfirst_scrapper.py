import os
import shutil
import time
from botocore.exceptions import ClientError
from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from datetime import datetime,timedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class IDFCFScrapper:

    def __init__(self,refid, timeBwPage=5,env='dev',mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        hostname = socket.gethostname()    
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.ref_id = refid
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots/"+self.ref_id)
        self.pdfDir = os.path.join(os.getcwd(), "pdfs/"+self.ref_id)
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath='/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url='https://my.idfcfirstbank.com/login'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,5)

    def readConfig(self):
        configFileName = f"config_{self.env}.json"
        with open(configFileName, 'r') as confFile:
            config = json.load(confFile)
            self.driverConfig = config['driverConfig']
            self.dbConfig = config['dbConfig']

    def makeDirIfNot(self, dirpath):
        try:
            os.makedirs(dirpath)
        except FileExistsError:
            pass

    def makeDriverDirs(self, a):
        if a == 'ss':
            self.makeDirIfNot(self.screenshotDir)
        elif a == 'pdf':
            self.makeDirIfNot(self.pdfDir)

    def check_exists_by_xpath(self,xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True
    
    def check_exists_by_id(self,idd):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, idd)))
        except:
            return False
        return True

    def check_exists_by_name(self,nm):
        try:
            self.wait.until(EC.visibility_of_element_located((By.NAME, nm)))
        except:
            return False
        return True

    def createDriver(self, mode='local'):

        self.prefs = {
            "download.default_directory": self.pdfDir,
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
            if self.driverPath is None:
                driver = webdriver.Chrome(chrome_options=self.chromeOptions)
                driver.maximize_window()
            else:
                driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=self.chromeOptions)
                driver.maximize_window()

        except Exception as e:
            self.logStatus("error", str(e))
            print(f'Driver error : {e}')

        self.params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {
                'behavior': 'allow',
                'downloadPath': self.pdfDir
            }
        }

        self.logStatus("info", "Driver created")
        return driver

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
        self.bucket.upload_file(Filename=filename, Key=key)

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'IDFCFIRST', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), 'screenshots/' + self.ref_id + "/" + sname)
        return sname

    def saving_pdf(self):
        d_lt=os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), 'pdfs/' + self.ref_id + "/" + i)
            self.logStatus("info", "pdf downloaded")
        if len(d_lt)>0:
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self, username, password, seml, smno):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        time.sleep(5)

        if self.check_exists_by_name('mobileNumber'):

            mobile_input = self.driver.find_element_by_name('mobileNumber')
            mobile_input.clear()
            mobile_input.send_keys(username)
            self.logStatus("info", "mobile number entered", self.takeScreenshot())

            self.driver.find_element_by_xpath(
                '/html/body/div[1]/section/div/div[2]/div[2]/div/div[1]/form/div[2]/button').click()

            if self.check_exists_by_name('customerId'):
                self.logStatus("info", "mobile number not registered", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

            elif self.check_exists_by_name('login-password-input'):
                password_input = self.driver.find_element_by_name('login-password-input')
                password_input.clear()
                password_input.send_keys(password)
                self.logStatus("info", "password entered", self.takeScreenshot())

                self.driver.find_element_by_xpath(
                    '/html/body/div[1]/section/div/div[2]/div[2]/div/div[1]/form/div[3]/button').click()

                time.sleep(5)

                bodyText = self.driver.find_element_by_tag_name('body').text.lower()

                if 'logout' in bodyText:
                    self.logStatus("info", "login success", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

                elif 'valid password' in bodyText:
                    self.logStatus("info", "incorrect credentials", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "EWC002",
                            "responseMsg": "Incorrect UserName Or Password."}

        self.logStatus("error", "website error", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "EIS042",
                "responseMsg": "Information Source is Not Working"}

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        time.sleep(self.timeBwPage)

        if len(fromdate) == 7 and len(todate) == 7:
            tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
            fromdate = '01' + "-" + fromdate
            todate = str(tdy) + "-" + todate

        fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
        todate = datetime.strptime(todate, '%d-%m-%Y')

        from dateutil.relativedelta import relativedelta

        six_months = (datetime.now() + relativedelta(months=-6)).date()

        six_months = six_months.replace(day=1)

        if fromdate.date() >= six_months or todate.date() >= six_months:

            self.logStatus("info", "data exist in 6 month range", self.takeScreenshot())

            for anchor in self.driver.find_elements_by_tag_name('a'):
                if 'have' in anchor.text.lower():
                    anchor.click()
                    break

            time.sleep(5)
            accfound = 0

            for div in self.driver.find_elements_by_xpath(
                    '/html/body/div[1]/div[1]/main/section/section/section/div[1]/div[2]'):
                if accountno in div.text.replace(' ', ''):
                    div.click()
                    accfound = 1
                    break

            time.sleep(5)

            if accfound == 1:
                self.driver.find_element_by_xpath(
                    '/html/body/div[1]/div[1]/main/section/section/section/article/div[2]/div[6]').click()

                self.logStatus("info", "download statement clicked", self.takeScreenshot())

                time.sleep(1)
                for label in self.driver.find_elements_by_tag_name('label'):
                    if 'last 6 months' in label.text.lower():
                        label.click()

                        self.logStatus("info", "last 6 months selected", self.takeScreenshot())
                        break

                time.sleep(1)
                for button in self.driver.find_elements_by_tag_name('button'):
                    if 'download' in button.text.lower():
                        button.click()

                        self.logStatus("info", "download clicked", self.takeScreenshot())
                        time.sleep(5)
                        self.driver.find_element_by_xpath(
                            '/html/body/div[2]/div/section/header/div/div[3]/button').click()
                        break

                dic = self.saving_pdf()
                return dic

            else:
                self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

        else:
            self.logStatus("error", "Data doesn't exist", self.takeScreenshot())

    def logout(self):
        if self.check_exists_by_xpath('/html/body/div[1]/div[1]/header/div/section/div[3]'):
            self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/header/div/section/div[3]').click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     obj=PNBScrapper('IDFCFIRST')
#     opstr=obj.login('com_ashu','Rihu@6688','','')
#     res=obj.downloadData('26-10-2019','08-12-2020','10063300734','','')
#     a,b=obj.logout()
#     obj.closeDriver()