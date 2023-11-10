from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import time
import uuid
from pprint import pprint
import boto3
from botocore.exceptions import ClientError
from data_base import DB

from datetime import date,  timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import socket
import calendar

from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
import pytz


class IciciStatement:

    def __init__(self,refid, timeBwPage=2,env='dev',mode='headless'):
        self.timeBwPage = 0.5
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.readConfig()
        self.CreateS3()
        self.timeBwPage = timeBwPage
        self.dbObj = DB(**self.dbConfig)
        self.refid = refid
        self.downloadDir = os.path.join(os.getcwd(), "pdfs")
        self.chromeOptions = Options()
        self.driver = self.createDriver(mode=mode)

        self.wait = WebDriverWait(self.driver, 5)

        """ netbanking url """
        self.netbanking_url = "https://infinity.icicibank.com/corp/AuthenticationController?FORMSGROUP_ID__=AuthenticationFG&__START_TRAN_FLAG__=Y&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=ICI&ITM=nli_personalb_personal_login_btn%22"

        """ select login section """
        self.loginSection_xp = "/html/body/form[1]/div[3]/div[2]/div[2]/p[3]/span/span/input"
        self.user_id_xp = "/html/body/form[1]/div[3]/div[3]/div[2]/p[3]/span/span/input"
        self.password_xp = "/html/body/form[1]/div[3]/div[3]/div[2]/p[6]/input[2]"
        self.submit_xp = "/html/body/form[1]/div[3]/div[3]/div[2]/p[11]/span[1]/input[1]"
        self.login_alert_xp = "/html/body/form[1]/div[3]/div[1]/div"

        """ select header option - BANK ACCOUNTS """
        self.headerOption_xp1 = "/html/body/form/div[1]/div[4]/div/div/div[3]/div[1]/div/div/div/ul/li[2]/a"
        self.headerOption_xp2 = "/html/body/form/div[1]/div[4]/div/div/div[3]/div[1]/div/div/div/ul/li[2]/a/div[2]/img[1]"

        """ select dropdown option - eStatement """
        self.eStatement_xp = "/html/body/form/div[1]/div[4]/div/div/div[3]/div[1]/div/div/div/ul/li[2]/div/div/a[8]"

        """ select view detailed statement """
        self.detailedStatement_xp = "/html/body/form[2]/div/div[4]/div[1]/div[6]/div[2]/div/div/div[8]/div/p/span[2]/input"

        """ get statement button"""
        self.getStatement_xp = "/html/body/form/div/div[4]/div[1]/div[6]/div[2]/div/div/div[3]/div[3]/div/p/span/input[3]"

        """ click ok to download pdf """
        self.ok_xp = "/html/body/form/div/div[4]/div[1]/div[6]/div[2]/div/div/div[5]/div/p/span/input"

        """ from date calendar selection """
        self.from_cal_xp = "/html/body/form/div/div[4]/div[1]/div[6]/div[2]/div/div/div[3]/div[1]/div/p[3]/span[2]/span/span/img"
        self.from_month_xp = "/html/body/div[4]/div/div[2]/div/div/select[1]"
        self.from_year_xp = "/html/body/div[4]/div/div[2]/div/div/select[2]"
        self.from_date_xp = "/html/body/div[4]/div/div[2]/div/table/tbody"

        """ to date calendar selection """
        self.to_cal_xp = "/html/body/form/div/div[4]/div[1]/div[6]/div[2]/div/div/div[3]/div[1]/div/p[3]/span[3]/span[2]/span/img"
        self.to_month_xp = "/html/body/div[4]/div/div[2]/div/div/select[1]"
        self.to_year_xp = "/html/body/div[4]/div/div[2]/div/div/select[2]"
        self.to_date_xp = "/html/body/div[4]/div/div[2]/div/table/tbody"
        
        self.date_status = "notExist"

        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)

        if not os.path.exists("Screenshots"):
            os.makedirs("Screenshots")

        if not os.path.exists("pdfs"):
            os.makedirs("pdfs")

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
            self.logStatus("error", f"could not connect to s3 {e}")
            raise Exception("couldn't connect to s3")
        except Exception as e:
            self.logStatus("error", f"could not connect to s3 {e}")

            raise Exception("couldn't connect to s3")

    def uploadToS3(self, filename, key):
        print(filename)
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

    def savePdf(self, customName):

        time.sleep(self.timeBwPage)

        os.rename(("pdfs/OpTransactionHistory" +
                   datetime.now().strftime('%d-%m-%Y') + ".pdf"), ("pdfs/" + customName))

        pname = customName

        pdfName = os.path.join(self.pdfDir, f"{pname}")

        self.uploadToS3(os.path.join(pdfName), 'pdfs/' + self.refid + "/" + pname)

        os.remove("pdfs/"+pname)

        return pname

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'ICICI', self.env,
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
            driver = webdriver.Chrome('/usr/local/bin/chromedriver',
                                      chrome_options=self.chromeOptions)
            # driver.maximize_window()
        except Exception as e:
            self.logStatus("error", str(e))
        self.params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {
                'behavior': 'allow',
                'downloadPath': self.downloadDir
            }
        }
#         self.logStatus("info", "Driver created")
        return driver

    def check_exists_by_xpath(self, xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True

    def check_exists_by_id(self, id1):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, id1)))
        except:
            return False
        return True

    def check_exists_by_name(self, name):
        try:
            self.wait.until(EC.visibility_of_element_located((By.NAME, name)))
        except:
            return False
        return True

    def login(self, user_id, password, seml, smno):

        response_dict = {"referenceId": self.refid}

        try:
            self.driver.get(self.netbanking_url)
        except:
            self.logStatus("info", "website error", self.takeScreenshot())
            response_dict["responseCode"] = "EIS042"
            response_dict["responseMsg"] = "Information Source is Not Working"
            return response_dict

        
        self.logStatus("info", "icicibank netbanking url opened", self.takeScreenshot())

        time.sleep(2)

        if self.check_exists_by_id("DUMMY1"):
            user_id_input = self.driver.find_element_by_id("DUMMY1")
            user_id_input.clear()
            user_id_input.send_keys(user_id)

            self.driver.find_element_by_xpath("/html/body/form[1]/div[3]/div[3]/div/p[3]/span/img").click()

        self.wait.until(EC.element_to_be_clickable((By.ID, "AuthenticationFG.USER_PRINCIPAL")))

        user_id_input = self.driver.find_element_by_id("AuthenticationFG.USER_PRINCIPAL")
        user_id_input.clear()
        user_id_input.send_keys(user_id)


        password_input = self.driver.find_element_by_id("AuthenticationFG.ACCESS_CODE")
        password_input.clear()
        password_input.send_keys(password)

        self.driver.find_element_by_id("VALIDATE_CREDENTIALS1").click()

        time.sleep(2)

        txt1 = ""

        try:
            txt1 = self.driver.find_element_by_xpath(self.login_alert_xp).text
            print(txt1)

            if "Invalid login Attempt" in txt1:

                self.logStatus("error", "Incorrect UserName Or Password.", self.takeScreenshot())
                response_dict["responseCode"] = "EWC002"
                response_dict["responseMsg"] = "Incorrect UserName Or Password."

                print("invalid user id")

            elif "unsuccessful attempt" in txt1:

                self.logStatus("error", "Incorrect UserName Or Password.", self.takeScreenshot())
                response_dict["responseCode"] = "EWC002"
                response_dict["responseMsg"] = "Incorrect UserName Or Password."
                print("wrong password")

        except:
            pass

        if txt1 == "":
            print("logged in successfully")
            self.logStatus("info", "successfully logged in", self.takeScreenshot())
            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"

        return response_dict

    def logout(self):
        try:
            self.driver.find_element_by_id("HREF_Logout").click()
            self.logStatus("info", "logout successfully", self.takeScreenshot())
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull",{"referenceId":self.refid,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.refid,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def selectCalenderDate(self, day,  month, year, day_xpath, month_xpath, year_xpath, cal_id):

        time.sleep(1)
        self.driver.find_element_by_id(cal_id).click()
        time.sleep(1)
        mnth = Select(self.driver.find_element_by_xpath(month_xpath))
        time.sleep(1)
        mnth.select_by_visible_text(month)
        time.sleep(1)
        yr = Select(self.driver.find_element_by_xpath(year_xpath))
        time.sleep(1)
        yr.select_by_visible_text(year)
        time.sleep(1)
        dt = self.driver.find_element_by_xpath(day_xpath)
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

    def closeDriver(self):
        self.driver.quit()

    def downloadData(self, fromDate, toDate, accountno, seml, smno):
        response_dict = {"referenceId": self.refid}

        if self.check_exists_by_xpath("/html/body/form/div[1]/div[5]/div/div[4]/div[2]/div/div/div[1]/div[2]/div/div/div[1]/div/div/div/div/div/ul/li[1]/div/a"):
            self.driver.find_element_by_xpath("/html/body/form/div[1]/div[5]/div/div[4]/div[2]/div/div/div[1]/div[2]/div/div/div[1]/div/div/div/div/div/ul/li[1]/div/a").click()

        self.logStatus("info", "select view bank statements option", self.takeScreenshot())

        for i in self.driver.find_elements_by_class_name("newListSelected"):
            if accountno in i.text:
                i.click()
                print("yes")
                break
        else:
            response_dict["responseCode"] = "EAF010"
            response_dict["responseMsg"] = "Authentication Failed"
            return response_dict

        self.check_exists_by_name("Action.LOAD_HISTORY")
        self.driver.find_element_by_name("Action.LOAD_HISTORY").click()
        time.sleep(2)
 

        if len(fromDate)==7 and len(toDate)==7:
            tdy=calendar.monthrange(int(toDate[3:]),int(toDate[:2]))[1]
            fromDate='01'+"-"+fromDate
            toDate=str(tdy)+"-"+toDate
        
        fromDate=datetime.strptime(fromDate, '%d-%m-%Y')
        toDate=datetime.strptime(toDate, '%d-%m-%Y')

        if toDate.year>=datetime.now().year and toDate.month>=datetime.now().month:
            toDate=datetime.now()-timedelta(days=1)

        dt_lst=[]
        date_list = pd.date_range(start=fromDate.strftime('%m-%d-%Y'),end=toDate.strftime('%m-%d-%Y'),freq=pd.DateOffset(years=1),closed=None).to_list()

        for ind1 in range(len(date_list)):

            if ind1 > 0:
                st = date_list[ind1-1]
                ed = date_list[ind1] - timedelta(days=1)
                dt_lst.append([str(st)[:10],str(ed)[:10]])

                self.selectCalenderDate(str(st.day), str(st.strftime("%B")), str(
                    st.year), self.from_date_xp, self.from_month_xp, self.from_year_xp, "TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG")

                self.selectCalenderDate(str(ed.day), str(ed.strftime("%B")), str(
                    ed.year), self.to_date_xp, self.to_month_xp, self.to_year_xp, "TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG")

                self.check_exists_by_name("Action.LOAD_HISTORY")
                self.driver.find_element_by_name("Action.LOAD_HISTORY").click()
                time.sleep(2)
                
                try:
                    time.sleep(1)
                    self.driver.find_element_by_id("MessageDisplay_TABLE")
                    # self.date_status = "notExist"
                except:
                    self.date_status = "exist"
                    
                    time.sleep(2)

                    print(self.ok_xp)

                    self.logStatus("info", "dates selected", self.takeScreenshot())

                    if self.check_exists_by_xpath(self.ok_xp):
                        self.driver.find_element_by_xpath(self.ok_xp).click()
                    else:
                        print("by id")
                        self.driver.find_element_by_id("Button3675786").click()

                    time.sleep(3)

                    customName = str(st.date()) + "_" + str(ed.date())+".pdf"
                    self.savePdf(customName)
                    self.logStatus("info", "pdf downloaded",
                                self.takeScreenshot())

                    print(st, ed)

        if len(dt_lst)>0 and toDate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d') :
            st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
            ed = toDate
            
            print("")
            print(fromDate)
            print(date_list[-1])
            print(st)
            print("")

            self.selectCalenderDate(str(st.day), str(st.strftime("%B")), str(
                st.year), self.from_date_xp, self.from_month_xp, self.from_year_xp, "TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG")

            self.selectCalenderDate(str(ed.day), str(ed.strftime("%B")), str(
                ed.year), self.to_date_xp, self.to_month_xp, self.to_year_xp, "TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG")

            self.check_exists_by_name("Action.LOAD_HISTORY")
            self.driver.find_element_by_name("Action.LOAD_HISTORY").click()
            time.sleep(2)
            
            try:
                time.sleep(1)
                self.driver.find_element_by_id("MessageDisplay_TABLE")
                # self.date_status = "notExist"
            except:
                self.date_status = "exist"
                
            
                time.sleep(2)

                self.logStatus("info", "dates selected", self.takeScreenshot())

                if self.check_exists_by_xpath(self.ok_xp):
                    self.driver.find_element_by_xpath(self.ok_xp).click()
                else:
                    print("by id")
                    self.driver.find_element_by_id("Button3675786").click()

                time.sleep(3)

                customName = str(st.date()) + "_" + str(ed.date())+".pdf"
                self.savePdf(customName)
                self.logStatus("info", "pdf downloaded",
                            self.takeScreenshot())

                print(st, ed)
            
        elif len(dt_lst)==0:
            
            dt_lst.append([fromDate.strftime('%Y-%m-%d'),toDate.strftime('%Y-%m-%d')])
            
            st = datetime.strptime(dt_lst[0][0], '%Y-%m-%d')
            ed = datetime.strptime(dt_lst[0][1], '%Y-%m-%d')

            self.selectCalenderDate(str(st.day), str(st.strftime("%B")), str(
                st.year), self.from_date_xp, self.from_month_xp, self.from_year_xp, "TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG")

            self.selectCalenderDate(str(ed.day), str(ed.strftime("%B")), str(
                ed.year), self.to_date_xp, self.to_month_xp, self.to_year_xp, "TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG")

            time.sleep(2)
            self.check_exists_by_name("Action.LOAD_HISTORY")
            self.driver.find_element_by_name("Action.LOAD_HISTORY").click()
            
            time.sleep(5)


            
            try:
                time.sleep(1)
                self.driver.find_element_by_id("MessageDisplay_TABLE")
                # self.date_status = "notExist"
            except:
                self.date_status = "exist"
                
            
                time.sleep(2)

                self.logStatus("info", "dates selected", self.takeScreenshot())

                if self.check_exists_by_xpath(self.ok_xp):
                    self.driver.find_element_by_xpath(self.ok_xp).click()
                else:
                    print("by id")
                    self.driver.find_element_by_id("Button3675786").click()

                time.sleep(3)

                customName = str(st.date()) + "_" + str(ed.date())+".pdf"
                self.savePdf(customName)
                self.logStatus("info", "pdf downloaded",
                            self.takeScreenshot())

        
        if self.date_status == "notExist":

            response_dict["responseCode"] = "END013"
            response_dict["responseMsg"] = "No Data Available"
            return response_dict
        
        elif self.date_status == "exist" :
            
            self.logStatus("info", "statement downloaded", self.takeScreenshot())
            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"
            return response_dict


# if __name__ == '__main__':

#     username = "daisysbanga"
#     password = "..J@smita17.."

#     mode = "Both"
#     bankName = "ICICI"

#     fromDate = "01-06-1900"
#     toDate = "10-08-1900"

#     icici1 = IciciStatement(refid="iciciTesting", env='quality')

#     if mode == "Login Check":

#         response = icici1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             icici1.logout()
#         else:
#             icici1.driver_quit()

#     elif mode == "Data Download":
#         response = icici1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = icici1.getStatements(fromDate, toDate)
#             print(response1)

#             icici1.logout()

#         else:
#             icici1.driver_quit()

#     elif mode == "Both":
#         response = icici1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = icici1.getStatements(fromDate, toDate)
#             print(response1)

#             icici1.logout()

#         else:
#             icici1.driver_quit()