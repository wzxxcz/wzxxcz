# coding=utf-8
"""
苹果CMS V10 标准 JSON 接口 | TVBox Python 爬虫
适用于任何采用苹果CMS V10 且开放 JSON 接口的影视网站
把 DEFAULT_HOST 换成目标网站域名即可

接口格式（苹果CMS V10 通用）:
  分类: /api.php/provide/vod/?ac=list
  列表: /api.php/provide/vod/?ac=detail&t={tid}&pg={page}
  搜索: /api.php/provide/vod/?wd={keyword}&pg={page}
  详情: /api.php/provide/vod/?ac=detail&ids={id}
"""
import json
import sys
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._sess_obj = None

        @property
        def _sess(self):
            if self._sess_obj is None:
                self._sess_obj = _rq.Session()
                self._sess_obj.verify = False
            return self._sess_obj

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[maccms]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===== 把这里改成任意苹果CMS V10 网站 =====
DEFAULT_HOST = "https://caiji.maotaizy.cc"
# 其他可替换示例:
#   https://cj.lziapi.com        (量子资源)
#   http://json.ffzyapi.com      (非凡资源)
#   http://api.1080zyku.com      (1080资源)
#   http://api.wwzy.tv           (旺旺资源)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class Spider(Spider):

    # ==================== 基础 ====================

    def getName(self):
        return "苹果CMS"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.host = (self.extend.get("host") or DEFAULT_HOST).rstrip("/")
        self.headers = {"User-Agent": UA}

    def _get_json(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            text = r.text if hasattr(r, "text") else str(r)
            return json.loads(text)
        except Exception as e:
            self.log("json fail %s -> %s" % (url, e))
            return {}

    def _to_videos(self, lst):
        out = []
        if not lst:
            return out
        for v in lst:
            out.append({
                "vod_id": str(v.get("vod_id", "")),
                "vod_name": v.get("vod_name", ""),
                "vod_pic": v.get("vod_pic", ""),
                "vod_remarks": v.get("vod_remarks", ""),
            })
        return out

    # ==================== 首页 ====================

    def homeContent(self, filter=False):
        try:
            data = self._get_json(self.host + "/api.php/provide/vod/?ac=list")
            classes = data.get("class", [])
            result = []
            for c in classes:
                result.append({
                    "type_id": str(c.get("type_id", "")),
                    "type_name": c.get("type_name", ""),
                })
            self.log("homeContent: %d classes" % len(result))
            return {"class": result, "filters": {}}
        except Exception as e:
            self.log("homeContent fail: %s" % e)
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        try:
            data = self._get_json(
                self.host + "/api.php/provide/vod/?ac=detail&pg=1")
            return {"list": self._to_videos(data.get("list", []))}
        except Exception:
            return {"list": []}

    # ==================== 分类 ====================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            url = "%s/api.php/provide/vod/?ac=detail&t=%s&pg=%d" % (
                self.host, tid, page)
            self.log("category: %s" % url)
            data = self._get_json(url)
            return {
                "list": self._to_videos(data.get("list", [])),
                "page": page,
                "pagecount": int(data.get("pagecount", 1) or 1),
                "limit": int(data.get("limit", 20) or 20),
                "total": int(data.get("total", 0) or 0),
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 20, "total": 0}

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            url = "%s/api.php/provide/vod/?wd=%s&pg=%d" % (
                self.host, urllib.parse.quote(key), page)
            self.log("search: %s" % url)
            data = self._get_json(url)
            return {
                "list": self._to_videos(data.get("list", [])),
                "page": page,
                "pagecount": int(data.get("pagecount", 1) or 1),
                "limit": int(data.get("limit", 20) or 20),
                "total": int(data.get("total", 0) or 0),
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 20, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ==================== 详情 ====================

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0])
            url = "%s/api.php/provide/vod/?ac=detail&ids=%s" % (self.host, vid)
            self.log("detail: %s" % url)
            data = self._get_json(url)
            items = data.get("list", [])
            if not items:
                return {"list": []}
            v = items[0]
            return {"list": [{
                "vod_id": str(v.get("vod_id", vid)),
                "vod_name": v.get("vod_name", ""),
                "vod_pic": v.get("vod_pic", ""),
                "vod_remarks": v.get("vod_remarks", ""),
                "vod_year": str(v.get("vod_year", "")),
                "vod_area": v.get("vod_area", ""),
                "vod_actor": v.get("vod_actor", ""),
                "vod_director": v.get("vod_director", ""),
                "vod_content": v.get("vod_content", ""),
                "vod_play_from": v.get("vod_play_from", ""),
                "vod_play_url": v.get("vod_play_url", ""),
            }]}
        except Exception as e:
            self.log("detail fail: %s" % e)
            return {"list": []}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        # 苹果CMS JSON 接口返回的 id 就是 m3u8 直链，直接播放
        try:
            return {
                "parse": 0,
                "playUrl": "",
                "url": id,
                "header": {"User-Agent": UA},
            }
        except Exception:
            return {"parse": 0, "playUrl": "", "url": id, "header": {}}

    # ==================== 其它 ====================

    def isVideoFormat(self, url):
        return ".m3u8" in str(url) or ".mp4" in str(url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
