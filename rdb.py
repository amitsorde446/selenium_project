import redis
import json

class RDB:

    def __init__(self,host,port,db):

        self.redisClient = redis.StrictRedis(host=host,port=port,db=db)

    def insert(self,refid,resp,stus):
        self.redisClient.hmset(refid,  {'Response_code':resp, 'message':stus})

    def insertone(self,refid,col,val):
        self.redisClient.hset(refid,col,val)

    def fetch(self,refid,field):
        return self.redisClient.hget(refid,field).decode('utf-8')

    def fetchall(self,refid):
        return self.redisClient.hgetall(refid)

    def deleteall(self,refid):
        return self.redisClient.delete(refid)
    