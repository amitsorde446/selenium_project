import os
import shutil
import time
from botocore.exceptions import ClientError
from data_base import DB
from rdb import RDB
import json
import boto3
import uuid
from Otp_sending import emailsending,msgsending
from datetime import datetime,timedelta
import socket
import calendar

class ABC:

    def __init__(self,refid):
        self.ref_id=refid
        self.env='dev'
        self.readConfig()
        self.robj=RDB(**self.rdbConfig)

    def readConfig(self):
        configFileName = f"config_{self.env}.json"
        with open(configFileName, 'r') as confFile:
            config = json.load(confFile)
            self.driverConfig = config['driverConfig']
            self.dbConfig = config['dbConfig']
            self.rdbConfig = config['rdbConfig']

    def toberun(self):
        reid=self.ref_id
        tmi=datetime.now()
        tmo=datetime.now()+timedelta(seconds=40)
        emailsending('prerna.singh@scoreme.in',reid)
        print('inserting refid',datetime.now())
        self.robj.insert(reid,"","","")
        print('inserted refid',datetime.now())
        print(self.robj.fetchall(reid))
        
        while 1:

            if datetime.now()>tmo:
                print('OTP timeout')
                self.robj.insertone(reid,'Response','ELE077')
                self.robj.insertone(reid,'Status','Expired')
                time.sleep(1)
                break

            if self.robj.fetch(reid,'Otp')!='':
                oottpp=self.robj.fetch(reid,'Otp')
                print(f"OTP : {oottpp}")

                break
