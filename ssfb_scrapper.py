from webdriver_manager.chrome import ChromeDriverManager
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

# from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class SSFBScrapper:

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
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage

        self.netbanking_url = "https://www.suryodaybank.com/"
        self.retail_banking_xp = "/html/body/div[1]/div/div/div[3]/div/a[1]"
        self.username_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[3]/div[2]/input"
        self.login_continue_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[4]/div/button"
        self.phrase_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[5]/div[1]/input"
        self.password_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[4]/div[2]/input[3]"
        self.login_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[6]/div/button"
        self.nav_bar_xp = "/html/body/div[1]/div[2]/div[1]/div/div/div/ul"
        self.account_type_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/select"
        self.account_list_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[1]/div[2]/div[2]/div/select"
        self.date_range_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[1]/label/input"
        self.from_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/span/button/span"
        self.to_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/span/button/span"

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
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, xclassnamepath)))
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
                driver = webdriver.Chrome(ChromeDriverManager().install(),
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
        tm = str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'SSFB', self.env,
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

        try:
            self.driver.get(self.netbanking_url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        self.check_exists_by_xpath(self.retail_banking_xp)
        self.driver.find_element_by_xpath(self.retail_banking_xp).click()
        self.driver.switch_to_window(self.driver.window_handles[-1])

        time.sleep(5)

        if self.check_exists_by_xpath(self.username_xp):
            username_input = self.driver.find_element_by_xpath(self.username_xp)
            username_input.clear()
            username_input.send_keys(username)
        else:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        self.check_exists_by_xpath(self.login_continue_xp)
        self.driver.find_element_by_xpath(self.login_continue_xp).click()

        self.logStatus("info", "username entered", self.takeScreenshot())

        password_input = self.driver.find_element_by_xpath(self.password_xp)
        password_input.clear()
        password_input.send_keys(password)

        self.logStatus("info", "password entered", self.takeScreenshot())

        try:
            self.driver.find_element_by_id("isSecChecked").click()
            self.logStatus("info", "phrase ticked", self.takeScreenshot())

            self.driver.find_element_by_xpath(self.login_xp).click()
        except:
            print("checkbox  not exist")
            self.logStatus("info", "no checkbox", self.takeScreenshot())
            self.driver.find_element_by_xpath(
                "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[5]/div/button").click()

        self.logStatus("info", "login  clicked", self.takeScreenshot())

        try:
            if "Invalid" in self.driver.find_element_by_id("authError"):
                print("incorrect details")
                self.logStatus("error", "invalid username or password", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}
        except:
            print("correct details")

        self.logStatus("info", "login successfull", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def find_calendar_div(self, calendar_name):
        for div in self.driver.find_elements_by_xpath('/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form'):
            if calendar_name in div.text.lower():
                for subDiv in div.find_elements_by_tag_name('div'):
                    if calendar_name in subDiv.text.lower():
                        for chk in subDiv.find_elements_by_tag_name('div'):
                            if calendar_name in chk.text.lower():
                                print(chk.text.lower())
                                return chk

    def selectCalendarDate(self, calendar_name, day, month, year):

        time.sleep(self.timeBwPage)

        div1 = self.find_calendar_div(calendar_name)

        div1.find_element_by_tag_name('button').click()

        time.sleep(self.timeBwPage)

        div2 = self.find_calendar_div(calendar_name)
        div2.find_element_by_tag_name('table').find_element_by_xpath('thead/tr[1]/th[2]/button').click()

        time.sleep(self.timeBwPage)

        div3 = self.find_calendar_div(calendar_name)
        from_th_list = div3.find_element_by_tag_name('table').find_element_by_tag_name(
            'thead').find_element_by_tag_name('tr').find_elements_by_tag_name('th')

        time.sleep(self.timeBwPage)

        while True:
            time.sleep(self.timeBwPage)
            year_text = from_th_list[1].text
            print(year_text)

            if int(year) > int(year_text):
                from_th_list[2].find_element_by_tag_name('button').click()
            elif int(year) < int(year_text):
                from_th_list[0].find_element_by_tag_name('button').click()
            elif year == year_text:
                self.logStatus('info', f'year {year} selected', self.takeScreenshot())
                break

        time.sleep(self.timeBwPage)

        div4 = self.find_calendar_div(calendar_name)
        month_table = div4.find_element_by_tag_name('table')

        from_month_S = 0
        time.sleep(self.timeBwPage)

        for row1 in month_table.find_element_by_tag_name("tbody").find_elements_by_tag_name("tr"):
            for td1 in row1.find_elements_by_tag_name("td"):
                if month.lower() in td1.text.lower() and td1.find_element_by_tag_name("button").is_enabled():
                    print(month)
                    from_month_S = 1
                    self.logStatus('info', f'month {td1.text} selected', self.takeScreenshot())
                    td1.click()

                    break

            if from_month_S == 1:
                print("from_month_S3", from_month_S)
                break

        time.sleep(self.timeBwPage)
        div5 = self.find_calendar_div(calendar_name)
        date_table = div5.find_element_by_tag_name('table')
        time.sleep(self.timeBwPage)
        date_list = []
        start_date = 0
        for row1 in date_table.find_element_by_tag_name("tbody").find_elements_by_tag_name("tr"):
            for td1 in row1.find_elements_by_tag_name("td"):
                try:
                    if not start_date and td1.text == '01':
                        start_date = 1

                    elif start_date and td1.text == '01':
                        start_date = 0

                    if td1.get_attribute('aria-disabled') == 'false' and start_date:
                        date_list.append(td1)
                        # print(td1.text)

                except:
                    pass

        status = 0

        for i in date_list:

            if int(i.text) - int(day) > 1:
                day = i.text
            elif int(day) < int(i.text):
                day = str((int(day)) + 1)

            if day in i.text:
                self.logStatus('info', f'day {i.text} selected', self.takeScreenshot())
                i.click()
                status = 1

                break

        time.sleep(self.timeBwPage)

        return status

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        for ul1 in self.driver.find_element_by_xpath(self.nav_bar_xp).find_elements_by_tag_name("li"):
            time.sleep(1)
            if ul1.text == "My Accounts":
                ul1.click()
                break

        self.logStatus("info", "My Accounts selected", self.takeScreenshot())

        for li1 in ul1.find_element_by_tag_name("ul").find_elements_by_tag_name("li"):
            time.sleep(1)
            if li1.text == "Account Statement":
                li1.click()
                break

        self.logStatus("info", "Account Statement selected", self.takeScreenshot())

        self.check_exists_by_xpath(self.account_type_xp)

        acc_type_Select = Select(self.driver.find_element_by_xpath(self.account_type_xp))  # add wait

        acc_type_Select.select_by_visible_text("Savings Account")

        self.logStatus("info", "Saving Account selected", self.takeScreenshot())

        acc_select = Select(self.driver.find_element_by_xpath(self.account_list_xp))
        acc_status = 0
        for i in acc_select.options:
            if accountno in i.text:
                acc_select.select_by_visible_text(i.text)
                acc_status = 1
                self.logStatus("info", "Account number selected", self.takeScreenshot())

                break

        if acc_status == 0:
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}
        else:
            time.sleep(self.timeBwPage)
            self.driver.find_element_by_xpath(self.date_range_xp).click()

            self.logStatus("info", "Date Range Selected", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            if len(fromdate) == 7 and len(todate) == 7:
                tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
                fromdate = '01' + "-" + fromdate
                todate = str(tdy) + "-" + todate
            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')

            if todate.date() >= datetime.now().date():
                todate = datetime.now() - timedelta(days=1)

            f_year = str(fromdate.year)
            f_day = str(fromdate.day)
            f_month = fromdate.strftime("%B").upper()

            t_year = str(todate.year)
            t_day = str(todate.day)
            t_month = todate.strftime("%B").upper()

            self.logStatus("info", "From Date calendar Selecting", self.takeScreenshot())
            self.selectCalendarDate('from date', f_day, f_month, f_year)

            self.logStatus("info", "To Date calendar Selecting", self.takeScreenshot())
            self.selectCalendarDate('to date', t_day, t_month, t_year)

            self.driver.find_element_by_xpath(
                "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[4]/button[1]").click()

            self.logStatus("info", "search Selected", self.takeScreenshot())

            if self.check_exists_by_xpath("/html/body/div[1]/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div[2]/strong"):
                if 'No records' in self.driver.find_element_by_xpath(
                        "/html/body/div[1]/div[2]/div[2]/div/div/div[2]/div[2]/div[1]/div[2]/strong").text:
                    self.logStatus("info", "data not exist", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

            else:

                self.driver.find_element_by_xpath(
                    "/html/body/div[1]/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div[4]/button").click()

                self.logStatus("info", "statement downloaded", self.takeScreenshot())

                time.sleep(5)
                self.saving_pdf()
                time.sleep(5)

                return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed"}

    def logout(self):
        try:
            self.driver.find_element_by_xpath("/html/body/div[1]/div[1]/div/div/div[3]/ul/button").click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except Exception as e:
            print(f'logout error : {e}')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull", {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#
#     account_no = "201050523422"
#     username   = "sonusonkar01"
#     password   = "Welcome@123"
#
#
#     obj=SSFBScrapper('Suryoday_Small_Finance_test')
#     opstr=obj.login(username,password,"","")
#     if opstr["responseCode"]=='SRC001':
#         res=obj.downloadData('01-01-2020','30-06-2021',account_no,"","")
#
#         print(res)
#         a,b=obj.logout()
#         obj.closeDriver()