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
from selenium.webdriver.support import expected_conditions as EC
from dateutil.relativedelta import relativedelta
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import socket
import calendar
import pytz

class AxisStatement:

    def __init__(self, refid, env="quality"):
        self.timeBwPage = 0.5
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.readConfig()
        self.CreateS3()

        self.dbObj = DB(**self.dbConfig)
        self.refid = refid
        self.downloadDir = os.path.join(os.getcwd(), "pdfs")
        self.chromeOptions = Options()
        self.driver = self.createDriver(mode='headless')

        self.wait = WebDriverWait(self.driver, 5)

        """ netbanking url """
        self.netbanking_url = "https://retail.axisbank.co.in/wps/portal/rBanking/axisebanking/AxisRetailLogin/!ut/p/a1/04_Sj9CPykssy0xPLMnMz0vMAfGjzOKNAzxMjIwNjLwsQp0MDBw9PUOd3HwdDQwMjIEKIoEKDHAARwNC-sP1o_ArMYIqwGNFQW6EQaajoiIAVNL82A!!/dl5/d5/L2dBISEvZ0FBIS9nQSEh/"

        """ login section """

        self.username_input_xp = "/html/body/div/div/div[2]/div/div[2]/div/div/section/div[2]/div[5]/form/div/div[5]/div[1]/div[2]/ul[1]/li[1]/div/div/input[2]"

        self.password_input_xp = '/html/body/div/div/div[2]/div/div[2]/div/div/section/div[2]/div[5]/form/div/div[5]/div[1]/div[2]/ul[1]/li[2]/div/div/input'

        self.login_error_xp = '/html/body/div/div/div[2]/div/div[2]/div/div/section/div[2]/div[5]/form/div/div[5]/div[1]/div[2]/ul[1]/li[2]/div/div[2]'

        self.login_button_xp = '/html/body/div/div/div[2]/div/div[2]/div/div/section/div[2]/div[5]/form/div/div[5]/div[1]/input[1]'

        self.select_saving_xp = "/html/body/div/div/div[2]/div/table/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[1]/td/table/tbody/tr/td/div/section/div[2]/div[2]/form/div/div/div[1]/div[1]/div[2]/div[1]/div/div/div/table/tbody/tr[3]/td[2]/span"

        self.detailed_statement_xp1 = '/html/body/div/div/div[2]/div/table/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[1]/td/table/tbody/tr/td/div/section/div[2]/form/div/div/div[1]/div[2]/div[1]/div/div/div/table/tbody/tr[9]/td[2]/span/a'

        self.detailed_statement_xp2 = "//a[text()='View Detailed Statement']"

        self.from_date_xp = "/html/body/div/div/div[2]/div/table/tbody/tr/td[1]/table/tbody/tr/td/div[1]/section/div[2]/form/div/div[3]/div/div/p/span[2]/span[1]/span/input"

        self.to_date_xp = "/html/body/div/div/div[2]/div/table/tbody/tr/td[1]/table/tbody/tr/td/div[1]/section/div[2]/form/div/div[3]/div/div/p/span[2]/span[2]/span/input"

        self.select_format_xp = "/html/body/div/div/div[2]/div/table/tbody/tr/td[1]/table/tbody/tr/td/div[1]/section/div[2]/form/div/div[4]/div/div/p[1]/span[2]/span/span/span/span/span[1]"

        self.pdf_format_xp = '/html/body/div/div/div[2]/div/table/tbody/tr/td[1]/table/tbody/tr/td/div[1]/section/div[2]/form/div/div[4]/div/div/p[1]/span[2]/span/span/span/ul/li[5]/a'

        self.statement_xp = "//span[text()='Get Statement']"

        self.logout_xp = "/html/body/div/header/div[1]/form/div[2]/div[1]/div[3]/a"
        
        self.date_status = "notExist"
        
        self.bnkname = "AXIS"

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

        pname1 = os.listdir("pdfs/")[0]

        pname2 = str(uuid.uuid1()) + '.pdf'

        os.rename(("pdfs/" + pname1), ("pdfs/" + pname2))

        pdfName = os.path.join(self.pdfDir, f"{pname2}")

        self.uploadToS3(os.path.join(pdfName), 'pdfs/' +
                        self.bnkname + "/" + self.refid + "/" + pname2)

        os.remove("pdfs/"+pname2)

        return pname2

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'AXIS', self.env,
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

    def login(self, username, password, seml, smno):
        response_dict = {"referenceId": self.refid}
#         self.driver.get(self.netbanking_url)
        
        try:
            self.driver.get(self.netbanking_url)
        
        except:
            self.logStatus("info", "website error", self.takeScreenshot())
            response_dict["responseCode"] = "EIS042"
            response_dict["responseMsg"] = "Information Source is Not Working"
            return response_dict
        
        self.logStatus("info", "axis bank netbanking page ", self.takeScreenshot())
        time.sleep(1)

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

        error_msg = ''
        try:
            error_msg = self.driver.find_element_by_xpath(self.login_error_xp).text
        except:
            pass

        if len(error_msg) > 0:

            if error_msg == "Your Login ID is disabled. Please visit your nearest branch to activate it or contact the customer care for further details.":
                print(" invalid user id")

            else:
                print(error_msg)
            self.logStatus("critical", "Incorrect UserName Or Password.", self.takeScreenshot())
            response_dict["responseCode"] = "EWC002"
            response_dict["responseMsg"] = "Incorrect UserName Or Password."
        else:
            chk_url = "https://retail.axisbank.co.in/wps/NetSecure2FA/_NetSecure2FA/jsp/html/ezidentity/jsp/tk_qa.jsp"
            try:
                if self.driver.current_url == chk_url:
                    self.logStatus("error", "Authentication failed", self.takeScreenshot())
                    return {"referenceId":self.refid,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
            except Exception as e:
                print(f'Authentication exception : {e}')
            print("successfull login")
            self.logStatus("info", "successfully logged in", self.takeScreenshot())
            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"

        return response_dict

    def logout(self):
        try:
            self.driver.find_element_by_xpath(self.logout_xp).click()
            time.sleep(1)
            self.logStatus("info", "successfull logout ", self.takeScreenshot())
            return "successfull",{"referenceId":self.refid,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.refid,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def downloadData(self, fromDate, toDate, accountno, seml, smno):
        response_dict = {"referenceId": self.refid}

        if len(fromDate)==7 and len(toDate)==7:
            tdy=calendar.monthrange(int(toDate[3:]),int(toDate[:2]))[1]
            fromDate='01'+"-"+fromDate
            toDate=str(tdy)+"-"+toDate

        toDate=datetime.strptime(toDate, '%d-%m-%Y')
        if toDate.year>=datetime.now().year and toDate.month>=datetime.now().month:
            toDate=datetime.now()-timedelta(days=1)

        toDate = toDate.strftime('%d-%m-%Y')

        if datetime.strptime(toDate, '%d-%m-%Y').year <=2012:
            self.logStatus("info", "statement not exist", self.takeScreenshot())
            response_dict["responseCode"] = "END013"
            response_dict["responseMessage"] = "No Data Available"
            return response_dict
        elif datetime.strptime(fromDate, '%d-%m-%Y').year<=2012:
            fromDate = "01-01-2013"

        time.sleep(2)
        # saving
        self.logStatus("info", "select saving option", self.takeScreenshot())
        # self.driver.find_element_by_xpath(self.select_saving_xp).click()

        chk_acc = 0

        table1 = self.driver.find_element_by_xpath("/html/body/div/div/div[2]/div/table/tbody/tr/td/table/tbody/tr/td[1]/table/tbody/tr[1]/td/table/tbody/tr/td/div/section/div[2]/div[2]/form/div/div/div[1]/div[1]/div[2]/div[1]/div/div/div/table")

        for row in table1.find_elements_by_tag_name("tr"):
            for row1 in row.find_elements_by_tag_name("td"):
                if len(row1.find_elements_by_tag_name("span"))>0:
                    if accountno  in row1.find_element_by_tag_name("span").text:
                        row1.find_element_by_tag_name("span").click()
                        print("yes")
                        chk_acc =1
                        break
                        
            if chk_acc==1:
                break
        else:
            print("no")
            response_dict["responseCode"] = "EAF010"
            response_dict["responseMsg"] = "Authentication Failed"
            return response_dict

        time.sleep(3)

        # view detailed statement

        self.logStatus("info", "select detailed statement", self.takeScreenshot())
        try:
            self.driver.find_element_by_xpath(self.detailed_statement_xp1).click()
            time.sleep(2)
        except:
            try:
                self.driver.find_element_by_xpath(self.detailed_statement_xp2).click()
                time.sleep(2)
            except Exception as e:
                print(e)
                pass

        date_list = pd.date_range(start=fromDate, end=toDate,
                                  freq=pd.DateOffset(years=3), closed=None).to_list()

        for ind1 in range(len(date_list)):

            if ind1 > 0:

                st = date_list[ind1-1]
                st = datetime.strptime(str(st.date()), '%Y-%m-%d').strftime('%d-%m-%Y')
                ed = date_list[ind1] - timedelta(days=1)
                ed = datetime.strptime(str(ed.date()), '%Y-%m-%d').strftime('%d-%m-%Y')

                print(st)
                print(ed)

                from_date_input = self.driver.find_element_by_xpath(self.from_date_xp)
                from_date_input.clear()
                from_date_input.send_keys(st)

                to_date_input = self.driver.find_element_by_xpath(self.to_date_xp)
                to_date_input.clear()
                to_date_input.send_keys(ed)
                time.sleep(1)

                self.driver.find_element_by_xpath(self.select_format_xp).click()
                time.sleep(1)

                self.driver.find_element_by_xpath(self.pdf_format_xp).click()
                time.sleep(1)

                self.driver.find_element_by_xpath(self.statement_xp).click()
                time.sleep(1)

                self.savePdf()
                self.logStatus("info", "download pdf for specific date range",
                               self.takeScreenshot() )

        time.sleep(2)

        if len(date_list)>0 and datetime.strptime(toDate, '%d-%m-%Y') > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
            st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
            ed = datetime.strptime(toDate, '%d-%m-%Y')

            st = datetime.strptime(str(st.date()), '%Y-%m-%d').strftime('%d-%m-%Y')
            ed = datetime.strptime(str(ed.date()), '%Y-%m-%d').strftime('%d-%m-%Y')

            print(st)
            print(ed)

            from_date_input = self.driver.find_element_by_xpath(self.from_date_xp)
            from_date_input.clear()
            from_date_input.send_keys(st)

            to_date_input = self.driver.find_element_by_xpath(self.to_date_xp)
            to_date_input.clear()
            to_date_input.send_keys(ed)
            time.sleep(1)

            self.driver.find_element_by_xpath(self.select_format_xp).click()
            time.sleep(1)

            self.driver.find_element_by_xpath(self.pdf_format_xp).click()
            time.sleep(1)

            self.driver.find_element_by_xpath(self.statement_xp).click()
            time.sleep(1)
            self.savePdf()
            self.logStatus("info", "download pdf for specific date range",
                           self.takeScreenshot() )
            
        elif len(date_list)==0:
            
            st = fromDate
            ed = toDate

            print(st)
            print(ed)

            from_date_input = self.driver.find_element_by_xpath(self.from_date_xp)
            from_date_input.clear()
            from_date_input.send_keys(st)

            to_date_input = self.driver.find_element_by_xpath(self.to_date_xp)
            to_date_input.clear()
            to_date_input.send_keys(ed)
            time.sleep(1)

            self.driver.find_element_by_xpath(self.select_format_xp).click()
            time.sleep(1)

            self.driver.find_element_by_xpath(self.pdf_format_xp).click()
            time.sleep(1)

            self.driver.find_element_by_xpath(self.statement_xp).click()
            time.sleep(1)
            self.savePdf()
            self.logStatus("info", "download pdf for specific date range",
                           self.takeScreenshot())
            
        # if self.date_status == "notExist":
            
        #     self.logStatus("info", "statement not exist", self.takeScreenshot())

        #     response_dict["responseCode"] = "END013"
        #     response_dict["responseMsg"] = "No Data Available"
        #     return response_dict
        
        # elif self.date_status == "exist" :
            
        self.logStatus("info", "statement downloaded", self.takeScreenshot())

        response_dict["responseCode"] = "SRC001"
        response_dict["responseMsg"] = "Successfully Completed"
        return response_dict

    def closeDriver(self):
        self.driver.quit()


# if __name__ == '__main__':

#     mode = "Data Download"
#     bankName = "AXIS"
#     username = "870533284"
#     password = 'Rpp$1234567'
#     fromDate = "02-10-2014"
#     toDate = "02-10-2020"

#     axis1 = AxisStatement(refid="axisTesting", env='quality')

#     if mode == "Login Check":

#         response = axis1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             axis1.logout()
#         else:
#             axis1.driver_quit()

#     elif mode == "Data Download":
#         response = axis1.login(username, password)
#         print(response)
        
#         if response["responseCode"] == "SRC001":
#             response1 = axis1.getStatements(fromDate, toDate)
#             print(response1)

#             axis1.logout()

#         else:
#             axis1.driver_quit()

#     elif mode == "Both":
#         response = axis1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = axis1.getStatements(fromDate, toDate)
#             print(response1)

#             axis1.logout()

#         else:
#             axis1.driver_quit()