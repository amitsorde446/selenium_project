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


class CUBScrapper:
    
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
        self.url='https://www.onlinecub.net/'
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'CUB', self.env,
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

            if self.check_exists_by_xpath('/html/body/div[1]/div/div[1]/div/a'):
                self.driver.find_element_by_xpath('/html/body/div[1]/div/div[1]/div/a').click()

        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        if self.check_exists_by_classname('myBtn'):
            btns=self.driver.find_elements_by_class_name('myBtn')

            for btn in btns:
                if 'Personal' in btn.text:
                    btn.click()
                    self.logStatus("info", "Go to personal netbanking", self.takeScreenshot())
                    time.sleep(self.timeBwPage)
                    time.sleep(self.timeBwPage)
                    self.driver.switch_to_window(self.driver.window_handles[-1])
                    break

        if self.check_exists_by_id('uid'):
            usernameInputField = self.driver.find_element_by_id('uid')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
            
        time.sleep(self.timeBwPage)

        gobtn = self.driver.find_element_by_id('continueBtn1')
        gobtn.click()
        self.logStatus("info", "continue to login btn clicked", self.takeScreenshot())
        
        time.sleep(self.timeBwPage)

        PasswordField = self.driver.find_element_by_name('pwd')
        PasswordField.clear()
        PasswordField.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        checkboxField=self.driver.find_element_by_name('MFACheckBox')
        checkboxField.click()
        self.logStatus("info", "check box clicked", self.takeScreenshot())

        time.sleep(self.timeBwPage)
            
        lgnbtn = self.driver.find_element_by_id('continueBtn')
        lgnbtn.click()
        self.logStatus("info", "login button clicked", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        if self.check_exists_by_classname('errmsg'):
            errormsg = self.driver.find_element_by_class_name('errmsg')
            print(errormsg.text)
            
            if 'Incorrect User Id Or Password' in errormsg.text:
                self.logStatus("error", "invalid credentials", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
                
            elif 'User already logged on' in errormsg.text:
                self.logStatus("error", "Account already opened somewhere", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

        time.sleep(self.timeBwPage)
        
        if self.check_exists_by_id('aftersubmitError'):
            errormsg=self.driver.find_element_by_id('aftersubmitError')
            print(errormsg.text)

            if 'Kindly Verify the EMail-ID Shown Below' in errormsg.text:
                btns=self.driver.find_elements_by_class_name('clsinfo')
                for btn in btns:
                    btnclk=btn.find_element_by_tag_name('img')
                    if 'skip' in btnclk.get_attribute('src'):
                        btnclk.click()
                        self.logStatus("info", "skip on email verification clicked", self.takeScreenshot())
                        time.sleep(self.timeBwPage)
                        break

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

        fdlmt=datetime.strptime('01-01-2014', '%d-%m-%Y')

        if fromdate<fdlmt:
            fromdate=fdlmt

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
            
            time.sleep(2)
            
            fd=datetime.strptime(dts[0], '%Y-%m-%d')
            td=datetime.strptime(dts[1], '%Y-%m-%d')

            self.logStatus("info", f"From date : {fd} and To date : {td}")

            time.sleep(self.timeBwPage)

            self.driver.switch_to_default_content()
            self.driver.switch_to_frame('treeFrame')
            
            accelem=self.driver.find_element_by_xpath('/html/body/nav/div/div[1]/a')
            if accelem.get_attribute('aria-expanded')!='true':
                accelem.click()
                self.logStatus("info", "Accounts option clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            accstmtelem=self.driver.find_element_by_xpath('/html/body/nav/div/div[1]/div/ul/li[2]/a')
            if accstmtelem.get_attribute('aria-expanded')!='true':
                accstmtelem.click()
                self.logStatus("info", "Account stmt option clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)
            
            self.driver.find_element_by_xpath('/html/body/nav/div/div[1]/div/ul/li[2]/div/ul/li[1]/a').click()
            self.logStatus("info", "transaction history clicked", self.takeScreenshot())

            time.sleep(self.timeBwPage)

            self.driver.switch_to_default_content()
            self.driver.switch_to_frame('folderFrame')

            if self.check_exists_by_xpath('/html/body/form[1]/table[1]/tbody/tr[2]/td[2]/select'):

                bankacc=Select(self.driver.find_element_by_xpath('/html/body/form[1]/table[1]/tbody/tr[2]/td[2]/select'))
                
                acn,selected='',False
                for accno in list(map(lambda x:x.text,bankacc.options)):
                    accnm=accno.split('-')
                    for an in accnm:
                        anm=an.replace(' ','')
                        lnac=len(anm)
                        if accountno[-(lnac):] == anm and selected==False:
                            acn=accno
                            bankacc.select_by_visible_text(acn)
                            selected=True
                            time.sleep(self.timeBwPage)
                            self.logStatus("info", "Account selected", self.takeScreenshot())
                            break
                    if selected==True:
                        break

                if acn=='':

                    self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
                    return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
            
            if self.check_exists_by_xpath('/html/body/form[1]/table[1]/tbody/tr[3]/td[2]/select'):
                
                transtyp=Select(self.driver.find_element_by_xpath('/html/body/form[1]/table[1]/tbody/tr[3]/td[2]/select'))

                for typ in list(map(lambda x:x.text,transtyp.options)):
                    if 'Select Period' in typ:
                        transtyp.select_by_visible_text('Select Period')
                        time.sleep(self.timeBwPage)
                        self.logStatus("info", "date range type selected", self.takeScreenshot())
                        break

            # FROM DATE SET

            FromDate = self.driver.find_element_by_xpath('/html/body/form[1]/table[1]/tbody/tr[6]/td[1]/input')
            FromDate.clear()
            FromDate.send_keys(fd.strftime('%d/%m/%Y'))
            self.logStatus("info", "from date entered", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            # TO DATE SET

            ToDate = self.driver.find_element_by_xpath('/html/body/form[1]/table[1]/tbody/tr[7]/td[1]/input')
            ToDate.clear()
            ToDate.send_keys(td.strftime('%d/%m/%Y'))
            self.logStatus("info", "to date entered", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            if self.check_exists_by_xpath('/html/body/form[1]/table[2]/tbody/tr/td[2]/select'):
                doctyp=Select(self.driver.find_element_by_xpath('/html/body/form[1]/table[2]/tbody/tr/td[2]/select'))

                for typ in list(map(lambda x:x.text,doctyp.options)):
                    if 'PDF' in typ:
                        doctyp.select_by_visible_text('PDF')
                        time.sleep(self.timeBwPage)
                        self.logStatus("info", "doc type selected", self.takeScreenshot())
                        break
            
            dwnldelem=self.driver.find_element_by_xpath('/html/body/form[1]/table[3]/tbody/tr[2]/td/a[2]')
            dwnldelem.click()
            self.logStatus("info", "download btn clicked", self.takeScreenshot())
            
            time.sleep(5)
            
            cnfrmbtn=self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[10]/td/a[1]')
            cnfrmbtn.click()
            self.logStatus("info", " confirm download btn clicked", self.takeScreenshot())
            
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

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame('nav')

        if self.check_exists_by_xpath('/html/body/form/table/tbody/tr[1]/td[2]/font/a[2]'):
            self.driver.find_element_by_xpath('/html/body/form/table/tbody/tr[1]/td[2]/font/a[2]').click()
            time.sleep(self.timeBwPage)
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
#     obj=CUBScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('6018976','RIL123456','','')
#     print(opstr)
#     res=obj.downloadData('25-12-2017','16-01-2021','12378277','','')
#     a,b=obj.logout()
#     obj.closeDriver()