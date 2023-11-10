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
from datetime import datetime, timedelta
from data_base import DB
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz
from dateutil.relativedelta import relativedelta


# from webdriver_manager.chrome import ChromeDriverManager


class CITIScrapper:

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
        self.dwnldDir = os.path.join(os.getcwd(), "downloads/" + self.ref_id)
        self.makeDriverDirs('dwn')
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url = 'https://www.online.citibank.co.in/'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 5)

        self.from_calendar = "/html/body/form/table[1]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/table[2]/tbody/tr[2]/td/table/tbody/tr[2]/td/table/tbody/tr/td[3]/div[2]/table/tbody/tr/td[3]/a[1]"
        self.to_calendar = "/html/body/form/table[1]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/table[2]/tbody/tr[2]/td/table/tbody/tr[2]/td/table/tbody/tr/td[3]/div[2]/table/tbody/tr/td[5]/a[1]"
        self.year_text = '/html/body/center/table[1]/tbody/tr[1]/td[2]/span'
        self.month_text = '/html/body/center/table[1]/tbody/tr[3]/td[2]/span'
        self.year_forward = '/html/body/center/table[1]/tbody/tr[1]/td[3]/a'
        self.year_backward = '/html/body/center/table[1]/tbody/tr[1]/td[1]/a'
        self.month_forward = '/html/body/center/table[1]/tbody/tr[3]/td[3]/a'
        self.month_backward = '/html/body/center/table[1]/tbody/tr[3]/td[1]/a'
        self.day_xp = '/html/body/center/table[2]/tbody'

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
                print("--------------------------------------------")
                driver = webdriver.Chrome(ChromeDriverManager().install(),chrome_options=self.chromeOptions)
                # driver.maximize_window()
            else:
                print("---------------------------------------------")
                capa = DesiredCapabilities.CHROME
                capa["pageLoadStrategy"] = "none"
                # from pyvirtualdisplay import Display
                # display = Display(visible=0, size=(1366, 768))
                # display.start()
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions,
                                          desired_capabilities=capa)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'CITI', self.env,
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
            self.uploadToS3(os.path.join(pdfname), self.refid + "/"+"automated_pdf_files/"+ i)
            self.logStatus("info", "pdf uploaded")
        if len(d_lt) > 0:
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
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

        time.sleep(20)
        try:
            self.driver.find_element_by_xpath("""/html/body/div[17]/div/div/img""").click()
            time.sleep(2)
        except:
            pass
        tb = self.driver.find_element_by_xpath("""//*[@id="nav"]/ul[3]/li/a/span[2]""").click()
        time.sleep(5)
        window_before = self.driver.window_handles[0]
        window_after = self.driver.window_handles[1]
        self.driver.switch_to.window(window_after)
        self.driver.find_element_by_xpath("""//*[@id="User_Id"]""").click()
        self.driver.find_element_by_xpath("""//*[@id="User_Id"]""").send_keys(username)

        time.sleep(1)
        self.driver.find_element_by_xpath("""//*[@id="password"]""").send_keys(password)
        self.driver.find_element_by_xpath(
            """//*[@id="main-wrapper"]/div/div[2]/div[2]/div[1]/div/div[2]/div[3]/div/a/div""").click()
        time.sleep(7)
        try:
            unsuccessful = self.driver.find_element_by_xpath(
                """/html/body/form/div/div[2]/div/div/div/div/div[1]""").text
        except:
            unsuccessful = ""
            pass
        print(unsuccessful, " checksuccessful")
        if unsuccessful.find("Sorry! Your login attempt has") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EWC002",
                    "responseMsg": "Incorrect UserName Or Password."}
        if unsuccessful.find("Unable to login.") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        iframe = self.driver.find_element_by_xpath("/html/frameset/frameset/frame")
        self.driver.switch_to.frame(iframe)
        gg = self.driver.find_element_by_xpath("""//*[@id="10"]/a""").click()
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def frame_switch(self, name):
        self.driver.switch_to.frame(self.driver.find_element_by_name(name))

    def select_date(self, day, month, year):

        window_after = self.driver.window_handles[2]
        self.driver.switch_to.window(window_after)

        selected_year = self.driver.find_element_by_xpath(self.year_text).text

        while True:

            if int(selected_year) > int(year):

                self.driver.find_element_by_xpath(self.year_backward).click()

            elif int(selected_year) < int(year):

                self.driver.find_element_by_xpath(self.year_forward).click()

            else:
                break

            selected_year = self.driver.find_element_by_xpath(self.year_text).text

        selected_month = self.driver.find_element_by_xpath(self.month_text).text
        import calendar
        abbr_to_num = {name: num for num, name in enumerate(calendar.month_abbr) if num}

        month_num = abbr_to_num[selected_month[:3]]

        while True:

            if int(month_num) > int(month):

                self.driver.find_element_by_xpath(self.month_backward).click()

            elif int(month_num) < int(month):

                self.driver.find_element_by_xpath(self.month_forward).click()

            else:
                break

            selected_month = self.driver.find_element_by_xpath(self.month_text).text

            month_num = abbr_to_num[selected_month[:3]]

        day_found = 0

        for tr in self.driver.find_elements_by_xpath(self.day_xp):
            if day_found == 1:
                break
            for td in tr.find_elements_by_tag_name('td'):
                try:
                    if int(day) == int(td.text):
                        td.find_element_by_tag_name('a').click()
                        day_found = 1
                        break
                except:
                    pass

    def downloadData(self, fromdate, todate, accountno, seml, smno):

        self.driver.switch_to.default_content()

        window_after = self.driver.window_handles[1]
        self.driver.switch_to.window(window_after)

        time.sleep(2)

        self.frame_switch('leftmenu')

        leftOption = self.driver.find_element_by_xpath(
            "/html/body/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr/td[1]/div[1]/table/tbody/tr[2]/td[2]/ul")

        for li in leftOption.find_elements_by_tag_name('li'):

            if "view account summary" in li.text.lower():
                li.find_element_by_tag_name('a').click()

        time.sleep(2)

        fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
        todate = datetime.strptime(todate, '%d-%m-%Y')

        from_range = datetime.now() - relativedelta(years=2) + timedelta(days=2)

        if fromdate < from_range:
            fromdate = from_range

        dt_lst = []
        date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'), end=todate.strftime('%m-%d-%Y'),
                                  freq=pd.DateOffset(years=1), closed=None).to_list()
        for ind1 in range(len(date_list)):
            if ind1 > 0:
                st = date_list[ind1 - 1]
                ed = date_list[ind1] - timedelta(days=1)
                dt_lst.append([str(st)[:10], str(ed)[:10]])
        if len(dt_lst) > 0 and todate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
            st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
            ed = todate
            dt_lst.append([str(st)[:10], str(ed)[:10]])
        elif len(dt_lst) == 0:
            dt_lst.append([fromdate.strftime('%Y-%m-%d'), todate.strftime('%Y-%m-%d')])

        self.driver.switch_to.default_content()

        for dts in dt_lst:

            fd = datetime.strptime(dts[0], '%Y-%m-%d')
            td = datetime.strptime(dts[1], '%Y-%m-%d')

            time.sleep(5)

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)

            self.frame_switch('content1')

            self.driver.find_element_by_xpath(
                '/html/body/form/div[2]/table/tbody/tr/td[1]/table/tbody/tr[2]/td[2]/table/tbody/tr[3]/td/div/div[1]/a/img').click()
            time.sleep(2)
            self.driver.find_element_by_xpath(
                '/html/body/form/div[2]/table/tbody/tr/td[1]/table/tbody/tr[2]/td[2]/table/tbody/tr[3]/td/div/div[2]/table/tbody/tr[2]/td[1]/a').click()
            time.sleep(2)

            self.driver.switch_to.default_content()

            time.sleep(5)

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)

            self.frame_switch('content1')

            select = Select(self.driver.find_element_by_id("select3"))

            select.select_by_visible_text("Date Range")

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)

            time.sleep(2)

            self.frame_switch('content1')

            self.driver.find_element_by_xpath(self.from_calendar).click()
            time.sleep(2)

            self.select_date(fd.day, fd.month, fd.year)

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)

            time.sleep(2)

            self.frame_switch('content1')

            self.driver.find_element_by_xpath(self.to_calendar).click()
            time.sleep(2)
            self.select_date(td.day, td.month, td.year)

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)
            time.sleep(2)
            self.frame_switch('content1')

            self.driver.find_element_by_xpath(
                '/html/body/form/table[1]/tbody/tr/td/table/tbody/tr[2]/td/table/tbody/tr[3]/td/table[2]/tbody/tr[2]/td/table/tbody/tr[2]/td/table/tbody/tr/td[3]/div[2]/table/tbody/tr/td[6]/a').click()
            time.sleep(5)

            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)
            time.sleep(2)
            self.frame_switch('content1')

            if self.check_exists_by_id('control0'):

                if 'Sorry! Your to date is less than account open date.' == self.driver.find_element_by_id(
                        'control0').text:
                    print('Sorry! Your to date is less than account open date.')

                    self.driver.find_element_by_id('acontrol0').click()
                    time.sleep(2)

            else:

                select = Select(self.driver.find_element_by_id("select2"))
                select.select_by_visible_text("PDF file")

                self.driver.find_element_by_xpath("//*[contains(text(), 'OK')]").click()

                time.sleep(5)

                self.driver.switch_to.window(self.driver.window_handles[2])

                self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[5]/td/a').click()

                try:
                    d_lt = os.listdir(self.dwnldDir)
                    shutil.move(self.dwnldDir + "/" + d_lt[0],
                                self.pdfDir + "/" + str(fd)[:10] + "-" + str(td)[:10] + '.pdf')
                except Exception as e:
                    window_after = self.driver.window_handles[1]
                    self.driver.switch_to.window(window_after)
                    self.frame_switch('content1')
                    if 'Service Unavailable' in self.driver.find_element_by_xpath("/html/body").text:
                        return {"referenceId": self.ref_id, "responseCode": "END013",
                                "responseMsg": "No Data Available"}

                # self.driver.switch_to.window(self.driver.window_handles[2])

                # self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[5]/td/a').click()

        dic = self.saving_pdf()

        return dic

    def logout(self):
        try:
            window_after = self.driver.window_handles[1]
            self.driver.switch_to.window(window_after)

            self.frame_switch('CBOL')

            self.driver.find_element_by_xpath(
                '/html/body/form[1]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr/td[2]/a').click()

            return {"referenceId": self.ref_id, "responseCode": "SRC001",
                    "responseMsg": "Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EWC002",
                    "responseMsg": "Incorrect UserName Or Password."}

    def closeDriver(self):
        # time.sleep(self.timeBwPage)
        # shutil.rmtree(self.pdfDir)
        # shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
# obj=CITIScrapper('citi_bank_5')
# opstr=obj.login(username = 'JPGRIL',password='Jyoti@981021')
# print(opstr, " opstr")
# if opstr['responseMsg']=='Successfully Completed.':
#     res=obj.downloadData('09-01-2018','09-08-2021','','','')
# print(res)
# b=obj.logout()

# obj.closeDriver()
