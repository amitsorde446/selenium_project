import os
import shutil
import time
from webdriver_manager.chrome import ChromeDriverManager

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
from Otp_sending import emailsending,msgsending
from data_base import DB
from rdb import RDB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz
print("+++++++++++++++++++++++++++++++=")

class KMBScrapper:
    
    def __init__(self,refid, timeBwPage=3,env='dev',mode='headless'):
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
        self.robj=RDB(**self.rdbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url='https://netbanking.kotak.com/knb2/'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver,10)

    def readConfig(self):
        configFileName = f"config_{self.env}.json"
        with open(configFileName, 'r') as confFile:
            config = json.load(confFile)
            self.driverConfig = config['driverConfig']
            self.dbConfig = config['dbConfig']
            self.rdbConfig = config['rdbConfig']

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

    def createDriver(self, mode='headless'):

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

        print("+++++++++++++++++++++++++++++++++++++++++++++++++++")
        self.chromeOptions.add_experimental_option("prefs", self.prefs)
        driver = webdriver.Chrome(ChromeDriverManager().install(),
                                  chrome_options=self.chromeOptions)
        return driver

        # try:
        #     if self.driverPath is None:
        #         driver = webdriver.Chrome(chrome_options=self.chromeOptions)
        #         driver.maximize_window()
        #     else:
        #         driver = webdriver.Chrome(ChromeDriverManager.install(), chrome_options=self.chromeOptions)
        #         driver.maximize_window()
        #
        # except Exception as e:
        #     self.logStatus("error", str(e))
        #     print(f'Driver error : {e}')
        #
        # self.params = {
        #     'cmd': 'Page.setDownloadBehavior',
        #     'params': {
        #         'behavior': 'allow',
        #         'downloadPath': self.pdfDir
        #     }
        # }
        #
        # self.logStatus("info", "Driver created")


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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'KOTAK', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName),self.ref_id + "/" + "screenshot/"+sname)
        return sname

    def saving_pdf(self):
        d_lt=os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), self.ref_id + "/"+"automated_pdf_files/"+ i)
        if len(d_lt)>0:
            self.logStatus("info", "pdfs downloaded")
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            self.logStatus("info", "no pdf downloaded")
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def fill_login_details(self,username,password):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        if self.check_exists_by_id('userName'):
            usernameInputField = self.driver.find_element_by_id('userName')
            usernameInputField.clear()
            usernameInputField.send_keys(username)
            self.logStatus("info", "username entered", self.takeScreenshot())
        else:
            print(f'Website error 404')
            self.logStatus("error", "website 404 error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}

        nextBtn = self.driver.find_element_by_class_name('cardFooter').find_element_by_tag_name('button')
        nextBtn.click()
        self.logStatus("info", "next button clicked", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        PasswordField = self.driver.find_element_by_id('credentialInputField')
        PasswordField.send_keys(password)
        self.logStatus("info", "password entered", self.takeScreenshot())

        secureLgn = self.driver.find_element_by_class_name('cardFooter').find_element_by_tag_name('button')
        secureLgn.click()
        self.logStatus("info", "securelogin1 button clicked", self.takeScreenshot())

        time.sleep(self.timeBwPage)

        allDiv = self.driver.find_elements_by_tag_name('div')
        for dv in allDiv:
            if dv.get_attribute('class') == 'Routerbox ng-trigger ng-trigger-fadeAnimation':
                if 'Login unsuccessful' in dv.text:
                    self.logStatus("error", "incorrect username", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "EWC002",
                            "responseMsg": "Incorrect UserName Or Password."}
            elif dv.get_attribute('class') == 'alert alert-primary':
                if 'Login details do not match' in dv.text:
                    self.logStatus("error", "incorrect password", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "EWC002",
                            "responseMsg": "Incorrect UserName Or Password."}

    def login(self,username,password,seml,smno):

        self.fill_login_details(username,password)

        time.sleep(self.timeBwPage)
        olp=1
        reid=self.ref_id
        tmi=datetime.now()
        tmo=datetime.now()+timedelta(seconds=88)
        emailsending(seml,reid,'90')
        # msgsending(rec_m,reid,'1.5')
        self.robj.insert(reid,"","","")

        otpexpirecounter = 0

        while olp<3 and otpexpirecounter<3:

            if datetime.now()>tmo:
                self.logStatus("error", "OTP timeout", self.takeScreenshot())
                self.robj.insertone(reid,'Response','EOE082')
                self.robj.insertone(reid,'Status','Expired')
                self.logStatus("error", "OTP Expired", self.takeScreenshot())
                self.robj.deleteall(reid)

                if otpexpirecounter <3:
                    otpexpirecounter +=1
                    self.fill_login_details(username, password)
                    time.sleep(self.timeBwPage)
                    tmi = datetime.now()
                    tmo = datetime.now() + timedelta(seconds=88)
                    emailsending(seml, reid, '90')
                    self.robj.insert(reid, "", "", "")
                else:
                    break

            if self.robj.fetch(reid,'Otp')!='':
                time.sleep(self.timeBwPage)



                if self.check_exists_by_id('otpMobile'):
                    captchaField = self.driver.find_element_by_id('otpMobile')
                    captchaField.clear()
                else:
                    self.logStatus("error", "website not working", self.takeScreenshot())
                    return {"referenceId": self.ref_id, "responseCode": "EIS042",
                            "responseMsg": "Information Source is Not Working"}

                oottpp=self.robj.fetch(reid,'Otp')
                self.logStatus("info", f"OTP : {oottpp}", self.takeScreenshot())
                
                captchaField.send_keys(oottpp)
                self.logStatus("info", "OTP entered", self.takeScreenshot())

                secureLgn=self.driver.find_element_by_class_name('cardFooter').find_element_by_tag_name('button')
                secureLgn.click()
                self.logStatus("info", "securelogin2 button clicked", self.takeScreenshot())
                
                time.sleep(self.timeBwPage)
                
                allDiv=self.driver.find_elements_by_tag_name('div')
                errorfound=False
                self.check_exists_by_classname('alert alert-primary')
                for dv in allDiv:
                    try:

                        if dv.get_attribute('class')=='alert alert-primary':
                            if "Incorrect OTP" in dv.text:
                                self.logStatus("debug", "Incorrect Otp", self.takeScreenshot())
                                self.robj.insertone(reid,'Response','ETP011')
                                self.robj.insertone(reid,'Otp','')
                                olp+=1
                                errorfound=True
                                break
                    except Exception as e:
                        print(e)
                        break

                if errorfound==False:
                    self.logStatus("info", "OTP success", self.takeScreenshot())
                    self.robj.insertone(reid,'Response','SOA078')
                    time.sleep(self.timeBwPage)
                    self.robj.deleteall(reid)
                    break

        if olp==3 or otpexpirecounter==3:
            self.logStatus("error", "no of attempts exhausted", self.takeScreenshot())
            self.robj.deleteall(reid)
            self.logStatus("error", "Authentication Failed", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

        allDiv=self.driver.find_elements_by_tag_name('div')
        for dv in allDiv:
            if dv.get_attribute('class')=='Routerbox ng-trigger ng-trigger-fadeAnimation':
                if '2-Step verification at dashboard' in dv.text:
                    self.logStatus("info", "2-step verification setup popup", self.takeScreenshot())
                    notNow=self.driver.find_element_by_class_name('cardFooter').find_element_by_tag_name('button')
                    notNow.click()
                    self.logStatus("info", "next btn clicked", self.takeScreenshot())
                break

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}

    def calenderselect(self,ftday,ftmonth,ftyear):

        dateElem=self.driver.find_element_by_tag_name('ngb-datepicker')
        selectElems=dateElem.find_elements_by_tag_name('select')
        for selm in selectElems:
            if selm.get_attribute('title')=='Select year':
                yearSelector=Select(selm)
                break

        for yr in list(map(lambda x:x.text,yearSelector.options)):
            if ftyear==yr:
                yearSelector.select_by_visible_text(yr)
                self.logStatus("info", "year selected", self.takeScreenshot())
                break
                
        dateElem=self.driver.find_element_by_tag_name('ngb-datepicker')
        selectElems=dateElem.find_elements_by_tag_name('select')
        for selm in selectElems:
            if selm.get_attribute('title')=='Select month':
                mnthSelector=Select(selm)
                break

        for mnth in list(map(lambda x:x.text,mnthSelector.options)):
            if ftmonth==mnth:
                mnthSelector.select_by_visible_text(mnth)
                self.logStatus("info", "month selected", self.takeScreenshot())
                break
                
        day=int(ftday)
        mnthView=self.driver.find_element_by_tag_name('ngb-datepicker-month-view')
        rowElem=mnthView.find_elements_by_tag_name('div')
        start,selected=False,False
        for rws in rowElem:
            if rws.get_attribute('role')=='row':
                cols=rws.find_elements_by_tag_name('div')
                for cl in cols:
                    if cl.text=='1' and start==False:
                        start=True
                    if str(day)==cl.text and start==True:
                        if 'disabled' in cl.get_attribute('class'):
                            day+=1
                        else:
                            cl.click()
                            self.logStatus("info", "day selected", self.takeScreenshot())
                            selected=True
                            break
                if selected==True:
                    break                

    def downloadData(self,fromdate,todate,accountno,seml,smno):
        time.sleep(self.timeBwPage)
        try:
            allDiv=self.driver.find_elements_by_tag_name('div')
        except:
            time.sleep(10)
            allDiv=self.driver.find_elements_by_tag_name('div')


        for dv in allDiv:
            if dv.get_attribute('class')=='section-dashboard left-side-nav-bar RLCC':
                navBar=dv
                break
                
        spanElem=navBar.find_elements_by_tag_name('span')
        for spn in spanElem:
            if 'Statements'==spn.text:
                spn.click()
                self.logStatus("info", "statements selected", self.takeScreenshot())
                break
                
        time.sleep(self.timeBwPage)
                
        optionsHead=self.driver.find_elements_by_tag_name('p')
        for opt in optionsHead:
            if 'Account Statements'==opt.text:
                opt.click()
                self.logStatus("info", "account statement selected", self.takeScreenshot())
                break
                
        time.sleep(self.timeBwPage)

        if len(fromdate)==7 and len(todate)==7:
            tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
            fromdate='01'+"-"+fromdate
            todate=str(tdy)+"-"+todate

        fromdate=datetime.strptime(fromdate, '%d-%m-%Y')
        todate=datetime.strptime(todate, '%d-%m-%Y')

        accpdt=datetime.now()-relativedelta(months=16)+timedelta(days=5)
        accpdt=accpdt.strftime('%d-%m-%Y')
        accpdt=datetime.strptime(accpdt, '%d-%m-%Y')

        if fromdate<accpdt and todate>accpdt:
            fromdate=accpdt
            self.logStatus("info", f"from date updated : {fromdate}")
        elif fromdate<accpdt and todate<accpdt:
            self.logStatus("info", "invalid date range")
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
        
        self.logStatus("info", f'Date list : {dt_lst}')

        flcount=1

        for dts in dt_lst:
            fd=datetime.strptime(dts[0], '%Y-%m-%d')
            td=datetime.strptime(dts[1], '%Y-%m-%d')
            self.logStatus("info", f'FROM DATE : {fd}')
            self.logStatus("info", f'TO DATE : {td}')

            fday=str(fd.day)
            fmonth=fd.strftime('%b')
            fyear=str(fd.year)
            tday=str(td.day)
            tmonth=td.strftime('%b')
            tyear=str(td.year)
            
            spanElem=self.driver.find_elements_by_tag_name('span')
            for spn in spanElem:
                if 'Advanced filters' in spn.text:
                    spn.click()
                    self.logStatus("info", "advanced filters selected", self.takeScreenshot())
                    break

            time.sleep(self.timeBwPage)

            # FROM DATE SET

            divElem=self.driver.find_elements_by_tag_name('div')
            for dv in divElem:
                if 'date float-left inline-block' in dv.get_attribute('class'):
                    if 'On / From' in dv.find_element_by_tag_name('label').text:
                        dv.find_element_by_tag_name('input').click()
                    break

            self.logStatus("info", "From Date calender clicked", self.takeScreenshot())
            self.calenderselect(fday,fmonth,fyear)
            self.logStatus("info", "From Date set", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            # TO DATE SET

            divElem=self.driver.find_elements_by_tag_name('div')
            for dv in divElem:
                if 'date float-left inline-block margin-left-16' in dv.get_attribute('class'):
                    if 'To (optional)' in dv.find_element_by_tag_name('label').text:
                        dv.find_element_by_tag_name('input').click()
                    break  

            self.logStatus("info", "To Date calender clicked", self.takeScreenshot())
            self.calenderselect(tday,tmonth,tyear)
            self.logStatus("info", "To Date set", self.takeScreenshot())
            time.sleep(self.timeBwPage)

            self.driver.find_element_by_xpath('/html/body/ngb-modal-window/div/div/div[2]/div/button').click()
            time.sleep(5)
            
            if self.check_exists_by_xpath('/html/body/app-root/div/app-core/div/div/div/div/app-statement/div/div[2]/section[1]/app-recent-statement/div/div[4]/div[2]'):
                errormsg=self.driver.find_element_by_xpath('/html/body/app-root/div/app-core/div/div/div/div/app-statement/div/div[2]/section[1]/app-recent-statement/div/div[4]/div[2]')
                if 'No Transactions found' in errormsg.text:
                    self.logStatus("info", "no transaction for this period", self.takeScreenshot())
                    time.sleep(self.timeBwPage)
                
                else:
                    spanElem=self.driver.find_elements_by_tag_name('span')
                    for spn in spanElem:
                        if 'Download Statements' in spn.text:
                            spn.click()
                            self.logStatus("info", "download statements clicked", self.takeScreenshot())
                            break

                    time.sleep(1)

                    liElem=self.driver.find_elements_by_tag_name('li')
                    for li in liElem:
                        if 'Download' in li.text:
                            li.click()
                            self.logStatus("info", "download clicked", self.takeScreenshot())
                            break

                    time.sleep(1)

                    liElem=self.driver.find_elements_by_tag_name('li')
                    for li in liElem:
                        if 'PDF' in li.text:
                            li.click()
                            self.logStatus("info", "PDF clicked", self.takeScreenshot())
                            break

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
            self.driver.find_element_by_xpath('/html/body/app-root/div/app-core/div/app-header/div/div[4]/div/ul/li[4]').click()
            self.logStatus("info", "profile btn clicked", self.takeScreenshot())
            time.sleep(self.timeBwPage)
            self.driver.find_element_by_xpath('/html/body/app-root/div/app-core/div/app-header/div/div[4]/div/div/div/div[2]/div[3]').click() 
            self.logStatus("info", "logout btn clicked", self.takeScreenshot())

            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:

            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return "unsuccessfull",{"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     # print(f'RefID : {str(uuid.uuid1())}')
#     obj=KMBScrapper('36526494-4a6f-11eb-80ce-7440bb00d0c5')
#     opstr=obj.login('370046520','Alienware@11..','','')
#     print(opstr)
#     res=obj.downloadData('01-08-2019','02-02-2021','7013017247','','')
#     a,b=obj.logout()
#     obj.closeDriver()