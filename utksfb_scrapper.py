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


class UTKSFBScrapper:
    
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
        self.url='https://netbanking.utkarsh.bank/iportalweb/iRetail@1'
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'UTKSFB', self.env,
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

        if self.check_exists_by_id('userNo'):
            usernameInputField = self.driver.find_element_by_id('userNo')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
            
        PasswordField = self.driver.find_element_by_id('userPin')
        PasswordField.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        lgnbtn = self.driver.find_element_by_id('LOGIN')
        lgnbtn.click()
        self.logStatus("info", "login button clicked", self.takeScreenshot())

        if self.check_exists_by_id('errid1'):
            mssg=self.driver.find_element_by_id('errid1')
            print(mssg.text)
            if 'Invalid User ID / Password' in mssg.text:
                self.logStatus("error", "incorrect credentials", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
 
        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}

    def calenderselect(self,ftday,ftmonth,ftyear):

        divmainlst=self.driver.find_elements_by_tag_name('div')

        for i in divmainlst:
            if i.get_attribute('class')=='x-menu x-menu-floating x-layer x-date-menu x-menu-plain x-menu-nosep':
                tabls=i
                break  

        tabllst=tabls.find_elements_by_tag_name('table')

        for i in tabllst:
            if i.get_attribute('class')=='x-btn x-btn-noicon':
                mntbl=i
                break    

        mntbl.find_element_by_tag_name('button').click()
        time.sleep(2)

        divlst=tabls.find_elements_by_tag_name('div')

        for i in divlst:
            if i.get_attribute('class')=='x-date-mp':
                mnyeartbl=i.find_element_by_tag_name('table')
                break  

        tbody=mnyeartbl.find_element_by_tag_name('tbody')
        trows=tbody.find_elements_by_tag_name('tr')
        mnthsel,yrsel=False,False
        for rw in trows:
            tcol=rw.find_elements_by_tag_name('td')
            for col in tcol:
                if col.text==ftmonth and mnthsel==False:
                    col.find_element_by_tag_name('a').click()
                    mnthsel=True
                if  col.text==ftyear and yrsel==False:
                    col.find_element_by_tag_name('a').click()
                    yrsel=True

        mnyeartbl.find_element_by_class_name('x-date-mp-ok').click()

        time.sleep(2)

        tabllst=tabls.find_elements_by_tag_name('table')

        for i in tabllst:
            if i.get_attribute('class')=='x-date-inner':
                dytbl=i
                break  

        tbody=dytbl.find_element_by_tag_name('tbody')
        trows=tbody.find_elements_by_tag_name('tr')
        startsel=False
        for rw in trows:
            tcol=rw.find_elements_by_tag_name('td')
            for col in tcol:
                if col.text=='1' and startsel==False:
                    startsel=True
                if  col.text==ftday and startsel==True:
                    col.find_element_by_tag_name('a').click()                

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(10)

        if self.check_exists_by_xpath('/html/body/div[1]/div/div/div/div/div/div/div/div[5]/div/div/table/tbody/tr/td/div/div[2]/div[1]/div/div/div/div/div[1]/div/div/div/div/div/table/tbody/tr[1]/td[2]/div/div/div/div/center/div[1]'):
            self.driver.find_element_by_xpath('/html/body/div[1]/div/div/div/div/div/div/div/div[5]/div/div/table/tbody/tr/td/div/div[2]/div[1]/div/div/div/div/div[1]/div/div/div/div/div/table/tbody/tr[1]/td[2]/div/div/div/div/center/div[1]').click()
            self.logStatus("info", "Accounta page clicked", self.takeScreenshot())
        time.sleep(10)

        acc=''
        if self.check_exists_by_classname('x-grid3-row-table'):
            table=self.driver.find_element_by_class_name('x-grid3-row-table')
            tbody=table.find_element_by_tag_name('tbody')
            trows=tbody.find_elements_by_tag_name('tr')

            for accns in trows:
                if accountno in accns.text:
                    acc='Found'
                    accns.click()
                    self.logStatus("info", "Account selected", self.takeScreenshot())
                
        if acc=='':
            
            print('Account number doesnot match')
            self.logStatus("error", "Account number doesn't match", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
        
        else:
            time.sleep(self.timeBwPage)

            if self.check_exists_by_xpath('/html/body/div[2]/div/div/div/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div[1]/div/div/div/div[3]/div/div/div/div/div/div/div[2]/div/div/div/div[2]/div/div/table/tbody/tr[3]/td/div/div/div'):
                self.driver.find_element_by_xpath('/html/body/div[2]/div/div/div/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div[1]/div/div/div/div[3]/div/div/div/div/div/div/div[2]/div/div/div/div[2]/div/div/table/tbody/tr[3]/td/div/div/div').click()
                self.logStatus("info", "View stmt page selected", self.takeScreenshot())

            time.sleep(10)

            radiobtnlst=self.driver.find_elements_by_tag_name('label')

            for i in radiobtnlst:
                if i.get_attribute('class')=='x-form-cb-label' and i.text=='Date Range':
                    i.click()
                    self.logStatus("info", "Date Range radio btn clicked", self.takeScreenshot())
                    break  

            time.sleep(self.timeBwPage)

            if len(fromdate)==7 and len(todate)==7:
                tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
                fromdate='01'+"-"+fromdate
                todate=str(tdy)+"-"+todate

            fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
            todate=datetime.strptime(todate, '%d-%m-%Y')

            accpdt=datetime.now()-relativedelta(years=1)+timedelta(days=1)
            accpdt=accpdt.strftime('%d-%m-%Y')
            accpdt=datetime.strptime(accpdt, '%d-%m-%Y')

            if fromdate<accpdt and todate>accpdt:
                fromdate=accpdt
            elif fromdate<accpdt and todate<accpdt:
                self.logStatus("info", "Invalid Date Range")
                return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

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

            
            print(f'Date list : {dt_lst}')

            flcount=1

            for dts in dt_lst:
                fd=datetime.strptime(dts[0], '%Y-%m-%d')
                td=datetime.strptime(dts[1], '%Y-%m-%d')
                print(f'FROM DATE : {fd}')
                print(f'TO DATE : {td}')

                fday=str(fd.day)
                fmonth=fd.strftime('%b')
                fyear=str(fd.year)
                tday=str(td.day)
                tmonth=td.strftime('%b')
                tyear=str(td.year)

                lst=self.driver.find_elements_by_tag_name('input')

                # FROM DATE SET

                for i in lst:
                    if i.get_attribute('name')=='AST13_FROM_DATE':
                        i.click()
                        break    
                self.logStatus("info", "From Date calender clicked", self.takeScreenshot())
                self.calenderselect(fday,fmonth,fyear)
                self.logStatus("info", "From Date set", self.takeScreenshot())

                # TO DATE SET

                for i in lst:
                    if i.get_attribute('name')=='AST14_TO_DATE':
                        i.click()
                        break    
                self.logStatus("info", "To Date calender clicked", self.takeScreenshot())
                self.calenderselect(tday,tmonth,tyear)
                self.logStatus("info", "To Date set", self.takeScreenshot())

                self.driver.find_element_by_xpath('/html/body/div[2]/div/div/div/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div[1]/div/div/div/div[2]/div/div[1]/div/div/div/div/div[2]/div/div/div/div[2]/div[2]/div[1]/div/div/div/div/div/form/div/table/tbody/tr[2]/td/fieldset/div/div/table/tbody/tr[3]/td/div/div[1]/div/div/div/div/a[1]').click()
                self.logStatus("info", "Pdf option clicked", self.takeScreenshot())
                time.sleep(10)

                
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
            alst=self.driver.find_elements_by_tag_name('a')
            for i in alst:
                if i.get_attribute('title')=='Logout':
                    i.click()
                    break 
            self.logStatus("info", "Logout btn clicked", self.takeScreenshot())

            divslst=self.driver.find_elements_by_tag_name('div')
            a=False
            for i in divslst:
                if i.get_attribute('class')=='x-window-body':
                    popup=i
                    a=True
                    break 

            if a==True:
                if 'Are you sure you want to logout' in popup.text:
                    
                    divslst=self.driver.find_elements_by_tag_name('div')

                    for i in divslst:
                        if i.get_attribute('class')=='x-window-bbar':
                            pubody=i
                            break 

                    tdlst=pubody.find_elements_by_tag_name('td')

                    for i in tdlst:
                        if i.get_attribute('class')=='x-btn-mc' and i.text=='Yes':
                            i.find_element_by_tag_name('button').click()
                            break 
            self.logStatus("info", "Confirm Logout clicked", self.takeScreenshot())

            divslst=self.driver.find_elements_by_tag_name('div')
            a=False
            for i in divslst:
                if i.get_attribute('class')=='x-window-tl':
                    a=True
                    break 
                    
            if a==True:
                    
                divslst=self.driver.find_elements_by_tag_name('div')

                for i in divslst:
                    if i.get_attribute('class')=='x-window-bbar':
                        pubody=i
                        break 

                tdlst=pubody.find_elements_by_tag_name('td')

                for i in tdlst:
                    if i.get_attribute('class')=='x-btn-mc' and i.text=='Ok':
                        i.find_element_by_tag_name('button').click()
                        break 
            self.logStatus("info", "Logout Confirmed", self.takeScreenshot())

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
#     # print(f'RefID : {str(uuid.uuid1())}')
#     obj=USFBScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('sonusonkar01','Ril#54321','','')
#     print(opstr)
#     res=obj.downloadData('01-09-2020','07-01-2021','1386019213884251','','')
#     a,b=obj.logout()
#     obj.closeDriver()