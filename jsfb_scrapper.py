import os
import shutil
import time
from botocore.exceptions import ClientError
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from datetime import datetime,timedelta
from google_captcha import captchabreak1
from dateutil.relativedelta import relativedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class JSFBScrapper:
    
    def __init__(self,refid, timeBwPage=3,env='quality',mode='headless'):
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
        self.url='https://ebanking.janabank.com/ib-retail-web/tenant/index'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,20)

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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'JSFB', self.env,
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
        if len(d_lt)>0:
            self.logStatus("info", "pdf downloaded")
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            self.logStatus("info", "No data Available")
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self,username,password,seml,smno):

        while 1:

            try:
                self.driver.get(self.url)
                self.logStatus("info", "website opened", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

            if self.check_exists_by_id('loginusername'):
                usernameInputField = self.driver.find_element_by_id('loginusername')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
                
            PasswordField = self.driver.find_element_by_id('loginpwd1')
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            lgnbtn = self.driver.find_element_by_id('loginSubmit')
            lgnbtn.click()
            self.logStatus("info", "login btn 1 clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            
            if self.check_exists_by_id('ValidatePreloginErr'):
                errromsg=self.driver.find_element_by_id('ValidatePreloginErr')
                print(errromsg.text)
                if 'Incorrect user name or Password' in errromsg.text:
                    self.logStatus("error", "incorrect username", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                if 'Incorrect Login ID or Password' in errromsg.text:
                    self.logStatus("error", "incorrect password", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

            self.driver.save_screenshot("screenshot.png")
            logincptch = self.driver.find_element_by_id('txtCaptcha')
            logincptch.clear()
            self.driver.find_element_by_xpath("""//*[@id="captchaimgdiv"]""").screenshot("captcha.png")
            logincptch.send_keys(captchabreak1())

            # try:
            #     logincptch.send_keys(captchabreak1())
            # except:
            #     self.logStatus("debug", "google captcha error", self.takeScreenshot())
            #     continue
            self.logStatus("info", "captcha entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            lgnbtn = self.driver.find_element_by_id('loginSubmit')
            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            try:
                name = self.driver.find_element_by_xpath("""//*[@id="ValidateCaptchaErr"]""").text
                if name == "Please Enter Correct Captcha":
                    logincptch = self.driver.find_element_by_id('txtCaptcha')
                    logincptch.clear()
                    self.driver.find_element_by_xpath("""//*[@id="captchaimgdiv"]""").screenshot("captcha.png")
                    logincptch.send_keys(captchabreak1())
                    time.sleep(self.timeBwPage)

                    lgnbtn = self.driver.find_element_by_id('loginSubmit')
                    lgnbtn.click()

                    time.sleep(self.timeBwPage)

                    name = self.driver.find_element_by_xpath("""//*[@id="ValidateCaptchaErr"]""").text
                    if name == "Please Enter Correct Captcha":
                        logincptch = self.driver.find_element_by_id('txtCaptcha')
                        logincptch.clear()
                        self.driver.find_element_by_xpath("""//*[@id="captchaimgdiv"]""").screenshot("captcha.png")
                        logincptch.send_keys(captchabreak1())
                        time.sleep(self.timeBwPage)
                        lgnbtn = self.driver.find_element_by_id('loginSubmit')
                        lgnbtn.click()
                        time.sleep(self.timeBwPage)
                        name = self.driver.find_element_by_xpath("""//*[@id="ValidateCaptchaErr"]""").text
                        if name == "Please Enter Correct Captcha":
                            logincptch = self.driver.find_element_by_id('txtCaptcha')
                            logincptch.clear()
                            self.driver.find_element_by_xpath("""//*[@id="captchaimgdiv"]""").screenshot("captcha.png")
                            logincptch.send_keys(captchabreak1())
                            time.sleep(self.timeBwPage)
                            lgnbtn = self.driver.find_element_by_id('loginSubmit')
                            lgnbtn.click()
                            time.sleep(self.timeBwPage)
                            name = self.driver.find_element_by_xpath("""//*[@id="ValidateCaptchaErr"]""").text
                            if name == "Please Enter Correct Captcha":
                                logincptch = self.driver.find_element_by_id('txtCaptcha')
                                logincptch.clear()
                                self.driver.find_element_by_xpath("""//*[@id="captchaimgdiv"]""").screenshot(
                                    "captcha.png")
                                logincptch.send_keys(captchabreak1())
                                time.sleep(self.timeBwPage)
                                lgnbtn = self.driver.find_element_by_id('loginSubmit')
                                lgnbtn.click()
                                time.sleep(self.timeBwPage)
            except:
                pass
            if self.check_exists_by_id('ValidateCaptchaErr'):
                putxt=self.driver.find_element_by_id('ValidateCaptchaErr')
                print(putxt.text)
                if 'Please Enter Correct Captcha' in putxt.text:
                    self.logStatus("debug", "incorrect captcha", self.takeScreenshot())
                    continue
                else:
                    self.logStatus("info", "correct captcha", self.takeScreenshot())
                    break
            else:
                self.logStatus("info", "correct captcha", self.takeScreenshot())
                break
 
        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}

    def dateselector(self,yer,mon,da):
        dttable=self.driver.find_element_by_class_name('table-condensed')
        dttable.find_element_by_tag_name('thead').find_elements_by_tag_name('tr')[1].find_elements_by_tag_name('th')[1].click()
        
        # YEAR SELECTOR
        
        dtyear=self.driver.find_element_by_class_name('datepicker-months').find_element_by_class_name('table-condensed')
        dtyear.find_element_by_tag_name('thead').find_elements_by_tag_name('tr')[1].find_elements_by_tag_name('th')[1].click()
        
        dtyears=self.driver.find_element_by_class_name('datepicker-years')
        dytbody=dtyears.find_element_by_tag_name('tbody')
        tyrow=dytbody.find_element_by_tag_name('tr')
        tyval=tyrow.find_element_by_tag_name('td')
        yrs=tyval.find_elements_by_tag_name('span')
        for yr in yrs:
            if (yr.text==yer) and ('disabled' not in yr.get_attribute('class')):
                yr.click()
                self.logStatus("info", "year selected", self.takeScreenshot())
                break
            elif (yr.text==yer) and ('disabled' in yr.get_attribute('class')):
                self.logStatus("error", "date not available", self.takeScreenshot())
                return 'not selected'
        
        # MONTH SELECTOR
        
        dtmonths=self.driver.find_element_by_class_name('datepicker-months')
        dmtbody=dtmonths.find_element_by_tag_name('tbody')
        tmrow=dmtbody.find_element_by_tag_name('tr')
        tmval=tmrow.find_element_by_tag_name('td')
        mnths=tmval.find_elements_by_tag_name('span')
        
        for mnth in mnths:
            if (mnth.text==mon) and ('disabled' not in mnth.get_attribute('class')):
                mnth.click()
                self.logStatus("info", "month selected", self.takeScreenshot())
                break
            elif (mnth.text==mon) and ('disabled' in mnth.get_attribute('class')):
                self.logStatus("error", "date not available", self.takeScreenshot())
                return 'not selected'
                
        # DAY SELECTOR
        
        dtdays=self.driver.find_element_by_class_name('datepicker-days')
        ddtbody=dtdays.find_element_by_tag_name('tbody')
        tdrow=ddtbody.find_elements_by_tag_name('tr')
        
        day=int(da)
        dayfound,start=False,False
        for rw in tdrow:    
            cols=rw.find_elements_by_tag_name('td')
            for col in cols:
                if (col.text=='1') and start==False:
                    start=True
                if (col.text==str(day)) and ('disabled' in col.get_attribute('class')) and start==True:
                    day+=1
                elif (col.text==str(day)) and ('old' not in col.get_attribute('class') or 'new' not in col.get_attribute('class')) and start==True:
                    col.click()
                    self.logStatus("info", "day selected", self.takeScreenshot())
                    dayfound=True
                    break
            if dayfound==True:
                return 'success'
                
        return 'not selected'

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        self.driver.switch_to_frame("canvas")

        if self.check_exists_by_id('onAccountInfoClick'):
            self.driver.find_element_by_id('onAccountInfoClick').find_element_by_tag_name('a').click()

        self.logStatus("info", "go to account info page", self.takeScreenshot())

        accfound=''
        if self.check_exists_by_id('DataTables_Table_0'):
            table=self.driver.find_element_by_id('DataTables_Table_0')
            tbody=table.find_element_by_tag_name('tbody')
            rows=tbody.find_elements_by_tag_name('tr')

            for rw in rows:
                col=rw.find_elements_by_tag_name('td')
                if accountno in col[1].text:
                    accfound='Done'
                    col[1].find_element_by_tag_name('a').click()
                    self.logStatus("info", "Account selected", self.takeScreenshot())
        
        time.sleep(self.timeBwPage)

        if accfound!='':
            
            if len(fromdate)==7 and len(todate)==7:
                tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
                fromdate='01'+"-"+fromdate
                todate=str(tdy)+"-"+todate

            fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
            todate=datetime.strptime(todate, '%d-%m-%Y')

            accptdt=datetime.now()-relativedelta(months=6) + timedelta(days=1)

            if fromdate<accptdt and todate>accptdt:
                dt=datetime.now()-relativedelta(months=6) + timedelta(days=1)
                fromdate=datetime.strptime(str(dt)[:10], '%Y-%m-%d')
            elif fromdate<accptdt and todate<accptdt:
                self.logStatus("error", "No Data Available", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

            if todate.year>=datetime.now().year and todate.month>=datetime.now().month:
                todate=datetime.now()-timedelta(days=1)

            print(f'FROM DATE : {fromdate}')
            print(f'TO DATE : {todate}')

            fday=str(fromdate.day)
            fmonth=fromdate.strftime('%b')
            fyear=str(fromdate.year)
            tday=str(todate.day)
            tmonth=todate.strftime('%b')
            tyear=str(todate.year)

            # FROM DATE SET

            if self.check_exists_by_id('fromDate'):
                self.driver.find_element_by_id('fromDate').click()
                res=self.dateselector(fyear,fmonth,fday)
                if res=='not selected':
                    self.logStatus("error", "Invalid Date range", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}
                self.logStatus("info", "from date set", self.takeScreenshot())

            # TO DATE SET

            if self.check_exists_by_id('toDate'):
                self.driver.find_element_by_id('toDate').click()
                res=self.dateselector(tyear,tmonth,tday)
                if res=='not selected':
                    self.logStatus("error", "Invalid Date range", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}
                self.logStatus("info", "to date set", self.takeScreenshot())

            if self.check_exists_by_id('lnkPDF'):
                self.driver.find_element_by_id('lnkPDF').click()

            time.sleep(5)

            dic=self.saving_pdf()
            return dic
        else:
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

    def logout(self):
        if self.check_exists_by_classname('hl-btn'):
            self.driver.find_element_by_class_name('hl-btn').click()
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
#     obj=JSFBScrapper('JANASMALLFINANCEBANK')
#     opstr=obj.login('RILASHUTOSH01','Ril@54321','','')
#     res=obj.downloadData('01-01-2020','30-06-2021','4514010023754411','','')
#     a,b=obj.logout()
#     obj.closeDriver()