import os
import shutil
import time
from webdriver_manager.chrome import ChromeDriverManager
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


class BBScrapper:

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
        self.url = 'https://bandhanbankonline.com/netbanking/#/'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 10)

        self.from_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/span/button"
        self.from_table_xp = '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/ul/li[1]/div/table'
        self.from_month_year_xp = "/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[2]/div[2]/div/ul/li[1]/div/table/thead/tr[1]/th[2]/button"

        self.to_calendar_xp = "/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/span/button"
        self.to_table_xp = "/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/ul/li[1]/div/table"
        self.to_month_year_xp = "/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[3]/div[2]/div/ul/li[1]/div/table/thead/tr[1]/th[2]/button"

        self.date_status = "notExist"

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
                driver = webdriver.Chrome(ChromeDriverManager().install(),chrome_options=self.chromeOptions)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'BB', self.env,
                                 screenshot, self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        print("-----------",sname)
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName) , self.ref_id +'/screenshots/' + str(sname))
        return sname

    def saving_pdf(self):
        d_lt = os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname),self.ref_id + "/" +"automated_pdf_files/" +i)
        if len(d_lt) > 0:
            self.logStatus("info", "file downloaded")
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
            self.logStatus("info", "no file downloaded")
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

    def login(self, username, password, seml, smno):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[3]/div[1]/button')

        self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[3]/div[1]/button').click()
        time.sleep(self.timeBwPage)

        if self.check_exists_by_name('username'):
            usernameInputField = self.driver.find_element_by_name('username')
            usernameInputField.clear()
            usernameInputField.send_keys(username)

            self.logStatus("info", "username entered", self.takeScreenshot())

        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[4]/div/button')

        self.driver.find_element_by_xpath(
            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[4]/div/button').click()
        time.sleep(self.timeBwPage)

        if self.check_exists_by_name('password'):
            passwordInputField = self.driver.find_element_by_name('password')
            passwordInputField.clear()
            passwordInputField.send_keys(password)

            self.logStatus("info", "password entered", self.takeScreenshot())

        if self.check_exists_by_id('isSecChecked'):
            self.driver.find_element_by_id('isSecChecked').click()
            self.logStatus("info", "secure image clicked", self.takeScreenshot())

        if self.check_exists_by_xpath(
                '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[6]/div/button'):
            self.driver.find_element_by_xpath(
                '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[6]/div/button').click()

        elif self.check_exists_by_xpath(
                '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[5]/div/button'):
            self.driver.find_element_by_xpath(
                '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[5]/div/button').click()

        self.logStatus("info", "second submit button clicked", self.takeScreenshot())

        if self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[2]/div/span'):
            if 'Invalid' in self.driver.find_element_by_xpath(
                    '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div/div/div/div/div[2]/div/span').text:
                print("invalid credentials")
                self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}

        self.logStatus("info", "login successfull", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def selectCalendarDate(self, calendar_xp, table_xp, month_year_xp, day, month, year):

        self.driver.find_element_by_xpath(calendar_xp).click()

        self.driver.find_element_by_xpath(month_year_xp).click()

        from_th_list = self.driver.find_element_by_xpath(table_xp).find_element_by_tag_name(
            'thead').find_element_by_tag_name('tr').find_elements_by_tag_name('th')

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
        month_table = self.driver.find_element_by_xpath(table_xp)
        from_month_S = 0

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
        date_table = self.driver.find_element_by_xpath(table_xp)

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

        return status

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        time.sleep(self.timeBwPage)

        self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[1]/div/div/div/ul')

        for opt in self.driver.find_element_by_xpath(
                '/html/body/div[1]/div[2]/div[1]/div/div/div/ul').find_elements_by_tag_name('li'):
            if 'account' in opt.text.lower():
                opt.click()
                time.sleep(self.timeBwPage)
                for url in opt.find_elements_by_tag_name('a'):
                    if 'statement' in url.text.lower():
                        print(url.text)
                        url.click()
                        break

        time.sleep(self.timeBwPage)

        self.check_exists_by_xpath(
            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/select')

        account_type = Select(self.driver.find_element_by_xpath(
            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/select'))

        account_type.select_by_visible_text('Savings Account')
        self.logStatus("info", "select option saving account", self.takeScreenshot())

        accountselctor = Select(self.driver.find_element_by_xpath(
            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[1]/div[2]/div[2]/div/select'))
        self.logStatus("info", "select account number", self.takeScreenshot())

        acc_exist = False
        for acc in list(map(lambda x: x.text, accountselctor.options)):
            if accountno in acc:
                acc_exist = True
                accountselctor.select_by_visible_text(acc)

        if acc_exist == False:
            print("no account found")
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}


        else:
            self.logStatus("info", "account number found", self.takeScreenshot())

            self.driver.find_element_by_xpath(
                '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[3]/div[1]/label/input').click()

            self.logStatus('info', 'date range option clicked', self.takeScreenshot())

            if len(fromdate) == 7 and len(todate) == 7:
                tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
                fromdate = '01' + "-" + fromdate
                todate = str(tdy) + "-" + todate

            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')

            from dateutil.relativedelta import relativedelta

            six_months = datetime.now() + relativedelta(months=-6)

            if todate <= six_months:
                self.logStatus('info',
                               'data is not available cause bank provide only last six months of data in date range')
            else:
                self.logStatus('info', 'data is available')

                if todate > datetime.now():
                    todate = datetime.now()

                if fromdate < six_months:
                    fromdate = six_months

                f_year = str(fromdate.year)
                f_day = str(fromdate.day)
                f_month = fromdate.strftime("%B").upper()

                t_year = str(todate.year)
                t_day = str(todate.day)
                t_month = todate.strftime("%B").upper()

                self.logStatus("info", "selecting from date calendar", self.takeScreenshot())
                from_status = self.selectCalendarDate(self.from_calendar_xp, self.from_table_xp,
                                                      self.from_month_year_xp, f_day, f_month, f_year)
                time.sleep(self.timeBwPage)

                self.logStatus("info", "selecting to date calendar", self.takeScreenshot())
                to_status = self.selectCalendarDate(self.to_calendar_xp, self.to_table_xp, self.to_month_year_xp, t_day,
                                                    t_month, t_year)
                time.sleep(self.timeBwPage)

                if from_status == 1 and to_status == 1:
                    self.date_status = "exist"

                    self.driver.find_element_by_xpath(
                        '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div[2]/form/div[4]/button[1]').click()

                    time.sleep(10)

                    if 'No records found' in self.driver.find_element_by_xpath(
                            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[2]/div[2]/div[1]/div[2]').text:
                        print("no statement")
                        self.logStatus("info", "no record found", self.takeScreenshot())
                    else:
                        self.driver.find_element_by_xpath(
                            '/html/body/div[1]/div[2]/div[2]/div[1]/div/div/div[2]/div[2]/div[2]/div[4]/button').click()
                        self.logStatus("info", "record found click download as pd", self.takeScreenshot())

                        time.sleep(10)

                        d_lt = os.listdir(self.dwnldDir)
                        shutil.move(self.dwnldDir + "/" + d_lt[0],
                                    self.pdfDir + "/" + str(fromdate)[:10] + "-" + str(todate)[:10] + '.pdf')

        dic = self.saving_pdf()

        return dic

    def logout(self):
        time.sleep(self.timeBwPage)
        self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div/div/div[2]/ul/li[2]/span/a/span[2]').click()
        time.sleep(self.timeBwPage)
        self.driver.find_element_by_xpath(
            '/html/body/div[1]/div[1]/div/div/div[2]/ul/li[2]/span/ul/li[2]/a/span[2]').click()
        self.logStatus("info", "logout successful", self.takeScreenshot())
        return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                               "responseMsg": "Successfully Completed."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     # Refid=str(uuid.uuid1())
#     # print(f'RefID : {Refid}')

#     username = "raju0705"
#     password = "Raju@1985"
#     accountno = "52210008585949"
#     obj=BBScrapper('bandhan_test8')
#     opstr=obj.login(username,password,'','')


#     print(opstr)
#     res=obj.downloadData('11-02-2021','11-08-2021',accountno,'','')

#     a,b=obj.logout()
#     obj.closeDriver()
