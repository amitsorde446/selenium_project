import os
from webdriver_manager.chrome import ChromeDriverManager
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
from datetime import datetime,timedelta

#from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from PIL import Image
import cv2
import pytesseract as pt
import os
import numpy as np
from pathlib import Path
import pytz


class PUNJABSINDHScrapper:
    
    def __init__(self,refid, timeBwPage=2,env='quality',mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        hostname = socket.gethostname()    
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.ref_id = refid
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots/"+self.ref_id)
        self.pdfDir = os.path.join(os.getcwd(), "pdfs/"+self.ref_id)
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath='/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        
        self.login_page_xp       = "/html/body/div[4]/div/div[2]/div[2]/div/div/p[1]/span/a"
        self.user_id_xp          = "/html/body/jsp:forward/form/table[1]/tbody/tr/td/table[3]/tbody/tr[2]/td[1]/table/tbody/tr/td/table[1]/tbody/tr[2]/td[2]/input"
        self.password_xp         = "/html/body/jsp:forward/form/table[1]/tbody/tr/td/table[3]/tbody/tr[2]/td[1]/table/tbody/tr/td/table[1]/tbody/tr[3]/td[2]/input"
        self.login_button_xp     = "/html/body/jsp:forward/form/table[1]/tbody/tr/td/table[3]/tbody/tr[2]/td[1]/table/tbody/tr/td/table[1]/tbody/tr[7]/td[2]/input"

        self.accounts_xp         = "/html/body/table[3]/tbody/tr/td[1]/a"

        self.statement_option_xp = "/html/body/p/table/tbody/tr/td[2]/form/table[3]/tbody/tr[2]/td[2]/select"

        self.go_xp = "/html/body/p/table/tbody/tr/td[2]/form/table[3]/tbody/tr[2]/td[3]/input"

        self.from_Date_xp = "/html/body/p/table/tbody/tr/td[2]/form/center[3]/center[2]/table[1]/tbody/tr[1]/td[3]/div/input"

        self.to_Date_xp = "/html/body/p/table/tbody/tr/td[2]/form/center[3]/center[2]/table[1]/tbody/tr[1]/td[5]/div/input"

        self.select_pdf_xp = "/html/body/p/table/tbody/tr/td[2]/form/center[3]/center[2]/table[3]/tbody/tr[2]/td/div/input[4]"

        self.statement_xp = "/html/body/p/table/tbody/tr/td[2]/form/center[3]/center[2]/center/input[1]"

        self.save_pdf_xp = "/html/body/p/table/tbody/tr/td[2]/form/center[2]/input[2]"

        self.logout_xp = "/html/body/table[1]/tbody/tr/td[3]/input"

        self.accounts_table_xp = "/html/body/p/table/tbody/tr/td[2]/form/table[5]"
        self.date_status = "notExist"


        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,10)


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

    def check_exists_by_xpath(self,xpath):
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        except:
            return False
        return True

    def check_exists_by_classname(self,classname):
        try:
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, xclassnamepath)))
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
        driver = webdriver.Chrome(ChromeDriverManager.install(), chrome_options=self.chromeOptions)

        try:
            driver = webdriver.Chrome(ChromeDriverManager.install(), chrome_options=self.chromeOptions)
            driver.maximize_window()
        except:
            pass
        #self.logStatus("info", "Driver created")
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'PUNJABSINDH', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), self.ref_id + "/" + "screenshot/"+sname)
        return sname

    def saving_pdf(self):
        d_lt=os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname),self.ref_id + "/"+"automated_pdf_files/"+ i)
            self.logStatus("info", "pdf downloaded")

    def login_captcha(self):
        
        # self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[3].find_elements_by_tag_name("td")[2].find_element_by_tag_name('input').click()
        # self.driver.save_screenshot("captcha.png")
        # image = Image.open("captcha.png")
        #
        # left = 320  # increase
        # top = 250  # increase"
        # right = 530  # decrease
        # bottom = 295  # decrease
        # image = image.crop((left, top, right, bottom))  # defines crop points
        # image.save("captcha.png")  # saves new cropped image
        time.sleep(2)
        self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[3].find_elements_by_tag_name("td")[1].screenshot("captcha.png")
        from azcaptchaapi import AZCaptchaApi
        api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
        with open("captcha.png", 'rb') as captcha_file:
            captcha = api.solve(captcha_file)
        cap = captcha.await_result()
        caplst=[]
        for i in list(cap):
            if i.isalpha():
                caplst.append(i.upper())
            else:
                caplst.append(i)
        cap=''.join(caplst)
        print(f'CAPTCHA : {cap}')
        return cap

    def login(self,username,password,seml,smno):

        try:
            self.driver.get("https://punjabandsindbank.co.in/")
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
        self.driver.find_element_by_xpath("""/html/body/div[3]/div[1]/span""").click()
        time.sleep(2)
        self.driver.find_element_by_xpath("""/html/body/div[3]/a/div[1]/span""").click()
        time.sleep(2)
        a = self.driver.find_element_by_xpath("""/html/body/div[3]/a/div""")
        b = a.find_element_by_xpath("""/html/body/div[3]/a/div/span""").click()
        time.sleep(2)
        self.driver.find_element_by_xpath("""/html/body/div[2]/div[2]/div/nav/ul/li[21]/a""").click()
        time.sleep(2)
        self.driver.find_element_by_xpath("""/html/body/div[2]/div[2]/div/nav/ul/li[21]/ul/li[1]/a""").click()
        time.sleep(2)

        self.driver.find_element_by_xpath(self.login_page_xp).click()

        time.sleep(1)
        self.driver.switch_to_window(self.driver.window_handles[-1]) 
        time.sleep(1)

        while True:
            print("inside while")
            
            cap = self.login_captcha()

            while len(cap)<5:
                cap = self.login_captcha()

            time.sleep(1)
            user_id = self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[1].find_elements_by_tag_name("td")[1].find_element_by_tag_name("input")
            user_id.clear()
            user_id.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
            time.sleep(1)
            pass_word = self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[2].find_elements_by_tag_name("td")[1].find_element_by_tag_name("input")
            pass_word.clear()
            pass_word.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())
            time.sleep(1)
            captcha_input = self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[4].find_elements_by_tag_name("td")[1].find_element_by_tag_name("input")
            captcha_input.clear()
            captcha_input.send_keys(cap)
            self.logStatus("info", "captcha entered", self.takeScreenshot())
            time.sleep(1)
            self.driver.find_elements_by_tag_name("table")[5].find_elements_by_tag_name("tr")[6].find_elements_by_tag_name("td")[1].find_element_by_tag_name("input").click()

            try:
                alert=self.driver.switch_to_alert()
                print(alert.text)
                # print("1")
                if "Invalid Login" in alert.text:
                    self.logStatus("critical", "invalid credentials")
                    alert.accept()
                    self.driver.switch_to_default_content()
                    
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                # print("2")
                if "Invalid Captcha" in alert.text:
                    # print("5555")
                    self.logStatus("info", "captcha entered")
                    # print("after logStatus")
                    alert.accept()
                    # print("after alert")
                    self.driver.switch_to_default_content()
                    # print("after driver")
                # print("3")
            except Exception as e:
                # print("4")
                # print("Invalid Captcha" in alert.text)
                print(f'Alert box : {e}')
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
            
    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        if len(fromdate)==7 and len(todate)==7:
            tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
            fromdate='01'+"-"+fromdate
            todate=str(tdy)+"-"+todate

        fromdate=datetime.strptime(fromdate, '%d-%m-%Y').strftime('%d/%m/%Y')
        todate=datetime.strptime(todate, '%d-%m-%Y').strftime('%d/%m/%Y')

        fromdate = fromdate[:6] + fromdate[-2:]
        todate   = todate[:6] + todate[-2:]

        self.driver.switch_to_window(self.driver.window_handles[-1]) 
        time.sleep(1)

        self.logStatus("info", "select accounts option", self.takeScreenshot())
        self.driver.find_element_by_xpath(self.accounts_xp).click()
        time.sleep(10)

        # acc_status=0
        # 
        # for row1 in self.driver.find_element_by_xpath(self.accounts_table_xp).find_element_by_tag_name("tbody").find_elements_by_tag_name("tr"):
        # 
        #     if accountno in row1.find_elements_by_tag_name("td")[3].text:
        #         
        #         row1.find_elements_by_tag_name("td")[2].click()
        #         acc_status +=1
        #         break
        # 
        # if acc_status==0:
        #     return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
        try:
            self.driver.find_element_by_xpath("""/html/body/p/table/tbody/tr/td[2]/form/table[5]/tbody/tr[2]/td[3]""").click()
        except:
            return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}
        time.sleep(3)
        self.logStatus("info", "select statement option", self.takeScreenshot())  
        statement_option = Select(self.driver.find_element_by_xpath(self.statement_option_xp))

        self.logStatus("info", "select detailed statement", self.takeScreenshot())
        statement_option.select_by_visible_text("Detailed Statement")

        self.logStatus("info", "click on go button", self.takeScreenshot())
        self.driver.find_element_by_xpath(self.go_xp).click()

        from_Date = self.driver.find_element_by_xpath(self.from_Date_xp)
        from_Date.clear()
        from_Date.send_keys(fromdate)
        self.logStatus("info", "entered from date", self.takeScreenshot())

        to_Date = self.driver.find_element_by_xpath(self.to_Date_xp)
        to_Date.clear()
        to_Date.send_keys(todate)
        self.logStatus("info", "entered to date", self.takeScreenshot())

        ### select pdf format
        self.logStatus("info", "select format", self.takeScreenshot())
        self.driver.find_element_by_xpath(self.select_pdf_xp).click()

        ### click statement
        self.logStatus("info", "click statement", self.takeScreenshot())
        self.driver.find_element_by_xpath(self.statement_xp).click()

        try:
            alert=self.driver.switch_to_alert()
            print(alert.text)
            if "No records fetched" in alert.text:
                alert.accept()
                self.driver.switch_to_default_content()
        except Exception as e:
            print(f'Alert box : {e}')
            self.date_status = "exist"   
            
        if self.date_status == "notExist":
            self.logStatus("info", "data not exist")
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}
        
        elif self.date_status == "exist" :

            #### save as pdf format
            self.logStatus("info", "save as pdf format", self.takeScreenshot())
            self.driver.find_element_by_xpath(self.save_pdf_xp).click()

            time.sleep(5)
            self.saving_pdf()
            
            self.logStatus("info", "statement downloaded", self.takeScreenshot())

            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed"}

    def logout(self):
        ### logout 
        try:
            self.driver.switch_to_window(self.driver.window_handles[-1]) 
            self.driver.find_element_by_xpath(self.logout_xp).click()
            
            self.logStatus("info", "logout successfull", self.takeScreenshot())
            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}



    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#
#     username = "014044679"
#     password = "S@ensible7"
#     accountno   = "1144100000513890"
#
#
#     obj=PUNJABSINDHScrapper('punjab_sindh_test')
#     opstr=obj.login(username,password,"","")
#     if opstr["responseCode"]=='SRC001':
#         res=obj.downloadData('01-09-2010','01-12-2020',accountno,"","")
#         print(res)
#         a,b=obj.logout()
#         obj.closeDriver()