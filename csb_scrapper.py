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

from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from tessrct import csbcaptcha
import pytz


class CSBScrapper:

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
        self.url = 'https://www.csbnet.co.in/netbanking.aspx?ivrfyparams=72775667nirn73241729000000000000iBank900(HomeLoginFrm)rnirnrvgseocxkajmdlwswhrirecuq@@@yggldukouglenwsinxqfwdlattgpju@@@mslceivmhexxieknjkyyeflosvtgqi@@@oueytsslrjlaqmgxthogkvqkqhhvih@@@npvxpdtikruwromdoxhtbmqkxrdthm@@@kvdjvvervdelvvkmdbwnriongbxlaw@@@yyaxgxthsqxvbeppquykobvttcgodt@@@wsrydekwolruifovgkxpkdloixdgee@@@qfexsfdcakfsfmssspexuvqmjtgdqf@@@bdsjtmqkmjrejmkqwxupfmbgjunqn#b'
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
                # driver.maximize_window()
            else:
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions)
                # driver.maximize_window()
                #'/usr/local/bin/chromedriver'

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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'CSB', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), self.ref_id+'/screenshot/'+ sname)
        return sname

    def saving_pdf(self):
        d_lt = os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname),self.ref_id + "/"+"automated_pdf_files/"+ i)
        if len(d_lt) > 0:
            self.logStatus("info", "pdfs downloaded")
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
            self.logStatus("info", "No pdfs available")
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

        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('BtnLogin'):
            self.driver.find_element_by_id('BtnLogin').click()

        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('newTxtUser'):
            usernameInputField = self.driver.find_element_by_id('newTxtUser')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        if self.check_exists_by_id('newButton_go'):
            gobtn = self.driver.find_element_by_id('newButton_go')
            gobtn.click()

        time.sleep(self.timeBwPage)
        try:
            alert = self.driver.switch_to_alert()
            print(alert.text)
            alert.accept()
            self.driver.switch_to_default_content()
        except Exception as e:
            print(f'Alert box : {e}')
        time.sleep(self.timeBwPage)

        while 1:
            time.sleep(1)

            self.driver.save_screenshot("screenshot.png")
            if self.check_exists_by_id('newTxtCaptcha'):
                captchaInputField = self.driver.find_element_by_id('newTxtCaptcha')
                captchaInputField.clear()
                self.driver.find_element_by_xpath("""//*[@id="newImgCaptcha"]""").screenshot("captcha.png")
                captchaInputField.send_keys(csbcaptcha())

            try:
                alert = self.driver.switch_to_alert()
                print(alert.text)
                self.logStatus("debug", "captcha failed", self.takeScreenshot())
                alert.accept()
                self.driver.switch_to_default_content()
                self.driver.find_element_by_id('LinkButton1').click()
                continue
            except Exception as e:
                print(f'Alert box : {e}')

            if self.check_exists_by_id('newButton_go'):
                gobtn = self.driver.find_element_by_id('newButton_go')
                gobtn.click()

            try:
                alert = self.driver.switch_to_alert()
                print(alert.text)
                self.logStatus("debug", "captcha failed", self.takeScreenshot())
                alert.accept()
                self.driver.switch_to_default_content()
                self.driver.find_element_by_id('LinkButton1').click()
                continue
            except Exception as e:
                print(f'Alert box : {e}')
                break

        if self.check_exists_by_xpath('/html/body/form/div[3]/div/div/div[1]/div[2]'):
            mssg = self.driver.find_element_by_xpath(
                '/html/body/form/div[3]/div/div/div[1]/div[2]').find_element_by_tag_name('h1')
            print(mssg.text)
            if 'Invalid UserID' in mssg.text:
                self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                return {"referenceId": self.ref_id, "responseCode": "EWC002",
                        "responseMsg": "Incorrect UserName Or Password."}
            else:
                if self.check_exists_by_id('newLabel2'):
                    PasswordField = self.driver.find_element_by_id('newLabel2')
                    PasswordField.clear()
                    PasswordField.send_keys(password)
                    self.logStatus("info", "password entered", self.takeScreenshot())

                if self.check_exists_by_id('newButtonLogin'):
                    lgnbtn = self.driver.find_element_by_id('newButtonLogin')
                    lgnbtn.click()
                    self.logStatus("info", "login button clicked", self.takeScreenshot())

                if self.check_exists_by_xpath('/html/body/form/div[4]/div/div/div[1]/div[2]'):
                    mssg = self.driver.find_element_by_xpath(
                        '/html/body/form/div[4]/div/div/div[1]/div[2]').find_element_by_tag_name('h1')
                    print(mssg.text)
                    if 'Your user ID or password is incorrect' in mssg.text:
                        self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                        return {"referenceId": self.ref_id, "responseCode": "EWC002",
                                "responseMsg": "Incorrect UserName Or Password."}
                else:
                    self.logStatus("info", "login successfull", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "SRC001",
                            "responseMsg": "Successfully Completed."}

    def downloadData(self, fromdate, todate, accountno, seml, smno):
        time.sleep(self.timeBwPage)
        self.logStatus("info", "statement page", self.takeScreenshot())
        if self.check_exists_by_id('rptrMenu__ctl4_LnkMenu'):
            self.driver.find_element_by_id('rptrMenu__ctl4_LnkMenu').click()
        time.sleep(10)
        self.logStatus("info", "select account option", self.takeScreenshot())

        if self.check_exists_by_id('_ctl0_ddActno'):
            print("yu")
            bankacc=Select(self.driver.find_element_by_id('_ctl0_ddActno'))

        elif self.check_exists_by_xpath('/html/body/form/div[4]/div/div[2]/div[2]/div[1]/section/div[2]/div[1]/div[2]/div/select'):
            bankacc= Select(self.driver.find_element_by_xpath('/html/body/form/div[4]/div/div[2]/div[2]/div[1]/section/div[2]/div[1]/div[2]/div/select'))

        else:
            try:
                bankacc=Select(self.driver.find_element_by_id('_ctl0_ddActno'))
            except:
                bankacc= Select(self.driver.find_element_by_xpath('/html/body/form/div[4]/div/div[2]/div[2]/div/section/div[3]/div[1]/div[2]/select'))

        accountno = accountno.replace("-","")

        acn=''
        for accno in list(map(lambda x:x.text,bankacc.options)):
            if accountno in accno.replace("-",""):
                acn=accno
                bankacc.select_by_visible_text(acn)
                self.logStatus("info", "Account number found", self.takeScreenshot())
                break


        if acn == '':

            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

        else:
            self.logStatus("info", "account selected", self.takeScreenshot())

            if len(fromdate) == 7 and len(todate) == 7:
                tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
                fromdate = '01' + "-" + fromdate
                todate = str(tdy) + "-" + todate

            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')

            curr_year = datetime.now().year
            curr_month = datetime.now().month

            if fromdate.year < curr_year and todate.year >= curr_year:
                fromdate = '01-01-' + str(curr_year)
                fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            else:
                print('No data available')

            if todate.year >= curr_year and todate.month >= curr_month:
                todate = datetime.now() - timedelta(days=1)

            dt_lst = []
            date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'), end=todate.strftime('%m-%d-%Y'),
                                      freq=pd.DateOffset(months=2), closed=None).to_list()
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

            print(f'Date list : {dt_lst}')

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

                # FROM DAY SET

                if len(fday) == 1:
                    fday = '0' + fday

                if self.check_exists_by_id('_ctl0_dpFrmDay'):
                    fdaysel = Select(self.driver.find_element_by_id('_ctl0_dpFrmDay'))
                    for dy in list(map(lambda x: x.text, fdaysel.options)):
                        if fday == dy:
                            fdaysel.select_by_visible_text(fday)
                            break

                # FROM MONTH SET

                if self.check_exists_by_id('_ctl0_dpFrmMonth'):
                    fmnthsel = Select(self.driver.find_element_by_id('_ctl0_dpFrmMonth'))
                    for mnth in list(map(lambda x: x.text, fmnthsel.options)):
                        if fmonth == mnth:
                            fmnthsel.select_by_visible_text(fmonth)
                            break

                # FROM YEAR SET
                if self.check_exists_by_id('_ctl0_dpFrmYear'):
                    fyrsel = Select(self.driver.find_element_by_id('_ctl0_dpFrmYear'))
                    for yr in list(map(lambda x: x.text, fyrsel.options)):
                        if fyear in yr:
                            fyrsel.select_by_visible_text(fyear)
                            break

                # TO DAY SET

                if len(tday) == 1:
                    tday = '0' + tday

                if self.check_exists_by_id('_ctl0_dpToDay'):
                    tdaysel = Select(self.driver.find_element_by_id('_ctl0_dpToDay'))
                    for dy in list(map(lambda x: x.text, tdaysel.options)):
                        if tday == dy:
                            tdaysel.select_by_visible_text(tday)
                            break

                # TO MONTH SET
                if self.check_exists_by_id('_ctl0_dpToMonth'):
                    tmnthsel = Select(self.driver.find_element_by_id('_ctl0_dpToMonth'))
                    for mnth in list(map(lambda x: x.text, tmnthsel.options)):
                        if tmonth == mnth:
                            tmnthsel.select_by_visible_text(tmonth)
                            break

                # TO YEAR SET

                if self.check_exists_by_id('_ctl0_dpToYear'):
                    tyrsel = Select(self.driver.find_element_by_id('_ctl0_dpToYear'))
                    for yr in list(map(lambda x: x.text, tyrsel.options)):
                        if tyear in yr:
                            tyrsel.select_by_visible_text(tyear)
                            break

                # SET FILE TYPE

                if self.check_exists_by_id('_ctl0_ddFileType'):
                    fltypsel = Select(self.driver.find_element_by_id('_ctl0_ddFileType'))
                    for fltyp in list(map(lambda x: x.text, fltypsel.options)):
                        if 'PDF' == fltyp:
                            fltypsel.select_by_visible_text('PDF')
                            break

                if self.check_exists_by_id('_ctl0_btnUploadSearch'):
                    self.driver.find_element_by_id('_ctl0_btnUploadSearch').click()

                try:
                    alert = self.driver.switch_to_alert()
                    print(alert.text)
                    alert.accept()
                    self.driver.switch_to_default_content()
                except Exception as e:
                    print(f'Alert box : {e}')

                time.sleep(5)

                d_lt = os.listdir(self.pdfDir)
                for fl in d_lt:
                    if len(fl[:-4]) > 2:
                        os.rename(os.path.join(self.pdfDir, fl), os.path.join(self.pdfDir, str(flcount) + '.pdf'))
                        flcount += 1

            dic = self.saving_pdf()
            return dic

    def logout(self):
        if self.check_exists_by_id('LnkSignOut'):
            self.driver.find_element_by_id('LnkSignOut').click()
            self.logStatus("info", "logout btn clicked", self.takeScreenshot())
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
#     # refid=str(uuid.uuid1())
#     # print(f'RefID : {refid}')
#     obj=CSBScrapper('960bd166-5011-11eb-999b-7440bb00d0c5')
#     opstr=obj.login('407308283','!QAZ1qaz23','','')
#     print(opstr)
#     res=obj.downloadData('31-10-2020','09-12-2020','0316-07308283-190001','','')
#     a,b=obj.logout()
#     obj.closeDriver()