# coding=utf-8
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
    except:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout)
            r.encoding = 'utf-8'
            return r

        def log(self, *a):
            pass

    Spider = _BaseSpider


HOST = "https://www.cupfoxdy.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class Spider(Spider):

    def getName(self):
        return "茶杯狐电影"

    def init(self, extend=""):
        self.site = HOST
        self.h = {"User-Agent": UA, "Referer": HOST + "/"}

    def _get(self, url):
        try:
            r = self.fetch(url, headers=self.h, timeout=15)
            return r.text or ""
        except:
            return ""

    def _list(self, html):
        out = []
        for m in re.finditer(
                r'<a class="stui-vodlist__thumb lazyload" '
                r'href="([^"]+)" '
                r'title="([^"]*)" '
                r'data-original="([^"]*)"', html):
            href, name, pic = m.groups()
            if not href.startswith("http"):
                href = HOST + href
            out.append({"vod_id": href, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
        return out

    def homeContent(self, filter):
        return {"class": [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "25", "type_name": "短剧"},
        ]}

    def homeVideoContent(self):
        try:
            return {"list": self._list(self._get(HOST + "/"))}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            html = self._get("%s/search.php?searchtype=5&tid=%s&page=%d" % (HOST, tid, page))
            return {"list": self._list(html), "page": page, "pagecount": 1, "limit": 24, "total": 999}
        except:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 24}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            html = self._get("%s/search.php?searchword=%s&page=%d" % (HOST, urllib.parse.quote(key), page))
            return {"list": self._list(html), "page": page, "pagecount": 1, "limit": 24, "total": 999}
        except:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 24}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        try:
            vid = ids[0]
            url = vid if vid.startswith("http") else HOST + vid
            html = self._get(url)

            name = ""
            m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            if m:
                name = m.group(1)

            pic = ""
            m = re.search(r'id="js-poster-img"[^>]*data-original="([^"]+)"', html)
            if m:
                pic = m.group(1)

            content = ""
            m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
            if m:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

            froms = []
            urls = []
            for panel in re.finditer(
                    r'<h3>([^<]+)</h3>[\s\S]*?'
                    r'<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>', html):
                line = panel.group(1)
                eps = []
                for a in re.finditer(r'<a title="([^"]+)" href="([^"]+)"', panel.group(2)):
                    ep_name, ep_url = a.groups()
                    if ep_url.startswith("/"):
                        ep_url = HOST + ep_url
                    eps.append("%s$%s" % (ep_name, ep_url))
                if eps:
                    froms.append(line)
                    urls.append("#".join(eps))

            if not froms:
                return {"list": []}

            return {"list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "$$$".join(froms),
                "vod_play_url": "$$$".join(urls),
            }]}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = id if id.startswith("http") else HOST + id
            html = self._get(url)
            m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
            if m:
                mm = re.search(r'/play/([^/]+)/?$', m.group(1))
                if mm:
                    m3u8 = "https://hd.kuktxu.com/play/%s/index.m3u8" % mm.group(1)
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": m3u8,
                        "header": {"User-Agent": UA, "Referer": "https://hd.kuktxu.com/"},
                    }
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": {"User-Agent": UA, "Referer": HOST + "/"}}
        except:
            return {"parse": 1, "playUrl": "", "url": id, "header": {}}

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
