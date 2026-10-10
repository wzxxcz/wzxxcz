# coding=utf-8
"""
AI搜剧 TVBox Python 爬虫
站点：http://dysou.de5.net/
说明：
  - 列表页走 AJAX 接口：hot_movie.php / hot_tv.php / variety.php / jp.php / dm.php?ajax=1&page=N
  - 详情页走 detail_api.php
  - 搜索走 search_api.php
  - 播放直接返回 m3u8
依赖：站点根目录需有 search_api.php 和 detail_api.php 两个文件
"""
import re
import sys
import json
import time
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
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[dysou]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "http://dysou.de5.net"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ============== 分类定义 ==============
# type_id 直接对应你站的页面文件名
CLASSES = [
    {"type_id": "hot_movie", "type_name": "电影"},
    {"type_id": "hot_tv",    "type_name": "电视剧"},
    {"type_id": "variety",   "type_name": "综艺"},
    {"type_id": "jp",        "type_name": "短剧"},
    {"type_id": "dm",        "type_name": "动漫"},
]

# 首页推荐分类（用于 homeVideoContent）
HOME_CATEGORIES = [
    "hot_movie", "hot_tv", "variety", "jp", "dm"
]


class Spider(Spider):

    def getName(self):
        return "AI搜剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.host = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.log("init: host=%s" % self.host)

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "http:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    # ============ 分类 ============
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    # ============ 首页 ============
    def homeVideoContent(self):
        videos = []
        for tid in HOME_CATEGORIES:
            try:
                one = self.categoryContent(tid, "1", False, {})
                videos.extend(one.get("list", []))
            except Exception as e:
                self.log("home %s fail: %s" % (tid, e))
        # 去重
        seen = set()
        out = []
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return {"list": out}

    # ============ 分类列表 ============
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = "%s/%s.php?ajax=1&page=%d" % (self.host, tid, page)
        self.log("category: %s" % url)

        try:
            rsp = self.fetch(url, headers=self.headers, timeout=15)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
        except Exception as e:
            self.log("category fail: %s" % e)
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        items = data.get("list") or []
        videos = []
        for item in items:
            title = item.get("title") or ""
            poster = item.get("poster") or ""
            rate = item.get("rate") or ""
            if not title:
                continue
            # 图片走你的代理
            if poster.startswith("http"):
                pic = "%s/image_proxy.php?url=%s" % (
                    self.host, urllib.parse.quote(poster, safe=""))
            else:
                pic = self._fix_url(poster)

            videos.append({
                "vod_id": title,          # 详情按片名查
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": rate,
            })

        # 判断是否还有下一页
        has_more = len(videos) >= 12
        pagecount = page + 1 if has_more else page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ============ 搜索 ============
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search_api.php?keyword=%s&page=%d" % (
            self.host, urllib.parse.quote(key), page)
        self.log("search: %s" % url)

        try:
            rsp = self.fetch(url, headers=self.headers, timeout=20)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
        except Exception as e:
            self.log("search fail: %s" % e)
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        items = data.get("list") or []
        videos = []
        for item in items:
            name = item.get("vod_name") or ""
            if not name:
                continue
            pic = item.get("vod_pic") or ""
            if pic.startswith("http"):
                pic = "%s/image_proxy.php?url=%s" % (
                    self.host, urllib.parse.quote(pic, safe=""))

            # vod_id 编码为 source|id|name 便于 detail 使用
            src = item.get("source") or ""
            vid = str(item.get("vod_id") or "")
            vod_id = "%s|%s|%s" % (src, vid, name)

            videos.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": item.get("vod_remarks") or "",
            })

        pagecount = data.get("pagecount") or 1
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": data.get("total") or len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ============ 详情 ============
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])

        # 解析 vod_id：source|id|name 或纯片名
        if "|" in vod_id:
            parts = vod_id.split("|", 2)
            source, vid, name = parts[0], parts[1], parts[2]
            url = "%s/detail_api.php?source=%s&id=%s" % (
                self.host, urllib.parse.quote(source), urllib.parse.quote(vid))
        else:
            name = vod_id
            url = "%s/detail_api.php?wd=%s" % (
                self.host, urllib.parse.quote(name))

        self.log("detail: %s" % url)

        try:
            rsp = self.fetch(url, headers=self.headers, timeout=20)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
        except Exception as e:
            self.log("detail fail: %s" % e)
            return {"list": []}

        items = data.get("list") or []
        if not items:
            return {"list": []}

        item = items[0]
        name = item.get("vod_name") or name
        pic = item.get("vod_pic") or ""
        if pic.startswith("http"):
            pic = "%s/image_proxy.php?url=%s" % (
                self.host, urllib.parse.quote(pic, safe=""))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": item.get("vod_content") or "",
            "vod_actor": item.get("vod_actor") or "",
            "vod_director": item.get("vod_director") or "",
            "vod_year": item.get("vod_year") or "",
            "vod_area": item.get("vod_area") or "",
            "vod_remarks": item.get("vod_remarks") or "",
            "type_name": item.get("type_name") or "",
            "vod_play_from": item.get("vod_play_from") or "",
            "vod_play_url": item.get("vod_play_url") or "",
        }]}

    # ============ 播放 ============
    def playerContent(self, flag, id, vipFlags):
        """
        id 格式由 detail_api.php 决定：集名$source|m3u8链接
        TVBox 会传进来 '|' 后面的部分
        """
        # 如果传进来的是完整格式，切一下
        url = id
        if "|" in url:
            url = url.split("|", 1)[1]

        # 不是 http 开头，补一下
        if not url.startswith("http"):
            url = self._fix_url(url)

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self.host + "/",
            },
        }

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
