from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import time
import uuid
from pprint import pprint
import boto3
from selenium.webdriver.support import expected_conditions as EC
from botocore.exceptions import ClientError
from data_base import DB
from rdb import RDB
from datetime import date,  timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta
from Otp_sending import emailsending,msgsending
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import socket
import calendar
import pytz


class DbsStatement:

    def __init__(self, refid, env="quality"):
        self.timeBwPage = 0.5
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.readConfig()
        self.CreateS3()

        self.dbObj = DB(**self.dbConfig)
        self.robj=RDB(**self.rdbConfig)
        self.refid = refid
        self.downloadDir = os.path.join(os.getcwd(), "pdfs")
        self.chromeOptions = Options()
        self.driver = self.createDriver(mode='headless')

        self.wait = WebDriverWait(self.driver, 5)

        """ netbanking url """
        self.netbanking_url = "https://internet-banking.retail.dbsbank.in/login"

        """ select login section """
        self.username_xp = "/html/body/div/div/div[4]/div[3]/div/div[2]/div[1]/div[2]/form/div[1]/label/input"
        self.password_xp = "/html/body/div/div/div[4]/div[3]/div/div[2]/div[1]/div[2]/form/div[2]/div/label/input"
        self.login_xp = "/html/body/div/div/div[4]/div[3]/div/div[2]/div[1]/div[2]/form/button"

        self.statement_xp = "/html/body/div/div/div[4]/div[1]/div/div[3]/div[2]/div[2]/div[3]/div/div[7]/div[1]/div[1]"
        self.e_statement_xp = "/html/body/div/div/div[4]/div[1]/div/div[3]/div[2]/div[2]/div[3]/div/div[7]/div[2]/div[1]/a"

        self.logout_xp = "/html/body/div/div/div[4]/div[1]/div/div[3]/div[2]/div[2]/div[3]/div/div[9]/a/div/div"

        self.submit_otp_xp = "/html/body/div/div/div[1]/div/div[1]/div/form/button"
        
        self.date_status  = "notExist"
        
        self.otp_xp = "/html/body/div/div/div[1]/div/div[1]/div/form/div[1]/div/label/input"
        try:
            hostname = socket.gethostname()
            self.ipadd = socket.gethostbyname(hostname)
        except:
            self.ipadd="127.1.1.1"

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
            self.rdbConfig = config['rdbConfig']

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
        print(filename)
        self.bucket.upload_file(
            Filename=filename, Key=key)

    def takeScreenshot(self):
        time.sleep(self.timeBwPage)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName),  self.refid+ "/" + "screenshot/"+sname)

        os.remove(screenshotName)
        return sname

    def savePdf(self):

        time.sleep(self.timeBwPage)

        pname = os.listdir("pdfs/")[0]

        pdfName = os.path.join(self.pdfDir, f"{pname}")

        self.uploadToS3(os.path.join(pdfName),self.refid + "/"+"automated_pdf_files/"+ pname)

        os.remove("pdfs/" + pname)

        return pname

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.refid, tm, level, message, 'DBS', self.env,
                                 screenshot,"127.1.1.1")
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
            driver = webdriver.Chrome(ChromeDriverManager().install(),
                                      chrome_options=self.chromeOptions)
            # driver.maximize_window()
        except Exception as e:
            self.logStatus("error", str(e))
            raise CouldNotCreateDriver
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

    def login(self, user_id, password, rec_em, rec_m):

        response_dict = {"referenceId": self.refid}
        
        try:
            self.driver.get(self.netbanking_url)
        except:
            self.logStatus("info", "website error", self.takeScreenshot())
            response_dict["responseCode"] = "EIS042"
            response_dict["responseMsg"] = "Information Source is Not Working"
            return response_dict
        
        self.logStatus("info", "dbsbank netbanking url opened", self.takeScreenshot())

        username_input = self.driver.find_element_by_xpath(self.username_xp)
        username_input.clear()
        username_input.send_keys(user_id)
        self.logStatus("info", "username entered", self.takeScreenshot())

        username_input = self.driver.find_element_by_xpath(self.password_xp)
        username_input.clear()
        username_input.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.login_xp).click()
        
        self.driver.switch_to_default_content()

        time.sleep(2)
        try:
            if self.driver.find_element_by_id("avatarUserName").text == user_id:

                print("logged in successfully")
                self.logStatus("info", "successfully logged in", self.takeScreenshot())
                response_dict["responseCode"] = "SRC001"
                response_dict["responseMsg"] = "Successfully Completed"

        except:
            print("wrong user id password")

            self.logStatus("critical", "Incorrect UserName Or Password.", self.takeScreenshot())
            response_dict["responseCode"] = "EWC002"
            response_dict["responseMsg"] = "Incorrect UserName Or Password."

        return response_dict

    def logout(self):
        try:
            self.driver.find_element_by_xpath(self.logout_xp).click()
            self.logStatus("info", "logout successfully", self.takeScreenshot())
            return "successfull",{"referenceId":self.refid,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.refid,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def closeDriver(self):
        self.driver.quit()

    def downloadData(self, fromDate, toDate, accountno, rec_em, rec_m):
        response_dict = {"referenceId": self.refid}

        self.driver.find_element_by_xpath(self.statement_xp).click()
        time.sleep(1)
        self.driver.find_element_by_xpath(self.e_statement_xp).click()

        if len(fromDate)==7 and len(toDate)==7:
            tdy=calendar.monthrange(int(toDate[3:]),int(toDate[:2]))[1]
            fromDate='01'+"-"+fromDate
            toDate=str(tdy)+"-"+toDate

        toDate=datetime.strptime(toDate, '%d-%m-%Y')
        if toDate.year>=datetime.now().year and toDate.month>=datetime.now().month:
            toDate=datetime.now()-timedelta(days=1)

        toDate = toDate.strftime('%d-%m-%Y')

        time.sleep(25)
        
        time.sleep(self.timeBwPage)
        olp=2
        reid=self.refid
        tmi=datetime.now()
        tmo=datetime.now()+timedelta(seconds=120)
        emailsending(rec_em,reid,'120')
        # msgsending(rec_m,reid,'2')
        self.robj.insert(reid,"","","")
        scs=False
        while olp>0:

            if datetime.now()>tmo:
                print('OTP timeout')
                self.robj.insertone(reid,'Response','EOE082')
                self.robj.insertone(reid,'Status','Expired')
                self.driver.find_element_by_xpath('/html/body/div/div/div[1]/div/div[2]').click()
                time.sleep(1)
                break

            if self.robj.fetch(reid,'Otp')!='':
                self.driver.find_element_by_xpath(self.otp_xp)
                otp_input = self.driver.find_element_by_xpath(self.otp_xp)
                otp_input.clear()
                oottpp=int(self.robj.fetch(reid,'Otp'))
                print(f"OTP : {oottpp}")
                otp_input.send_keys(oottpp)

                self.driver.find_element_by_xpath(self.submit_otp_xp).click()
                time.sleep(5)

                resend1 = self.driver.find_element_by_tag_name("a")

                if resend1.text == "RESEND OTP":
                    print('here')
                    try:
                        resend1.click()
                        self.robj.insertone(reid,'Response','ETP011')
                        self.robj.insertone(reid,'Otp','')
                        olp-=1
                        tmo=datetime.now()+timedelta(seconds=120)
                    except:
                        self.robj.insertone(reid,'Response','ETP011')
                        self.robj.insertone(reid,'Otp','')
                        olp-=1
                        print("Resend not clickable")

                elif "attempts left" in self.driver.find_element_by_tag_name("span").text:
                    self.robj.insertone(reid,'Response','ETP011')
                    self.robj.insertone(reid,'Otp','')
                    olp-=1
                
                elif self.driver.find_element_by_tag_name("Button").text == "OTP HAS EXPIRED":
                    self.driver.find_element_by_xpath('/html/body/div/div/div[1]/div/div[2]').click()
                    self.robj.insertone(reid,'Response','EOE082')
                    self.robj.insertone(reid,'Status','Expired')
                    self.driver.find_element_by_xpath('/html/body/div/div/div[1]/div/div[2]').click()
                    break

                else:
                    print('OTP success')
                    self.robj.insertone(reid,'Response','SOA078')
                    time.sleep(5)
                    scs=True
                    self.robj.deleteall(reid)
                    break      

        if scs==False:
            self.robj.deleteall(reid)
            return {"referenceId":self.refid,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

        fromDate = datetime.strptime(fromDate, '%d-%m-%Y').strftime("%m-%d-%Y")
        toDate = datetime.strptime(toDate, '%d-%m-%Y').strftime("%m-%d-%Y")

        date_list = pd.date_range(start=fromDate, end=toDate,
                                  freq=pd.DateOffset(months=1), closed=None).to_list()

        date_list = [(str(dt.year)+" "+dt.month_name()) for dt in date_list]

        time.sleep(2)
        try:
            self.driver.find_element_by_xpath("/html/body/div/div/div[4]/div[2]/div/div[2]/div[3]/div[2]/div/div[1]/div[2]/div/div/form").click()
            time.sleep(5)
         
        except:
            pass
        
        
        print(date_list)
        for selected_div in self.driver.find_elements_by_xpath("//*[@class='Pure__HistoryBox-eOEylx QJzGc']"):
            year = selected_div.find_element_by_xpath(
                './/div[@class="Pure__HistoryDate-deQkFJ bpPrTU"]')
            months = selected_div.find_elements_by_xpath(
                './/div[@class="Pure__StatementInfo-iLNjPg fNHCxw"]')
            
            for m1 in months:

                if (str(year.text) + " " + m1.text) in date_list:
                    m1.click()
                    time.sleep(5)

                    try:
                        self.savePdf()
                    except :
                        self.logStatus('info','file not yet downloaded waiting for 10 seconds')
                        time.sleep(10)
                        self.savePdf()
                    
                    self.logStatus("info", "pdf downloaded", self.takeScreenshot())
                    
                    self.date_status  = "exist"
                    
                    time.sleep(3)

                    
    
        if self.date_status == "notExist":
            
            self.logStatus("info", "statement not exist", self.takeScreenshot())

            response_dict["responseCode"] = "END013"
            response_dict["responseMsg"] = "No Data Available"
            return response_dict
        
        elif self.date_status == "exist" :
            
            self.logStatus("info", "statement downloaded", self.takeScreenshot())

            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"
            return response_dict


# if __name__ == '__main__':

#     username = "santsy03"
#     password = "!QAZ1qaz"

#     mode = "Data Download"
#     bankName = "DBS"

#     fromDate = "01-06-2018"
#     toDate = "10-08-2020"

#     dbs1 = DbsStatement(refid="dbsTesting", env='quality')

#     if mode == "Login Check":

#         response = dbs1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             dbs1.logout()
#         else:
#             dbs1.driver_quit()

#     elif mode == "Data Download":
#         response = dbs1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = dbs1.getStatements(fromDate, toDate)
#             print(response1)

#             dbs1.logout()

#         else:
#             dbs1.driver_quit()

#     elif mode == "Both":
#         response = dbs1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = dbs1.getStatements(fromDate, toDate)
#             print(response1)

#             dbs1.logout()

#         else:
#             dbs1.driver_quit()