from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
import json
import zipfile
import json
import os
import time
import uuid
from pprint import pprint
import boto3
from botocore.exceptions import ClientError
from data_base import DB
from selenium.webdriver.common.by import By
from datetime import date, timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import cv2
import pytesseract
import os
import numpy as np
from pathlib import Path
import socket
import calendar
import pytz



class INDUSINDStatement:

    def __init__(self, refid, env="dev"):
        self.timeBwPage = 0.5
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", (
            "env value should be either quality or prod or dev or sandbox")
        self.env = env
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.readConfig()
        self.CreateS3()

        self.dbObj = DB(**self.dbConfig)
        self.refid = refid
        self.downloadDir = os.path.join(os.getcwd(), "pdfs")
        self.chromeOptions = Options()

        proxyhost = '35.200.150.56'
        proxyport = '3128'
        proxyusername = 'user1'
        proxypassword = 'Scoreme@1234'
        self.addProxy(proxyhost, proxyport, proxyusername, proxypassword)

        self.driver = self.createDriver(mode='headless')

        self.wait = WebDriverWait(self.driver, 5)

        self.ref_id = refid

        self.url = "https://indusnet.indusind.com/corp/BANKAWAY?Action.RetUser.Init.001=Y&AppSignonBankId=234&AppType=corporate&CorporateSignonLangId=001"

        self.username_input_xp = "/html/body/div[2]/div/div[1]/div[1]/form/div[1]/input"

        self.password_input_xp = '/html/body/div[2]/div/div[1]/div[1]/form/div[2]/input'

        self.login_button_xp = '/html/body/div[2]/div/div[1]/div[1]/form/a'

        self.from_cal_xp = "/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[2]/td[1]/div/table[2]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/table/tbody/tr/td[3]/a/img"
        self.to_cal_xp = "/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[2]/td[1]/div/table[2]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/table/tbody/tr/td[4]/a/img"

        self.month_year_xp = "/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td[2]/nobr/b/span"

        self.year_before_xp = "/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td[1]/span/b/a[1]/img"
        self.next_year_xp = "/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td[3]/span/b/a[2]/img"

        self.month_before_xp = "/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td[1]/span/b/a[2]/img"
        self.next_month_xp = "/html/body/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td[3]/span/b/a[1]/img"

        self.day_xp = "/html/body/table/tbody/tr/td/table"

        self.submit_xp = "/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[2]/td[1]/div/table[2]/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr/td/input"

        self.download_pdf_xp = "/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td[1]/table[2]/tbody/tr/td/table/tbody[3]/tr/td/table[2]/tbody/tr[3]/td/table/tbody/tr[3]/td/table/tbody/tr/td[3]/input"

        self.back_xp = "/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td[1]/table[2]/tbody/tr/td/table/tbody[3]/tr/td/table[2]/tbody/tr[3]/td/table/tbody/tr[3]/td/table/tbody/tr/td[5]/input"

        self.saving_option_xp = "/html/body/center/div[3]/table/tbody/tr/td[1]/div/div/a[2]"

        self.statement_option_xp = "/html/body/center/div[3]/table/tbody/tr/td[1]/div/div/div/b/font/a/b/font"

        self.adhoc_statement_xp = "/html/body/center/div[3]/table/tbody/tr/td[1]/div/div/div/b/font/div[1]/a[2]/font"

        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)

        if not os.path.exists("Screenshots"):
            os.makedirs("Screenshots")

        if not os.path.exists("pdfs"):
            os.makedirs("pdfs")

    def addProxy(self, phost, pport, puser, ppasswd):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """
        background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                },
                bypassList: []
                }
            };
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (phost, pport, puser, ppasswd)
        pluginfile = 'proxy_auth_plugin.zip'
        with zipfile.ZipFile(pluginfile, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        self.chromeOptions.add_extension(pluginfile)

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

        pdfName = os.path.join(self.pdfDir, f"{pname}")

        self.uploadToS3(os.path.join(pdfName), "pdfs/" + self.refid + "/" + pname)

        os.remove("pdfs/" + pname)

        return pname

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'INDUSIND', self.env,
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
                'downloadPath': self.downloadDir
            }
        }

        self.logStatus("info", "Driver created")
        return driver

    def check_exists_by_xpath(self, xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True

    def login(self, username, password, seml, smno):

        try:
            self.driver.get(self.url)
            time.sleep(10)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        self.logStatus("info", "open indusind netbanking webpage", self.takeScreenshot())

        username_input = self.driver.find_element_by_xpath(self.username_input_xp)
        username_input.clear()
        username_input.send_keys(username)

        time.sleep(1)

        password_input = self.driver.find_element_by_xpath(self.password_input_xp)
        password_input.clear()
        password_input.send_keys(password)
        time.sleep(1)

        self.driver.find_element_by_xpath(self.login_button_xp).click()
        time.sleep(1)

        try:
            alert = self.driver.switch_to_alert()
            print(alert.text)
            txt = alert.text
            alert.accept()
            self.driver.switch_to_default_content()
            if "incorrect" in txt:
                print("incorrect credentials")
                self.logStatus("info", "incorrect credentials", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}
        except Exception as e:
            print(f'Alert box : {e}')

        try:
            try:
                self.driver.find_elements_by_xpath("//*[contains(text(), 'Additional Authentication Needed')]")
                self.logStatus("info", "Authentication Questions", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}
            except:
                print("no authentication question")
                self.logStatus("info", "No Authentication Questions", self.takeScreenshot())

            if self.driver.find_element_by_xpath("//*[contains(text(), 'Logout')]"):
                self.logStatus("info", "logged in", self.takeScreenshot())
                print("logged in")
                return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed"}
        except:
            print("not logged in")

    def logout(self):
        try:
            self.driver.find_element_by_xpath("//*[contains(text(), 'Logout')]").click()
            self.driver.switch_to_default_content()
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull", {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}

    def selectCalenderDate(self, select_date, cal_xp):
        self.driver.find_element_by_xpath(cal_xp).click()
        self.driver.switch_to_window(self.driver.window_handles[-1])
        current_m_y = self.driver.find_element_by_xpath(self.month_year_xp).text

        target_m_y = select_date.strftime("%B") + " " + str(select_date.year)

        while True:
            current_m_y = self.driver.find_element_by_xpath(self.month_year_xp).text

            if int(current_m_y.split()[1]) == select_date.year:
                break

            if int(current_m_y.split()[1]) < select_date.year:
                self.driver.find_element_by_xpath((self.next_year_xp)).click()
            elif int(current_m_y.split()[1]) > select_date.year:
                self.driver.find_element_by_xpath((self.year_before_xp)).click()

        calendar_list = [calendar.month_name[month_idx] + " " + str(select_date.year) for month_idx in range(1, 13)]

        while True:
            current_m_y = self.driver.find_element_by_xpath(self.month_year_xp).text
            ind1 = calendar_list.index(current_m_y)

            if calendar_list.index(target_m_y) == ind1:
                break

            if calendar_list.index(target_m_y) > ind1:
                self.driver.find_element_by_xpath((self.next_month_xp)).click()
            elif calendar_list.index(target_m_y) < ind1:
                self.driver.find_element_by_xpath((self.month_before_xp)).click()

        table = self.driver.find_element_by_xpath(self.day_xp)
        ind3 = 0
        for row in table.find_elements_by_xpath(".//tr"):

            for td in row.find_elements_by_xpath(".//td"):

                if ind3 > 2 and td.text != " " and int(td.text) == select_date.day:
                    ind3 = 55
                    td.click()
                    break

            if ind3 == 55:
                break

            ind3 += 1

        self.driver.switch_to_window(self.driver.window_handles[0])

    def downloadData(self, fromDate, toDate, accountno, seml, smno):

        if self.check_exists_by_xpath(
                '/html/body/center/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr[1]/td/table[2]/tbody/tr[2]/td/table/tbody/tr[3]/td/table/tbody/tr[8]/td/a[2]'):
            self.driver.find_element_by_xpath(
                '/html/body/center/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr[1]/td/table[2]/tbody/tr[2]/td/table/tbody/tr[3]/td/table/tbody/tr[8]/td/a[2]').click()
            time.sleep(3)
            obj = self.driver.switch_to.alert
            time.sleep(1)
            obj.accept()

        if len(fromDate) == 7 and len(toDate) == 7:
            tdy = calendar.monthrange(int(toDate[3:]), int(toDate[:2]))[1]
            fromDate = '01' + "-" + fromDate
            toDate = str(tdy) + "-" + toDate

        toDate = datetime.strptime(toDate, '%d-%m-%Y')
        if toDate.year >= datetime.now().year and toDate.month >= datetime.now().month:
            toDate = datetime.now() - timedelta(days=1)

        toDate = toDate.strftime('%d-%m-%Y')

        data_status = "F"
        time.sleep(2)

        self.driver.find_element_by_xpath(self.saving_option_xp).click()
        time.sleep(2)
        self.driver.find_element_by_xpath(self.statement_option_xp).click()
        try:
            obj = self.driver.switch_to.alert
            time.sleep(1)
            obj.accept()
        except Exception:
            pass
        time.sleep(2)
        self.driver.find_element_by_xpath(self.adhoc_statement_xp).click()

        bankacc = Select(self.driver.find_element_by_xpath(
            '/html/body/center/div[3]/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[2]/td[1]/div/table[2]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td[3]/select'))

        acn = ''
        for accno in list(map(lambda x: x.text, bankacc.options)):
            if accountno in accno.replace("-", ""):
                acn = accno
                bankacc.select_by_visible_text(acn)

                break

        if acn == '':

            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

        else:

            # select_account_option = Select(self.driver.find_element_by_name('IndexCount'))

            # select_account_option.select_by_value("0")

            date_list = pd.date_range(start=fromDate, end=toDate, freq=pd.DateOffset(days=365), closed=None).to_list()

            for ind1 in range(len(date_list)):
                if ind1 > 0:

                    st = date_list[ind1 - 1].strftime('%d-%m-%Y')
                    ed = (date_list[ind1] - timedelta(days=1)).strftime('%d-%m-%Y')
                    st = (datetime.strptime(st, '%d-%m-%Y'))
                    ed = (datetime.strptime(ed, '%d-%m-%Y'))

                    print(st, ed)

                    self.selectCalenderDate(st, self.from_cal_xp)

                    self.selectCalenderDate(ed, self.to_cal_xp)

                    self.driver.find_element_by_xpath(self.submit_xp).click()

                    try:
                        alert = self.driver.switch_to_alert()
                        print(alert.text)
                        txt = alert.text
                        alert.accept()
                        self.driver.switch_to_default_content()
                        if "No Transactions" in txt:
                            print("No data")
                            # data_status = "F"
                            self.logStatus("info", "no data for speified period", self.takeScreenshot())
                    #                         return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                    except Exception as e:
                        print(f'Alert box : {e}')

                        self.driver.find_element_by_xpath(self.download_pdf_xp).click()

                        self.driver.find_element_by_xpath(self.back_xp).click()

                        time.sleep(2)
                        data_status = "T"
                        self.savePdf()
                        self.logStatus("info", "pdf downloaded", self.takeScreenshot())

            if len(date_list) > 0 and datetime.strptime(toDate, '%d-%m-%Y') > datetime.strptime(str(date_list[-1])[:10],
                                                                                                '%Y-%m-%d'):
                st = (datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')).strftime('%d-%m-%Y')
                st = (datetime.strptime(st, '%d-%m-%Y'))
                ed = (datetime.strptime(toDate, '%d-%m-%Y'))
                print(st, ed)

                self.selectCalenderDate(st, self.from_cal_xp)

                self.selectCalenderDate(ed, self.to_cal_xp)

                self.driver.find_element_by_xpath(self.submit_xp).click()

                try:
                    alert = self.driver.switch_to_alert()
                    print(alert.text)
                    txt = alert.text
                    alert.accept()
                    self.driver.switch_to_default_content()
                    if "No Transactions" in txt:
                        print("No data")
                        # data_status = "F"
                        self.logStatus("info", "no data for speified period", self.takeScreenshot())
                #                         return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                except Exception as e:

                    self.driver.find_element_by_xpath(self.download_pdf_xp).click()

                    self.driver.find_element_by_xpath(self.back_xp).click()
                    print(f'Alert box : {e}')
                    time.sleep(2)
                    data_status = "T"
                    self.savePdf()
                    self.logStatus("info", "pdf downloaded", self.takeScreenshot())

            elif len(date_list) == 1:

                st = (datetime.strptime(fromDate, '%d-%m-%Y'))
                ed = (datetime.strptime(toDate, '%d-%m-%Y'))
                print(st, ed)

                self.selectCalenderDate(st, self.from_cal_xp)

                self.selectCalenderDate(ed, self.to_cal_xp)

                self.driver.find_element_by_xpath(self.submit_xp).click()

                try:
                    alert = self.driver.switch_to_alert()
                    print(alert.text)
                    txt = alert.text
                    alert.accept()
                    self.driver.switch_to_default_content()
                    if "No Transactions" in txt:
                        print("No data")
                        # data_status = "F"
                        self.logStatus("info", "no data for speified period", self.takeScreenshot())
                #                         return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                except Exception as e:

                    self.driver.find_element_by_xpath(self.download_pdf_xp).click()

                    self.driver.find_element_by_xpath(self.back_xp).click()
                    print(f'Alert box : {e}')

                    time.sleep(2)
                    data_status = "T"
                    self.savePdf()
                    self.logStatus("info", "pdf downloaded", self.takeScreenshot())

            if data_status == "F":
                return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}
            else:
                return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed"}

    def closeDriver(self):
        self.driver.quit()

# if __name__ == '__main__':

# ind1 = INDUSINDStatement(refid="canaraTesting", env='quality')
#
# mode = "Data Download"
# bankName = "INDUSIND"
# username = "manked83"
# password = 'Ril@@54321'
# fromDate = "19-11-2018"
# toDate = "09-04-2021"
# accountno = "159810205767"
#
# response = ind1.login(username, password)
# response1 = ind1.getStatements(fromDate, toDate, accountno)
# ind1.logout()
# ind1.closeDriver()
