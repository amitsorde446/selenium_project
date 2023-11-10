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
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import Select
from datetime import datetime,timedelta
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
from tessrct import audiocaptcha
from dateutil.relativedelta import relativedelta
import socket
import calendar
import pytz


class SBIScrapper:
    
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
        self.url="https://retail.onlinesbi.com/retail/login.htm"
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,5)

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
                # driver.maximize_window()
            else:
                driver = webdriver.Chrome('/usr/local/bin/chromedriver', chrome_options=self.chromeOptions)
                # driver.maximize_window()

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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'SBI', self.env,
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

        if self.check_exists_by_xpath('//*[@id="banner"]/div[2]/a'):
            tb=self.driver.find_element_by_xpath('//*[@id="banner"]/div[2]/a')
            tb.click() 
        else:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        time.sleep(self.timeBwPage)
        msg=''
        while 1: 

            try:
                usernameInputField = self.driver.find_element_by_xpath('//*[@id="username"]')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}       


            time.sleep(self.timeBwPage)
                
            PasswordField = self.driver.find_element_by_xpath('//*[@id="label2"]')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())
            
            self.driver.find_elements_by_id('capOption')[1].click()
            self.wait.until(EC.presence_of_element_located((By.ID, "loginAudioCaptcha")))
            url = self.driver.find_element_by_xpath('//*[@id="loginAudioCaptcha"]').get_attribute('src')
            self.driver.get(url)

            time.sleep(5)

            logincptch = self.driver.find_element_by_xpath('//*[@id="loginCaptchaValue"]')
            logincptch.clear()
            logincptch.send_keys(audiocaptcha(os.path.join(self.pdfDir,"audio.wav")))

            lgnbtn = self.driver.find_element_by_xpath('//*[@id="Button2"]')
            lgnbtn.click()

            os.remove(os.path.join(self.pdfDir,"audio.wav"))

            try:
                alert=self.driver.switch_to_alert()
                print(alert.text)
                alert.accept()
                self.driver.switch_to_default_content()
                continue
            except Exception as e:
                print(f'Alert box : {e}')
                
            time.sleep(self.timeBwPage)

            if self.check_exists_by_xpath('//*[@id="login_block"]/div[3]'):
                errormsg=self.driver.find_element_by_xpath('//*[@id="login_block"]/div[3]')
                if 'Invalid Captcha' in errormsg.text:
                    print('Invalid Captcha')
                    self.logStatus("debug", "Invalid Captcha", self.takeScreenshot())
                    msg={"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
                elif 'Invalid Username or Password' in errormsg.text:
                    print('Username or password invalid')
                    self.logStatus("error", "Username or password invalid", self.takeScreenshot())
                    msg={"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                    break
            else:
                if self.check_exists_by_xpath('//*[@id="login_block"]/div[3]')==False:
                    msg={"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
                    self.logStatus("info", "login successfull", self.takeScreenshot())
                    break
        if self.check_exists_by_xpath('//*[@id="d-content"]/div/div[4]/span[1]/input[2]'):
            self.driver.find_element_by_xpath('//*[@id="d-content"]/div/div[4]/span[1]/input[2]').click()
            self.logStatus("info", "popup closed", self.takeScreenshot())
        
        return msg 

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        
        time.sleep(self.timeBwPage)

        if len(fromdate)==7 and len(todate)==7:
            tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
            fromdate='01'+"-"+fromdate
            todate=str(tdy)+"-"+todate
        
        self.driver.find_element_by_xpath('//*[@id="quick_links_nh"]/li[2]/a').click()
        self.logStatus("info", "Acc summary page opened", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        accnotable=self.driver.find_element_by_xpath('/html/body/div[1]/div[3]/div[2]/div[2]/div[2]/form[2]/div[1]/table')
        accnos=accnotable.find_element_by_tag_name('tbody')
        acclist=accnos.find_elements_by_tag_name('tr')
        print(list(map(lambda x:x.text,acclist)))
        accfound=''
        for accs in acclist:
            acc=accs.text.split(' ')[0]
            if accountno in acc:
                allelem=accs.find_elements_by_tag_name('td')
                print(f'ACC name : {list(map(lambda x:x.text,allelem))}')
                allelem[0].find_element_by_tag_name('input').click()
                accfound='Done'
                break
        
        time.sleep(self.timeBwPage)
        if accfound!='':

            fd=datetime.strptime(fromdate, '%d-%m-%Y')
            td=datetime.strptime(todate, '%d-%m-%Y')

            if td.year>=datetime.now().year and td.month>=datetime.now().month:
                td=datetime.now()-timedelta(days=1)

            cd=datetime.today()-relativedelta(years=1)

            if int(fd.year)<2017 and int(td.year)<2017:
                return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

            elif (fd.year>cd.year) or (fd.year==cd.year and fd.month>=cd.month):
                self.driver.find_element_by_xpath('//*[@id="bydate"]').click()
                self.logStatus("info", "went to by date", self.takeScreenshot())

                fromDate = self.driver.find_element_by_xpath('//*[@id="datepicker1"]')
                fromDate.clear()
                fromDate.send_keys(fd.strftime('%d/%m/%Y'))
                self.logStatus("info", "from date set", self.takeScreenshot())

                toDate = self.driver.find_element_by_xpath('//*[@id="datepicker2"]')
                toDate.clear()
                toDate.send_keys(td.strftime('%d/%m/%Y'))
                self.logStatus("info", "to date set", self.takeScreenshot())
                
                self.driver.find_element_by_xpath('//*[@id="pdfformat"]').click()
                self.logStatus("info", "pdf format", self.takeScreenshot())

                self.driver.find_element_by_xpath('//*[@id="Submit3"]').click()

                time.sleep(self.timeBwPage)

            else:
                self.driver.find_element_by_xpath('//*[@id="bymonth"]').click()
                self.logStatus("info", "went to by month", self.takeScreenshot())
                if int(fd.year)<2017:
                    fmonth='January'
                    fyear='2017'
                else:
                    fmonth=fd.strftime('%B')
                    fyear=str(fd.year)
                tmonth=td.strftime('%B')
                tyear=str(td.year)

                yrs=list(range(int(fyear),int(tyear)+1))
                mnth_lst=['January', 'February', 'March', 'April', 'May', 'June', 'July' , 'August', 'September', 'October', 'November', 'December']
                yr_dict={}
                apnd=False
                for yr in yrs:
                    mn=[]
                    for m in mnth_lst:
                        if m==fmonth and str(yr)==fyear:
                            apnd=True
                        if apnd==True:
                            mn.append(m)
                        if m==tmonth and str(yr)==tyear:
                            apnd=False
                    yr_dict[str(yr)]=mn

                for yrs in list(yr_dict.keys()):
                    yrslct=Select(self.driver.find_element_by_xpath('//*[@id="year"]'))
                    yrslct.select_by_value(yrs)
                    self.logStatus("info", f"year {yrs} selected", self.takeScreenshot())
                    for mnth in yr_dict[yrs]:
                        mnslct=Select(self.driver.find_element_by_xpath('//*[@id="date"]'))
                        mnslct.select_by_value(datetime.strptime(mnth, '%B').strftime('%m'))
                        self.logStatus("info", f"mnth {mnth} selected", self.takeScreenshot())

                        self.driver.find_element_by_xpath('//*[@id="excelformat"]').click()
                        self.driver.find_element_by_xpath('//*[@id="pdfformat"]').click()
                        self.driver.find_element_by_xpath('//*[@id="Submit3"]').click()
                        time.sleep(self.timeBwPage)
                self.logStatus("info", "Data Downloaded")

            dic=self.saving_pdf()
            return dic
        else:
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

    def logout(self):
        if self.check_exists_by_xpath('//*[@id="headerContent"]/div[3]/div/a'):
            self.driver.find_element_by_xpath('//*[@id="headerContent"]/div[3]/div/a').click()
            self.logStatus("info", "logout successfull", self.takeScreenshot())
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
#     obj=SBIScrapper('QWERTY123')
#     opstr=obj.login('prernasingh2110','PRERNA@2110')
#     print(opstr)
#     if opstr=='LOGIN SUCCESSFULL':
#         obj.downloadData('26-12-2019','10-09-2020')
#         obj.logout()
#     obj.closeDriver()