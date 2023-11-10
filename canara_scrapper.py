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
from selenium.webdriver.common.by import By
from datetime import date,  timedelta, datetime
import pandas as pd
from selenium.webdriver.support.ui import Select
from dateutil.relativedelta import relativedelta
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import calendar
from PIL import Image
import cv2
import pytesseract 
import os
import numpy as np
from pathlib import Path
import socket
import pytz


class CANARAStatement:

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

        pname = os.listdir("pdfs/")[0]

        pdfName = os.path.join(self.pdfDir, f"{pname}")

        self.uploadToS3(os.path.join(pdfName), 'pdfs/' + self.refid + "/" + pname)

        os.remove("pdfs/" + pname)

        return pname

    def logStatus(self, level, message, screenshot=None):
        IST = pytz.timezone('Asia/Kolkata')
        tm=str(datetime.now(IST))[:19]
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'CANARA', self.env,
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
    
    def canaracaptchlite(self, binPath=None):
        if binPath is not None:
            pytesseract.pytesseract.tesseract_cmd = binPath
        image = Image.open("screenshot.png")
        left = 591
        top = 450
        right = 790
        bottom = 498
        image = image.crop((left, top, right, bottom))
        image.save("screenshot.png")
        image = cv2.imread("screenshot.png")
        cap=pytesseract.image_to_string(image)
        
        if len(cap.split())!=0:
            try:
                print(f'CAPTCHA : {cap.split()[0]}')
                return cap.split()[0]
                
            except:
                print(f'CAPTCHA : {cap}')
                return cap

        return "ABC"

    def login(self, username, password, seml, smno):

        response_dict = {"referenceId": self.refid}

        while 1:

            self.driver.get("https://candi.canarabank.in/omnichannel/")
            time.sleep(2)
            self.logStatus("info", "open canara netbanking webpage", self.takeScreenshot())
            if self.check_exists_by_xpath('/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[1]/span[1]/span[1]/ul[2]/li[2]/span/input'):
                pass
            else:
                return {"referenceId":self.refid,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}       


            usernameInputField = self.driver.find_element_by_xpath("/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[1]/span[1]/span[1]/ul[2]/li[2]/span/input")
            usernameInputField.clear()
            usernameInputField.send_keys(username)

            PasswordField = self.driver.find_element_by_xpath('/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[1]/span[1]/span[2]/ul[2]/li[2]/span/input')
            PasswordField.clear()
            PasswordField.send_keys(password)

            self.driver.save_screenshot("screenshot.png")
            logincptch = self.driver.find_element_by_xpath('/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[1]/span[2]/span/ul[2]/li[2]/span/input')
            logincptch.clear()

            captcha=self.canaracaptchlite()

            if captcha=='':
                try:
                    print("chk1")
                    self.driver.find_element_by_xpath('/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[1]/span[3]/span[2]/ul/li[2]/button').click()
                except:
                    time.sleep(1)
                    print("chk2")
                    ul1 = self.driver.find_element_by_id("login__Login__el_icn_1_ul")
                    l1 = self.driver.find_element_by_id("login__Login__el_icn_1_li")
                    l1.find_element_by_id("login__Login__el_icn_1").click()

                time.sleep(1)
                self.driver.save_screenshot("screenshot.png")

            logincptch.send_keys(captcha)

            self.driver.find_element_by_xpath('/html/body/div[6]/div[1]/div/section/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]/div/div[2]/ul[2]/li[2]/button').click()
            time.sleep(3)
            if self.check_exists_by_xpath('/html/body/div[7]/div/div/nav/button'):
                
                print('here1')
                self.driver.find_element_by_xpath('/html/body/div[7]/div/div/nav/button').click()
            else:
                print('here')
                break
                
        try:
            if "Captcha" not in self.driver.find_element_by_class_name("msg").text and "Invalid" in self.driver.find_element_by_class_name("msg").text :
                self.driver.find_element_by_class_name("ok").click()

                self.logStatus("critical", "Incorrect UserName Or Password.", self.takeScreenshot())
                response_dict["responseCode"] = "EWC002"
                response_dict["responseMessage"] = "Incorrect UserName Or Password."
                return response_dict
        except Exception as e:
            print(e)
            pass
        
        self.logStatus("info", "successfully logged in", self.takeScreenshot())
        response_dict["responseCode"] = "SRC001"
        response_dict["responseMessage"] = "Successfully Completed"
        return response_dict

    def logout(self):
        try:
            self.driver.find_element_by_id("canara__LandingPage__el_btn_4").click()
            time.sleep(2)
            if "logout" in self.driver.find_element_by_class_name("dialog").text:
                self.driver.find_element_by_class_name("ok").click()
            self.logStatus("info", "logout successfully", self.takeScreenshot())
            return "successfull",{"referenceId":self.refid,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.refid,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def selectCalenderDate( self,day,  month, year, day_xpath, month_xpath, year_xpath, cal_id):

        self.driver.find_element_by_id(cal_id).click()

        yr = Select(self.driver.find_element_by_xpath(year_xpath))

        yr.select_by_visible_text(year)

        mnth = Select(self.driver.find_element_by_xpath(month_xpath))

        mnth.select_by_visible_text(month)

        dt = self.driver.find_element_by_xpath(day_xpath)
        dts = dt.find_elements_by_tag_name('tr')
        ext = False
        for i in dts:
    #         print(i)
            val = i.find_elements_by_tag_name('td')
            for j in val:
                if str(j.text) == day:
                    j.click()
                    ext = True
                    break
            if ext == True:
                break

    def downloadData(self, fromDate, toDate, accountno, seml, smno):

        response_dict = {"referenceId": self.refid}

        try:
            self.driver.find_element_by_id("dash__Dashboard__el_btn_3_0").click()
        except:
            self.driver.find_element_by_xpath('/html/body/div[6]/div[2]/div/section/div[10]/div/div/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/ul/li/span/span[2]/span[1]/button').click()
        time.sleep(2)

        try:
            self.driver.find_element_by_id("accsum__transactionHistoryFCDB__el_hpl_3_txtcnt").click()
        except:
            self.driver.find_element_by_xpath('/html/body/div[6]/div[2]/div/section/div[10]/div/div/div/div[3]/div/div/div[1]/div[2]/div/div/div[1]/ul/li[2]/span[1]/a/span').click()

        if len(fromDate)==7 and len(toDate)==7:
            tdy=calendar.monthrange(int(toDate[3:]),int(toDate[:2]))[1]
            fromDate='01'+"-"+fromDate
            toDate=str(tdy)+"-"+toDate

        fromDate = datetime.strptime(fromDate, '%d-%m-%Y')
        toDate = datetime.strptime(toDate, '%d-%m-%Y')

        if toDate.year>=datetime.now().year and toDate.month>=datetime.now().month:
            toDate=datetime.now()-timedelta(days=1)
        
        if (datetime.now() - relativedelta(months=6)) > fromDate and (datetime.now() - relativedelta(months=6)) > toDate:
            self.logStatus("info", "statement not exist", self.takeScreenshot())
            response_dict["responseCode"] = "END013"
            response_dict["responseMsg"] = "No Data Available"
            return response_dict
        
        fromCalId = "accsum__transactionHistoryFCDB__fromDate_button"
        toCalId  = "accsum__transactionHistoryFCDB__toDate_button"

        day_xpath = "/html/body/div[7]/table"
        month_xpath = "/html/body/div[7]/div/div/select[1]"
        year_xpath = "/html/body/div[7]/div/div/select[2]"
        
        if (datetime.now() - relativedelta(months=6)) > fromDate  :
            fromDate = (datetime.now() - relativedelta(months=6)) 
            
        print(fromDate)

        self.selectCalenderDate( str(fromDate.day),  fromDate.strftime("%b"), str(fromDate.year), day_xpath, month_xpath, year_xpath, fromCalId)
        self.selectCalenderDate( str(toDate.day),  toDate.strftime("%b"), str(toDate.year), day_xpath, month_xpath, year_xpath, toCalId)
        
        time.sleep(2)
        self.driver.find_element_by_id("accsum__transactionHistoryFCDB__el_icn_4").click()
        time.sleep(5)

        try:
            if  "downloaded" in self.driver.find_element_by_class_name("msg").text:
                self.driver.find_element_by_class_name("ok").click()
        except:
            pass
        
        try:
            time.sleep(2)
            if self.driver.find_element_by_class_name("msg").text == "No records found, to search again please amend your inputs" :
                print("no data available")
                self.driver.find_element_by_class_name("ok").click()
                
            self.logStatus("info", "statement not exist", self.takeScreenshot())
            response_dict["responseCode"] = "END013"
            response_dict["responseMsg"] = "No Data Available"
            return response_dict
        except:
            self.savePdf()
            self.logStatus("info", "pdf downloaded", self.takeScreenshot() )

            self.logStatus("info", "successfully logged in", self.takeScreenshot())
            response_dict["responseCode"] = "SRC001"
            response_dict["responseMsg"] = "Successfully Completed"
            return response_dict

    def closeDriver(self):
        self.driver.quit()

    def downlaod_captcha(self):

        self.driver.find_element_by_xpath(
            "/html/body/div/form/table/tbody/tr[1]/td[2]/a/img").click()
        time.sleep(2)

        self.driver.save_screenshot("captcha.png")
        image = Image.open("captcha.png")

        left = 428  # increase
        top = 245  # increase
        right = 628  # decrease
        bottom = 315  # decrease
        image = image.crop((left, top, right, bottom))  # defines crop points
        image.save("captcha.png")  # saves new cropped image

        image = cv2.imread('captcha.png')
        image = cv2.blur(image, (3, 3))
        ret, image = cv2.threshold(image, 90, 255, cv2.THRESH_BINARY)
        image = cv2.dilate(image, np.ones((2, 1), np.uint8))
        image = cv2.erode(image, np.ones((1, 2), np.uint8))
        cv2.imshow("1", np.array(image))
        cap = pt.image_to_string(image)
        print(cap.split("\n\x0c")[0])

        return cap.split("\n\x0c")[0]


# if __name__ == '__main__':

#     hdfc1 = CANARAStatement(refid="canaraTesting", env='quality')

#     mode = "Both"
#     bankName = "CANARA"
#     username = "127089468"
#     password = '.J@smita17.'
#     fromDate = "19-11-2017"
#     toDate = "09-11-2020"

#     if mode == "Login Check":

#         response = hdfc1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             hdfc1.logout()
#         else:
#             hdfc1.driver_quit()

#     elif mode == "Data Download":
#         response = hdfc1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = hdfc1.getStatements(fromDate, toDate)
#             print(response1)

#             hdfc1.logout()

#         else:
#             hdfc1.driver_quit()

#     elif mode == "Both":
#         response = hdfc1.login(username, password)
#         print(response)

#         if response["responseCode"] == "SRC001":
#             response1 = hdfc1.getStatements(fromDate, toDate)
#             print(response1)

#             hdfc1.logout()

#         else:
#             hdfc1.driver_quit()