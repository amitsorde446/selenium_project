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

#from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
from tessrct import kvcaptcha
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz
from webdriver_manager.chrome import ChromeDriverManager



class KVScrapper:
    
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
        self.url='https://www.kvbin.com/B001/ENULogin.jsp'
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

    def check_exists_by_name(self,nm):
        try:
            self.wait.until(EC.visibility_of_element_located((By.NAME, nm)))
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
                driver = webdriver.Chrome(ChromeDriverManager().install(),
                                      chrome_options=self.chromeOptions)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'KV', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName),  self.ref_id + "/" + "screenshot/"+sname)
        return sname

    def saving_pdf(self):
        d_lt=os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname),self.ref_id + "/"+"automated_pdf_files/"+ i)
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

        while 1:

            if self.check_exists_by_name('fldLoginUserId'):
                usernameInputField = self.driver.find_element_by_name('fldLoginUserId')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
                
            time.sleep(self.timeBwPage)

            PasswordField = self.driver.find_element_by_name('fldPassword')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())
            self.driver.save_screenshot("screenshot.png")
            
            time.sleep(self.timeBwPage)

            captchaInputField = self.driver.find_element_by_id('fldcaptcha')
            captchaInputField.clear()
            self.driver.find_element_by_id("""TuringImage""").screenshot("captcha.png")
            captchaInputField.send_keys(kvcaptcha()) 
            self.logStatus("info", "captcha entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)
                
            btns=self.driver.find_elements_by_id('NewUser')
            for btn in btns:
                if 'Login' in btn.text:
                    btn.click()
                    self.logStatus("info", "login button clicked", self.takeScreenshot())
                    break    
                    
            self.driver.switch_to_window(self.driver.window_handles[-1])      

            time.sleep(self.timeBwPage)

            if self.check_exists_by_classname('LogoutTable'):
                errormsg=self.driver.find_element_by_class_name('LogoutTable')
                print(errormsg.text)
                
                if 'Invalid Captcha' in errormsg.text:
                    self.logStatus("debug", "invalid captcha", self.takeScreenshot())
                    self.driver.find_element_by_name('fldSubmit').click()
                    self.driver.switch_to_window(self.driver.window_handles[0])
                    continue
                    
                elif 'Invalid User ID / Password' in errormsg.text:
                    self.driver.find_element_by_name('fldSubmit').click()
                    self.driver.switch_to_window(self.driver.window_handles[0])
                    self.logStatus("error", "invalid credentials", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."} 
            else:
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}                

    def calenderSelector(self,day,month,year):

        if self.check_exists_by_classname('ui-datepicker-year'):

            yearselect=Select(self.driver.find_element_by_class_name('ui-datepicker-year'))
            for opt in list(map(lambda x:x.text,yearselect.options)):
                if year in opt:
                    yearselect.select_by_visible_text(year)
                    self.logStatus("info", "year selected", self.takeScreenshot())
                    break

            mnthselect=Select(self.driver.find_element_by_class_name('ui-datepicker-month'))
            for opt in list(map(lambda x:x.text,mnthselect.options)):
                if month in opt:
                    mnthselect.select_by_visible_text(month)
                    self.logStatus("info", "month selected", self.takeScreenshot())
                    break

            dytable=self.driver.find_element_by_class_name('ui-datepicker-calendar')
            dytbody=dytable.find_element_by_tag_name('tbody')
            dyrows=dytbody.find_elements_by_tag_name('tr')
            dylst=list(map(lambda x:x.text,dyrows))
            selected,start=False,False 
            for i in dyrows:
                cols=i.find_elements_by_tag_name('td')
                for j in cols:
                    if str(j.text)=='1' and start==False:
                        start=True
                    if str(j.text)==str(day) and start==True:
                        j.click()
                        selected=True
                        self.logStatus("info", "day selected", self.takeScreenshot())
                        break
                if selected==True:
                    selected=False
                    break

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame('frame_menu')

        time.sleep(self.timeBwPage)

        if self.check_exists_by_id('RRAAClink'):
            self.driver.find_element_by_id('RRAAClink').click()

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame('frame_txn')

        time.sleep(self.timeBwPage)

        acn=''
        if self.check_exists_by_name('fldacctno'):

            bankacc=Select(self.driver.find_element_by_name('fldacctno'))

            for accno in list(map(lambda x:x.text,bankacc.options)):
                if accountno in accno:
                    acn=accno
                    bankacc.select_by_visible_text(acn)
                    self.logStatus("info", "Account selected", self.takeScreenshot())
                    break

        if acn=='':

            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

        else:

            searchBy=Select(self.driver.find_element_by_name('fldsearch'))

            for opt in list(map(lambda x:x.text,searchBy.options)):
                if 'Specify Period' in opt:
                    searchBy.select_by_visible_text('Specify Period')
                    self.logStatus("info", "info search by selected", self.takeScreenshot())
                    break

            if len(fromdate)==7 and len(todate)==7:
                tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
                fromdate='01'+"-"+fromdate
                todate=str(tdy)+"-"+todate

            fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
            todate=datetime.strptime(todate, '%d-%m-%Y')

            fdlmt=datetime.strptime('01-04-2018', '%d-%m-%Y')

            if fromdate<fdlmt:
                fromdate=fdlmt

            if todate.year>=datetime.now().year and todate.month>=datetime.now().month:
                todate=datetime.now()-timedelta(days=1)

            time.sleep(self.timeBwPage)

            print(f'FROM DATE : {fromdate} TO DATE : {fromdate}')

            fday=str(fromdate.day)
            fmonth=fromdate.strftime('%b')
            fyear=str(fromdate.year)
            tday=str(todate.day)
            tmonth=todate.strftime('%b')
            tyear=str(todate.year)

            # FROM DATE SET

            self.driver.find_element_by_name('anchor').click()
            time.sleep(self.timeBwPage)
            self.logStatus("info", "from date popup opened", self.takeScreenshot())
            self.calenderSelector(fday,fmonth,fyear)
            self.logStatus("info", "from date entered", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            # TO DATE SET

            self.driver.find_element_by_name('anchor1').click()
            time.sleep(self.timeBwPage)
            self.logStatus("info", "to date popup opened", self.takeScreenshot())
            self.calenderSelector(tday,tmonth,tyear)
            self.logStatus("info", "to date entered", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_name('fldsubmit').click()
            self.logStatus("info", "search btn clicked", self.takeScreenshot())

            time.sleep(5)

            docFrmt=Select(self.driver.find_element_by_name('fldsearchformat'))

            for opt in list(map(lambda x:x.text,docFrmt.options)):
                if 'PDF' in opt:
                    docFrmt.select_by_visible_text(opt)
                    self.logStatus("info", "pdf format selected", self.takeScreenshot())
                    break
            time.sleep(self.timeBwPage)

            dwnldField=self.driver.find_element_by_name('flddownload')
            dwnldField.click()
            self.logStatus("info", "download btn clicked", self.takeScreenshot())
            
            time.sleep(5)
            
        dic=self.saving_pdf()
        return dic
    
    def logout(self):

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame('frame_top')

        try:
            anchortags=self.driver.find_elements_by_tag_name('a')
            for atg in anchortags:
                if 'Logout' in atg.text:
                    atg.click()
                    break
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_name('fldSubmit').click()
            self.driver.switch_to_window(self.driver.window_handles[0])

            self.logStatus("info", "Logout successful", self.takeScreenshot())
            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessful", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     # print(f'RefID : {str(uuid.uuid1())}')
#     obj=KVScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('15275384','Password1','','')
#     print(opstr)
#     res=obj.downloadData('01-01-2020','19-06-2021','4201155000130210','','')
#     a,b=obj.logout()
#     obj.closeDriver()