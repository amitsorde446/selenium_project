from webdriver_manager.chrome import ChromeDriverManager
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

#from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from tessrct import tmbcaptcha
import pytz


class TMBScrapper:
    
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
        self.url='https://www.tmbnet.in/corp/AuthenticationController?FORMSGROUP_ID__=AuthenticationFG&__START_TRAN_FLAG__=Y&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=TMB'
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
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'TMB', self.env,
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

        while 1:
            if self.check_exists_by_id('AuthenticationFG.USER_PRINCIPAL'):
                usernameInputField = self.driver.find_element_by_id('AuthenticationFG.USER_PRINCIPAL')
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            else:
                print(f'Website error 404')
                self.logStatus("error", "website 404 error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
            
            time.sleep(self.timeBwPage)
            PasswordField = self.driver.find_element_by_id('AuthenticationFG.ACCESS_CODE')
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            self.driver.save_screenshot("screenshot.png")
            logincptch = self.driver.find_element_by_id('AuthenticationFG.VERIFICATION_CODE')
            logincptch.clear()
            # df = self.driver.find_elements_by_xpath("""//*[@id="HDisplay1"]/div[3]""")
            # df =df.find_elements_by_xpath("""//*[@id="HDisplay1"]/div[3]""")
            # df = df.find_elements_by_tag_name("""//*[@id="HDisplay1.Rb10"]""")
            # df = df.find_elements_by_xpath("""//*[@id="HDisplay1.Rb10.C3"]""")
            # df.find_elements_by_tag_name("""img""").screenshot("captcha.png")
            self.driver.find_elements_by_xpath("""/html/body/form/div/div/div[4]/div[3]/div/p[4]/span/img""")[0].screenshot("captcha.png")
            logincptch.send_keys(tmbcaptcha())
            self.logStatus("info", "captcha entered", self.takeScreenshot())

            lgnbtn = self.driver.find_element_by_id('VALIDATE_CREDENTIALS')
            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            if self.check_exists_by_id('MessageDisplay_TABLE'):
                errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                print(errormsg.text)
                if 'Enter the characters as seen in the picture' in errormsg.text:
                    print('Invalid captcha')
                    self.logStatus("debug", "incorrect captcha", self.takeScreenshot())
                elif "Invalid login credentials" in errormsg.text:
                    print('User ID invalid')
                    self.logStatus("error", "incorrect Username", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                elif 'Invalid Password' in errormsg.text:
                    print('Password invalid')
                    self.logStatus("error", "incorrect Password", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
            else:
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
                
    def downloadData(self,fromdate,todate,accountno,seml,smno):
        acn=''

        if self.check_exists_by_id('HDisplay1.Rowset1'):
            self.driver.find_element_by_id('HDisplay1.Rowset1').find_element_by_id('HREF_Account_Statement').click()
            self.logStatus("info", "Statement page opened", self.takeScreenshot())

        if self.check_exists_by_id('TransactionHistoryFG.INITIATOR_ACCOUNT'):
            bankacc=Select(self.driver.find_element_by_id('TransactionHistoryFG.INITIATOR_ACCOUNT'))
            print(list(map(lambda x:x.text,bankacc.options))) 

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
            self.logStatus("info", "Bank account selected", self.takeScreenshot())

            if self.check_exists_by_id('TransactionHistoryFG.SELECTED_RADIO_INDEX'):
                radiobtns=self.driver.find_elements_by_id('TransactionHistoryFG.SELECTED_RADIO_INDEX')
                for rdbn in radiobtns:
                    if rdbn.get_attribute('value')=="0":
                        rdbn.click()
                        break

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
            date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'),end=todate.strftime('%m-%d-%Y'),freq=pd.DateOffset(months=3),closed=None).to_list()
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
                fd=datetime.strptime(dts[0], '%Y-%m-%d').strftime('%d/%m/%Y')
                td=datetime.strptime(dts[1], '%Y-%m-%d').strftime('%d/%m/%Y')
                print(f'Date Range : from {fd} to {td}')

                diccls=self.driver.find_element_by_id('SearchPanel.Rowset1')

                pidfd=diccls.find_element_by_id('SearchPanel.Ra2')
                fromdatefield = pidfd.find_element_by_id("TransactionHistoryFG.FROM_TXN_DATE")
                fromdatefield.clear()
                fromdatefield.send_keys(fd)
                self.logStatus("info", "from date selected", self.takeScreenshot())

                pidtd=diccls.find_element_by_id('SearchPanel.Ra3')
                todatefield = pidtd.find_element_by_id('TransactionHistoryFG.TO_TXN_DATE')
                todatefield.clear()
                todatefield.send_keys(td)
                self.logStatus("info", "to date selected", self.takeScreenshot())
                
                time.sleep(self.timeBwPage)
                pidsb=self.driver.find_element_by_id('NavPanel')
                pidsb.find_element_by_id('SEARCH').click()
                time.sleep(5)
                self.logStatus("info", "Search button clicked", self.takeScreenshot())
                
                if self.check_exists_by_id('MessageDisplay_TABLE'):
                    errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                    if 'The transactions do not exist for the account with the entered criteria' in errormsg.text:
                        self.logStatus("info", "Stmt doesn't exists for this date range", self.takeScreenshot())
                else: 
                    self.logStatus("info", "Stmt exists for this date range", self.takeScreenshot())
                    optyp=Select(self.driver.find_element_by_id('TransactionHistoryFG.OUTFORMAT'))
                    optyp.select_by_visible_text('PDF file')
                    self.driver.find_element_by_id('okButton').click()
                    self.logStatus("info", "pdf download button clicked", self.takeScreenshot())
                    time.sleep(5)

                    d_lt=os.listdir(self.pdfDir)
                    for fl in d_lt:
                        if len(fl[:-4])>2:
                            os.rename(os.path.join(self.pdfDir,fl),os.path.join(self.pdfDir,str(flcount)+'.pdf'))
                            flcount+=1

                time.sleep(self.timeBwPage)

            dic=self.saving_pdf()
            return dic

    def logout(self):
        try:
            mgmn=self.driver.find_element_by_id('mega_menu')
            logout=mgmn.find_element_by_id('Log_Out')
            logout.click()
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
#     obj=TMBScrapper('TMB')
#     opstr=obj.login('LOMR42362','$$netbanking2020$$','','')
#     print(opstr)
#     res=obj.downloadData('01-01-2020','30-12-2021','507100050300535','','')
#     a,b=obj.logout()
#     obj.closeDriver()