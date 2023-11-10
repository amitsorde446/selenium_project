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
from tessrct import fbcaptcha
from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


# from tessrct import fccaptcha

class FINCAREScrapper:

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
        self.dwnldDir = os.path.join(os.getcwd(), "downloads/" + self.ref_id)
        self.makeDriverDirs('dwn')
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage

        self.netbanking_url = "https://ib.fincarebank.com/RIB/#/"

        self.username_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[3]/div[2]/input"

        self.login_continue_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[5]/div/button"

        self.phrase_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[6]/div[1]/div/label"

        self.password_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[4]/div[2]/div[1]/input[3]"

        self.login_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[7]/div/button/span"

        self.my_accounts_xp = "/html/body/div[1]/div[2]/div[1]/div/div/div/ul/li[3]/a"

        self.account_statement_xp = '/html/body/div[1]/div[2]/div[1]/div/div/div/ul/li[3]/ul/li[5]/a'

        self.date_range_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[1]/label/input"

        self.from_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/span/button"

        self.from_table_xp = '/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/ul/li[1]/div/table'

        self.from_month_year_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/ul/li[1]/div/table/thead/tr[1]/th[2]/button"

        self.to_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/span/button"

        self.to_table_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/ul/li[1]/div/table"

        self.to_month_year_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/ul/li[1]/div/table/thead/tr[1]/th[2]/button"

        self.submit_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/form/div[5]/button[1]"
        self.download_xp = "/html/body/div[1]/div[2]/div[2]/div/div/div[2]/div[2]/div[2]/div[4]/button"
        self.logout_xp = "/html/body/div[1]/div[1]/div/div/div[2]/ul/li[5]/a"

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
                # driver.maximize_window()
            else:
                driver = webdriver.Chrome('/usr/local/bin/chromedriver',
                                          chrome_options=self.chromeOptions)  # , chrome_options=self.chromeOptions
                # driver.maximize_window()

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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'FC', self.env,
                                 screenshot, self.ipadd)
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
            self.logStatus("info", "pdf uploaded")
        if len(d_lt) > 0:
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

    def login(self, username, password, seml, smno):

        try:
            self.driver.get(self.netbanking_url)
            time.sleep(5)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        username_input = self.driver.find_element_by_xpath(self.username_xp)
        username_input.clear()
        username_input.send_keys(username)
        self.driver.find_element_by_xpath(self.login_continue_xp).click()

        self.logStatus("info", "username entered", self.takeScreenshot())

        password_input = self.driver.find_element_by_xpath(self.password_xp)
        password_input.clear()
        password_input.send_keys(password)

        self.logStatus("info", "password entered", self.takeScreenshot())

        # self.driver.find_element_by_xpath(
        #     """/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[6]/div[1]/div/label""").click()
        try:
            self.driver.find_element_by_xpath(
                """/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[6]/div[1]/div/label""").click()
            self.logStatus("info", "phrase ticked", self.takeScreenshot())
        except:
            print("checkbox  not exist")
            self.logStatus("info", "no checkbox", self.takeScreenshot())
        # try:
        #     # self.driver.find_element_by_xpath("""//*[@id="txtCaptcha"]""").screenshot("captcha.png")
        #     # self.driver.find_element_by_xpath("""/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[6]/div[2]/input""").send_keys(fccaptcha())
        #     self.driver.find_element_by_id("btnSignIn").click()
        #     self.logStatus("info", "login  clicked", self.takeScreenshot())
        #     try:
        #         if "Invalid User ID or Password" in self.driver.find_element_by_xpath(
        #                 "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[2]").text:
        #             print("incorrect details")
        #             self.logStatus("error", "invalid username or password", self.takeScreenshot())
        #             return {"referenceId": self.ref_id, "responseCode": "EWC002",
        #                     "responseMsg": "Incorrect UserName Or Password."}
        #     except:
        #         print("correct details")
        # except:

        self.driver.find_element_by_id("btnSignIn").click()
        self.logStatus("info", "login  clicked", self.takeScreenshot())

        try:
            if "Invalid User ID or Password" in self.driver.find_element_by_xpath(
                    "/html/body/div[1]/div[2]/div[2]/div/div/div[1]/div[2]/div/div[2]").text:
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
                if month in td1.text and td1.find_element_by_tag_name("button").is_enabled():
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

    def selectSavings(self, accountno):

        self.driver.find_element_by_xpath(self.my_accounts_xp).click()
        time.sleep(self.timeBwPage)
        self.driver.find_element_by_xpath(self.account_statement_xp).click()
        time.sleep(self.timeBwPage)
        selecteAccType = self.driver.find_element_by_name('accountType')
        accType = Select(selecteAccType)
        time.sleep(self.timeBwPage)
        typeOption = selecteAccType.find_elements_by_tag_name('option')

        for typ in typeOption:

            if 'saving' in typ.text.lower():
                print(typ.text)
                type1 = typ.get_attribute('value')
                accType.select_by_value(type1)
                self.logStatus('info', f'saving account option selected', self.takeScreenshot())
                break

        time.sleep(self.timeBwPage)

        selectelem = self.driver.find_element_by_name('account')
        bankacc = Select(selectelem)

        bankaccopt = selectelem.find_elements_by_tag_name('option')

        acc = ''
        for accno in bankaccopt:
            if accountno in accno.text:
                acc = accno.get_attribute('value')
                bankacc.select_by_value(acc)
                self.logStatus('info', f'Account found', self.takeScreenshot())
                break

        time.sleep(self.timeBwPage)

        return acc

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        self.logStatus("info", "going to accounts page", self.takeScreenshot())

        acc = self.selectSavings(accountno)

        if acc == '':
            print('Account number doesnot match')
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
            if todate.year >= datetime.now().year and todate.month >= datetime.now().month:
                todate = datetime.now() - timedelta(days=1)

            time.sleep(self.timeBwPage)

            fd = fromdate
            td = todate

            time.sleep(self.timeBwPage)
            print(f'{fd} , {td}')

            f_year = str(fd.year)
            f_day = str(fd.day)
            f_month = fd.strftime("%B").upper()

            t_year = str(td.year)
            t_day = str(td.day)
            t_month = td.strftime("%B").upper()

            for opt in self.driver.find_elements_by_tag_name('label'):
                if "date range" in opt.text:
                    opt.click()
                    break

            self.logStatus("info", "date range option clicked", self.takeScreenshot())
            # self.driver.find_element_by_xpath(self.date_range_xp).click()
            time.sleep(self.timeBwPage)

            self.logStatus("info", "selecting from date calendar", self.takeScreenshot())
            from_status = self.selectCalendarDate('from date', f_day, f_month, f_year)
            time.sleep(self.timeBwPage)

            self.logStatus("info", "selecting to date calendar", self.takeScreenshot())
            to_status = self.selectCalendarDate('to date', t_day,
                                                t_month, t_year)
            time.sleep(self.timeBwPage)

            if from_status == 1 and to_status == 1:
                self.date_status = "exist"

                for btn in self.driver.find_elements_by_tag_name('button'):
                    if 'submit' in btn.text.lower():
                        btn.click()

                time.sleep(self.timeBwPage)

                if 'No records found' in self.driver.find_element_by_tag_name("body").text:
                    print('no records')

                else:

                    for btn in self.driver.find_elements_by_tag_name('button'):
                        if 'download' in btn.text.lower():
                            btn.click()

                    time.sleep(10)
                    d_lt = os.listdir(self.dwnldDir)
                    shutil.move(self.dwnldDir + "/" + d_lt[0],
                                self.pdfDir + "/" + str(fd)[:10] + "-" + str(td)[:10] + '.pdf')
                    self.logStatus("info", "pdf download button clicked", self.takeScreenshot())

        dic1 = self.saving_pdf()

        return dic1

    def logout(self):

        try:
            self.driver.find_element_by_xpath(self.logout_xp).click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except:
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
#     account_no = "20100000815080"
#     username   = "lokeshyadav"
#     password   = "Scoreme@12345"
#     obj=FINCAREScrapper('FINCARE_test')
#     opstr=obj.login(username,password,"","")
#     if opstr["responseCode"]=='SRC001':
#         res=obj.downloadData('01-01-2020','09-06-2021',account_no,"","")
#         a,b=obj.logout()
#         obj.closeDriver()