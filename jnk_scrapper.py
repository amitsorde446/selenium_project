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
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


from webdriver_manager.chrome import ChromeDriverManager


class JNKScrapper:

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
        self.url = 'https://www.jkbankonline.com'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 5)

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

    def createDriver(self, mode):

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
                from pyvirtualdisplay import Display
                display = Display(visible=0, size=(1366, 768))
                display.start()
                driver = webdriver.Chrome(chrome_options=self.chromeOptions)
                driver.maximize_window()
            else:
                driver = webdriver.Chrome(ChromeDriverManager().install(),
                                          chrome_options=self.chromeOptions)

                capa = DesiredCapabilities.CHROME
                capa["pageLoadStrategy"] = "none"
                from pyvirtualdisplay import Display
                display = Display(visible=0, size=(1366, 768))
                display.start()
                driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=self.chromeOptions, desired_capabilities=capa)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'J&K', self.env,
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

    def login(self, username, password,seml,smno):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}
        from selenium.webdriver.support.ui import WebDriverWait as wait
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        time.sleep(14)
        tb = self.driver.find_element_by_xpath("""/html/body/div[4]/div/div/div/div/h3[1]""").click()
        #time.sleep(30)
        #self.driver.find_element_by_xpath("""/html/body/form/div/div[2]/div/div[2]/div/div[1]/div/p[2]/span/span/input""").click()
        wait(self.driver, 160).until(
            EC.visibility_of_element_located((By.XPATH, """/html/body/form/div/div[2]/div/div[2]/div/div[1]/div/p[2]/span/span/input"""))).click()
        time.sleep(1)
        self.driver.find_element_by_xpath("""/html/body/form/div/div[2]/div/div[2]/div/div[1]/div/p[2]/span/span/input""").send_keys(username)
        self.driver.find_element_by_xpath("""//*[@id="STU_VALIDATE_CREDENTIALS"]""").click()
        time.sleep(4)
        self.driver.find_element_by_xpath("""//*[@id="AuthenticationFG.ACCESS_CODE"]""").send_keys(password)
        self.driver.find_element_by_xpath("""//*[@id="AuthenticationFG.TARGET_CHECKBOX"]""").click()
        self.driver.find_element_by_xpath("""//*[@id="VALIDATE_STU_CREDENTIALS"]""").click()
        time.sleep(15)
        try:
            unsuccessful = self.driver.find_element_by_xpath("""//*[@id="MessageDisplay_TABLE"]/div[2]""").text
        except:
            unsuccessful = ""
            pass
        print(unsuccessful, " checksuccessful")
        if unsuccessful.find("unsuccessful attempt(s)") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EWC002","responseMsg": "Incorrect UserName Or Password."}
        if unsuccessful.find("Unable to login.") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EIS042","responseMsg": "Information Source is Not Working"}
        #self.driver.find_element_by_xpath("""//*[@id="Detailed Statement"]""").click()
        wait(self.driver, 160).until(
            EC.visibility_of_element_located(
                (By.XPATH, """//*[@id="Detailed Statement"]"""))).click()
        time.sleep(9)
        self.driver.find_element_by_xpath("""/html/body/form/div/div[3]/div[2]/div[2]/div[6]/div/div/p/span[2]""").click()
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def calenderSelector(self, day, month, year):
        if self.check_exists_by_xpath('//*[@id="outerTab"]/div[2]'):
            mnth = Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[1]'))
            mnth.select_by_visible_text(month)

            yr = Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[2]'))
            yr.select_by_visible_text(year)

            dt = self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/table/tbody')
            dts = dt.find_elements_by_tag_name('tr')
            ext = False
            for i in dts:
                val = i.find_elements_by_tag_name('td')
                for j in val:
                    if str(j.text) == day:
                        j.click()
                        ext = True
                        break

                if ext == True:
                    break

    def downloadData(self, fromdate, todate, accountno, seml, smno):
        fromdates = fromdate
        todates = todate
        try:
            from datetime import datetime,timedelta
            fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
            fromdate = fromdate.strftime('%d/%m/%Y')
            todate = datetime.strptime(todate, '%d-%m-%Y')
            todate = todate.strftime('%d/%m/%Y')
            fromdates = fromdate
            todates = todate
        except:
            pass
        print(fromdate)
        print(todate)
        # fromdate = "02-03-2019"
        # todate = "02-04-2021"
        # from datetime import datetime,timedelta
        # fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
        # todate = datetime.strptime(todate, '%d-%m-%Y')
        # if todate > fromdate:
        #     print("yes")
        # else:
        #     print("no")
        import time
        from datetime import datetime, timedelta
        fromdate2 = datetime.strptime(fromdate, '%d/%m/%Y')
        # fromdate = date_obj.strftime('%d-%b-%Y')

        todate2 = datetime.strptime(todate, '%d/%m/%Y')
        # todate = date_obj.strftime('%d-%b-%Y')
        num = todate2 - fromdate2
        num = str(num)
        num = num.split(" days,")[0]
        num = int(num)
        time.sleep(5)
        if num>90:
            fromdate = datetime.strptime(fromdate, '%d/%m/%Y')
            todate = datetime.strptime(todate, '%d/%m/%Y')
            datearray = []
            while todate > fromdate:
                fromdate = fromdate + timedelta(days=90)
                if todate > fromdate:
                    datearray.append(fromdate)
            # print(fromdate)
            fromdate = fromdates
            todate = todates
            from datetime import datetime, timedelta
            fromdate = datetime.strptime(fromdate, '%d/%m/%Y')
            todate = datetime.strptime(todate, '%d/%m/%Y')
            print(todate)
            import time
            jjj = 0
            for i in datearray:
                jjj = jjj + 1
                todate1 = i
                #     time.sleep(5)
                if len(datearray) == jjj:
                    todate1 = todate
                    fromdate = todate - timedelta(days=90)
                print(fromdate, " fromdate")
                print(todate1, " todate")
                try:
                    fromdate2 = fromdate.strftime('%d/%m/%Y')
                    todate2 = todate1.strftime('%d/%m/%Y')
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").clear()
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").send_keys(fromdate2)
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").clear()
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").send_keys(todate2)
                    self.driver.find_element_by_xpath("""//*[@id="SEARCH"]""").click()
                    time.sleep(4)
                    try:
                        transact = self.driver.find_element_by_xpath("""//*[@id="MessageDisplay_TABLE"]/div[2]""").text
                        if transact.find("The transactions do not exist"):
                            print(transact)

                    except Exception as e:
                        pass
                    time.sleep(3)
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]""").click()
                    time.sleep(3)
                    self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]/option[6]""").click()
                    self.driver.find_element_by_xpath("""//*[@id="okButton"]""").click()
                    time.sleep(3)

                except:
                    pass
                fromdate = todate1
            time.sleep(5)
            dic = self.saving_pdf()
            return dic
        else:
            self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").clear()
            self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").send_keys(str(fromdate))
            self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").clear()
            self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").send_keys(str(todate))
            self.driver.find_element_by_xpath("""//*[@id="SEARCH"]""").click()
            time.sleep(4)

            try:

                transact = self.driver.find_element_by_xpath("""//*[@id="MessageDisplay_TABLE"]/div[2]""").text
                print(transact)
                if transact.find("The transactions do not exist") != -1:

                    print(transact)
                    return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}
            except Exception as e:
                print(e)
                pass
            try:
                print("dhano4")
                self.driver.find_element_by_xpath("""/html/body/form/div/div[3]/div[2]/div[2]/div[9]/div/p/span/span/span/select""").click()
            except:
                return {"referenceId": self.ref_id, "responseCode": "ENI004", "responseMsg": "No Information Found."}
            time.sleep(3)
            self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]/option[6]""").click()
            self.driver.find_element_by_xpath("""//*[@id="okButton"]""").click()
            time.sleep(5)
            dic = self.saving_pdf()
            return dic
        # time.sleep(5)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").clear()
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").send_keys(fromdate)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").clear()
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").send_keys(todate)
        # self.driver.find_element_by_xpath("""//*[@id="SEARCH"]""").click()
        # time.sleep(4)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]""").click()
        # time.sleep(3)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]/option[6]""").click()
        # self.driver.find_element_by_xpath("""//*[@id="okButton"]""").click()

        # tbl = self.driver.find_element_by_class_name('open')
        # accstmt = tbl.find_element_by_link_text('Account Statement')
        # accstmt.click()
        #
        # time.sleep(self.timeBwPage)
        # self.logStatus("info", "Acc stmt page opened", self.takeScreenshot())
        #
        # accountselctor = Select(self.driver.find_element_by_class_name('dropdownexpandalbe'))
        # print(list(map(lambda x: x.text, accountselctor.options)))
        # accfound = ''
        # for acc in list(map(lambda x: x.text, accountselctor.options)):
        #     if accountno in acc:
        #         accfound = 'Done'
        #         accountselctor.select_by_visible_text(acc)
        #         break
        #
        # time.sleep(self.timeBwPage)
        #
        # if accfound != '':
        #
        #     self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.SELECTED_RADIO_INDEX"]').click()
        #
        #     if len(fromdate) == 7 and len(todate) == 7:
        #         tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
        #         fromdate = '01' + "-" + fromdate
        #         todate = str(tdy) + "-" + todate
        #
        #     fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
        #     todate = datetime.strptime(todate, '%d-%m-%Y')
        #
        #     if todate.year >= datetime.now().year and todate.month >= datetime.now().month:
        #         todate = datetime.now() - timedelta(days=1)
        #
        #     dt_lst = []
        #     date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'), end=todate.strftime('%m-%d-%Y'),
        #                               freq=pd.DateOffset(years=1), closed=None).to_list()
        #     for ind1 in range(len(date_list)):
        #         if ind1 > 0:
        #             st = date_list[ind1 - 1]
        #             ed = date_list[ind1] - timedelta(days=1)
        #             dt_lst.append([str(st)[:10], str(ed)[:10]])
        #     if len(dt_lst) > 0 and todate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
        #         st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
        #         ed = todate
        #         dt_lst.append([str(st)[:10], str(ed)[:10]])
        #     elif len(dt_lst) == 0:
        #         dt_lst.append([fromdate.strftime('%Y-%m-%d'), todate.strftime('%Y-%m-%d')])
        #
        #     flcount = 1
        #     for dts in dt_lst:
        #         fd = datetime.strptime(dts[0], '%Y-%m-%d')
        #         td = datetime.strptime(dts[1], '%Y-%m-%d')
        #
        #         fday = str(fd.day)
        #         fmonth = fd.strftime('%B')
        #         fyear = str(fd.year)
        #         tday = str(td.day)
        #         tmonth = td.strftime('%B')
        #         tyear = str(td.year)
        #
        #         # FROM DATE SET
        #
        #         self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG"]').click()
        #         time.sleep(2)
        #         self.calenderSelector(fday, fmonth, fyear)
        #         self.logStatus("info", "from date set", self.takeScreenshot())
        #
        #         # TO DATE SET
        #
        #         self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG"]').click()
        #         time.sleep(2)
        #         self.calenderSelector(tday, tmonth, tyear)
        #         self.logStatus("info", "to date set", self.takeScreenshot())
        #
        #         self.driver.find_element_by_xpath('//*[@id="SEARCH"]').click()
        #
        #         if self.check_exists_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'):
        #             doctype = Select(self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'))
        #             doctype.select_by_visible_text('PDF file')
        #             self.logStatus("info", "pdf format selected", self.takeScreenshot())
        #
        #             self.driver.find_element_by_xpath('//*[@id="okButton"]').click()
        #             time.sleep(3)
        #             d_lt = os.listdir(self.pdfDir)
        #             for fl in d_lt:
        #                 if len(fl[:-4]) > 2:
        #                     os.rename(os.path.join(self.pdfDir, fl), os.path.join(self.pdfDir, str(flcount) + '.pdf'))
        #                     flcount += 1
        #
        #         time.sleep(self.timeBwPage)
        #
        #     dic = self.saving_pdf()
        #     return dic
        # else:
        #     return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

    def logout(self):
        try:
            self.driver.find_element_by_xpath("""//*[@id="HREF_Logout"]""").click()
            time.sleep(4)
            self.driver.find_element_by_xpath("""//*[@id="LOG_OUT"]""").click()
            try:
                from pyvirtualdisplay import Display
                display = Display(visible=0, size=(1366, 768))
                display.stop()
            except:
                pass
            return {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            try:
                from pyvirtualdisplay import Display
                display = Display(visible=0, size=(1366, 768))
                display.stop()
            except:
                pass
            return {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}


    def closeDriver(self):
        # time.sleep(self.timeBwPage)
        # shutil.rmtree(self.pdfDir)
        # shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     obj=JNKScrapper('QWERTY123')
#     opstr=obj.login(username = 'ASHUTOSH15713287',password='Ril#54321',seml="",smno="")
#     print(opstr, " opstr")
#     if opstr['responseMsg']=='Successfully Completed.':
#         res=obj.downloadData('01-01-2021','19-07-2021','','','')
#     print(res)
#     b=obj.logout()
#
#     obj.closeDriver()