import os
import shutil
import time
from botocore.exceptions import ClientError
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from datetime import datetime,timedelta
from data_base import DB
from rdb import RDB
import json
import boto3
from botocore.exceptions import ClientError
import uuid
from Otp_sending import emailsending,msgsending
import socket
import calendar
print("++++++++++++++++++++++++++++++++++++++++++++++++++++++")
class KTKScrapper:
    
    def __init__(self,refid, timeBwPage=2,env='dev',mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", ("env value should be either quality or prod or dev or sandbox")
        self.env = env
        hostname = socket.gethostname()    
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots")
        self.pdfDir = os.path.join(os.getcwd(), "pdfs")
        self.ref_id = refid
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath='/'
        self.dbObj = DB(**self.dbConfig)
        self.robj=RDB(**self.rdbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url='https://www.kotak.com/j1001mp/netapp/MainPage.jsp'
        self.driver = self.createDriver(mode="headless")
        self.wait = WebDriverWait(self.driver,5)

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

    def createDriver(self, mode='headless'):
        print("+++++++++++++++++++++++++++++++++++")

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
            print("-----------------------------------------------")

        self.chromeOptions.add_experimental_option("prefs", self.prefs)
        driver = webdriver.Chrome(ChromeDriverManager.install(), chrome_options=self.chromeOptions)
        self.logStatus("info", "Driver created")
        return driver


        # try:
        #     if self.driverPath is None:
        #         driver = webdriver.Chrome(chrome_options=self.chromeOptions)
        #         # driver.maximize_window()
        #     else:
        #         driver = webdriver.Chrome(ChromeDriverManager.install(), chrome_options=self.chromeOptions)
        #         # driver.maximize_window()
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
        if self.dbObj is not None:
            self.dbObj.insertLog(self.ref_id, time.strftime('%Y-%m-%d %H-%M-%S'), level, message, 'KOTAKBANK', self.env,
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
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), self.ref_id + "/"+"automated_pdf_files/"+ i)
            self.logStatus("info", "pdf downloaded")
        if len(d_lt)>0:
            return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        elif len(d_lt)==0:
            return {"referenceId":self.ref_id,"responseCode":"END013","responseMsg":"No Data Available"}

    def login(self,username,password,rec_em,rec_m):
        lg=3
        while lg>0:
            try:
                self.driver.get(self.url)
                self.logStatus("info", "website opened", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}       

            try:
                self.driver.switch_to_frame("framemain")
                self.driver.find_element_by_xpath('/html/body/div[1]/div/a[2]/img').click()
                usernameInputField = self.driver.find_element_by_xpath("/html/body/form/div[1]/div[2]/div[1]/div[1]/div[1]/div/div/div[1]/fieldset/div[1]/div/div/div[1]/input")
                usernameInputField.clear()
                usernameInputField.send_keys(username)
                self.logStatus("info", "username entered", self.takeScreenshot())
            except Exception as e:
                print(f'Website error : {e}')
                self.logStatus("error", "website error", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"EIS042","responseMsg":"Information Source is Not Working"}       

            time.sleep(self.timeBwPage)

            PasswordField = self.driver.find_element_by_xpath('/html/body/form/div[1]/div[2]/div[1]/div[1]/div[1]/div/div/div[1]/fieldset/div[2]/input[1]')
            PasswordField.clear()
            PasswordField.send_keys(password)
            self.logStatus("info", "password entered", self.takeScreenshot())

            lgnbtn = self.driver.find_element_by_xpath('/html/body/form/div[1]/div[2]/div[1]/div[1]/div[1]/div/div/div[1]/fieldset/div[6]/a[2]')
            lgnbtn.click()

            time.sleep(self.timeBwPage)
                
            try:
                alert=self.driver.switch_to_alert()
                print(alert.text)
                txt=alert.text
                alert.accept()
                self.driver.switch_to_default_content()
                if "Please enter correct User ID and password" in txt:
                    return {"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}
            except Exception as e:
                print(f'Alert box : {e}')
                
            time.sleep(self.timeBwPage)
            olp=3
            reid=self.ref_id+'_'+str(lg)
            tmi=datetime.now()
            tmo=datetime.now()+timedelta(seconds=90)
            emailsending(rec_em,reid)
            # msgsending(rec_m,reid,'1.5')
            self.robj.insert(reid,"","","")
            scs=False
            while olp>0:

                if datetime.now()>tmo:
                    print('OTP timeout')
                    self.robj.insertone(reid,'Response','EGO045')
                    self.robj.insertone(reid,'Status','Expired')
                    self.initiallogout()
                    time.sleep(1)
                    self.driver.refresh()
                    self.driver.switch_to_default_content()
                    break

                if self.robj.fetch(reid,'Otp')!='':
                    OTPField = self.driver.find_element_by_xpath('/html/body/div/div[2]/div[1]/div/div/div/div[1]/form/fieldset/div[1]/input')
                    OTPField.clear()
                    oottpp=self.robj.fetch(reid,'Otp')
                    print(f"OTP : {oottpp}")
                    OTPField.send_keys(oottpp)

                    lgnbtn = self.driver.find_element_by_xpath('/html/body/div/div[2]/div[1]/div/div/div/div[1]/form/fieldset/div[2]/a[1]')
                    lgnbtn.click()

                    try:
                        alert=self.driver.switch_to_alert()
                        print(alert.text)
                        txt=alert.text
                        alert.accept()
                        self.driver.switch_to_default_content()
                        if "You have entered an incorrect One time Password" in txt:
                            print("Incorrect Otp")
                            self.robj.insertone(reid,'Response','EAU043')
                            self.robj.insertone(reid,'Otp','')
                            olp-=1
                            tmo=datetime.now()+timedelta(seconds=90)
                            self.driver.switch_to_frame("framemain")
                        if "Your One time Password has expired" in txt:
                            print("Otp expired")
                            self.robj.insertone(reid,'Response','EGO045')
                            self.robj.insertone(reid,'Status','Expired')
                            self.initiallogout()
                            time.sleep(1)
                            self.driver.refresh()
                            self.driver.switch_to_default_content()
                            break
                    except Exception as e:
                        print(f'Alert box : {e}')
                        print('OTP success')
                        self.robj.insertone(reid,'Response','SAC041')
                        scs=True
                        break
                time.sleep(2)
            
            if scs==False:
                lg-=1
                self.robj.deleteall(reid)
                continue

            if self.check_exists_by_xpath('/html/body/center/font/form/font/table/tbody/tr/td/blockquote/blockquote/center/h3/nobr'):
                hd=self.driver.find_element_by_xpath('/html/body/center/font/form/font/table/tbody/tr/td/blockquote/blockquote/center/h3/nobr')
                if hd.text=='Change Password':
                    print('Authentication Failed')
                    return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

            if scs==True:
                self.robj.deleteall(reid)
                self.logStatus("info", "login successfull", self.takeScreenshot())
                return {"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
                break
                 
        return {"referenceId":self.ref_id,"responseCode":"EAF010","responseMsg":"Authentication Failed"}

    def downloadData(self,fromdate,todate,accountno,rec_em,rec_m):
        time.sleep(self.timeBwPage)

        if len(fromdate)==7 and len(todate)==7:
            tdy=calendar.monthrange(int(todate[3:]),int(todate[:2]))[1]
            fromdate='01'+"-"+fromdate
            todate=str(tdy)+"-"+todate
    
        self.driver.switch_to_default_content()
        self.driver.switch_to_frame("framemain")
        iframe1 = self.driver.find_elements_by_tag_name("iframe")[1]
        self.driver.switch_to_frame(iframe1)
        self.driver.find_element_by_xpath('/html/body/div[1]/div/div/ul/li[8]/a').click()

        time.sleep(self.timeBwPage)

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame("framemain")
        self.driver.find_element_by_xpath('/html/body/div[4]/ul/li[6]/a').click()

        time.sleep(self.timeBwPage)

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame("framemain")
        iframe1 = self.driver.find_elements_by_tag_name("iframe")[2]
        self.driver.switch_to_frame(iframe1)
        self.driver.switch_to_frame('appmenu')
        self.driver.find_element_by_xpath('/html/body/table/tbody/tr[2]/td/a').click()

        time.sleep(self.timeBwPage)

        self.driver.switch_to_default_content()
        self.driver.switch_to_frame("framemain")
        iframe1 = self.driver.find_elements_by_tag_name("iframe")[2]
        self.driver.switch_to_frame(iframe1)
        self.driver.switch_to_frame('right_bottom')
        table=self.driver.find_element_by_xpath('/html/body/form/table[2]/tbody')
        rows=table.find_elements_by_tag_name('tr')

        fd=datetime.strptime(fromdate, '%d-%m-%Y')
        td=datetime.strptime(todate, '%d-%m-%Y')

        if td.year>=datetime.now().year and td.month>=datetime.now().month:
            td=datetime.now()-timedelta(days=1)

        fmonth=fd.strftime('%b')
        fyear=str(fd.strftime('%y'))
        tmonth=td.strftime('%b')
        tyear=str(td.strftime('%y'))
        yrs=list(range(int(fyear),int(tyear)+1))
        mnth_lst=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul' , 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        yr_dict=[]
        apnd=False
        for yr in yrs:
            for m in mnth_lst:
                if m==fmonth and str(yr)==fyear:
                    apnd=True
                if apnd==True:
                    yr_dict.append(m+'-'+str(yr))
                if m==tmonth and str(yr)==tyear:
                    apnd=False

        for r in rows[1:]:
            columns=r.find_elements_by_tag_name('td')
            print(list(map(lambda x:x.text,columns)))
            if columns[0].text in yr_dict:
                print('yes')
                columns[1].find_element_by_tag_name('a').click()

        time.sleep(self.timeBwPage)
        dic=self.saving_pdf()
        return dic

    def initiallogout(self):
        time.sleep(self.timeBwPage)
        self.driver.switch_to_default_content()
        self.driver.switch_to_frame("framemain")
        self.driver.find_element_by_xpath('/html/body/div/div[1]/div/div/a').click()

    def logout(self):
        time.sleep(self.timeBwPage)
        try:
            self.driver.switch_to_default_content()
            self.driver.switch_to_frame("framemain")
            iframe1 = self.driver.find_elements_by_tag_name("iframe")[0]
            self.driver.switch_to_frame(iframe1)
            self.driver.find_element_by_xpath('//*[@id="logout"]').click()
            return "successfull",{"referenceId":self.ref_id,"responseCode":"SRC001","responseMsg":"Successfully Completed."}
        except:
            return "unsuccessfull",{"referenceId":self.ref_id,"responseCode":"EWC002","responseMsg":"Incorrect UserName Or Password."}

    def closeDriver(self):
        time.sleep(self.timeBwPage)
        shutil.rmtree(self.pdfDir)
        shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     obj=KTKScrapper('QWERTY123')
#     opstr=obj.login('370046520','!QAZ1qaz','yogesh.sati@scoreme.in','9560119795')
#     print(opstr)
#     if opstr=='LOGIN SUCCESSFULL':
#         obj.downloadData('26-05-2020','10-09-2020')
#         obj.logout()
#     obj.closeDriver()