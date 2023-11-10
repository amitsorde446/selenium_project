import json
import sqlalchemy as db

class DB:

    def __init__(self,host, port, user, password, database,table_nm):

        self.engine = db.create_engine(f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}')
        self.connection = self.engine.connect()
        self.meta = db.MetaData()

        self.logTable = db.Table(table_nm, self.meta, autoload=True, autoload_with=self.engine)

    def insertLog(self,refId, timestamp, level, log,logType,devEnv ,screenshotPath,ipadd):
        query = db.insert(self.logTable).values(refId = refId,timestamp=timestamp, level=level, log=log,type = logType,
                                                screenshotName=screenshotPath ,devEnvironment = devEnv,ipadd=ipadd)
        ResultProxy = self.connection.execute(query)


    def close(self):
        self.connection.close()
        self.engine.dispose()



