# coding=utf-8
import sys
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):

    def getName(self):
        return "茶杯狐"

    def init(self, extend=""):
        pass

    def homeContent(self, filter=False):
        return {"class": [{"type_id": "1", "type_name": "电影"}], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 24}

    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 24}

    def detailContent(self, ids):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 1, "playUrl": "", "url": id, "header": {}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
