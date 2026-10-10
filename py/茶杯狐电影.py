# coding=utf-8
"""
茶杯狐电影 cupfoxdy.com | TVBox Python 爬虫
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
DEFAULT_PIC = "https://www.cupfoxdy.com/templets/cupfoxdy/images/img/load.png"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "25", "type_name": "短剧"},
]

FILTERS = {}


class Spider(Spider):

    def getName(self):
        return "茶杯狐电影"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
        }
        self._play_cache = {}
        print("[cupfox] init OK: %s" % self.site_url)

    # ---------- 网络（兼容不同 TVBox 的 fetch 签名）----------
    def _fetch(self, url):
        try:
            try:
                r = self.fetch(url, headers=self.headers, timeout=15)
            except TypeError:
                r = self.fetch(url, headers=self.headers)
            if hasattr(r, "text"):
                return r.text or ""
            if hasattr(r, "content"):
                return r.content.decode("utf-8", "ignore")
            return str(r)
        except Exception as e:
            print("[cupfox] fetch fail %s -> %s" % (url, e))
            return ""

    def _fix_url(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return HOST + u
        return urllib.parse.urljoin(HOST + "/", u)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _parse_list(self, html):
        out = []
        if not html:
            return out
        seen = set()
        pattern = re.compile(
            r'<a class="stui-vodlist__thumb lazyload" '
            r'href="([^"]+)" '
            r'title="([^"]*)" '
            r'data-original="([^"]*)"',
            re.S)
        for m in pattern.finditer(html):
            href, title, pic = m.groups()
            if href in seen:
                continue
            seen.add(href)
            if href.startswith("/"):
                href = HOST + href
            out.append({
                "vod_id": href,
                "vod_name": self._clean(title),
                "vod_pic": pic.strip() or DEFAULT_PIC,
                "vod_remarks": "",
            })
        return out

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        print("[cupfox] homeContent called, %d classes" % len(CLASSES))
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(HOST + "/")
        videos = self._parse_list(html)
        print("[cupfox] homeVideoContent: %d items" % len(videos))
        return {"list": videos}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (HOST, tid, page)
        print("[cupfox] category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_list(html)
        pc = 1
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            try:
                pc = int(m.group(1))
            except Exception:
                pc = 1
        print("[cupfox] category result: %d items, %d pages" % (len(videos), pc))
        return {"list": videos, "page": page, "pagecount": pc,
                "limit": 24, "total": pc * 24}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search.php?searchword=%s&page=%d" % (
            HOST, urllib.parse.quote(key), page)
        print("[cupfox] search: %s" % url)
        html = self._fetch(url)
        return {"list": self._parse_list(html), "page": page,
                "pagecount": 1, "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = vid if vid.startswith("http") else self._fix_url(vid)
        print("[cupfox] detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = ""
        m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vid

        pic = DEFAULT_PIC
        m = re.search(r'id="js-poster-img"[^>]*data-original="([^"]+)"', html)
        if m:
            pic = m.group(1).strip()

        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if m:
            content = self._clean(m.group(1))

        actor = ""
        m = re.search(r'主演[：:]\s*([\s\S]*?)</span>', html)
        if m:
            actor = self._clean(m.group(1))

        director = ""
        m = re.search(r'导演[：:]\s*([\s\S]*?)</span>', html)
        if m:
            director = self._clean(m.group(1))

        play_from = []
        play_url = []
        for panel in re.finditer(
                r'<h3>([^<]+)</h3>[\s\S]{0,500}?'
                r'<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
                html):
            line = panel.group(1).strip()
            eps = []
            for a in re.finditer(
                    r'<a\s+title="([^"]+)"\s+href="([^"]+)"', panel.group(2)):
                ep_name = a.group(1).strip()
                href = a.group(2)
                if href.startswith("/"):
                    href = HOST + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line)
                play_url.append("#".join(eps))

        print("[cupfox] detail lines: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self._fix_url(id)
        print("[cupfox] player: %s" % url)

        now = int(time.time())
        if url in self._play_cache:
            ts, res = self._play_cache[url]
            if now - ts < 600:
                return res

        html = self._fetch(url)
        m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if m:
            now_url = m.group(1).strip()
            mm = re.search(r'/play/([^/]+)/?$', now_url)
            if mm:
                m3u8 = "https://hd.kuktxu.com/play/%s/index.m3u8" % mm.group(1)
                print("[cupfox] m3u8: %s" % m3u8)
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8,
                    "header": {
                        "User-Agent": UA,
                        "Referer": "https://hd.kuktxu.com/",
                    },
                }
                self._play_cache[url] = (now, res)
                return res

        res = {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
        }
        self._play_cache[url] = (now, res)
        return res

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
