import os
import shutil
from webdriver_manager.chrome import ChromeDriverManager
import time
from botocore.exceptions import ClientError
from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from tessrct import sccaptcha
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class SCScrapper:

    def __init__(self, refid, timeBwPage=2, env='dev', mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", (
            "env value should be either quality or prod or dev or sandbox")
        self.env = env
        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.ref_id = refid
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots/" + self.ref_id)
        self.pdfDir = os.path.join(os.getcwd(), "pdfs/" + self.ref_id)
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url = 'https://retail.sc.com/in/nfs/login.htm'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 10)

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

    def check_exists_by_xpath(self, xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True

    def check_exists_by_id(self, idd):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, idd)))
        except:
            return False
        return True

    def check_exists_by_classname(self, clsnm):
        try:
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, clsnm)))
        except:
            return False
        return True

    def check_exists_by_name(self, nm):
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
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions)
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
        tm = str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'SC', self.env,
                                 screenshot, self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), self.ref_id + "/" + "screenshot/"+sname)
        return sname

    def saving_pdf(self):
        d_lt = os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), self.ref_id + "/"+"automated_pdf_files/"+ i)
        if len(d_lt) > 0:
            self.logStatus("info", "file downloaded")
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
            self.logStatus("info", "no file downloaded")
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

    def login(self, username, password, seml, smno):

        while 1:

            try:
                self.driver.get(self.url)
                self.logStatus("info", "website opened", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}

            if self.check_exists_by_name('j_username'):
                usernameInputField = self.driver.find_element_by_name('j_username')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}

            time.sleep(self.timeBwPage)

            PasswordField = self.driver.find_element_by_name('j_password')
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            lgnbtn = self.driver.find_element_by_name('Login')
            time.sleep(1)
            lgnbtn.location_once_scrolled_into_view
            self.logStatus("info", "scrolled down", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            self.driver.save_screenshot("screenshot.png")
            captchaInputField = self.driver.find_element_by_name('code')
            captchaInputField.clear()
            captchaInputField.send_keys(sccaptcha())
            self.logStatus("info", "captcha entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            if self.check_exists_by_classname('txt_error'):
                errormsg = self.driver.find_element_by_class_name('txt_error')
                print(errormsg.text)
                if 'Invalid code' in errormsg.text:
                    self.logStatus("debug", "invalid captcha", self.takeScreenshot())
                    continue
                elif 'invalid username or password' in errormsg.text:
                    self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "EWC002",
                            "responseMsg": "Incorrect UserName Or Password."}
            else:
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def downloadData(self, fromdate, todate, accountno, seml, smno):
        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('parentMenu'):

            mainmenu = self.driver.find_element_by_id('parentMenu')
            menulst = mainmenu.find_elements_by_id('parentMenuHead')

            for mn in menulst:
                if mn.text == 'Accounts':
                    mn.find_element_by_tag_name('a').click()
                    self.logStatus("info", "clicked on accounts in menu", self.takeScreenshot())
                    break

        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('parentMenu'):

            mainmenu = self.driver.find_element_by_id('parentMenu')
            submenulst = mainmenu.find_element_by_id('parentMenuContentSelected').find_elements_by_id('contentLink')

            for sm in submenulst:
                if 'Transaction History' in sm.text:
                    sm.find_element_by_tag_name('a').click()
                    self.logStatus("info", "clicked on transaction history in menu", self.takeScreenshot())
                    break

        time.sleep(10)

        acn = ''
        if self.check_exists_by_name('accountSelectIndex'):

            bankacc = Select(self.driver.find_element_by_name('accountSelectIndex'))

            for acc in list(map(lambda x: x.text, bankacc.options)):
                if accountno in acc:
                    acn = acc
                    bankacc.select_by_visible_text(acc)
                    self.logStatus("info", "Account selected", self.takeScreenshot())
                    break

        if acn == '':

            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

        else:
            time.sleep(self.timeBwPage)

            if len(fromdate) == 7 and len(todate) == 7:
                tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
                fromdate = '01' + "-" + fromdate
                todate = str(tdy) + "-" + todate

            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')

            dayslmt = datetime.now() - timedelta(days=90)

            if fromdate < dayslmt:
                fromdate = dayslmt

            if todate.date() >= datetime.now().date() :
                todate = datetime.now() - timedelta(days=1)

            fromdate = fromdate.strftime('%d/%m/%Y')
            todate = todate.strftime('%d/%m/%Y')

            print(f'FROM DATE : {fromdate} TO DATE : {todate}')

            # FROM DATE SET

            FromDate = self.driver.find_element_by_name('searchHistoryVO.startDate')
            FromDate.clear()
            FromDate.send_keys(fromdate)
            self.logStatus("info", "from date entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            # TO DATE SET

            ToDate = self.driver.find_element_by_name('searchHistoryVO.endDate')
            ToDate.clear()
            ToDate.send_keys(todate)
            self.logStatus("info", "to date entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            self.driver.find_element_by_name('Proceed').click()
            self.logStatus("info", "Proceed button clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            if self.check_exists_by_xpath('/html/body/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/form/table/tbody/tr[3]/td/span'):

                error_text = self.driver.find_element_by_xpath(
                    '/html/body/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[1]/td[2]/form/table/tbody/tr[3]/td/span').text

                if 'no transactions' in error_text:
                    print("There are no transactions found within your search criteria")

                elif 'adjust your start date' in error_text:
                    print(
                        'Sorry, we are only able to retrieve details from the last 90 days, please adjust your start date')

            else:

                dwnldopt = self.driver.find_elements_by_name('btndownload')

                for opt in dwnldopt:
                    if opt.text == 'Excel':
                        opt.click()
                        break

            time.sleep(5)

            dic = self.saving_pdf()
            return dic

    def logout(self):

        if self.check_exists_by_name('Logout'):
            self.driver.find_element_by_name('Logout').click()
            self.logStatus("info", "logout successful", self.takeScreenshot())
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        else:
            self.logStatus("error", "logout unsuccessful", self.takeScreenshot())
            return "unsuccessfull", {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     # Refid=str(uuid.uuid1())
#     # print(f'RefID : {Refid}')
#     obj=SCScrapper('9004dd50-57cb-11eb-b128-7440bb00d0c5')
#     opstr=obj.login('comashu01','Password#321','','')
#     print(opstr)
#     res=obj.downloadData('01-09-2017','14-01-2021','53510925221','','')
#     a,b=obj.logout()
#     obj.closeDriver()