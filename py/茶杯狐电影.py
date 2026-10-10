# coding=utf-8
"""
茶杯狐电影 cupfoxdy.com | TVBox Python 爬虫
结构完全参照用户提供的模板，只替换网站相关内容
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

# 播放地址来源 / 目标主机
PLAY_HOST_TO = "hd.kuktxu.com"


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ==================== 基础 ====================

    def _fetch(self, url, timeout=60, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
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
        if not html:
            return videos
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
                href = self.site_url + href
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title),
                "vod_pic": pic.strip() or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    # ==================== 首页 ====================

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = "%s/" % self.site_url
        self.log("home: %s" % url)
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("home 抓到: %d" % len(videos))
        return {"list": videos}

    # ==================== 分类 ====================

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (
            self.site_url, tid, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        pc = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pc))
        return {
            "list": videos,
            "page": page,
            "pagecount": pc,
            "limit": 24,
            "total": pc * 24,
        }

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (
            self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": 24,
            "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ==================== 详情 ====================

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报
        pic = self.default_pic
        m = re.search(r'id="js-poster-img"[^>]*data-original="([^"]+)"', html)
        if m:
            pic = m.group(1).strip()

        # 简介
        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if m:
            content = self._clean(m.group(1))

        # 主演 / 导演
        actor = ""
        m = re.search(r'主演[：:]\s*([\s\S]*?)</span>', html)
        if m:
            actor = self._clean(m.group(1))

        director = ""
        m = re.search(r'导演[：:]\s*([\s\S]*?)</span>', html)
        if m:
            director = self._clean(m.group(1))

        # 播放列表
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
                    href = self.site_url + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line)
                play_url.append("#".join(eps))

        self.log("  lines: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)

        # 播放页: var now="https://1080p.huyall.com/play/en5QEn4d";
        # iframe:  const vid = 'https://hd.kuktxu.com/play/en5QEn4d/index.m3u8';
        m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if m:
            now_url = m.group(1).strip()
            mm = re.search(r'/play/([^/]+)/?$', now_url)
            if mm:
                play_id = mm.group(1)
                m3u8_url = "https://%s/play/%s/index.m3u8" % (PLAY_HOST_TO, play_id)
                self.log("  now: %s" % now_url)
                self.log("  m3u8: %s" % m3u8_url)
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8_url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": "https://%s/" % PLAY_HOST_TO,
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

        self.log("  兜底嗅探")
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }
        self._play_cache[play_page] = (now, res)
        return res

    # ==================== 其它 ====================

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
