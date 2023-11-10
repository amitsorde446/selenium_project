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
from tessrct import fbcaptcha
from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class FBScrapper:
    
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
        self.url='https://www.fednetbank.com/corp/AuthenticationController?__START_TRAN_FLAG__=Y&FORMSGROUP_ID__=AuthenticationFG&__EVENT_ID__=LOAD&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=049&LANGUAGE_ID=001'
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'FB', self.env,
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

            if self.check_exists_by_id('application-security-error'):
                errormsg=self.driver.find_element_by_id('application-security-error')
                print(errormsg.text)
                if 'APPLICATION ENDED FOR UNKNOWN REASON' in errormsg.text:
                    self.logStatus("info", "application error page opened", self.takeScreenshot())
                    divbtn=self.driver.find_element_by_id('application-security-error')
                    abtn=divbtn.find_elements_by_tag_name('a')

                    for i in abtn:
                        if 'Go to Login Page' in i.text:
                            i.click()
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

            PasswordField = self.driver.find_element_by_name('AuthenticationFG.ACCESS_CODE')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            self.driver.save_screenshot("screenshot.png")
            captchaInputField = self.driver.find_element_by_id('AuthenticationFG.VERIFICATION_CODE')
            captchaInputField.clear()
            captchaInputField.send_keys(fbcaptcha())
            self.logStatus("info", "captcha entered", self.takeScreenshot())
            
            time.sleep(self.timeBwPage)
                
            lgnbtn = self.driver.find_element_by_id('VALIDATE_CREDENTIALS')
            lgnbtn.click()
            self.logStatus("info", "login button clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            if self.check_exists_by_id('MessageDisplay_TABLE'):
                errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                print(errormsg.text)
                if 'Enter the characters displayed in the captcha' in errormsg.text:
                    self.logStatus("debug", "invalid captcha", self.takeScreenshot())
                    continue
                elif 'Invalid User ID or Password' in errormsg.text:
                    self.logStatus("error", "invalid credentials", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
            else:
                break
 
        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}                

    def fromcalenderSelector(self,day,month,year):

        if self.check_exists_by_xpath('/html/body/div[2]/div[1]/table/thead/tr[1]/th[2]'):

            self.driver.find_element_by_xpath('/html/body/div[2]/div[1]/table/thead/tr[1]/th[2]').click()
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_xpath('/html/body/div[2]/div[2]/table/thead/tr/th[2]').click()
            time.sleep(self.timeBwPage)

            while 1:

                yrtable=self.driver.find_element_by_xpath('/html/body/div[2]/div[3]/table')
                yrtbody=yrtable.find_element_by_tag_name('tbody')
                yrrows=yrtbody.find_element_by_tag_name('tr')

                if str(year) in yrrows.text:
                    selected=False 

                    cols=yrrows.find_element_by_tag_name('td').find_elements_by_tag_name('span')
                    for j in cols:
                        if str(j.text)==str(year):
                            j.click()
                            selected=True
                            break
                    if selected==True:
                        selected=False
                        break
                elif int(year)>int(yrrows.text.split('\n')[-1]):
                    self.driver.find_element_by_xpath('/html/body/div[2]/div[3]/table/thead/tr/th[3]').click()
                    time.sleep(self.timeBwPage)
                elif int(year)<int(yrrows.text.split('\n')[0]):
                    self.driver.find_element_by_xpath('/html/body/div[2]/div[3]/table/thead/tr/th[1]').click()
                    time.sleep(self.timeBwPage)

            mnthtable=self.driver.find_element_by_xpath('/html/body/div[2]/div[2]/table')
            mnthtbody=mnthtable.find_element_by_tag_name('tbody')
            mnthrows=mnthtbody.find_element_by_tag_name('tr')

            cols=mnthrows.find_element_by_tag_name('td').find_elements_by_tag_name('span')
            for j in cols:
                if str(j.text)==str(month):
                    j.click()
                    break

            dytable=self.driver.find_element_by_xpath('/html/body/div[2]/div[1]/table')
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
                        break
                if selected==True:
                    selected=False
                    break

    def tocalenderSelector(self,day,month,year):

        if self.check_exists_by_xpath('/html/body/div[3]/div[1]/table/thead/tr[1]/th[2]'):

            self.driver.find_element_by_xpath('/html/body/div[3]/div[1]/table/thead/tr[1]/th[2]').click()
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_xpath('/html/body/div[3]/div[2]/table/thead/tr/th[2]').click()
            time.sleep(self.timeBwPage)

            while 1:

                yrtable=self.driver.find_element_by_xpath('/html/body/div[3]/div[3]/table')
                yrtbody=yrtable.find_element_by_tag_name('tbody')
                yrrows=yrtbody.find_element_by_tag_name('tr')

                if str(year) in yrrows.text:
                    selected=False 

                    cols=yrrows.find_element_by_tag_name('td').find_elements_by_tag_name('span')
                    for j in cols:
                        if str(j.text)==str(year):
                            j.click()
                            selected=True
                            break
                    if selected==True:
                        selected=False
                        break
                elif int(year)>int(yrrows.text.split('\n')[-1]):
                    self.driver.find_element_by_xpath('/html/body/div[3]/div[3]/table/thead/tr/th[3]').click()
                    time.sleep(self.timeBwPage)
                elif int(year)<int(yrrows.text.split('\n')[0]):
                    self.driver.find_element_by_xpath('/html/body/div[3]/div[3]/table/thead/tr/th[1]').click()
                    time.sleep(self.timeBwPage)

            mnthtable=self.driver.find_element_by_xpath('/html/body/div[3]/div[2]/table')
            mnthtbody=mnthtable.find_element_by_tag_name('tbody')
            mnthrows=mnthtbody.find_element_by_tag_name('tr')

            cols=mnthrows.find_element_by_tag_name('td').find_elements_by_tag_name('span')
            for j in cols:
                if str(j.text)==str(month):
                    j.click()
                    break

            dytable=self.driver.find_element_by_xpath('/html/body/div[3]/div[1]/table')
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
                        break
                if selected==True:
                    selected=False
                    break

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)

        self.driver.find_element_by_name(' HREF_Accounts').find_element_by_tag_name('i').click()
        time.sleep(1)
        self.driver.find_element_by_id('Accounts-Info_Operative-Accounts').click()
        time.sleep(1)
        self.driver.find_element_by_name('Action.VIEW_TRANSACTION_HISTORY').find_element_by_tag_name('i').click()

        time.sleep(self.timeBwPage)

        bankacc=Select(self.driver.find_element_by_name('TransactionHistoryFG.INITIATOR_ACCOUNT'))

        acn=''
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

                fday=str(fd.day)
                fmonth=fd.strftime('%b').upper()
                fyear=str(fd.year)
                tday=str(td.day)
                tmonth=td.strftime('%b').upper()
                tyear=str(td.year)

                # FROM DATE SET

                divlst=self.driver.find_elements_by_id('SearchPanel.Ra1')[1].find_elements_by_tag_name('div')
                for sp in divlst:
                    if sp.get_attribute('class')=='input-group-addon':
                        sp.click()
                time.sleep(self.timeBwPage)
                self.fromcalenderSelector(fday,fmonth,fyear)
                self.logStatus("info", "from date entered", self.takeScreenshot())

                # TO DATE SET

                divlst=self.driver.find_elements_by_id('SearchPanel.Ra1')[2].find_elements_by_tag_name('div')
                for sp in divlst:
                    if sp.get_attribute('class')=='input-group-addon':
                        sp.click()
                time.sleep(self.timeBwPage)
                self.tocalenderSelector(tday,tmonth,tyear)
                self.logStatus("info", "to date entered", self.takeScreenshot())
                
                self.driver.find_element_by_name('Action.SEARCH').click()
                self.logStatus("info", "Search button clicked", self.takeScreenshot())
                
                time.sleep(5)

                if self.check_exists_by_id('MessageDisplay_TABLE'):                    
                    errormsg=self.driver.find_element_by_id('MessageDisplay_TABLE')
                    print(errormsg.text)
                    if 'No transactions found for the selected period' in errormsg.text:
                        time.sleep(self.timeBwPage)
                        self.logStatus("info", "No data for this date range", self.takeScreenshot())
                else:
                    dwnldbtn=self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[2]/div[2]/div/div[2]/div/div[2]/div/div[4]/div/div/div[2]/input')
                    dwnldbtn.location_once_scrolled_into_view
                    dwnldbtn.click()
                    self.logStatus("info", "download pdf button clicked", self.takeScreenshot())
                    
                    time.sleep(5)
                    
                    gnrtrpbtn=self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[2]/div[2]/div/div[2]/div/div[2]/div/div[2]/div/div/div[1]/button')
                    gnrtrpbtn.location_once_scrolled_into_view
                    gnrtrpbtn.click()
                    self.logStatus("info", "generate button clicked", self.takeScreenshot())
                    
                    time.sleep(5)

                    d_lt=os.listdir(self.pdfDir)
                    for fl in d_lt:
                        if len(fl[:-4])>2:
                            os.rename(os.path.join(self.pdfDir,fl),os.path.join(self.pdfDir,str(flcount)+'.pdf'))
                            flcount+=1

                    bckbtn=self.driver.find_element_by_xpath('/html/body/form/div[3]/div/div/div[2]/div[2]/div/div[2]/div/div[2]/div/div[2]/div/div/div[2]/input')
                    bckbtn.location_once_scrolled_into_view
                    bckbtn.click()
                    self.logStatus("info", "back button clicked", self.takeScreenshot())

            dic=self.saving_pdf()
            return dic
    
    def logout(self):

        if self.check_exists_by_xpath('/html/body/form/div[3]/header/div/div/div/ul/li[5]/a/span/span[1]'):
            self.driver.find_element_by_xpath('/html/body/form/div[3]/header/div/div/div/ul/li[5]/a/span/span[1]').click()
            
            time.sleep(self.timeBwPage)   
            self.driver.find_element_by_name('HREF_HREF_Logout').click()

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
#     obj=FBScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('ASHU0105','Ril@6688','','')
#     print(opstr)
#     res=obj.downloadData('25-12-2018','13-01-2021','99980114502318','','')
#     a,b=obj.logout()
#     obj.closeDriver()