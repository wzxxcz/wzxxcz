# coding=utf-8
import re
import sys
import json
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
                a = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', a)
                self._session.mount('http://', a)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[cupfox]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.cupfoxdy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "25", "type_name": "短剧"},
]


class Spider(Spider):

    def getName(self):
        return "茶杯狐电影"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
        }
        self.log("init")

    def _get(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            return r.text
        except Exception as e:
            self.log("get fail:", url, str(e))
            return ""

    # ---- 首页 ----
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        html = self._get(HOST + "/")
        return {"list": self._parse_list(html)}

    # ---- 分类 ----
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (HOST, tid, page)
        self.log("cat:", url)
        html = self._get(url)
        videos = self._parse_list(html)
        pc = 1
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            pc = int(m.group(1))
        self.log("cat result:", len(videos), "items,", pc, "pages")
        return {"list": videos, "page": page, "pagecount": pc,
                "limit": 24, "total": pc * 24}

    # ---- 搜索 ----
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (HOST, kw, page)
        self.log("search:", url)
        html = self._get(url)
        return {"list": self._parse_list(html), "page": page,
                "pagecount": 1, "limit": 24, "total": 999}

    # ---- 详情 ----
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith("http") else HOST + vid
        self.log("detail:", url)
        html = self._get(url)

        name = ""
        m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()

        pic = ""
        m = re.search(r'id="js-poster-img" data-original="([^"]+)"', html)
        if m:
            pic = m.group(1)

        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 播放列表：<h3>线路名</h3> ... <ul class="stui-content__playlist clearfix"> ... </ul>
        # 里面是 <li id="00"><a title="第1集" href="/fox/17111-0-0.html" target="_self">第1集</a></li>
        play_from, play_url = [], []
        for m in re.finditer(
                r'<h3>([^<]+)</h3>[\s\S]*?<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
                html):
            line = m.group(1).strip()
            eps = []
            for a in re.finditer(r'<a title="([^"]+)" href="([^"]+)"', m.group(2)):
                ep_name, href = a.group(1), a.group(2)
                if href.startswith("/"):
                    href = HOST + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line)
                play_url.append("#".join(eps))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---- 播放 ----
    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else HOST + id
        html = self._get(url)
        m = re.search(r'var now="([^"]+)"', html)
        target = m.group(1) if m else url
        return {"parse": 1, "playUrl": "", "url": target,
                "header": {"User-Agent": UA, "Referer": HOST + "/"}}

    # ---- 列表：完全按你 HTML 那一行硬写 ----
    def _parse_list(self, html):
        out = []
        for m in re.finditer(
                r'<a class="stui-vodlist__thumb lazyload" '
                r'href="([^"]+)" '
                r'title="([^"]*)" '
                r'data-original="([^"]*)"',
                html):
            href, title, pic = m.groups()
            if href.startswith("/"):
                href = HOST + href
            out.append({
                "vod_id": href,
                "vod_name": title.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": "",
            })
        return out

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        pass
