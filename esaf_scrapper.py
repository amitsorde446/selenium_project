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
from dateutil.relativedelta import relativedelta
from datetime import datetime,timedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class ESAFScrapper:
    
    def __init__(self,refid, timeBwPage=2,env='dev',mode='headless'):
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
        self.url='https://netbanking.esafbank.com/RIB/?pc=Personal#/'
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
    
    def check_exists_by_id(self,idd):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, idd)))
        except:
            return False
        return True

    def check_exists_by_classname(self,clsnm):
        try:
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, clsnm)))
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'ESAF', self.env,
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
        d_lt=os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), 'pdfs/' + self.ref_id + "/" + i)
        if len(d_lt)>0:
            self.logStatus("info", "pdfs downloaded")
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            self.logStatus("info", "no pdf downloaded")
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self,username,password,seml,smno):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        if self.check_exists_by_id('username'):
            usernameInputField = self.driver.find_element_by_id('username')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
            
        time.sleep(self.timeBwPage)

        btnlst=self.driver.find_elements_by_tag_name('button')
        for i in btnlst:
            if 'CONTINUE TO LOGIN'.lower() in i.text.lower():
                i.click()
                break

        time.sleep(self.timeBwPage)

        PasswordField = self.driver.find_element_by_id('password')
        PasswordField.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('isSecChecked'):
            chcklst=self.driver.find_elements_by_tag_name('label')
            for i in chcklst:
                if i.get_attribute('for')=='isSecChecked':
                    i.click()
                    self.logStatus("info", "check box clicked", self.takeScreenshot())
                    break

        time.sleep(self.timeBwPage)

        btnlst=self.driver.find_elements_by_tag_name('button')

        for i in btnlst:
            if 'LOGIN'.lower() in i.text.lower():
                i.click()
                break
        self.logStatus("info", "login button clicked", self.takeScreenshot())

        if self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div/div[3]/div[2]/div[2]/div/span'):
            errormsg=self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div/div[3]/div[2]/div[2]/div/span')
            print(errormsg.text)
            if 'Invalid User id or Password' in errormsg.text:
                self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
 
        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}                

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        if len(fromdate)==7 and len(todate)==7:
            tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
            fromdate='01'+"-"+fromdate
            todate=str(tdy)+"-"+todate

        fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
        todate=datetime.strptime(todate, '%d-%m-%Y')

        if todate.year>=datetime.now().year and todate.month>=datetime.now().month:
            todate=datetime.now()-timedelta(days=1)

        self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[1]/div/div/div/ul/li[3]/a').click()

        time.sleep(self.timeBwPage)

        self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[1]/div/div/div/ul/li[3]/ul/li[5]/a').click()

        time.sleep(self.timeBwPage)

        acctyp=Select(self.driver.find_element_by_name('accountType'))
        for acty in list(map(lambda x:x.text,acctyp.options)):
            if 'Savings Account' == acty:
                acctyp.select_by_visible_text('Savings Account')
                break

        acc=''
        accnos=Select(self.driver.find_element_by_name('account'))
        for acc in list(map(lambda x:x.text,accnos.options)):
            if accountno in acc:
                accnos.select_by_visible_text(acc)
                acc='Found'
                self.logStatus("info", "Account selected", self.takeScreenshot())
                break
                
        if acc=='':
            
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
        
        else:
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/div[1]/div[2]/form/div[3]/div[1]/label/span/span').click()
            self.logStatus("info", "By date range selected", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            FromDate = self.driver.find_element_by_name('fromDate')
            FromDate.clear()
            FromDate.send_keys(fromdate.strftime('%d/%m/%Y'))  
            self.logStatus("info", "from date entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            ToDate = self.driver.find_element_by_name('toDate')
            ToDate.clear()
            ToDate.send_keys(todate.strftime('%d/%m/%Y'))
            self.logStatus("info", "to date entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/div[1]/div[2]/form/div[4]/button[1]').click()
            self.logStatus("info", "Search button clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            if self.check_exists_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/div[2]/div[2]/div[1]/div[2]'):
                errormsg=self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/div[2]/div[2]/div[1]/div[2]')
                if 'No records found' in errormsg.text:
                    self.logStatus("info", "No data for this date range", self.takeScreenshot())
            else:
                printtype=Select(self.driver.find_element_by_name('printTypeDropdown'))
                for ptyp in list(map(lambda x:x.text,printtype.options)):
                    if 'PDF' in ptyp:
                        printtype.select_by_visible_text('PDF')
                        break
                self.driver.find_element_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div[2]/div[2]/div[1]/div/button').click()
                self.logStatus("info", "data found for this date range", self.takeScreenshot())
                time.sleep(20)

            dic=self.saving_pdf()
            return dic
    
    def logout(self):

        if self.check_exists_by_xpath('/html/body/div[1]/div[1]/div/div/div[2]/ul/li[3]/a'):
            self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div/div/div[2]/ul/li[3]/a').click()
            self.logStatus("info", "Logout button clicked", self.takeScreenshot())
            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        else:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     # print(f'RefID : {str(uuid.uuid1())}')
#     obj=ESAFScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('sonu9213','Ril@54321','','')
#     print(opstr)
#     res=obj.downloadData('01-09-2017','07-01-2021','53200000730521','','')
#     a,b=obj.logout()
#     obj.closeDriver()