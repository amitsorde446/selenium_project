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
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class PNBScrapper:
    
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
        self.url='https://netbanking.netpnb.com/corp/AuthenticationController?__START_TRAN_FLAG__=Y&FORMSGROUP_ID__=AuthenticationFG&__EVENT_ID__=LOAD&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=024&LANGUAGE_ID=001'
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
            #self.chromeOptions.add_argument("--headless")
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
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'HDFC', self.env,
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
            self.uploadToS3(os.path.join(pdfname), self.ref_id + "/"+"automated_pdf_files/"+ i)
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

        if self.check_exists_by_xpath('/html/body/font/table[1]'):
            tb=self.driver.find_element_by_xpath('/html/body/font/table[1]')
            if "Error 404" in tb.text:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}       

        if self.check_exists_by_xpath('//*[@id="AuthenticationFG.USER_PRINCIPAL"]'):
            usernameInputField = self.driver.find_element_by_xpath('//*[@id="AuthenticationFG.USER_PRINCIPAL"]')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        time.sleep(self.timeBwPage)

        if self.check_exists_by_xpath('//*[@id="MessageDisplay_TABLE"]/div[2]'):
            errormsg=self.driver.find_element_by_xpath('//*[@id="MessageDisplay_TABLE"]/div[2]')
            if 'We are unable to process your request now. Please try after sometime.' == errormsg.text:
                print('Bank server error')
                self.logStatus("error", "Bank server error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        cntnbtn = self.driver.find_element_by_xpath('//*[@id="STU_VALIDATE_CREDENTIALS"]')
        cntnbtn.click()

        time.sleep(self.timeBwPage)
            
        PasswordField = self.driver.find_element_by_xpath('//*[@id="AuthenticationFG.ACCESS_CODE"]')
        PasswordField.clear()
        PasswordField.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        lgnbtn = self.driver.find_element_by_xpath('//*[@id="VALIDATE_STU_CREDENTIALS1"]')
        lgnbtn.click()
            
        time.sleep(self.timeBwPage)

        if self.check_exists_by_xpath('//*[@id="MessageDisplay_TABLE"]/div[2]'):
            print('here')
            errormsg=self.driver.find_element_by_xpath('//*[@id="MessageDisplay_TABLE"]/div[2]')
            if 'user ID is either invalid or disabled' in errormsg.text:
                print('User ID invalid')
                self.logStatus("error", "username invalid", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
            elif 'unsuccessful attempt(s)' in errormsg.text:
                print('Password invalid')
                self.logStatus("error", "password invalid", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
            elif 'We are unable to process your request now. Please try after sometime.' == errormsg.text:
                print('Bank server error')
                self.logStatus("error", "Bank server error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EUP007","responseMsg":"Unable To Process. Please Reach Out To Support."}

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}

    def calenderSelector(self,day,month,year):
        if self.check_exists_by_xpath('//*[@id="outerTab"]/div[2]'):
            mnth=Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[1]'))
            mnth.select_by_visible_text(month)
            
            yr=Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[2]'))
            yr.select_by_visible_text(year)
            
            dt=self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/table/tbody')
            dts=dt.find_elements_by_tag_name('tr')
            ext=False
            for i in dts:
                val=i.find_elements_by_tag_name('td')
                for j in val:
                    if str(j.text)==day:
                        j.click()
                        ext=True
                        break
            
                if ext==True:
                    break

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)
    
        tbl=self.driver.find_element_by_class_name('open')
        accstmt=tbl.find_element_by_link_text('Account Statement')
        accstmt.click()

        time.sleep(self.timeBwPage)
        self.logStatus("info", "Acc stmt page opened", self.takeScreenshot())

        accountselctor=Select(self.driver.find_element_by_class_name('dropdownexpandalbe'))
        print(list(map(lambda x:x.text,accountselctor.options)))
        accfound=''
        for acc in list(map(lambda x:x.text,accountselctor.options)):
            if accountno in acc:
                accfound='Done'
                accountselctor.select_by_visible_text(acc)
                break
        
        time.sleep(self.timeBwPage)

        if accfound!='':

            self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.SELECTED_RADIO_INDEX"]').click()

            if len(fromdate)==7 and len(todate)==7:
                tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
                fromdate='01'+"-"+fromdate
                todate=str(tdy)+"-"+todate

            fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
            todate=datetime.strptime(todate, '%d-%m-%Y')

            if todate.year>=datetime.now().year and todate.month>=datetime.now().month:
                todate=datetime.now()-timedelta(days=1)

            dt_lst=[]
            date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'),end=todate.strftime('%m-%d-%Y'),freq=pd.DateOffset(years=1),closed=None).to_list()
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

            flcount=1
            for dts in dt_lst:
                fd=datetime.strptime(dts[0], '%Y-%m-%d')
                td=datetime.strptime(dts[1], '%Y-%m-%d')

                fday=str(fd.day)
                fmonth=fd.strftime('%B')
                fyear=str(fd.year)
                tday=str(td.day)
                tmonth=td.strftime('%B')
                tyear=str(td.year)

                # FROM DATE SET

                self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG"]').click()
                time.sleep(2)
                self.calenderSelector(fday,fmonth,fyear)
                self.logStatus("info", "from date set", self.takeScreenshot())

                # TO DATE SET

                self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG"]').click()
                time.sleep(2)
                self.calenderSelector(tday,tmonth,tyear)
                self.logStatus("info", "to date set", self.takeScreenshot())

                self.driver.find_element_by_xpath('//*[@id="SEARCH"]').click()

                if self.check_exists_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'):
                    doctype=Select(self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'))
                    doctype.select_by_visible_text('PDF file')
                    self.logStatus("info", "pdf format selected", self.takeScreenshot())
                    
                    self.driver.find_element_by_xpath('//*[@id="okButton"]').click()
                    time.sleep(3)
                    d_lt=os.listdir(self.pdfDir)
                    for fl in d_lt:
                        if len(fl[:-4])>2:
                            os.rename(os.path.join(self.pdfDir,fl),os.path.join(self.pdfDir,str(flcount)+'.pdf'))
                            flcount+=1
                    
                time.sleep(self.timeBwPage)

            dic=self.saving_pdf()
            return dic
        else:
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

    def logout(self):
        if self.check_exists_by_xpath('//*[@id="HREF_Logout"]'):
            self.driver.find_element_by_xpath('//*[@id="HREF_Logout"]').click()
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
#     obj=PNBScrapper('QWERTY123')
#     opstr=obj.login('Rjtanjli143','Rjtanjli@200396')
#     # if opstr=='LOGIN SUCCESSFULL':
#     res=obj.downloadData('26-10-2018','10-09-2020')
#     a,b=obj.logout()
#     obj.closeDriver()