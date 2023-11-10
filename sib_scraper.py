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
from datetime import datetime, timedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from PIL import Image
import pytz
from tessrct import sibcaptcha

class SIBscraper:

    def __init__(self, refid, timeBwPage=2, env='dev', mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev", ("env value should be either quality or prod or dev")
        self.env = env
        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.ref_id = refid
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots/" + self.ref_id)
        self.pdfDir = os.path.join(os.getcwd(), "pdfs/" + self.ref_id)
        self.dwnldDir = os.path.join(os.getcwd(), "downloads/" + self.ref_id)
        self.makeDriverDirs('dwn')
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,10)

        self.statement_stat = False

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

        if a == 'dwn':
            self.makeDirIfNot(self.dwnldDir)
        elif a == 'ss':
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

    def check_exists_by_id(self, id1):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, id1)))
        except:
            return False
        return True


    def createDriver(self, mode='local'):

        self.prefs = {
            "download.default_directory": self.dwnldDir,
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
            #self.chromeOptions.add_argument("--headless")
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
                'downloadPath': self.dwnldDir
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'SIB', self.env,
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
            self.logStatus("info", "pdf downloaded")

    def login(self, username, password, seml, smno):

        while True:

            try:
                self.driver.get(
                    'https://sibernet.southindianbank.com/corp/AuthenticationController?FORMSGROUP_ID__=AuthenticationFG&__START_TRAN_FLAG__=Y&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=059')
                self.logStatus("info", "website opened", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}

            if self.check_exists_by_id("AuthenticationFG.USER_PRINCIPAL"):

                user_input = self.driver.find_element_by_id("AuthenticationFG.USER_PRINCIPAL")
                user_input.clear()
                user_input.send_keys(username)

                self.logStatus("info", "username entered", self.takeScreenshot())

                pwd_input = self.driver.find_element_by_id("AuthenticationFG.ACCESS_CODE")
                pwd_input.clear()
                pwd_input.send_keys(password)

                self.logStatus("info", "password entered", self.takeScreenshot())
                self.driver.save_screenshot("captcha.png")
                cap1 = sibcaptcha()

                cap_input = self.driver.find_element_by_id('AuthenticationFG.VERIFICATION_CODE')
                cap_input.clear()
                cap_input.send_keys(cap1)

                self.logStatus("info", "captcha entered", self.takeScreenshot())

                self.driver.find_element_by_id('VALIDATE_CREDENTIALS').click()

                self.logStatus("info", "login  clicked", self.takeScreenshot())

                if self.check_exists_by_id('MessageDisplay_TABLE'):
                    if 'Invalid login credentials' in self.driver.find_element_by_id('MessageDisplay_TABLE').text:
                        print("invalid credentials")
                        self.logStatus("error", "invalid username or password", self.takeScreenshot())
                        return {"referenceId": self.ref_id, "responseCode": "EWC002",
                                "responseMsg": "Incorrect UserName Or Password."}

                    elif 'Enter the characters' in self.driver.find_element_by_id('MessageDisplay_TABLE').text:
                        print("incorrect captcha")
                        self.logStatus("info", "incorrect captcha, retrying", self.takeScreenshot())
                else:
                    print("correct credentials and captcha")
                    self.logStatus("info", "login successfull", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "SRC001",
                            "responseMsg": "Successfully Completed."}

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        self.driver.find_element_by_xpath(
            '/html/body/form/div[4]/div[5]/div[2]/div/div/div[1]/div[1]/div/div/div[1]/a').click()

        print("View Account Detials")

        self.logStatus("info", "View Account Detials clicked", self.takeScreenshot())

        for li1 in self.driver.find_element_by_xpath(
                '/html/body/form/div[6]/div[3]/div/div[1]/ul').find_elements_by_tag_name("li"):
            if 'STATEMENTS' in li1.text:
                print("statement option")
                li1.click()

                self.logStatus("info", "statements option clicked", self.takeScreenshot())

                break

        acc_Select = Select(self.driver.find_element_by_id('XeoStatement'))

        acc_status = 0

        for acc1 in acc_Select.options:

            if accountno in acc1.text:
                acc1.click()
                print(acc1.text)
                self.logStatus("info", "account selected", self.takeScreenshot())
                acc_status = 1
                break

        if acc_status == 0:
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}
        else:
            time.sleep(self.timeBwPage)

            search_statement = self.driver.find_element_by_xpath('/html/body/form/div[7]/div[3]/div/div/div/div[2]/a')
            search_statement.click()
            self.logStatus("info", "Search Statement Option clicked", self.takeScreenshot())

            date_list = pd.date_range(start=fromdate, end=todate, freq=pd.DateOffset(days=365), closed=None).to_list()

            for ind1 in range(len(date_list)):
                if ind1 > 0:

                    st = date_list[ind1 - 1].strftime('%d-%m-%Y')
                    ed = (date_list[ind1] - timedelta(days=1)).strftime('%d-%m-%Y')
                    st = (datetime.strptime(st, '%d-%m-%Y'))
                    ed = (datetime.strptime(ed, '%d-%m-%Y'))

                    print((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)),
                          (str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))

                    from_date_input = self.driver.find_element_by_id('TransactionHistoryFG.FROM_TXN_DATE')
                    from_date_input.clear()
                    from_date_input.send_keys((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)))
                    self.logStatus("info", "from date selected", self.takeScreenshot())

                    to_date_input = self.driver.find_element_by_id('TransactionHistoryFG.TO_TXN_DATE')
                    to_date_input.clear()
                    to_date_input.send_keys((str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))
                    self.logStatus("info", "to date selected", self.takeScreenshot())

                    self.driver.find_element_by_id('SEARCH').click()
                    self.logStatus("info", "search clicked", self.takeScreenshot())

                    if self.check_exists_by_id('MessageDisplay_TABLE'):
                        if 'The transactions do not exist for the account with the entered criteria' in self.driver.find_element_by_id(
                                'MessageDisplay_TABLE').text:
                            print("statement do'nt exist")
                            self.logStatus("info", "statement doesn't exist", self.takeScreenshot())


                    else:
                        print("statement exist")

                        self.logStatus("info", "statement exist", self.takeScreenshot())

                        self.statement_stat = True

                        self.driver.find_element_by_xpath(
                            "/html/body/form/div[7]/div[3]/div/div[8]/div/div[1]/div/div/div/div/h3/span[3]/div/a[1]").click()
                        time.sleep(self.timeBwPage)
                        time.sleep(5)
                        d_lt = os.listdir(self.dwnldDir)
                        shutil.move(self.dwnldDir + "/" + d_lt[0],
                                    self.pdfDir + "/" + str(st)[:10] + "-" + str(ed)[:10] + '.pdf')

            if len(date_list) > 0 and datetime.strptime(todate, '%d-%m-%Y') > datetime.strptime(str(date_list[-1])[:10],
                                                                                                '%Y-%m-%d'):
                st = (datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')).strftime('%d-%m-%Y')
                st = (datetime.strptime(st, '%d-%m-%Y'))
                ed = (datetime.strptime(todate, '%d-%m-%Y'))

                print((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)),
                      (str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))

                from_date_input = self.driver.find_element_by_id('TransactionHistoryFG.FROM_TXN_DATE')
                from_date_input.clear()
                from_date_input.send_keys((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)))
                self.logStatus("info", "from date selected", self.takeScreenshot())

                to_date_input = self.driver.find_element_by_id('TransactionHistoryFG.TO_TXN_DATE')
                to_date_input.clear()
                to_date_input.send_keys((str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))
                self.logStatus("info", "to date selected", self.takeScreenshot())

                self.driver.find_element_by_id('SEARCH').click()
                self.logStatus("info", "search clicked", self.takeScreenshot())

                if self.check_exists_by_id('MessageDisplay_TABLE'):
                    if 'The transactions do not exist for the account with the entered criteria' in self.driver.find_element_by_id(
                            'MessageDisplay_TABLE').text:
                        print("statement do'nt exist")
                        self.logStatus("info", "statement doesn't exist", self.takeScreenshot())

                else:
                    print("statement exist")

                    self.logStatus("info", "statement exist", self.takeScreenshot())

                    self.statement_stat = True

                    self.driver.find_element_by_xpath(
                        "/html/body/form/div[7]/div[3]/div/div[8]/div/div[1]/div/div/div/div/h3/span[3]/div/a[1]").click()
                    time.sleep(self.timeBwPage)
                    time.sleep(5)
                    d_lt = os.listdir(self.dwnldDir)
                    shutil.move(self.dwnldDir + "/" + d_lt[0],
                                self.pdfDir + "/" + str(st)[:10] + "-" + str(ed)[:10] + '.pdf')


            elif len(date_list) == 1:

                st = (datetime.strptime(fromdate, '%d-%m-%Y'))
                ed = (datetime.strptime(todate, '%d-%m-%Y'))

                print((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)),
                      (str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))

                from_date_input = self.driver.find_element_by_id('TransactionHistoryFG.FROM_TXN_DATE')
                from_date_input.clear()
                from_date_input.send_keys((str(st)[8:10] + '-' + st.strftime("%b") + '-' + str(st.year)))
                self.logStatus("info", "from date selected", self.takeScreenshot())

                to_date_input = self.driver.find_element_by_id('TransactionHistoryFG.TO_TXN_DATE')
                to_date_input.clear()
                to_date_input.send_keys((str(ed)[8:10] + '-' + ed.strftime("%b") + '-' + str(ed.year)))
                self.logStatus("info", "to date selected", self.takeScreenshot())

                self.driver.find_element_by_id('SEARCH').click()
                self.logStatus("info", "search clicked", self.takeScreenshot())

                if self.check_exists_by_id('MessageDisplay_TABLE'):
                    if 'The transactions do not exist for the account with the entered criteria' in self.driver.find_element_by_id(
                            'MessageDisplay_TABLE').text:
                        print("statement do'nt exist")
                        self.logStatus("info", "statement doesn't exist", self.takeScreenshot())


                else:
                    print("statement exist")

                    self.logStatus("info", "statement exist", self.takeScreenshot())

                    self.statement_stat = True

                    self.driver.find_element_by_xpath(
                        "/html/body/form/div[7]/div[3]/div/div[8]/div/div[1]/div/div/div/div/h3/span[3]/div/a[1]").click()
                    time.sleep(self.timeBwPage)
                    time.sleep(5)
                    d_lt = os.listdir(self.dwnldDir)
                    shutil.move(self.dwnldDir + "/" + d_lt[0],
                                self.pdfDir + "/" + str(st)[:10] + "-" + str(ed)[:10] + '.pdf')

        if self.statement_stat == False:
            self.logStatus("info", "data not exist", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}
        else:

            self.logStatus("info", " data downloaded", self.takeScreenshot())

            time.sleep(5)
            self.saving_pdf()
            time.sleep(5)

            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed"}

    def logout(self):

        self.driver.find_element_by_id('HREF_Logout').click()

        self.logStatus("info", "logout successfull", self.takeScreenshot())
        return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                               "responseMsg": "Successfully Completed."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()


# if __name__ == '__main__':
#
#     account_no = "5556053000042707"
#     username = "SONU9213"
#     password = "H@ppyw1r3"
#
#     obj = SouthIndianBank('sib_test3')
#     opstr = obj.login(username, password, "", "")
#     if opstr["responseCode"] == 'SRC001':
#         res = obj.downloadData('01-05-2018', '05-07-2021', account_no, "", "")
#
#         print(res)
#         a, b = obj.logout()
#         obj.closeDriver()