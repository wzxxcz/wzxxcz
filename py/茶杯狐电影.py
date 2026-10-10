# coding=utf-8
"""
茶杯狐电影 cupfoxdy.com | TVBox Python 爬虫
- 优先使用 requests 直连（绕过 TVBox fetch 签名差异）
- 所有解析规则来自网站真实 HTML
"""
import re
import sys
import json
import time
import urllib.parse

sys.path.append('..')

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        def __init__(self):
            pass
        def fetch(self, *args, **kwargs):
            return None
        def log(self, *args):
            pass


HOST = "https://www.cupfoxdy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/templets/cupfoxdy/images/img/load.png"

# 完全按网站源码：/cup/1.html 电影 /cup/2.html 电视剧 /cup/3.html 综艺 /cup/4.html 动漫 /cup/25.html 短剧
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
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ============ 网络：requests 优先，TVBox fetch 回退 ============
    def _fetch(self, url):
        # 1) 优先 requests（最稳定，不受 TVBox fetch 签名差异影响）
        if _HAS_REQUESTS:
            try:
                r = requests.get(url, headers=self.headers, timeout=15, verify=False)
                r.encoding = "utf-8"
                if r.text:
                    return r.text
            except Exception:
                pass
        # 2) 回退 TVBox fetch（尝试多种签名，防止 TypeError）
        for call in (
            lambda: self.fetch(url, headers=self.headers, timeout=15),
            lambda: self.fetch(url, headers=self.headers),
            lambda: self.fetch(url),
        ):
            try:
                rsp = call()
            except Exception:
                continue
            if rsp is None:
                continue
            if hasattr(rsp, "text") and rsp.text:
                return rsp.text
            if hasattr(rsp, "content"):
                c = rsp.content
                if isinstance(c, bytes):
                    return c.decode("utf-8", "ignore")
                return str(c)
            if isinstance(rsp, bytes):
                return rsp.decode("utf-8", "ignore")
            s = str(rsp)
            if s and s != "None":
                return s
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

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

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        # 源码卡片：<a class="stui-vodlist__thumb lazyload" href="/mov/868.html" title="..." data-original="...">
        pattern = re.compile(
            r'<a class="stui-vodlist__thumb lazyload" '
            r'href="([^"]+)" '
            r'title="([^"]*)" '
            r'data-original="([^"]*)"', re.S)
        for m in pattern.finditer(html):
            href, title, pic = m.groups()
            if href in seen:
                continue
            seen.add(href)
            if href.startswith("/"):
                href = self.site_url + href
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": pic.strip() or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        # 源码：<li class="active num"><a>1/3105</a></li>
        if not html:
            return 1
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    # ============ 首页 ============
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    # ============ 分类 ============
    def categoryContent(self, tid, pg, filter, extend):
        # 源码分页链接：?page=1&searchtype=5&tid=1&
        page = int(pg) if pg else 1
        url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (self.site_url, tid, page)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html)
        return {"list": videos, "page": page, "pagecount": pc,
                "limit": 24, "total": pc * 24}

    # ============ 搜索 ============
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search.php?searchword=%s&page=%d" % (
            self.site_url, urllib.parse.quote(key), page)
        html = self._fetch(url)
        return {"list": self._extract_videos(html), "page": page,
                "pagecount": 1, "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ============ 详情 ============
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = vid if vid.startswith("http") else self._fix_url(vid)
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

        pic = self.default_pic
        m = re.search(r'id="js-poster-img"[^>]*data-original="([^"]+)"', html)
        if m:
            pic = m.group(1).strip()

        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<span class="detail-sketch">([\s\S]*?)</span>', html)
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

        # 源码：<h3>foxyun</h3> ... <ul class="stui-content__playlist clearfix">
        #       <li id="00"><a title="第1集" href="/fox/17111-0-0.html">第1集</a></li>
        play_from = []
        play_url = []
        for panel in re.finditer(
                r'<h3>([^<]+)</h3>[\s\S]{0,500}?'
                r'<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
                html):
            origin = panel.group(1).strip()
            eps = []
            for a in re.finditer(
                    r'<a\s+title="([^"]+)"\s+href="([^"]+)"', panel.group(2)):
                ep_name = a.group(1).strip()
                href = a.group(2)
                if href.startswith("/"):
                    href = self.site_url + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(origin)
                play_url.append("#".join(eps))

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
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ============ 播放 ============
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        # 源码：<script>var now="https://1080p.huyall.com/play/en5QEn4d";</script>
        # iframe 内: const vid = 'https://hd.kuktxu.com/play/en5QEn4d/index.m3u8';
        m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if m:
            mm = re.search(r'/play/([^/]+)/?$', m.group(1).strip())
            if mm:
                m3u8_url = "https://hd.kuktxu.com/play/%s/index.m3u8" % mm.group(1)
                res = {"parse": 0, "playUrl": "", "url": m3u8_url,
                       "header": {"User-Agent": UA, "Referer": "https://hd.kuktxu.com/"}}
                self._play_cache[play_page] = (now, res)
                return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
