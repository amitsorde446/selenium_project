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
from dateutil.relativedelta import relativedelta
from datetime import datetime,timedelta
from tessrct import kbcaptcha
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class KBScrapper:
    
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
        self.url='https://moneyclick.karnatakabank.co.in/BankAwayRetail/AuthenticationController?__START_TRAN_FLAG__=Y&FORMSGROUP_ID__=AuthenticationFG&__EVENT_ID__=LOAD&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=KBL&LANGUAGE_ID=001'
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'KB', self.env,
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

        while 1:

            try:
                self.driver.get(self.url)
                self.logStatus("info", "website opened", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

            if self.check_exists_by_id('mobilemainpage'):
                errormsg=self.driver.find_element_by_id('mobilemainpage')
                print(errormsg.text)
                if 'APPLICATION SECURITY ERROR' in errormsg.text:
                    self.logStatus("debug", "application error page opened", self.takeScreenshot())
                    divbtn=self.driver.find_element_by_id('MBLogoutHDisplay')
                    abtn=divbtn.find_elements_by_tag_name('a')
                    
                    for i in abtn:
                        if 'Go to Login Page' in i.text:
                            i.click()
                            time.sleep(self.timeBwPage)
                            self.logStatus("info", "Login page opened again", self.takeScreenshot())
                            break

            time.sleep(self.timeBwPage)

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

            self.driver.save_screenshot("screenshot.png")
            self.driver.find_element_by_xpath("""//*[@id="IMAGECAPTCHA"]""").screenshot("captcha.png")
            captchaInputField = self.driver.find_element_by_id('AuthenticationFG.VERIFICATION_CODE')
            captchaInputField.clear()
            captchaInputField.send_keys(kbcaptcha())
            self.logStatus("info", "captcha entered", self.takeScreenshot())
            
            time.sleep(self.timeBwPage)
                
            gobtn = self.driver.find_element_by_id('STU_VALIDATE_CREDENTIALS')
            gobtn.click()
            self.logStatus("info", "Go to login clicked", self.takeScreenshot())

            if self.check_exists_by_id('MessageDisplay_TABLE'):
                errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                print(errormsg.text)
                if 'Enter the characters that are seen in the picture' in errormsg.text:
                    self.logStatus("debug", "Invalid Captcha", self.takeScreenshot())
                    continue
            else:
                self.logStatus("info", "Captcha passed", self.takeScreenshot())
                break

        while 1:
            
            time.sleep(self.timeBwPage)

            if self.check_exists_by_id('AuthenticationFG.TARGET_CHECKBOX_Label'):
                self.driver.find_element_by_id('AuthenticationFG.TARGET_CHECKBOX_Label').click()
                self.logStatus("info", "check box clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            PasswordField = self.driver.find_element_by_name('AuthenticationFG.ACCESS_CODE')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            lgnbtn = self.driver.find_element_by_name('Action.VALIDATE_STU_CREDENTIALS_UX')
            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            if self.check_exists_by_id('MessageDisplay_TABLE'):
                errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                print(errormsg.text)
                if 'Confirm your selection before proceeding' in errormsg.text:
                    self.logStatus("debug", "checkbox not clicked", self.takeScreenshot())
                    continue
                elif 'unsuccessful attempt' in errormsg.text:
                    self.logStatus("error", "invalid password", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                elif 'The user ID is invalid' in errormsg.text:
                    self.logStatus("error", "invalid username", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                else:
                    break
            else:
                break
 
        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}                

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        self.check_exists_by_id('topnav')
        topnav=self.driver.find_element_by_id('topnav')
        topnavclickable=topnav.find_elements_by_tag_name('a')

        clicked=False
        for i in topnavclickable:
            if 'Accounts' in i.text and clicked==False:
                clicked=True
                i.click()
            if clicked==True and 'Account Enquiry / Opening' in i.text:
                i.click()
                time.sleep(2)
                self.driver.find_element_by_xpath('/html/body/form[1]/div[2]/ul[1]/li[2]/a').click()
                break

        time.sleep(5)

        acc=''
        selectelem=self.driver.find_element_by_name('TransactionHistoryFG.INITIATOR_ACCOUNT')
        bankacc=Select(selectelem)
        bankaccopt=selectelem.find_elements_by_tag_name('option')

        for accno in bankaccopt:
            print(accno.get_attribute('value'))
            if accountno in accno.get_attribute('value'):
                acc=accno.get_attribute('value')
                bankacc.select_by_value(acc)
                self.logStatus("info", "Account selected", self.takeScreenshot())
                break

        if acc=='':
            
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
        
        else:
            time.sleep(self.timeBwPage)

            pageelemnts=self.driver.find_element_by_id('PageConfigurationMaster_RASUX3W__1:SearchPanel_Stage34.SubSection1')
            pageelemnts.find_element_by_id('PageConfigurationMaster_RASUX3W__1:txnDateFromLabel').click()
            self.logStatus("info", "By date range selected", self.takeScreenshot())

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
                
                time.sleep(self.timeBwPage)
                
                fd=datetime.strptime(dts[0], '%Y-%m-%d')
                td=datetime.strptime(dts[1], '%Y-%m-%d')
                self.logStatus("info", f"From date : {fd} and To date : {td}", self.takeScreenshot())

                # FROM DATE SET

                FromDate = self.driver.find_element_by_id('PageConfigurationMaster_RASUX3W__1:TransactionHistoryFG.FROM_TXN_DATE')
                FromDate.clear()
                FromDate.send_keys(fd.strftime('%m,%d,%Y'))
                self.logStatus("info", "from date entered", self.takeScreenshot())
                
                time.sleep(self.timeBwPage)
                        
                # TO DATE SET

                ToDate = self.driver.find_element_by_id('PageConfigurationMaster_RASUX3W__1:TransactionHistoryFG.TO_TXN_DATE')
                ToDate.clear()
                ToDate.send_keys(td.strftime('%m,%d,%Y'))
                self.logStatus("info", "to date entered", self.takeScreenshot())
                
                time.sleep(self.timeBwPage)
                        
                searchelem=self.driver.find_element_by_name('Action.SEARCH')
                searchelem.location_once_scrolled_into_view
                searchelem.click()
                self.logStatus("info", "Search button clicked", self.takeScreenshot())
                
                time.sleep(5)
                
                if self.check_exists_by_id('PageConfigurationMaster_RASUX3W__1:MessageDisplay_TABLE'):
                    errormsg=self.driver.find_element_by_id('PageConfigurationMaster_RASUX3W__1:MessageDisplay_TABLE')
                    print(errormsg.text)
                    if 'The transactions do not exist for the account with the entered criteria.Use Search Transactions' in errormsg.text:
                        self.logStatus("info", "No data for this date range", self.takeScreenshot())    
                
                else:
                    time.sleep(self.timeBwPage)
                    
                    doctyp=self.driver.find_element_by_xpath('/html/body/form/div[2]/div[2]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[3]/div/div/div/div[3]/div/div/p/span[1]/span[3]/input')
                    doctyp.clear()
                    doctyp.send_keys('PDF')
                    self.logStatus("info", "doc type set", self.takeScreenshot())
                    
                    time.sleep(self.timeBwPage)
                    
                    self.driver.find_element_by_name('Action.GENERATE_REPORT').click()
                    self.logStatus("info", "download button clicked", self.takeScreenshot())
                    
                    time.sleep(5)

                    d_lt=os.listdir(self.pdfDir)
                    for fl in d_lt:
                        if len(fl[:-4])>2:
                            os.rename(os.path.join(self.pdfDir,fl),os.path.join(self.pdfDir,str(flcount)+'.pdf'))
                            flcount+=1
                    
                displaycriteria=self.driver.find_element_by_id('critPlus')
                displaycriteria.click()

                if 'block' in displaycriteria.get_attribute('style'):
                    displaycriteria.click()
                    time.sleep(self.timeBwPage)

                self.logStatus("info", "expanded search criteria", self.takeScreenshot())

            dic=self.saving_pdf()
            return dic
    
    def logout(self):

        if self.check_exists_by_xpath('/html/body/form/div[2]/nav/div/div/div/div[2]/ul[1]/li[6]/a/i'):
            self.driver.find_element_by_xpath('/html/body/form/div[2]/nav/div/div/div/div[2]/ul[1]/li[6]/a/i').click()
            
            time.sleep(self.timeBwPage)   
            self.driver.find_element_by_name('HREF_LOG_OUT').click()

            self.logStatus("info", "Logout successful", self.takeScreenshot())
            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        else:
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
#     obj=KBScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('R01229890','Ril@543210','','')
#     print(opstr)
#     res=obj.downloadData('01-09-2017','07-01-2021','2612500103097201','','')
#     a,b=obj.logout()
#     obj.closeDriver()