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

from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from tessrct import esfbcaptcha
import pytz



class ESFBScrapper:

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
        self.xcx = 0
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url = 'https://inet.equitasbank.com/EquitasConsumerApp/'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 20)

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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'esfb', self.env,
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

        if self.check_exists_by_id('popup_container'):
            contnr = self.driver.find_element_by_id('popup_container')
            putxt = contnr.find_element_by_id('popup_content')
            print(putxt.text)
            contnr.find_element_by_id('popup_ok').click()

        time.sleep(20)

        while 1:

            if self.check_exists_by_xpath(
                    '/html/body/div[2]/div[2]/div/div/div[2]/div/div/div/div[3]/div/div[2]/div[2]/div/div[2]/div/div[1]/div/div/ul/li[2]/div/input'):
                usernameInputField = self.driver.find_element_by_xpath(
                    '/html/body/div[2]/div[2]/div/div/div[2]/div/div/div/div[3]/div/div[2]/div[2]/div/div[2]/div/div[1]/div/div/ul/li[2]/div/input')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}

            PasswordField = self.driver.find_element_by_xpath(
                '/html/body/div[2]/div[2]/div/div/div[2]/div/div/div/div[3]/div/div[2]/div[2]/div/div[2]/div/div[2]/div/div[1]/ul/li[2]/div/input')
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            self.driver.save_screenshot("screenshot.png")
            logincptch = self.driver.find_element_by_xpath(
                '/html/body/div[2]/div[2]/div/div/div[2]/div/div/div/div[3]/div/div[2]/div[2]/div/div[2]/div/div[3]/div/div/div[3]/div/ul/li[2]/div/input')
            logincptch.clear()

            time.sleep(10)

            logincptch.send_keys(esfbcaptcha())

            self.logStatus("info", "captcha entered", self.takeScreenshot())

            lgnbtn = self.driver.find_element_by_id('login')
            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            if self.check_exists_by_id('popup_container'):
                contnr = self.driver.find_element_by_id('popup_container')
                putxt = contnr.find_element_by_id('popup_content')
                print(putxt.text)
                if "Enter your UserID" in putxt.text:
                    contnr.find_element_by_id('popup_ok').click()
                elif ("Invalid User ID or Password" in putxt.text) or ('Invalid UserId or Password' in putxt.text):
                    print('User ID or Password invalid')
                    self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                    contnr.find_element_by_id('popup_ok').click()
                    return {"referenceId": self.ref_id, "responseCode": "EWC002",
                            "responseMsg": "Incorrect UserName Or Password."}
                elif 'Please enter the correct captcha' in putxt.text:
                    self.logStatus("debug", "incorrect captcha", self.takeScreenshot())
                    contnr.find_element_by_id('popup_ok').click()
                # elif 'Enjoy unlimited A/c Balance & more features by converting Self’E a/c to full fledge digital a/c. Kindly contact nearest branch or call customer care' in putxt.text:
                #     contnr.find_element_by_id('popup_ok').click()
                #     break
                else:
                    break
            else:
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def calenderSelector(self, day, month, year):

        if self.check_exists_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[1]/div/div[2]/span'):
            self.driver.find_element_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[1]/div/div[2]/span').click()
            time.sleep(1)

            yrtable = self.driver.find_element_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div[3]/div/div[2]/div')
            yrrows = yrtable.find_elements_by_tag_name('div')
            yrlst = list(map(lambda x: x.text, yrrows))

            if str(year) in ' '.join(yrlst):
                selected = False
                for i in yrrows:
                    cols = i.find_elements_by_tag_name('div')
                    for j in cols:
                        if str(j.text) == str(year):
                            j.click()
                            selected = True
                            break
                    if selected == True:
                        selected = False
                        break

        if self.check_exists_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[1]/div/div[1]/div[2]/span'):
            self.driver.find_element_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[1]/div/div[1]/div[2]/span').click()
            time.sleep(1)

            mnthtable = self.driver.find_element_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div[2]/div/div[2]/div')
            mnthrows = mnthtable.find_elements_by_tag_name('div')
            mnthlst = list(map(lambda x: x.text, mnthrows))

            selected = False
            for i in mnthrows:
                cols = i.find_elements_by_tag_name('div')
                for j in cols:
                    if str(j.text) == str(month):
                        j.click()
                        selected = True
                        break
                if selected == True:
                    selected = False
                    break

            dytable = self.driver.find_element_by_xpath(
                '/html/body/div[6]/div/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div[1]/div[2]/div[2]/div[2]/div[1]')
            dyrows = dytable.find_elements_by_class_name('dw-cal-row')
            dylst = list(map(lambda x: x.text, dyrows))

            selected, start = False, False
            for i in dyrows:
                cols = i.find_elements_by_tag_name('div')
                for j in cols:
                    if str(j.text) == '1' and start == False:
                        start = True
                    if str(j.text) == str(day) and start == True:
                        j.click()
                        selected = True
                        break
                if selected == True:
                    selected = False
                    break

    def downloadData(self, fromdate, todate, accountno, seml, smno):
        time.sleep(10)

        if self.check_exists_by_id('popup_cancel'):
            self.driver.find_element_by_id('popup_cancel').click()

        time.sleep(self.timeBwPage)

        if self.check_exists_by_xpath('/html/body/div[3]/div[2]/div[1]'):
            self.driver.find_element_by_xpath('/html/body/div[3]/div[2]/div[1]').click()

        if self.check_exists_by_id('element_button_12'):
            self.driver.find_element_by_id('element_button_12').click()

        self.logStatus("info", "go to bank statement page", self.takeScreenshot())

        time.sleep(20)

        try:
            if self.check_exists_by_xpath(
                    '/html/body/div[2]/div[2]/div/div[2]/div[3]/div/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div[1]/div/ul/li[2]/a'):
                self.driver.find_element_by_xpath(
                    '/html/body/div[2]/div[2]/div/div[2]/div[3]/div/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div[1]/div/ul/li[2]/a').click()
        except:
            time.sleep(10)
            if self.check_exists_by_xpath(
                    '/html/body/div[2]/div[2]/div/div[2]/div[3]/div/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div[1]/div/ul/li[2]/a'):
                self.driver.find_element_by_xpath(
                    '/html/body/div[2]/div[2]/div/div[2]/div[3]/div/div[2]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div[1]/div/ul/li[2]/a').click()

        self.logStatus("info", "advanced search option selected", self.takeScreenshot())

        if self.check_exists_by_id('element_button_7'):
            self.driver.find_element_by_id('element_button_7').click()

        accountselctor = self.driver.find_element_by_id('fgp_acclistthree_main')
        accountselctorlst = accountselctor.find_element_by_id('fgp_acclistthree_ul')
        accountlst = accountselctorlst.find_elements_by_tag_name('li')
        print(list(map(lambda x: x.text, accountlst)))

        accfound = ''
        for acc in accountlst:
            if accountno in acc.text:
                accfound = 'Done'
                acc.click()
                self.logStatus("info", "Account selected", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        if accfound != '':

            if len(fromdate) == 7 and len(todate) == 7:
                tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
                fromdate = '01' + "-" + fromdate
                todate = str(tdy) + "-" + todate

            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')

            curr_year = datetime.now().year

            if fromdate.year < curr_year - 1:
                fromdate = fromdate.replace(day=1, month=1, year=curr_year - 1)

            if fromdate >= todate:
                todate = todate.replace(day=7)

            if todate.year >= datetime.now().year and todate.month >= datetime.now().month:
                todate = datetime.now() - timedelta(days=1)

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

            flcount = 1
            for dts in dt_lst:
                fd = datetime.strptime(dts[0], '%Y-%m-%d')
                td = datetime.strptime(dts[1], '%Y-%m-%d')
                print(f'FROM DATE : {fd}')
                print(f'TO DATE : {td}')

                fday = str(fd.day)
                fmonth = fd.strftime('%b')
                fyear = str(fd.year)
                tday = str(td.day)
                tmonth = td.strftime('%b')
                tyear = str(td.year)

                # TO DATE SET

                self.driver.find_element_by_id('enddatethree_btn').click()
                time.sleep(2)
                self.calenderSelector(tday, tmonth, tyear)
                self.logStatus("info", "to date set", self.takeScreenshot())

                # FROM DATE SET

                self.driver.find_element_by_id('startdatethree_btn').click()
                time.sleep(2)
                self.calenderSelector(fday, fmonth, fyear)
                self.logStatus("info", "from date set", self.takeScreenshot())

                self.driver.find_element_by_id('element_button_12').click()

                if self.check_exists_by_id('popup_container'):
                    contnr = self.driver.find_element_by_id('popup_container')
                    putxt = contnr.find_element_by_id('popup_content')
                    print(putxt.text)
                    if "Periodic Statement will be downloaded shortly. Use your customer ID to open the statement" in putxt.text:
                        contnr.find_element_by_id('popup_ok').click()

                if self.check_exists_by_id('popup_container'):
                    contnr = self.driver.find_element_by_id('popup_container')
                    putxt = contnr.find_element_by_id('popup_content')
                    print(putxt.text)
                    if "No transaction found in specified period" in putxt.text:
                        contnr.find_element_by_id('popup_ok').click()
                    elif "Account statemnt generation failed" in putxt.text:
                        self.logStatus("info", "Account statement generation failed", self.takeScreenshot())
                        contnr.find_element_by_id('popup_ok').click()
                else:
                    time.sleep(5)
                    d_lt = os.listdir(self.pdfDir)
                    for fl in d_lt:
                        if len(fl[:-4]) > 2:
                            os.rename(os.path.join(self.pdfDir, fl), os.path.join(self.pdfDir, str(flcount) + '.pdf'))
                            flcount += 1

                time.sleep(self.timeBwPage)

            dic = self.saving_pdf()
            self.driver.find_element_by_id('element_button_9').click()
            return dic
        else:
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

    def logout(self):
        print("asassa")
        if self.check_exists_by_id('element_text_13'):
            print("asassa")
            self.driver.find_element_by_id('element_text_13').click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            print("asassa")
            if self.check_exists_by_id('element_button_33'):
                self.driver.find_element_by_id('element_button_33').click()
                time.sleep(3)
                #self.driver.find_element_by_id('element_text_12').click()
            if self.check_exists_by_id('popup_container'):
                contnr = self.driver.find_element_by_id('popup_container')
                putxt = contnr.find_element_by_id('popup_content')
                self.logStatus("error", "pop up opened", self.takeScreenshot())
                if "A valid session does not exist" in putxt.text:
                    contnr.find_element_by_id('popup_ok').click()
                elif "Do you want to logout?" in putxt.text:
                    contnr.find_element_by_id('popup_ok').click()
            try:
                alert = self.driver.switch_to_alert()
                # print(alert.text)
                alert.accept()
                self.driver.switch_to_default_content()
            except Exception as e:
                print(f'Alert box : {e}')
            print("yha")
            return "successfull", {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        else:
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
#     obj=ESFBScrapper('EQUITASSMALLFINANCEBANK')
#     opstr=obj.login('8337989','Ril@12345678','','')
#     print(opstr)
#     res=obj.downloadData('01-01-2020','30-06-2021','100009855941','','')
#     a,b=obj.logout()
#     obj.closeDriver()