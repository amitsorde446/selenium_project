#https://retail.onlinesbi.com/
import os
import shutil
import time

import cv2
from botocore.exceptions import ClientError
from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from datetime import datetime, timedelta
from data_base import DB
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import boto3
from botocore.exceptions import ClientError
import uuid
import pandas as pd
import socket
import calendar
from google.cloud import vision
from webdriver_manager.chrome import ChromeDriverManager
import pytz



class LaxmiScrapper:

    def __init__(self, refid, timeBwPage=2, env='quality', mode='headless'):
        assert env == "quality" or env == "prod" or env == "dev" or env == "sandbox", (
            "env value should be either quality or prod or dev or sandbox")
        self.env = env
        hostname = socket.gethostname()
        self.ipadd = socket.gethostbyname(hostname)
        self.readConfig()
        self.CreateS3()
        self.ref_id = refid
        self.screenshotDir = os.path.join(os.getcwd(), "Screenshots/" + self.ref_id)
        self.pdfDir = os.path.join(os.getcwd(), "pdfs/" + self.ref_id)
        self.makeDriverDirs('ss')
        self.makeDriverDirs('pdf')
        self.driverPath = '/'
        self.dbObj = DB(**self.dbConfig)
        self.chromeOptions = webdriver.ChromeOptions()
        self.timeBwPage = timeBwPage
        self.url = 'https://www.lvbankonline.in/index.html?module=login'
        self.driver = self.createDriver(mode=mode)
        self.wait = WebDriverWait(self.driver, 5)
        credential_path = r"vision_api_token.json"
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
        self.timeBwPage = 0.5
        self.client = vision.ImageAnnotatorClient()
        self.FILE_NAME = "captcha.png"
        self.FOLDER_PATH = os.getcwd()

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

    def check_exists_by_xpath(self, xpath):
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
                capa = DesiredCapabilities.CHROME
                capa["pageLoadStrategy"] = "none"
                # from pyvirtualdisplay import Display
                # display = Display(visible=0, size=(1366, 768))
                # display.start()
                driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=self.chromeOptions, desired_capabilities=capa)
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
            self.dbObj.insertLog(self.ref_id, tm, level, message, 'LAXMI', self.env,
                                 screenshot,self.ipadd)
        print(f"{level}: {message}, screenshot: {screenshot}")

    def takeScreenshot(self):
        time.sleep(0.5)
        sname = str(uuid.uuid1()) + '.png'
        screenshotName = os.path.join(self.screenshotDir, f"{sname}")
        self.driver.save_screenshot(screenshotName)
        self.uploadToS3(os.path.join(screenshotName), 'screenshots/' + self.ref_id + "/" + sname)
        return sname

    def captchabreaker(self):
        import io
        from google.cloud import vision
        credential_path = r"vision_api_token.json"
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
        self.driver.find_element_by_xpath("""//*[@id="refreshImgCaptcha"]""").screenshot('captcha.png')
        #k = self.dbObj.breakcaptchanow()
        img = cv2.imread(r"captcha.png")
        filename = 'savedImage.jpg'

        # Using cv2.imwrite() method
        # Saving the image
        cv2.imwrite(filename, img)
        img = cv2.imread(r"savedImage.jpg")
        filename = "captcha.png"
        cv2.imwrite(filename, img)
        with io.open(os.path.join(self.FOLDER_PATH, self.FILE_NAME), 'rb') as image_file:
            content = image_file.read()

        image = vision.types.Image(content=content)
        response = self.client.text_detection(image=image)
        texts = response.text_annotations

        for text in texts:
            z = ('"{}"'.format(text.description))
        try:
            h = str(z).split('"')
        except:
            pass
        k = h[1]+"infoss"
        print(k)
        try:
            sname = str(k) + '.png'
            screenshotName = os.path.join(self.screenshotDir, f"{sname}")
            self.driver.find_element_by_xpath("""//*[@id="captchaEpicImg"]""").screenshot(screenshotName)
            self.uploadToS3(os.path.join(screenshotName), 'voter/' + sname)
        except:
            pass
        print(k)
        self.driver.find_element_by_xpath("""//*[@id="loginCaptchaValue"]""").click()
        self.driver.find_element_by_xpath("""//*[@id="loginCaptchaValue"]""").send_keys(k)
        self.driver.find_element_by_xpath("""//*[@id="Button2"]""").click()
        self.logStatus("info", "enter k", self.takeScreenshot())
        # window_before = self.driver.window_handles[0]
        # window_before_title = self.driver.title
        # self.driver.find_element_by_xpath("""//*[@id="btnEpicSubmit"]""").click()
    def breakcaptcha(self):
        import io
        import os
        from google.cloud import vision
        import time
        import io
        self.driver.find_element_by_xpath("""//*[@id="mat-tab-content-0-0"]/div/mat-card-content/app-s110/form/div[1]/div/div[1]/img""").screenshot('captcha.png')
        # k = self.dbObj.breakcaptchanow()
        img = cv2.imread(r"captcha.png")
        filename = 'savedImage.jpg'

        # Using cv2.imwrite() method
        # Saving the image
        cv2.imwrite(filename, img)
        img = cv2.imread(r"savedImage.jpg")
        filename = "captcha.png"
        cv2.imwrite(filename, img)
        with io.open(os.path.join(self.FOLDER_PATH, self.FILE_NAME), 'rb') as image_file:
            content = image_file.read()

        image = vision.types.Image(content=content)
        response = self.client.text_detection(image=image)
        print(response, " response")
        texts = response.text_annotations
        print(texts)
        for text in texts:
            z = ('"{}"'.format(text.description))
        try:
            h = str(z).split('"')
            k = h[1] + "infos"
        except:
            k = "infoss"
            pass


        try:
            sname = str(k) + '.png'
            screenshotName = os.path.join(self.screenshotDir, f"{sname}")
            self.driver.find_element_by_xpath("""//*[@id="captcha"]""").screenshot(screenshotName)
            self.uploadToS3(os.path.join(screenshotName), 'IEC/' + sname)
        except:
            pass
        self.driver.find_element_by_xpath("""//*[@id="mat-input-2"]""").click()

        self.driver.find_element_by_xpath("""//*[@id="mat-input-2"]""").send_keys(k)
        time.sleep(1)
        self.driver.find_element_by_xpath("""//*[@id="mat-tab-content-0-0"]/div/mat-card-content/app-s110/form/div[3]/button""").click()

    def saving_pdf(self):
        d_lt = os.listdir(self.pdfDir)
        print(f"Files : {d_lt}")
        for i in d_lt:
            pdfname = os.path.join(self.pdfDir, i)
            self.uploadToS3(os.path.join(pdfname), 'pdfs/' + self.ref_id + "/" + i)
            self.logStatus("info", "pdf downloaded")
        if len(d_lt) > 0:
            return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}
        elif len(d_lt) == 0:
            return {"referenceId": self.ref_id, "responseCode": "END013", "responseMsg": "No Data Available"}

    def login(self, username, password):

        try:
            self.driver.get(self.url)
            self.logStatus("info", "website opened", self.takeScreenshot())
        except Exception as e:
            print(f'Website error : {e}')
            self.logStatus("error", "website error", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}
        import time
        time.sleep(20)
        tb = self.driver.find_element_by_xpath("""//*[@id="login_username|input"]""").click()
        # window_before = self.driver.window_handles[0]
        # window_after = self.driver.window_handles[1]
        # self.driver.switch_to.window(window_after)
        # tb = self.driver.find_element_by_xpath("""//*[@id="main-wrapper"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/div[2]/div[2]/div[2]""").click()
        self.driver.find_element_by_xpath("""//*[@id="login_username|input"]""").send_keys(username)
        self.driver.find_element_by_xpath("""//*[@id="login_password|input"]""").click()
        time.sleep(2)
        self.driver.find_element_by_xpath("""//*[@id="login_password|input"]""").send_keys(password)
        self.driver.find_element_by_xpath("""//*[@id="ui-id-13"]""").click()
        time.sleep(3)

        try:
            unsuccessful = self.driver.find_element_by_xpath("""//*[@id="maincontent"]/div/div[2]/div[2]/section/div/login-form/div/obdx-component/div/div/div[2]/div/div/span""").text
        except:
            unsuccessful = ""

        print(unsuccessful, " checksuccessful")
        if unsuccessful.find("Invalid Username") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EWC002","responseMsg": "Incorrect UserName Or Password."}
        if unsuccessful.find("Unable to login.") != -1:
            return {"referenceId": self.ref_id, "responseCode": "EIS042","responseMsg": "Information Source is Not Working"}
        time.sleep(5)
        try:
            self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/header/div/obdx-component/div/div/div[1]/div[1]/div""").click()
        except:
            return {"referenceId": self.ref_id, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}
        return {"referenceId": self.ref_id, "responseCode": "SRC001", "responseMsg": "Successfully Completed."}

    def calenderSelector(self, day, month, year):
        if self.check_exists_by_xpath('//*[@id="outerTab"]/div[2]'):
            mnth = Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[1]'))
            mnth.select_by_visible_text(month)

            yr = Select(self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/div/select[2]'))
            yr.select_by_visible_text(year)

            dt = self.driver.find_element_by_xpath('//*[@id="outerTab"]/div[2]/div/div[2]/div/table/tbody')
            dts = dt.find_elements_by_tag_name('tr')
            ext = False
            for i in dts:
                val = i.find_elements_by_tag_name('td')
                for j in val:
                    if str(j.text) == day:
                        j.click()
                        ext = True
                        break

                if ext == True:
                    break

    def calendar(self,fromdate):
        year1  = fromdate.split("/")[2]
        year1 = int(year1)
        # year2 = todate.split("/")[2]
        # year2 = int(year2)
        month1 = fromdate.split("/")[1]
        month1 = int(month1)
        # month2 = todate.split("/")[1]
        # month2 = int(month2)
        from datetime import date
        todays_date = date.today()
        currentyear = todays_date.year
        num = currentyear-year1
        dd = self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[1]/td[2]/span""").text
        if int(dd) < currentyear:
            while dd != str(currentyear):
                dd = self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[1]/td[2]/span""").text
                self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[1]/td[3]""").click()
        while num > 0:
            self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[1]/td[1]/a""").click()
            num = num-1

        currentmonth = self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[3]/td[2]/span""").text
        if currentmonth.find("Jan") != -1:
            currentmonthv = 1
        if currentmonth.find("Feb") != -1:
            currentmonthv = 2
        if currentmonth.find("Mar") != -1:
            currentmonthv = 3
        if currentmonth.find("Apr") != -1:
            currentmonthv = 4
        if currentmonth.find("May") != -1:
            currentmonthv = 5
        if currentmonth.find("Jun") != -1:
            currentmonthv = 6
        if currentmonth.find("Jul") != -1:
            currentmonthv = 7
        if currentmonth.find("Aug") != -1:
            currentmonthv = 8
        if currentmonth.find("Sep") != -1:
            currentmonthv = 9
        if currentmonth.find("Oct") != -1:
            currentmonthv = 10
        if currentmonth.find("Nov") != -1:
            currentmonthv = 11
        if currentmonth.find("Dec") != -1:
            currentmonthv = 12
        if month1>currentmonthv:
            currentmonth = month1-currentmonthv
            while currentmonth != 0:
                self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[3]/td[3]""").click()
                currentmonth = currentmonth-1
        if month1<currentmonthv:
            currentmonth = currentmonthv-month1
            while currentmonth != 0:
                self.driver.find_element_by_xpath("""/html/body/center/table[1]/tbody/tr[3]/td[1]""").click()
                currentmonth = currentmonth - 1
        if month1 == currentmonthv:
            pass
        table = self.driver.find_element_by_xpath("""/html/body/center/table[2]""")
        i = 0
        while i != -77:
            j = table.find_elements_by_tag_name("tr")[1].find_elements_by_tag_name("td")[i].text
            if j == "1":
                break
            else:
                i = i + 1
        print(i)
        date1 = fromdate.split("/")[0]
        date1 = int(date1)
        v= 1
        while date1 != -77:
            try:
                j = table.find_elements_by_tag_name("tr")[v].find_elements_by_tag_name("td")[i].text
                if j == str(date1):
                    print(date1, " dsdsd")
                    table.find_elements_by_tag_name("tr")[v].find_elements_by_tag_name("td")[i].click()
                    break
                else:
                    i = i+1
            except:
                v = v+1
                i = 0
        print(v, " v")
        print(i, " i")
        v = v+1
        i = i+1
        self.driver.find_element_by_xpath("""/html/body/center/table[2]/tbody/tr["""+str(v)+"""]/td["""+str(i)+"""]/a""").click()
        print(j)
        return j

    def calendar1(self, fromdate):
        year1 = fromdate.split("/")[2]
        year1 = int(year1)
        # year2 = todate.split("/")[2]
        # year2 = int(year2)
        month1 = fromdate.split("/")[1]
        month1 = int(month1)
        from datetime import datetime
        date_obj = datetime.strptime(fromdate, '%d/%m/%Y')
        dateOfBirth = date_obj.strftime('%d %b %Y')
        print(dateOfBirth, " dateofbirth")
        return dateOfBirth
    def downloadData(self, fromdate, todate, accountno, seml, smno):
        import time
        time.sleep(3)
        # window_after = self.driver.window_handles[1]
        # self.driver.switch_to.window(window_after)
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/div/nav/div/obdx-component/div[2]/oj-navigation-list/div[2]/div/ul/li[1]/div/a[2]/span[2]""").click()
        time.sleep(3)
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/div/nav/div/obdx-component/div[2]/oj-navigation-list/div[2]/div/ul/li[1]/ul/li[1]/div/a[2]/span""").click()
        time.sleep(3)
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/div/nav/div/obdx-component/div[2]/oj-navigation-list/div[2]/div/ul/li[1]/ul/li[1]/ul/li[1]/a/span""").click()

        # self.driver.switch_to.default_content()
        # self.driver.switch_to.frame("leftmenu")
        time.sleep(2)
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/div/main/div/div[2]/div/modal-window/obdx-component/div/div/div[3]/div/div/div/oj-button[1]/button/div""").click()
        time.sleep(3)
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/div[2]/oj-select-one/div/div[1]/a""").click()
        # table = self.driver.find_element_by_xpath("""/html/body/form[1]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table""")
        # table.find_elements_by_tag_name("tr")[0].find_elements_by_tag_name("td")[0].find_elements_by_tag_name("a")[1].click()
        #self.driver.find_element_by_xpath("/html/body/form[1]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr/td[1]/a[2]").click()
        # WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "3"))).click()
        time.sleep(2)
        self.logStatus("info", "cx opened", self.takeScreenshot())
        self.driver.find_element_by_xpath("""/html/body/div[1]/div/div/ul/li[4]/div/oj-option/span""").click()
        # self.driver.switch_to.default_content()
        # self.driver.switch_to.frame("""content1""")
        time.sleep(2)
        befdate = todate
        import datetime
        from datetime import timedelta
        from datetime import datetime
        fromdate = datetime.strptime(fromdate,'%d/%m/%Y')
        todate = datetime.strptime(todate,'%d/%m/%Y')
        fromdate = (fromdate.strftime('%m/%d/%Y'))
        todate = (todate.strftime('%m/%d/%Y'))
        date_list = pd.date_range(start=fromdate, end=todate, freq=pd.DateOffset(days=365), closed=None).to_list()
        for ind1 in range(len(date_list)):
            if ind1 > 0:
                st = date_list[ind1 - 1].strftime('%d/%m/%Y')
                ed = (date_list[ind1] - timedelta(days=1)).strftime('%d/%m/%Y')
                date_obj1 = datetime.strptime(st, '%d/%m/%Y')
                fromdate = date_obj1.strftime('%d %b %Y')
                date_obj2 = datetime.strptime(ed, '%d/%m/%Y')
                todate = date_obj2.strftime('%d %b %Y')
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[2]/oj-input-date/div/input""").clear()
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[2]/oj-input-date/div/input""").send_keys(
                    fromdate)
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[4]/oj-input-date/div/input""").clear()
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[4]/oj-input-date/div/input""").send_keys(
                    todate)
                time.sleep(1)
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[1]/div[3]/div/oj-menu-button/button/div/span[1]""").click()
                self.logStatus("info", "cx opened", self.takeScreenshot())
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/div[4]/oj-button[1]/button/div/span""").click()
                time.sleep(5)
                try:
                    ff = self.driver.find_element_by_xpath("""/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[2]/div/oj-table/table/thead/tr/th[2]/div""").text
                    print(ff)
                    self.driver.find_element_by_xpath(
                        """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[1]/div[3]/div/oj-menu-button/button/div/span[1]""").click()
                    gg = self.driver.find_element_by_id("""myMenu""")
                    time.sleep(1)
                    gg.find_element_by_link_text("pdf").click()
                except:
                    pass

        import datetime
        import dateutil
        if ed != todate:
            time.sleep(3)
            print(befdate, " dateha")
            a_date = datetime.datetime.strptime(befdate, "%d/%m/%Y")
            a_month = dateutil.relativedelta.relativedelta(months=1)
            date_plus_month = a_date - a_month
            print(date_plus_month)
            date_plus_month = str(date_plus_month)
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[2]/oj-input-date/div/input""").clear()
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[2]/oj-input-date/div/input""").send_keys(
                date_plus_month)
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[4]/oj-input-date/div/input""").clear()
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/oj-validation-group/div/div[4]/oj-input-date/div/input""").send_keys(
                befdate)
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[1]/div[3]/div/oj-menu-button/button/div/span[1]""").click()
            time.sleep(1)
            self.driver.find_element_by_xpath(
                """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[1]/div[4]/oj-button[1]/button/div/span""").click()
            time.sleep(2)
            try:
                ff = self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[2]/div/oj-table/table/thead/tr/th[2]/div""").text
                print(ff)
                self.driver.find_element_by_xpath(
                    """/html/body/div[2]/div/div/div/div/main/div/div[2]/div/div[2]/obdx-component/div/div/div/div[2]/div[1]/div[3]/div/oj-menu-button/button/div/span[1]""").click()
                gg = self.driver.find_element_by_id("""myMenu""")
                gg.find_element_by_link_text("pdf").click()
            except:
                pass

                # gg[0].click()
                time.sleep(3)

        dic = self.saving_pdf()
        return dic
        # time.sleep(5)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").clear()
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.FROM_TXN_DATE"]""").send_keys(fromdate)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").clear()
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.TO_TXN_DATE"]""").send_keys(todate)
        # self.driver.find_element_by_xpath("""//*[@id="SEARCH"]""").click()
        # time.sleep(4)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]""").click()
        # time.sleep(3)
        # self.driver.find_element_by_xpath("""//*[@id="TransactionHistoryFG.OUTFORMAT"]/option[6]""").click()
        # self.driver.find_element_by_xpath("""//*[@id="okButton"]""").click()

        # tbl = self.driver.find_element_by_class_name('open')
        # accstmt = tbl.find_element_by_link_text('Account Statement')
        # accstmt.click()
        #
        # time.sleep(self.timeBwPage)
        # self.logStatus("info", "Acc stmt page opened", self.takeScreenshot())
        #
        # accountselctor = Select(self.driver.find_element_by_class_name('dropdownexpandalbe'))
        # print(list(map(lambda x: x.text, accountselctor.options)))
        # accfound = ''
        # for acc in list(map(lambda x: x.text, accountselctor.options)):
        #     if accountno in acc:
        #         accfound = 'Done'
        #         accountselctor.select_by_visible_text(acc)
        #         break
        #
        # time.sleep(self.timeBwPage)
        #
        # if accfound != '':
        #
        #     self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.SELECTED_RADIO_INDEX"]').click()
        #
        #     if len(fromdate) == 7 and len(todate) == 7:
        #         tdy = calendar.monthrange(int(todate[3:]), int(todate[:2]))[1]
        #         fromdate = '01' + "-" + fromdate
        #         todate = str(tdy) + "-" + todate
        #
        #     fromdate = datetime.strptime(fromdate, '%d-%m-%Y')
        #     todate = datetime.strptime(todate, '%d-%m-%Y')
        #
        #     if todate.year >= datetime.now().year and todate.month >= datetime.now().month:
        #         todate = datetime.now() - timedelta(days=1)
        #
        #     dt_lst = []
        #     date_list = pd.date_range(start=fromdate.strftime('%m-%d-%Y'), end=todate.strftime('%m-%d-%Y'),
        #                               freq=pd.DateOffset(years=1), closed=None).to_list()
        #     for ind1 in range(len(date_list)):
        #         if ind1 > 0:
        #             st = date_list[ind1 - 1]
        #             ed = date_list[ind1] - timedelta(days=1)
        #             dt_lst.append([str(st)[:10], str(ed)[:10]])
        #     if len(dt_lst) > 0 and todate > datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d'):
        #         st = datetime.strptime(str(date_list[-1])[:10], '%Y-%m-%d')
        #         ed = todate
        #         dt_lst.append([str(st)[:10], str(ed)[:10]])
        #     elif len(dt_lst) == 0:
        #         dt_lst.append([fromdate.strftime('%Y-%m-%d'), todate.strftime('%Y-%m-%d')])
        #
        #     flcount = 1
        #     for dts in dt_lst:
        #         fd = datetime.strptime(dts[0], '%Y-%m-%d')
        #         td = datetime.strptime(dts[1], '%Y-%m-%d')
        #
        #         fday = str(fd.day)
        #         fmonth = fd.strftime('%B')
        #         fyear = str(fd.year)
        #         tday = str(td.day)
        #         tmonth = td.strftime('%B')
        #         tyear = str(td.year)
        #
        #         # FROM DATE SET
        #
        #         self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.FROM_TXN_DATE_Calendar_IMG"]').click()
        #         time.sleep(2)
        #         self.calenderSelector(fday, fmonth, fyear)
        #         self.logStatus("info", "from date set", self.takeScreenshot())
        #
        #         # TO DATE SET
        #
        #         self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.TO_TXN_DATE_Calendar_IMG"]').click()
        #         time.sleep(2)
        #         self.calenderSelector(tday, tmonth, tyear)
        #         self.logStatus("info", "to date set", self.takeScreenshot())
        #
        #         self.driver.find_element_by_xpath('//*[@id="SEARCH"]').click()
        #
        #         if self.check_exists_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'):
        #             doctype = Select(self.driver.find_element_by_xpath('//*[@id="TransactionHistoryFG.OUTFORMAT"]'))
        #             doctype.select_by_visible_text('PDF file')
        #             self.logStatus("info", "pdf format selected", self.takeScreenshot())
        #
        #             self.driver.find_element_by_xpath('//*[@id="okButton"]').click()
        #             time.sleep(3)
        #             d_lt = os.listdir(self.pdfDir)
        #             for fl in d_lt:
        #                 if len(fl[:-4]) > 2:
        #                     os.rename(os.path.join(self.pdfDir, fl), os.path.join(self.pdfDir, str(flcount) + '.pdf'))
        #                     flcount += 1
        #
        #         time.sleep(self.timeBwPage)
        #
        #     dic = self.saving_pdf()
        #     return dic
        # else:
        #     return {"referenceId": self.ref_id, "responseCode": "EAF010", "responseMsg": "Authentication Failed"}

    def logout(self):
        try:
            self.driver.find_element_by_xpath("//*[@id='profileLauncher']").click()
            time.sleep(4)
            self.driver.find_element_by_xpath("//*[@id='profileLauncherPopup']/div/ul/li[2]/a/span[2]").click()
            return {"referenceId": self.ref_id, "responseCode": "SRC001",
                                   "responseMsg": "Successfully Completed."}
        except:
            print('logout error')
            self.logStatus("error", "logout unsuccessfull", self.takeScreenshot())
            return {"referenceId": self.ref_id, "responseCode": "EWC002",
                                     "responseMsg": "Incorrect UserName Or Password."}


    def closeDriver(self):
        # time.sleep(self.timeBwPage)
        # shutil.rmtree(self.pdfDir)
        # shutil.rmtree(self.screenshotDir)
        self.driver.quit()

# if __name__ == '__main__':
#     obj=JMUUScrapper('QWERTY1235')
#     opstr=obj.login(username = 'Lokeshyadav1988',password='H@ppyw1r3')
#     print(opstr, " opstr")
#     if opstr['responseMsg']=='Successfully Completed.':
#         res=obj.downloadData('09/01/2018','09/03/2021','','','')
#     print(res)
#     b=obj.logout()
#     obj.closeDriver()