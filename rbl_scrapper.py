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
from datetime import datetime, timedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from selenium.webdriver.common.keys import Keys
from dateutil.relativedelta import relativedelta
import pytz



class RBLScrapper:

    def __init__(self, refid, timeBwPage=2, env='quality', mode='headless'):
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

        """ netbanking url """
        self.netbanking_url = "https://online.rblbank.com/corp/AuthenticationController?FORMSGROUP_ID__=AuthenticationFG&__START_TRAN_FLAG__=Y&__FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=176"

        self.username_xp = "/html/body/form/div/div/div[6]/div/div[2]/div/div/input"

        self.next_xp = "/html/body/form/div/div/div[6]/div/div[3]/span/span/i/input"

        self.phrase_xp = "/html/body/form/div/div/div[5]/div/p[4]/span[1]/span"

        self.password_xp = "/html/body/form/div/div/div[5]/div/div[3]/div/div/input[1]"

        self.login_xp = "/html/body/form/div/div/div[5]/div/div[5]/span/span/i/input"

        self.account_statements_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[2]/div[2]/div/div/div[1]/div/div/div/div/div/ol/li[5]/a"

        self.account_table_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div/div/div[1]/div/table"

        self.from_date_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[2]/div[2]/div/p[2]/span/span/span/input[1]"
        self.to_date_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[2]/div[2]/div/p[3]/span/span/span/input[1]"
        self.search_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[2]/div[6]/div/p/span[2]/span/i/input"
        self.pdf_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[6]/div/div/span[3]/span/i/input"

        self.from_date_id = "PageConfigurationMaster_RXACBSW__1:TransactionHistoryFG.FROM_TXN_DATE"
        self.to_date_id = "PageConfigurationMaster_RXACBSW__1:TransactionHistoryFG.TO_TXN_DATE"
        self.search_id = "PageConfigurationMaster_RXACBSW__1:SEARCH"
        self.pdf_id = "PageConfigurationMaster_RXACBSW__1:GENERATE_REPORT5"

        self.incorrect_user_xp = "/html/body/form/div/div/div[6]/div/div[2]/div[2]/span/p[3]"

        self.incorrect_pwd_xp = "/html/body/form/div/div/div[5]/div/div[2]/div[2]/span/p[3]"

        self.logout_xp = "/html/body/form[1]/div[1]/div/div[1]/div/div/div/div[2]/ul/li[4]/p/span/span/a"

        self.logout_confirm_xp = "/html/body/div[11]/div[2]/div/div[3]/div/div/div/p[4]/span/span[2]/a"

        self.not_exist_xp = "/html/body/form[1]/div[1]/div/div[5]/div/div[5]/div/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[3]/div[2]/span/p[3]"
        self.date_status = "notExist"

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

    def check_exists_by_classname(self, classname):
        try:
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, classname)))
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
                driver = webdriver.Chrome('/usr/local/bin/chromedriver',
                                          chrome_options=self.chromeOptions)  # , chrome_options=self.chromeOptions
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'RBL', self.env,
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
        d_lt = os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), 'pdfs/' + self.ref_id + "/" + i)
            self.logStatus("info", "pdf downloaded")

    def login(self, username, password, seml, smno):

        try:
            self.driver.get(self.netbanking_url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        username_input = self.driver.find_element_by_xpath(self.username_xp)
        username_input.clear()
        username_input.send_keys(username)

        self.logStatus("info", "username entered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.next_xp).click()

        try:
            if "Incorrect User" in self.driver.find_element_by_xpath(self.incorrect_user_xp).text:
                self.logStatus("error", "invalid user id ", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}
        except:
            pass

        self.driver.find_element_by_xpath(self.phrase_xp).click()
        self.logStatus("info", "phrase ticked", self.takeScreenshot())

        password_input = self.driver.find_element_by_xpath(self.password_xp)
        password_input.clear()
        password_input.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.login_xp).click()
        self.logStatus("info", "login  clicked", self.takeScreenshot())

        try:
            if "Forgot Password" in self.driver.find_element_by_xpath(self.incorrect_pwd_xp).text:
                self.logStatus("error", "invalid password", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}
        except:
            pass

        self.logStatus("info", "login successfull", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def get_date_list(self, fromDate, toDate):

        if len(fromDate) == 7 and len(toDate) == 7:
            tdy = calendar.monthrange(int(toDate[3:]), int(toDate[:2]))[1]
            fromDate = '01' + "-" + fromDate
            toDate = str(tdy) + "-" + toDate

        fromDate = datetime.strptime(fromDate, '%d-%m-%Y')
        toDate = datetime.strptime(toDate, '%d-%m-%Y')

        lower_limit = datetime.now() - relativedelta(years=5) + timedelta(days=1)

        if fromDate <= lower_limit and toDate <= lower_limit:
            #     return {"referenceId": refid, "responseCode": "END013", "responseMsg": "No Data Available"}
            print({"referenceId": '123', "responseCode": "END013", "responseMsg": "No Data Available"})

        elif fromDate >= datetime.now() and toDate >= datetime.now():
            #     return {"referenceId": refid, "responseCode": "END013", "responseMsg": "No Data Available"}
            print({"referenceId": '123', "responseCode": "END013", "responseMsg": "No Data Available"})

        if datetime.now() <= toDate:
            toDate = datetime.now() - timedelta(days=1)

        if fromDate < lower_limit:
            fromDate = lower_limit

        dt_lst = []
        date_list = pd.date_range(start=fromDate.strftime('%m-%d-%Y'), end=toDate.strftime('%m-%d-%Y'),
                                  freq=pd.DateOffset(months=6), closed=None).to_list()
        for ind1 in range(len(date_list)):
            if ind1 > 0:
                st = date_list[ind1 - 1].date()
                ed = (date_list[ind1] - timedelta(days=1)).date()

                dt_lst.append([st, ed])

        if len(dt_lst) > 0 and toDate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
            st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d').date()
            ed = toDate.date()
            dt_lst.append([st, ed])
        elif len(dt_lst) == 0:
            dt_lst.append([fromDate.date(), toDate.date()])

        print(dt_lst)

        return dt_lst

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        self.driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.HOME)

        header_options = self.driver.find_element_by_id('flexiselDemo4').find_elements_by_tag_name('li')

        for opt in header_options:
            if 'accounts' in opt.text.lower():
                self.logStatus('info', "click on accounts option", self.takeScreenshot())
                opt.find_element_by_tag_name('a').click()
                break

        for ulOption in opt.find_elements_by_tag_name('ul'):
            if "account statement" in ulOption.text.lower():
                #         print(ulOption.text)
                break

        for liOption in ulOption.find_elements_by_tag_name('li'):
            if "account statement" in liOption.text.lower():
                self.logStatus('info', "select Account Statement option", self.takeScreenshot())
                #         print(liOption.text)
                liOption.find_element_by_tag_name('a').click()
                break

        acc_status = 0

        account_table = self.driver.find_element_by_tag_name('table')
        rows = account_table.find_elements(By.TAG_NAME, "tr")

        for row in rows:
            if accountno in row.text:
                #         print(row.text)
                break

        for td in row.find_elements(By.TAG_NAME, "td"):
            if accountno in td.text:
                self.logStatus('info', f'{td.text}', self.takeScreenshot())
                td.find_element_by_tag_name('a').click()
                acc_status = 1
                break

        if acc_status == 0:
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}
        else:

            dt_lst = self.get_date_list(fromdate, todate)
            time.sleep(5)
            for dts in dt_lst:
                fd = dts[0].strftime('%d/%m/%Y')
                td = dts[1].strftime('%d/%m/%Y')

                from_date_input = self.driver.find_element_by_id(self.from_date_id)
                from_date_input.clear()
                from_date_input.send_keys(fd)

                self.logStatus("info", "from date selected", self.takeScreenshot())
                time.sleep(self.timeBwPage)

                to_date_input = self.driver.find_element_by_id(self.to_date_id)
                to_date_input.clear()
                to_date_input.send_keys(td)

                self.logStatus("info", "to date selected", self.takeScreenshot())
                time.sleep(self.timeBwPage)

                self.driver.find_element_by_id(self.search_id).click()
                time.sleep(self.timeBwPage)

                try:
                    if "do not exist" in self.driver.find_element_by_xpath(self.not_exist_xp).text:
                        print("statement not exist")
                except:
                    self.date_status = "exist"
                    self.driver.find_element_by_id(self.pdf_id).click()
                    self.logStatus("info", "pdf download button clicked", self.takeScreenshot())
                    time.sleep(self.timeBwPage)

                    time.sleep(5)

        self.saving_pdf()

        if self.date_status == "notExist":
            self.logStatus("info", "data not exist", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

        elif self.date_status == "exist":
            self.logStatus("info", "statement downloaded", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed"}

    def logout(self):
        try:
            self.driver.find_element_by_xpath(self.logout_xp).click()
            if self.check_exists_by_xpath(self.logout_confirm_xp):
                self.driver.find_element_by_xpath(self.logout_confirm_xp).click()

            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull", {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':

#     accountno = "309011782362"
#     username   = "102781470"
#     password   = "Password#321"


#     obj=RBLScrapper('rbl_test')
#     opstr=obj.login(username,password,"","")
#     if opstr["responseCode"]=='SRC001':
#         res=obj.downloadData('01-09-2018','09-12-2020',accountno,"","")
#         a,b=obj.logout()
#         obj.closeDriver()