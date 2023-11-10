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
from datetime import datetime,timedelta
from tessrct import bomcaptcha
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz

class BOMScrapper:
    
    def __init__(self,refid, timeBwPage=2,env='dev',mode='local'):
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
        self.url='https://www.mahaconnect.in/InternetBanking1/ib/login.jsf?lt=R'
        self.driver = self.createDriver(mode='headless')
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
            self.chromeOptions.add_argument("--disable-infobars")
            self.chromeOptions.add_argument("--disable-popup-blocking")
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'BOM', self.env,
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
        print(f'Files : {d_lt}')
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), 'pdfs/' + self.ref_id + "/" + i)
            self.logStatus("info", "pdf downloaded")
        if len(d_lt)>0:
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self,username,password,seml,smno):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        while 1:

            if self.check_exists_by_xpath('/html/body/div[2]/div/div/form[1]/div[2]/div[2]/table/tbody/tr[1]/td[3]/input'):
                usernameInputField = self.driver.find_element_by_xpath('/html/body/div[2]/div/div/form[1]/div[2]/div[2]/table/tbody/tr[1]/td[3]/input')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

            time.sleep(self.timeBwPage)

            PasswordField = self.driver.find_element_by_xpath('/html/body/div[2]/div/div/form[1]/div[2]/div[2]/table/tbody/tr[2]/td[3]/input')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "Password entered", self.takeScreenshot())

            self.driver.save_screenshot("screenshot.png")
            logincptch = self.driver.find_element_by_xpath('/html/body/div[2]/div/div/form[1]/div[2]/div[2]/table/tbody/tr[5]/td[3]/input')
            logincptch.clear()
            logincptch.send_keys(bomcaptcha())
            self.logStatus("info", "captcha entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            self.driver.find_element_by_xpath('/html/body/div[2]/div/div/form[1]/div[2]/div[2]/div/table/tbody/tr/td[1]/button').click()
            time.sleep(self.timeBwPage)
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            if self.check_exists_by_xpath('/html/body/div[2]/div/div/form[1]/div[1]/div'):
                msg=self.driver.find_element_by_xpath('/html/body/div[2]/div/div/form[1]/div[1]/div').text
                if 'Wrong Captcha Entered' in msg:
                    self.logStatus("debug", "wrong captcha break", self.takeScreenshot())
                elif 'Invalid Login Credentials' in msg:
                    self.logStatus("error", "username or password invalid", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                elif 'Your last session was terminated incorrectly or is currently active' in msg:
                    self.logStatus("error", "Account already opened somewhere", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
            else:
                self.logStatus("info", "login successfull", self.takeScreenshot())

                if self.check_exists_by_xpath('/html/body/form/table/tbody/tr[5]/td/table/tbody/tr/td[1]/table/tbody/tr[2]/td[2]'):
                    chckmsg=self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[5]/td/table/tbody/tr/td[1]/table/tbody/tr[2]/td[2]').text
                    if 'You have been enrolled for MahaSecure' in chckmsg:
                        self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[18]/td/table/tbody/tr/td[1]/a').click() 

                return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)
    
        self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[1]/div/ul/li[2]/a').click()
        time.sleep(self.timeBwPage)
        self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[2]/div/ul/li[3]/a').click()
        time.sleep(self.timeBwPage)
        bankacc=Select(self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[3]/div/div[2]/div[2]/fieldset/div/table/tbody/tr[1]/td[3]/select'))

        acn=''
        for accno in list(map(lambda x:x.text,bankacc.options)):
            if accountno in accno:
                acn=accno
                break
            
        if acn=='':
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
        else:
            bankacc.select_by_visible_text(acn)

            time.sleep(self.timeBwPage)

            if len(fromdate)==7 and len(todate)==7:
                tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
                fromdate='01'+"-"+fromdate
                todate=str(tdy)+"-"+todate

            fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
            todate=datetime.strptime(todate, '%d-%m-%Y')

            if todate.year>=datetime.now().year and todate.month>=datetime.now().month:
                todate=datetime.now()-timedelta(days=1)

            dt_lst=[]
            date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'),end=todate.strftime('%m-%d-%Y'),freq=pd.DateOffset(months=2),closed=None).to_list()
            for ind1 in range(len(date_list)):
                if ind1>0:
                    st = date_list[ind1-1]
                    ed = date_list[ind1] - timedelta(days=1)
                    dt_lst.append([str(st)[:10],str(ed)[:10]])
            if len(dt_lst)>0 and todate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d') :
                st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
                ed = todate
                dt_lst.append([str(st)[:10],str(ed)[:10]])
            elif len(dt_lst)==0:
                dt_lst.append([fromdate.strftime('%Y-%m-%d'),todate.strftime('%Y-%m-%d')])

            print(f'Date list : {dt_lst}')

            for dts in dt_lst:
                fd=datetime.strptime(dts[0], '%Y-%m-%d').strftime('%d/%m/%Y')
                td=datetime.strptime(dts[1], '%Y-%m-%d').strftime('%d/%m/%Y')

                fromdatefield = self.driver.find_element_by_xpath("/html/body/form/div[3]/div/div/div[3]/div/div[2]/div[2]/fieldset/div/table/tbody/tr[4]/td[3]/span/input")
                fromdatefield.clear()
                fromdatefield.send_keys(fd)
                self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[3]/div/div[2]/div[2]/fieldset/div/table/tbody/tr[2]/td[1]/label').click()
                self.logStatus("info", "from date selected", self.takeScreenshot())

                time.sleep(self.timeBwPage)
                todatefield = self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[3]/div/div[2]/div[2]/fieldset/div/table/tbody/tr[5]/td[3]/span/input')
                todatefield.clear()
                todatefield.send_keys(td)
                self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[3]/div/div[2]/div[2]/fieldset/div/table/tbody/tr[2]/td[1]/label').click()
                self.logStatus("info", "to date selected", self.takeScreenshot())

                time.sleep(self.timeBwPage)
                self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[3]/div/table/tbody/tr/td[2]/span/button').click()
                time.sleep(self.timeBwPage)
                self.driver.find_element_by_xpath('/html/body/div[10]/ul/li[1]/a').click()
                self.logStatus("info", "pdf download button clicked", self.takeScreenshot())
                time.sleep(self.timeBwPage)

        dic=self.saving_pdf()
        return dic

    def logout(self):
        try:
            time.sleep(self.timeBwPage)
            self.driver.find_element_by_xpath('/html/body/form/div[2]/div[2]/div/table/tbody/tr/td[5]/a').click()
            if self.check_exists_by_id('mainform:skipAndlogout'):
                time.sleep(5)
                self.driver.find_element_by_id('mainform:skipAndlogout').click()
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
#     obj=BOMScrapper('testing')
#     opstr=obj.login('40223168984','S@ensible7')
#     res=obj.downloadData('26-10-2020','24-11-2020','60373009024')
#     a,b=obj.logout()
#     obj.closeDriver()