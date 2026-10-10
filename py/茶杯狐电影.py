# coding=utf-8
"""
茶杯狐电影 cupfoxdy.com | TVBox Python 爬虫
所有解析规则均来自网站实际 HTML
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


# ============================================================
# 站点常量
# ============================================================
HOST = "https://www.cupfoxdy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/templets/cupfoxdy/images/img/load.png"

# 分类列表（对应网站 /cup/N.html 和 /search.php?tid=N）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "25", "type_name": "短剧"},
]


class Spider(Spider):

    # ============================================================
    # 基础接口
    # ============================================================

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
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ============================================================
    # 网络请求
    # ============================================================

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
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
            return self.site_url + u
        return urllib.parse.urljoin(self.site_url + "/", u)

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

    # ============================================================
    # 列表解析（卡片 + 分页）
    # ============================================================

    def _extract_videos(self, html):
        """
        从 HTML 中提取视频卡片
        对应 HTML：
        <a class="stui-vodlist__thumb lazyload" href="/mov/100213.html"
           title="假面骑士零一真实×时间劇場版"
           data-original="https://image.huyajs.com/cover/xxx.jpg">
        """
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
        """
        对应 HTML：<li class="active num"><a>1/3105</a></li>
        """
        if not html:
            return 1
        m = re.search(r'<li class="active num"><a>\d+/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    # ============================================================
    # 首页
    # ============================================================

    def homeContent(self, filter=False):
        """返回分类列表（TVBox 侧边栏或顶部标签使用）"""
        return {
            "class": CLASSES,
            "filters": {},
        }

    def homeVideoContent(self):
        """返回首页推荐视频列表（TVBox 首页内容）"""
        try:
            html = self._fetch(self.site_url + "/")
            videos = self._extract_videos(html)
            self.log("home: %d items" % len(videos))
            return {"list": videos}
        except Exception as e:
            self.log("homeVideoContent FAIL: %s" % e)
            return {"list": []}

    # ============================================================
    # 分类
    # ============================================================

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类页 URL 格式（来自实际 HTML 分页链接）：
        /search.php?page=1&searchtype=5&tid=1&
        """
        try:
            page = int(pg) if pg else 1
            url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (
                self.site_url, tid, page)
            self.log("category: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            pc = self._page_count(html)
            self.log("  -> %d items, %d pages" % (len(videos), pc))
            return {
                "list": videos,
                "page": page,
                "pagecount": pc,
                "limit": 24,
                "total": pc * 24,
            }
        except Exception as e:
            self.log("categoryContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 24, "total": 24}

    # ============================================================
    # 搜索
    # ============================================================

    def searchContent(self, key, quick, pg="1"):
        """
        搜索页 URL 格式：
        /search.php?searchword=老舅&page=1
        """
        try:
            page = int(pg) if pg else 1
            url = "%s/search.php?searchword=%s&page=%d" % (
                self.site_url, urllib.parse.quote(key), page)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            self.log("  -> %d items" % len(videos))
            return {
                "list": videos,
                "page": page,
                "pagecount": 1,
                "limit": 24,
                "total": 999,
            }
        except Exception as e:
            self.log("searchContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 24, "total": 24}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ============================================================
    # 详情
    # ============================================================

    def detailContent(self, ids):
        """
        详情页解析，包括：
        - 标题：<h1 class="title">老舅</h1>
        - 海报：<img id="js-poster-img" data-original="...">
        - 简介：<span class="detail-content">...</span>
        - 播放线路：<h3>foxyun</h3> ... <ul class="stui-content__playlist clearfix">
                    <li><a title="第1集" href="/fox/17111-0-0.html">第1集</a></li>
        """
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0])
            url = vid if vid.startswith("http") else self._fix_url(vid)
            self.log("detail: %s" % url)
            html = self._fetch(url)
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
            name = name or vid

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
            if not content:
                m = re.search(r'<span class="detail-sketch">([\s\S]*?)</span>', html)
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

            # 播放列表（支持多线路）
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
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url":  "$$$".join(play_url),
            }]}
        except Exception as e:
            self.log("detailContent FAIL: %s" % e)
            return {"list": []}

    # ============================================================
    # 播放
    # ============================================================

    def playerContent(self, flag, id, vipFlags):
        """
        播放页解析：
        - 播放页里有：<script>var now="https://1080p.huyall.com/play/en5QEn4d";</script>
        - iframe 里真实的 m3u8：
              const vid = 'https://hd.kuktxu.com/play/en5QEn4d/index.m3u8';
        规则：取 now 中 /play/ 后面的 ID，拼成
              https://hd.kuktxu.com/play/{ID}/index.m3u8
        """
        try:
            url = id if id.startswith("http") else self._fix_url(id)
            self.log("player: %s" % url)

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
                    play_id = mm.group(1)
                    m3u8_url = "https://hd.kuktxu.com/play/%s/index.m3u8" % play_id
                    self.log("  m3u8: %s" % m3u8_url)
                    res = {
                        "parse": 0,
                        "playUrl": "",
                        "url": m3u8_url,
                        "header": {
                            "User-Agent": UA,
                            "Referer": "https://hd.kuktxu.com/",
                        },
                    }
                    self._play_cache[url] = (now, res)
                    return res

            # 兜底：交给 TVBox 嗅探
            self.log("  fallback sniff")
            res = {
                "parse": 1,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[url] = (now, res)
            return res
        except Exception as e:
            self.log("playerContent FAIL: %s" % e)
            return {"parse": 1, "playUrl": "", "url": id, "header": {}}

    # ============================================================
    # 其它必备方法
    # ============================================================

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
