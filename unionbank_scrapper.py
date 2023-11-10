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

from webdriver_manager.chrome import ChromeDriverManager

from data_base import DB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
import pytz


class UNIONScrapper:
    
    def __init__(self,refid, timeBwPage=5,env='quality',mode='headless'):
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
        
        
        """ netbanking url """
        self.netbanking_url = "https://www.unionbankonline.co.in/corp/AuthenticationController?__START_TRAN_FLAG__=Y&FORMSGROUP_ID__=AuthenticationFG&__EVENT_ID__=LOAD&FG_BUTTONS__=LOAD&ACTION.LOAD=Y&AuthenticationFG.LOGIN_FLAG=1&BANK_ID=026&LANGUAGE_ID=001"
        self.user_id_xp = "/html/body/form/div/div/div[5]/div[1]/p[1]/span[2]/span/input"
        self.login_button_xp = "/html/body/form/div/div/div[5]/div[1]/p[5]/span/span/input"

        self.verification_input_xp = "/html/body/form/div/div/div[5]/div[1]/p[4]/span/span/input"
        self.verification_text_xp = "/html/body/form/div/div/div[5]/div[1]/p[3]/span[2]/label"
        self.verification_refresh_xp = "/html/body/form/div/div/div[5]/div[1]/p[3]/span[2]/a/img"

        self.confirm_phrase_xp = "/html/body/form/div/div/div[4]/div[1]/p[3]/span[1]/input"

        self.password_xp = "/html/body/form/div/div/div[4]/div[1]/p[5]/span[2]/input"

        self.login_confirm_xp = "/html/body/form/div/div/div[4]/div[1]/p[6]/span/span[1]/input"

        self.header_xp = "/html/body/form/div/div/div[2]/div/div/div"

        self.accounts_xp = "/html/body/form/div/div/div[2]/div/div/div/div/div/ul/li[2]/a"

        self.balance_xp = "/html/body/form/div/div/div[2]/div/div/div/div/div/ul/li[2]/div/div/div[2]/ul/li[1]/a"

        self.account_summary_xp = "/html/body/form/div/div/div[2]/div/div/div/div/div/ul/li[2]/div/div/div[2]/ul/li[1]/ul/li[4]/a"

        self.accounts_table_class = "width100percent footable-loaded footable BreakPointE"
        self.accounts_table_xp    = '/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[3]/div/div/div/div/table'

        self.view_statement_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[4]/div/h3/a/img"

        self.from_calendar_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[4]/div/div/div[2]/p[2]/span[1]/span/span/img"
        self.to_calendar_xp   = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[4]/div/div/div[2]/p[2]/span[2]/span/span/img"

        self.search_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[4]/div/div/div[2]/p[11]/span[2]/span/input"

        self.calendar_alert_class = "errorContentWrapper redbg"

        self.format_select_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[6]/div/div/p/span[1]/span[2]/a"
        self.format_input_xp = """//*[@id="PageConfigurationMaster_RACUX3W__1:TransactionHistoryFG.OUTFORMAT_comboText"]"""

        self.format_button_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[4]/div[6]/div/div/p/span[1]/span[3]/input"
        self.logout_xp = "/html/body/form/div/div/div[1]/div/div/div/div[2]/ul/li[4]/p/span/span/a"
        self.logout_confirm_xp = "/html/body/div[3]/div[2]/div/div[3]/div/div/div/p[3]/span/span[2]/a"
        
        self.date_status = "notExist"
        self.funct_error_xp = "/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[3]/div[2]"
        
        self.view_statement_id = "PageConfigurationMaster_RACUX3W__1:searchHeader"
        self.from_calendar_id = "PageConfigurationMaster_RACUX3W__1:TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG"
        self.to_calendar_id   = "PageConfigurationMaster_RACUX3W__1:TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG"
        self.search_id = "PageConfigurationMaster_RACUX3W__1:SEARCH"
        
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

    def check_exists_by_classname(self,classname):
        try:
            self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, classname)))
        except:
            return False
        return True
    
    def check_exists_by_id(self,idd):
        try:
            self.wait.until(EC.visibility_of_element_located((By.ID, idd)))
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
                # ChromeDriverManager().install()
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions) #, chrome_options=self.chromeOptions
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'UNION', self.env,
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
            self.uploadToS3(os.path.join(pdfname), self.ref_id + "/"+"automated_pdf_files/"+ i)
            self.logStatus("info", "pdf downloaded")
#         if len(d_lt)>0:
#             return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
#         elif len(d_lt)==0:
#             return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self,username,password,seml,smno):

        try:
            self.driver.get(self.netbanking_url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}

        user_id = self.driver.find_element_by_xpath(self.user_id_xp)
        user_id.clear()
        user_id.send_keys(username)
        
        self.logStatus("info", "username entered", self.takeScreenshot())


        verification_text = self.driver.find_element_by_xpath(self.verification_text_xp).text



        while verification_text=="":
            self.driver.find_element_by_xpath(self.verification_refresh_xp).click()
            time.sleep(1)
            verification_text = self.driver.find_element_by_xpath(self.verification_text_xp).text



        if "biggest" in verification_text : 
            l1 = verification_text.split("value ")[1].split("?")[0].split(",")

            answer = str(max([int(i) for i in l1]))

        elif "smallest" in verification_text : 
            l1 = verification_text.split("value ")[1].split("?")[0].split(",")

            answer = str(min([int(i) for i in l1]))

        elif "result" in verification_text : 

            s1 = verification_text.split("of ")[1].split("?")[0]


            l1 = s1.split("+")
            answer = sum([int(i) for i in l1])

        print(verification_text , answer)
        print("")

        verification_input = self.driver.find_element_by_xpath(self.verification_input_xp)
        verification_input.clear()
        verification_input.send_keys(answer)
        self.logStatus("info", "verification question answered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.login_button_xp).click()
        
        self.driver.find_element_by_xpath(self.confirm_phrase_xp).click()
        self.logStatus("info", "phrase ticked", self.takeScreenshot())

        pass_word = self.driver.find_element_by_xpath(self.password_xp)
        pass_word.clear()
        pass_word.send_keys(password)
        
        self.logStatus("info", "password entered", self.takeScreenshot())

        self.driver.find_element_by_xpath(self.login_confirm_xp).click()
        x=self.driver.find_element_by_xpath("/html/body/form/div/div/div[4]/div[2]/span").text
        print("==========================",x)
        try:
            x = self.driver.find_element_by_xpath("/html/body/form/div/div/div[4]/div[2]/span").text
            x=str(x)
            x=x.split("The")

            if ' user ID or Password is invalid.' in x:
                print("invalid login credentials")
                self.logStatus("error", "invalid login credentials", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
        except:
            pass

        try:
            alert=self.driver.switch_to_alert()
            print(alert.text)
            alert.accept()
            self.driver.switch_to_default_content()

        except Exception as e:
            print(f'Alert box : {e}')  

        self.logStatus("info", "login successfull", self.takeScreenshot())        
        return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}    

    def calenderSelector(self,day,month,year):
        
        self.check_exists_by_xpath('/html/body/div[9]/div/div[2]/div/div/select[2]')
        yr=Select(self.driver.find_element_by_xpath('/html/body/div[9]/div/div[2]/div/div/select[2]'))
        yr.select_by_visible_text(year)
        
        self.check_exists_by_xpath('/html/body/div[9]/div/div[2]/div/div/select[1]')
        mnth=Select(self.driver.find_element_by_xpath('/html/body/div[9]/div/div[2]/div/div/select[1]'))
        mnth.select_by_visible_text(month)

        self.check_exists_by_xpath('/html/body/div[9]/div/div[2]/div/table/tbody')
        dt=self.driver.find_element_by_xpath('/html/body/div[9]/div/div[2]/div/table/tbody')
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
        import time
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
            fd=datetime.strptime(dts[0], '%Y-%m-%d')
            td=datetime.strptime(dts[1], '%Y-%m-%d')
            fday=str(fd.day)
            fmonth=fd.strftime('%B')
            fyear=str(fd.year)
            tday=str(td.day)
            tmonth=td.strftime('%B')
            tyear=str(td.year)
            if self.check_exists_by_xpath(self.accounts_xp):
                try:
                    self.driver.find_element_by_xpath(self.accounts_xp).click()
                    self.driver.find_element_by_xpath(self.balance_xp).click()
                except:
                    import time
                    time.sleep(5)
                    self.driver.find_element_by_xpath(self.balance_xp).click()
                self.driver.find_element_by_xpath(self.account_summary_xp).click()
                self.logStatus("info", "select account summary")
            else:
                self.logStatus("critical", "page option  not found", self.takeScreenshot())
            if self.check_exists_by_xpath(self.funct_error_xp) and "functionality" in self.driver.find_element_by_xpath(self.funct_error_xp).text:
                self.logStatus("critical", "functionality not exist", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}
            acc_status=0
            if self.check_exists_by_xpath(self.accounts_table_xp):
                print("1")
                while True:
                    acc_status = 0
                    for row in self.driver.find_element_by_xpath(self.accounts_table_xp).find_element_by_tag_name("tbody").find_elements_by_tag_name("tr"):
                        for column in row.find_elements_by_tag_name("td"):
                            if accountno in column.text:
                                column.find_element_by_tag_name("a").click()
                                print(f'Acc number : {column.text}')
                                acc_status = 1
                                break
                        if acc_status==1:
                            break
                    time.sleep(5)
                    if self.check_exists_by_id(self.view_statement_id):
                        break
            if acc_status==0:
                return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}
            time.sleep(2) 
            self.driver.find_element_by_id(self.view_statement_id).click()
            # FROM DATE SET
            time.sleep(1)
            self.driver.find_element_by_id(self.from_calendar_id).click()
            time.sleep(1)
            self.calenderSelector(fday,fmonth,fyear)
            self.logStatus("info", "from date set", self.takeScreenshot())
            # TO DATE SET
            time.sleep(1)
            self.driver.find_element_by_id(self.to_calendar_id).click()
            time.sleep(1)
            self.calenderSelector(tday,tmonth,tyear)
            self.logStatus("info", "to date set", self.takeScreenshot())
            self.driver.find_element_by_id(self.search_id).click() 
            try:
                time.sleep(3)
                if "not exist" in self.driver.find_element_by_xpath("/html/body/form/div/div/div[3]/div[1]/div[1]/div[3]/div/div[3]/div/div/div[1]/div/div[3]/div[2]").text:
                    pass
                print('yooo')
            except:
                print("tyt")
                self.date_status = "exist"
                time.sleep(2)
                if self.check_exists_by_xpath(self.format_select_xp):
                    self.driver.find_element_by_xpath(self.format_select_xp).click()
                time.sleep(2)
                if self.check_exists_by_xpath(self.format_input_xp):
                    self.driver.find_element_by_xpath("""//*[@id="PageConfigurationMaster_RACUX3W__1:TransactionHistoryFG.OUTFORMAT_comboText"]""").clear()
                    self.driver.find_element_by_xpath("""//*[@id="PageConfigurationMaster_RACUX3W__1:TransactionHistoryFG.OUTFORMAT_comboText"]""").send_keys("PDF")

                #self.driver.find_element_by_xpath(self.format_input_xp).click()
                self.logStatus("info", "select PDF", self.takeScreenshot())
                time.sleep(2)
                if self.check_exists_by_xpath(self.format_button_xp):
                    self.driver.find_element_by_xpath(self.format_button_xp).click()
                time.sleep(5)
        if self.date_status == "notExist":
            self.logStatus("info", "data not exist", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}
        elif self.date_status == "exist" :
            time.sleep(2)
            d_lt=os.listdir(self.pdfDir)
            print(d_lt)
            for fl in d_lt:
                if len(fl[:-4])>2:
                    os.rename(os.path.join(self.pdfDir,fl),os.path.join(self.pdfDir,str(flcount)+'.pdf'))
                    flcount+=1
            self.saving_pdf()
            time.sleep(2)
            self.logStatus("info", "statement downloaded", self.takeScreenshot())
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed"}

    def logout(self):
        try:
            self.driver.find_element_by_xpath(self.logout_xp).click()
            if self.check_exists_by_xpath(self.logout_confirm_xp):
                self.driver.find_element_by_xpath(self.logout_confirm_xp).click()
            
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
#
#     username = "611224067"
#     password = "H@ppyw1r3"
#     accountno   = "30712010000057"
#
#
#     obj=UNIONScrapper('union_test')
#     opstr=obj.login(username,password,"","")
#     if opstr["responseCode"]=='SRC001':
#         #res=obj.downloadData('09-2020','12-2020',accountno,"","")
#         res=obj.downloadData('01-01-2020','30-06-2021',accountno,"","")
#         a,b=obj.logout()
#         obj.closeDriver()