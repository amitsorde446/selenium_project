from datetime import datetime, timedelta
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import traceback
import boto3
import json
import time
import datetime
from datetime import date
from rdb import RDB
from data_base import DB
import socket
import pytz
import timeout_decorator
from pnb_scrapper import PNBScrapper
from sbi_scrapper import SBIScrapper
from kmb_scrapper import KMBScrapper
from hdfc_scrapper import HdfcStatement
from deutschebank_scrapper import DeutscheStatement
from icici_scrapper import IciciStatement
from dbs_scrapper import DbsStatement
from axis_scrapper import AxisStatement
from canara_scrapper import CANARAStatement
from indusind_scrapper import INDUSINDStatement
from bom_scrapper import BOMScrapper
from unionbank_scrapper import UNIONScrapper
from punjab_sindh_scrapper import PUNJABSINDHScrapper
from idfcfirst_scrapper import IDFCFScrapper
from esfb_scrapper import ESFBScrapper
from rbl_scrapper import RBLScrapper
from dcb_scrapper import DCBScrapper
from tmb_scrapper import TMBScrapper
from fc_scrapper import FINCAREScrapper
from csb_scrapper import CSBScrapper
from ssfb_scrapper import SSFBScrapper
from cub_scrapper import CUBScrapper
from esaf_scrapper import ESAFScrapper
from fb_scrapper import FBScrapper
from idbi_scrapper import IDBIScrapper
from kb_scrapper import KBScrapper
from kv_scrapper import KVScrapper
from sc_scrapper import SCScrapper
from usfb_scrapper import USFBScrapper
from utksfb_scrapper import UTKSFBScrapper
from jsfb_scrapper import JSFBScrapper
from citi_scrapper import CITIScrapper
from laxmi_scrapper import  LaxmiScrapper
from jnk_scrapper import JNKScrapper
from sib_scraper import SIBscraper
from bb_scraper import BBScrapper
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
import sqlalchemy as db

# configFile = f"config_{env1}.json"
# with open(configFile, 'r') as confFile:
#     conf = json.load(confFile)
# host=conf["dbConfig1"]["host"]
# port=conf["dbConfig1"]["port"]
# user=conf["dbConfig1"]["user"]
# password=conf["dbConfig1"]["password"]
# table_nm=conf["dbConfig1"]["table_nm"]
# database=conf["dbConfig1"]["database"]

hostname = socket.gethostname()    
ipaddrs = socket.gethostbyname(hostname)


global env1, rec_queue_url, send_queue_url1, send_queue_url2

env1='quality'

# config_redis = f"config_{env1}.json"
# with open(config_redis, 'r') as con:
#     print("------------------------------------",con)
#     conf = json.load(con)
# rdbConfig = conf['rdbConfig']
# redis = RDB(rdbConfig["host"],rdbConfig["port"],rdbConfig["db"])

configFileName1 = f"config_{env1}.json"
with open(configFileName1, 'r') as confFile:
    config1 = json.load(confFile)

rec_queue_url = config1['queue_data']['rec_queue_url']
send_queue_url1 = config1['queue_data']['send_queue_url1'] # for login response
send_queue_url2 = config1['queue_data']['send_queue_url2'] # for data download response
dbConfig_queue = config1['dbConfig_queue'] # for data download response

engine = create_engine(f'mysql+pymysql://{dbConfig_queue["user"]}:{dbConfig_queue["password"]}@{dbConfig_queue["host"]}:{dbConfig_queue["port"]}/{dbConfig_queue["database"]}')

meta = MetaData()
students = Table(
    'bsa_queue_process_request_details',
     meta,
     Column('reference_id', String),
     Column('queue_name', String),
     Column('request_received_json',String),
     Column('updated_date', String),
     Column('response_code', String),
     Column('request_received_date', String),
     Column('response_message', String),
     Column('request_type', String),

 )

try:
    conn = engine.connect()
except:
    print("error in sql data base may be username password wrong")

# Create SQS client
sqs = boto3.client('sqs', aws_access_key_id=config1['queue_data']['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=config1['queue_data']['AWS_SECRET_ACCESS_KEY'],region_name=config1['queue_data']['REGION_HOST'])

def logStatus(refid, level, message, screenshot=None, env1=env1):
    configFileName = f"config_{env1}.json"
    with open(configFileName, 'r') as confFile:
        config = json.load(confFile)
        dbConfig = config['dbConfig']
    myDBobj = DB(**dbConfig)
    if myDBobj is not None:
        IST = pytz.timezone('Asia/Kolkata')
        from datetime import datetime
        tm=str(datetime.now(IST))[:19]
        myDBobj.insertLog(refid, tm, level, message, 'runTask', env1, screenshot, ipaddrs)
    print(f"{level}: {message}, screenshot: {screenshot}")

response = sqs.receive_message(
    QueueUrl=rec_queue_url,
    AttributeNames=[
        'SentTimestamp'
    ],
    MaxNumberOfMessages=1,
    MessageAttributeNames=[
        'All'
    ],
    WaitTimeSeconds=0
)

#list={"Messages": [{"MessageId": "2cfcc9cb-62a4-4169-bb5c-d3fe8bc53f1d", "ReceiptHandle": "AQEBj6/atUNek4LxfZMNt08n5Cxng3tl3hx6L1WOA96CxNvNzYKL+vkBSVdicgoUd5ZT7vylbA7n70MpaWkO/G1tj/GT8iwgDGJ5OYHMLuHqCNKMrd2iCRDTCNIUOqcbDpch84zo+T1Y6LMQrVgSLnUoat/qTY8YR9+L5sOUKMDKOlKHCnlS4l2mO2+/pQuZUqmUBRQcQHHh1jVwx4AALO9JlFBhQcts7rmE89ioOZ+09girYUiFtMtmVpEo/tUIsBJ0ruiPg6HOp1009XIG9PPLPvsiIk8/Hal2Joi0qiY3nn4aoqySVUwvtoyqiwrlPOrHH4ooIekKHeGg/m1pohXZtgoQzAnIUXquvfvCPk1Fk75c2RWvbB0dbbNSYdKY4Pimw5G2KBND9B0fQBPl6cKbDiUw8g/9rVIC64MDzl1KNVw=", "MD5OfBody": "0d9042a1f5f84ff65fe878392183def9", "Body": "{\"requestType\":\"/bsa/external/fileAutomatedRequestUsingLink\",\"bankCode\":\"FI00030\",\"panCard\":\"ANAND0420C\",\"companyType\":\"Individual\",\"purpose\":\"both\",\"toDate\":\"15-09-2021\",\"companyName\":\"DELHI PUBLIC SCHOOL PANIPAT CITY OD Limit\",\"accountType\":\"current\",\"bankName\":\"HDFC Bank\",\"mobileNo\":\"e\",\"userName\":\"161401714\",\"accountNumber\":\"50100404160674\",\"OD_Sanction_Limit\":\"123\",\"referenceId\":\"0b28d8c7-1647-40f9-8f6a-78810286b275\",\"fromDate\":\"01-05-2021\",\"password\":\"Resurgent@4321\",\"transactionPassword\":\"1234\",\"inhouse_Keywords\":\"G\",\"OD_Monthly_Drawing_Power_Limit\":[{\"month\":\"\",\"year\":\"\",\"amount\":\"\"}],\"email\":\"yogesh.sati@scoreme.in\"}", "Attributes": {"SentTimestamp": "1632986670414"}, "MD5OfMessageAttributes": "c60dead1ea4afb3d5f8369f6f21bb570", "MessageAttributes": {"Content-Type": {"StringValue": "application/json", "DataType": "String"}, "Result-Queue": {"StringValue": "blabla", "DataType": "String"}, "Task-Type": {"StringValue": "Sending Data to Queue", "DataType": "String"}}}], "ResponseMetadata": {"RequestId": "23d6194b-3ed5-5710-9f0a-4084570146c1", "HTTPStatusCode": 200, "HTTPHeaders": {"x-amzn-requestid": "23d6194b-3ed5-5710-9f0a-4084570146c1", "date": "Thu, 30 Sep 2021 07:30:28 GMT", "content-type": "text/xml", "content-length": "2467"}, "RetryAttempts": 0}}
#list={'Messages': [{'MessageId': '514f29f2-48d6-4987-ba8f-3ead15c4bddf', 'ReceiptHandle': 'AQEBwvsnrGpBY5FjVzFPp9bmbcdAcEnbG2Cgg94z7Dy5izinTGMLtUrprC5M0IY8rmduDMeJziBiUOCPmRXJ92W97xonTyrD6mI8gOS8oqcsuycYCfSHR+xMYIcwk4QQLqhp7ygSvBV4SAAd8YcGyb2bvdqfhwNu2H39woFFkgQSbhR7oGiti4dyl9pgrjrgPgkU9vmvaQ6UDPwrHM18A0Qa6AEfJOMNHkMFbbmOKoMPi4zPgOSgQKSW2w+QhtFOnTIAioadouUZj2fmlpQ614AVjxK4DQUirk6nmVwZcxCPoo+lHWoo2XhFjV3AwZrlopPL0fPAs/IomW9QdlNe6tKhzmdzCsBNOo+o/fzTwytxDO+3/4ogL5FIiohoD9QJL5wuDQ00WU7fbypJJFeRsZCMp8DOO72PIQn4wximWAcMKB4=', 'MD5OfBody': '9e003110377075ed53fc3755be46b973', 'Body': '{"bankCode":"FI00030","panCard":"vgftr6543w","clientId":"85a55d204c3fc467764f1985205aaa67","requestType":"/bsa/external/fileAutomatedRequest/validationCheck","companyType":"trust","purpose":"both","toDate":"01-09-2021","companyName":"abc","accountType":"over_draft","bankName":"HDFC Bank","mobileNo":"0000000000","userName":"161401714","accountNumber":"50100404160674","OD_Sanction_Limit":"123","referenceId":"65e2a878-fe91-46d4-9636-7a4edaf37c01","fromDate":"06-06-2021","queue_name":"bsa-internet-banking-quality-queue","password":"Resurgent@4321","transactionPassword":"87sdf#gh","inhouse_Keywords":"G","clientCode":"Score-Me","OD_Monthly_Drawing_Power_Limit":[{"month":"01","year":"2021","amount":"100000"}],"email":"garima.malik@scoreme.in"}', 'Attributes': {'SentTimestamp': '1634538758836'}, 'MD5OfMessageAttributes': 'c60dead1ea4afb3d5f8369f6f21bb570', 'MessageAttributes': {'Content-Type': {'StringValue': 'application/json', 'DataType': 'String'}, 'Result-Queue': {'StringValue': 'blabla', 'DataType': 'String'}, 'Task-Type': {'StringValue': 'Sending Data to Queue', 'DataType': 'String'}}}], 'ResponseMetadata': {'RequestId': '64e26fce-aa6e-5556-9827-3629bd164bea', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': '64e26fce-aa6e-5556-9827-3629bd164bea', 'date': 'Mon, 18 Oct 2021 06:33:28 GMT', 'content-type': 'text/xml', 'content-length': '2718'}, 'RetryAttempts': 0}}

# list={"bankCode":"FI00030","panCard":"ANAND0420C",
# "clientId":"85a55d204c3fc467764f1985205aaa67",
# "requestType":"/bsa/external/fileAutomatedRequestUsingLink",
# "companyType":"Individual","purpose":"both","toDate":"15-09-2021",
# "companyName":"DELHI PUBLIC SCHOOL PANIPAT CITY OD Limit",
# "accountType":"current","bankName":"HDFC Bank","mobileNo":"8801289261",
# "userName":"vikash","accountNumber":"50100404160674","OD_Sanction_Limit":"123.00",
# "referenceId":"eedbd2e2-78d1-4514-93ac-979797a130ce","fromDate":"01-05-2021",
# "password":"kjghg","inhouse_Keywords":"G","clientCode":"Score-Me",
# "OD_Monthly_Drawing_Power_Limit":null,"email":"vikashgupta.gupta5@gmail.com"}
#response=list
print(response)

print("data fetched done")
@timeout_decorator.timeout(10*60)
def bankcall(prpse,clsnm,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body=None,bank_code=None,client_code=None,client_id=None,bankname=None):
    try:
        if prpse=='logincheck':
            obj=clsnm(refid,env=env1)
            opstr=obj.login(username,password,emal,mno)
            if opstr['responseCode']=="SRC001":
                print("+++++++++++++++++++++++++++++++")
                res = {"refId": refid, "responseCode": "SRC001", "responseMsg": "Successfully logincheck"}
                sendresp(send_queue_url1, json.dumps(res))
                print("++++++++++++++++++++++++++++++")
                a, b = obj.logout()

            try:
                error_msg = obj.find_element_by_tag_name("body").text.lower()
                if 'service unavailable' in error_msg:
                    opstr =  {"referenceId": refid, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}
            except:
                pass

            obj.closeDriver()
            sendresp(send_queue_url1,json.dumps(opstr))

        elif prpse=='datadownload':
            obj=clsnm(refid,env=env1)

            opstr=obj.login(username,password,emal,mno)

            if opstr['responseCode']=="SRC001":

                opt=obj.downloadData(fromdate,todate,accnumber,emal,mno)
                a,b=obj.logout()
                opstr=opt

            try:
                error_msg = obj.find_element_by_tag_name("body").text.lower()
                if 'service unavailable' in error_msg:
                    opstr =   {"referenceId": refid, "responseCode": "EIS042",
                    "responseMsg": "Information Source is Not Working"}
            except:
                pass

            obj.closeDriver()
            sendresp(send_queue_url2,json.dumps(opstr))

        elif prpse=='both':
            obj=clsnm(refid,env=env1)
            opstr=obj.login(username,password,emal,mno)

            if opstr['responseCode']!="SRC001":

                try:
                    error_msg = obj.find_element_by_tag_name("body").text.lower()
                    if 'service unavailable' in error_msg:
                        opstr =   {"referenceId": refid, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}
                except:
                    pass
                sendresp(send_queue_url1,json.dumps(opstr))

            if opstr['responseCode']=="SRC001":
                ###################################################################33
                table_nm1 = "bsa_queue_process_request_details"
                engine1 = db.create_engine(
                    f'mysql+pymysql://qualitybsajavacode:AqdLwCqCLCJUx4hP@65.0.16.35:3306/sm_bsa')
                meta = MetaData()
                logTable = db.Table(table_nm1, meta, autoload=True, autoload_with=engine1)
                connection1 = engine1.connect()
                message_ = {"username": username, "accnumber": accnumber, "clientid": client_id,
                            "clientcode": client_code,
                            "queuename": "bsa-python-to-java-login-quality-queue",
                            "requestype": requestType,
                            "purpose": prpse, "responsemessage": "successfully login",
                            "responsecode": "SRC001",
                            "referenceid": refid}
                query1 = db.insert(logTable).values(updated_date=dat, reference_id=refid, created_date=dat,
                                                    queue_name="bsa-python-to-java-login-quality-queue",
                                                    request_sent_date=dat, client_id=client_id,
                                                    client_code=client_code, request_sent_json=str(message_),
                                                    response_code="SRC001",
                                                    response_message="successfully login", bank_code=bank_code,
                                                    request_type=requestType)
                connection1.execute(query1)
                print("++++++++++++++++++++++++++++++++++++++++")
                res = {"refId": refid, "responseCode": "SRC001", "responseMsg": "successfully login"}
                sendresp(send_queue_url1, json.dumps(res))
                print("+++++++++++++++++++++++++++++++++++++++++")
                ####################################################################
                #response_message="successfully login"
                # try:
                #     redis.insert(refid, opstr["response_code"],response_message)
                # except:
                #     print("problem in redis uploading")

                opt=obj.downloadData(fromdate,todate,accnumber,emal,mno)
                print("----jjjjjj----")
                try:
                    table_nm1 = "bsa_queue_process_request_details"
                    engine1 = db.create_engine(
                        f'mysql+pymysql://qualitybsajavacode:AqdLwCqCLCJUx4hP@65.0.16.35:3306/sm_bsa')
                    meta = MetaData()
                    logTable = db.Table(table_nm1, meta, autoload=True, autoload_with=engine1)
                    connection1 = engine1.connect()
                    message_ = {"username": username, "accnumber": accnumber, "clientid": client_id,
                                "clientcode": client_code,
                                "queuename": "bsa-python-to-java-bankstatement-quality-queue",
                                "requestype": requestType,
                                "purpose": prpse, "responsemessage": "successfully downloaded",
                                "responsecode": "SRC001",
                                "referenceid": refid, "filetype": "pdf"}
                    query1 = db.insert(logTable).values(updated_date=dat, reference_id=refid, created_date=dat,
                                                        queue_name="bsa-python-to-java-bankstatement-quality-queue",
                                                        request_sent_date=dat, client_id=client_id,
                                                        client_code=client_code, request_sent_json=str(message_),
                                                        response_code="SRC001",
                                                        response_message="successfully downloaded", bank_code=bank_code
                                                        , request_type=requestType)
                    connection1.execute(query1)
                    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                    res = {"refId": refid, "responseCode": "SRC001", "responseMsg": "successfully downloaded"}
                    sendresp(send_queue_url2, json.dumps(res))
                    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                except:
                    print("--3---")



                try:
                    a,b=obj.logout()
                except Exception as e:
                    print(e)
                opstr=opt

                try:
                    error_msg = obj.find_element_by_tag_name("body").text.lower()
                    if 'service unavailable' in error_msg:
                        opstr =   {"referenceId": refid, "responseCode": "EIS042",
                        "responseMsg": "Information Source is Not Working"}
                except:
                    pass
                #res = {"refid": refid, "responsecode": "SRC001", "responsemessage": "successfully downloaded"}
                #sendresp(send_queue_url2, json.dumps(res))
                #sendresp(send_queue_url2, json.dumps(opstr))

            obj.closeDriver()

    except Exception as e:
        errorMsg = traceback.format_exc()
        logStatus(refid, level="error", message=f"Error in scrapping process {errorMsg}")
        sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"EUP007","responseMsg":"Unable To Process. Please Reach Out To Support."}))


def sendresp(queuenm,respmsg):
    print(f"Queue Name : {queuenm}")
    print(f'Response msg : {respmsg}')
    response = sqs.send_message(
    QueueUrl=queuenm,
    MessageAttributes={},
    MessageBody=(respmsg)
        )
####
if 'Messages' in response:
    for message in response['Messages']:
        message_body = json.loads(message['Body'])
        receipt_handle = message['ReceiptHandle']
        print(receipt_handle)
        username=message_body['userName']#"161402244"
        print(username)
        password=message_body['password']
        print(password)
        bankname=message_body['bankName']
        print(bankname)
        panCard = message_body['panCard']
        print(panCard)
        companyType= message_body['companyType']
        print(companyType)
        fromdate=message_body['fromDate']
        print(fromdate)
        todate = message_body['toDate']
        print(todate)
        accnumber=message_body['accountNumber']#"50100404161243"
        print(accnumber)
        companyName=message_body["companyName"]
        print(companyName)
        transpass=message_body['transactionPassword']
        print(transpass)
        refid =message_body['referenceId']
        print(refid)
        mno=message_body['mobileNo']
        print(mno)
        emal=message_body['email']
        print(emal)
        prpse=message_body['purpose']
        print(prpse)
        queue_name=message_body["queue_name"]
        print(queue_name)
        x = datetime.datetime.now()
        dat=x
        request_received_date=x
        bank_code=message_body["bankCode"]
        print(bank_code)
        client_id = message_body["clientId"]
        print(client_id)
        client_code = message_body["clientCode"]
        print(client_code)
        # try:
        #     client_id=message_body["clientId"]
        # except:
        #     client_id="00000"
        # try:
        #     client_code=message_body["client_code"]
        # except:
        #     client_code="000000"
        requestType = message_body["requestType"]
        print(requestType)
        print(f"Bank name : {bankname}")

        if bankname == 'Bandhan Bank':
            try:
                bankcall(prpse, BBScrapper, refid, username, password, accnumber, fromdate, todate, emal, mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2, json.dumps({"referenceId": refid, "responseCode": "ETL056",
                                                      "responseMsg": "Time limit exceeded while downloading files"}))

        elif bankname=='South Indian Bank':
            try:
                bankcall(prpse,SIBscraper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Punjab National Bank':
            try:
                bankcall(prpse,PNBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='State Bank of India':
            try:
                bankcall(prpse,SBIScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Kotak Mahindra Bank':
            if emal=='' and mno=='':
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"EAF010","responseMsg":"Authentication Failed"}))
            else:
                try:
                    bankcall(prpse,KMBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
                except timeout_decorator.timeout_decorator.TimeoutError as e:
                    print('Time out')
                    sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))
        
        elif bankname=='HDFC Bank':
            message_ = {"username": username, "accnumber": accnumber, "clientid": client_id,
                        "clientcode": client_code,
                        "queuename": "bsa-python-to-java-login-quality-queue",
                        "requestype": requestType,
                        "purpose": prpse, "responsemessage": "successfully login",
                        "responsecode": "SRC001",
                        "referenceid": refid, "fromdate": fromdate, "todate": todate}
            try:
                stmt = students.update().where(students.c.reference_id == refid).where(
                    students.c.queue_name == queue_name).values(
                    updated_date=dat, response_code="SRS016",
                    response_message="Successfully Submitted", request_received_date=dat,
                    request_received_json=str(message_), request_type=requestType)
                conn.execute(stmt)
                print("successfully updated database")
            except:
                print("error in updating the database")
            try:
                bankcall(prpse,HdfcStatement,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Deutsche Bank':
            try:
                bankcall(prpse,DeutscheStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='ICICI Bank':
            try:
                bankcall(prpse,IciciStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='DBS Bank':
            if emal=='' and mno=='':
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"EAF010","responseMsg":"Authentication Failed"}))
            else:
                try:
                    bankcall(prpse,DbsStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
                except timeout_decorator.timeout_decorator.TimeoutError as e:
                    print('Time out')
                    sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Axis Bank':
            try:
                bankcall(prpse,AxisStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Canara Bank':
            try:
                bankcall(prpse,CANARAStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='IndusInd Bank':
            try:
                bankcall(prpse,INDUSINDStatement,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Bank of Maharashtra':
            try:
                bankcall(prpse,BOMScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Union Bank of India':
            message_ = {"username": username, "accnumber": accnumber, "clientid": client_id,
                        "clientcode": client_code,
                        "queuename": "bsa-python-to-java-login-quality-queue",
                        "requestype": requestType,
                        "purpose": prpse, "responsemessage": "successfully login",
                        "responsecode": "SRC001",
                        "referenceid": refid, "fromdate": fromdate, "todate": todate}
            try:
                stmt = students.update().where(students.c.reference_id == refid).where(
                    students.c.queue_name == queue_name).values(
                    updated_date=dat, response_code="SRS016",
                    response_message="Successfully Submitted", request_received_date=dat,
                    request_received_json=str(message_), request_type=requestType)
                conn.execute(stmt)
                print("successfully updated database")
            except:
                print("error in updating the database")
            try:
                bankcall(prpse,UNIONScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Punjab & Sind Bank':
            try:
                bankcall(prpse,PUNJABSINDHScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='IDFC First Bank':
            try:
                bankcall(prpse,IDFCFScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Equitas Small Finance Bank':
            try:
                bankcall(prpse,ESFBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='RBL Bank':
            try:
                bankcall(prpse,RBLScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='DCB Bank':
            try:
                bankcall(prpse,DCBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Tamilnad Mercantile Bank':
            try:
                bankcall(prpse,TMBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Fincare Small Finance Bank':
            try:
                bankcall(prpse,FINCAREScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Catholic Syrian Bank':
            try:
                bankcall(prpse,CSBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Suryoday Small Finance Bank':
            try:
                bankcall(prpse,SSFBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='City Union Bank':
            try:
                bankcall(prpse,CUBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='ESAF Small Finance Bank':
            try:
                bankcall(prpse,ESAFScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Federal Bank':
            try:
                bankcall(prpse,FBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='IDBI Bank':
            try:
                bankcall(prpse,IDBIScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Karnataka Bank':
            try:
                bankcall(prpse,KBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Karur Vysya Bank':
            try:
                bankcall(prpse,KVScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Standard Chartered Bank':
            try:
                bankcall(prpse,SCScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Ujjivan Small Finance Bank':
            try:
                bankcall(prpse,USFBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno,message_body,bank_code,client_code,client_id,bankname)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Utkarsh Small Finance Bank':
            try:
                bankcall(prpse,UTKSFBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        elif bankname=='Jana Small Finance Bank':
            try:
                bankcall(prpse,JSFBScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))


        elif bankname=='Citi Bank':
            try:
                bankcall(prpse,CITIScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))
        elif bankname=='J&K Bank':
            try:
                bankcall(prpse,JNKScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))
        elif bankname=='Lakshmi Vilas Bank':
            try:
                bankcall(prpse,LaxmiScrapper,refid,username,password,accnumber,fromdate,todate,emal,mno)
            except timeout_decorator.timeout_decorator.TimeoutError as e:
                print('Time out')
                sendresp(send_queue_url2,json.dumps({"referenceId":refid,"responseCode":"ETL056","responseMsg":"Time limit exceeded while downloading files"}))

        sqs_result = sqs.delete_message(
            QueueUrl=rec_queue_url,
            ReceiptHandle=receipt_handle
        )

        print(sqs_result)
        print('deleted from sqs')
        logStatus(refid, level="info", message="process end",env1=env1)
