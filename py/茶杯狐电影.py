# coding=utf-8
import sys
import re
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.log("init: %s" % self.site_url)

    def _fetch(self, url, timeout=15):
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(r, "text"):
                return r.text or ""
            if hasattr(r, "content"):
                return r.content.decode("utf-8", "ignore")
            return str(r)
        except Exception as e:
            self.log("fetch FAIL: %s %s" % (url, e))
            return ""

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_list(html)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 站点分类列表页的真实分页格式（来自你提供的动作片/大陆剧页 URL）
        url = "%s/search.php?searchtype=5&tid=%s&page=%d" % (
            self.site_url, tid, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_list(html)
        pc = self._page_count(html)
        self.log("  -> %d items, %d pages" % (len(videos), pc))
        return {
            "list": videos,
            "page": page,
            "pagecount": pc,
            "limit": 24,
            "total": pc * 24,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        return {
            "list": self._parse_list(html),
            "page": page,
            "pagecount": self._page_count(html),
            "limit": 24,
            "total": 9999,
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = vid if vid.startswith("http") else self.site_url + vid
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 名称：详情页有 <h1 class="title">老舅</h1>
        name = ""
        m = re.search(r'<h1\s+class="title">([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = m.group(1).split("_")[0].split("-")[0].strip()

        # 海报：详情页 id="js-poster-img" 的 img 标签
        pic = ""
        m = re.search(r'id="js-poster-img"[^>]*?data-original="([^"]+)"', html)
        if not m:
            m = re.search(
                r'data-original="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
        if m:
            pic = m.group(1).strip()

        # 简介：<span class="detail-content"> 或 detail-sketch
        content = ""
        m = re.search(
            r'<span\s+class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if not m:
            m = re.search(
                r'<span\s+class="detail-sketch">([\s\S]*?)</span>', html)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 主演 / 导演
        actor = ""
        m = re.search(r'主演[：:]([\s\S]*?)</span>', html)
        if m:
            actor = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        director = ""
        m = re.search(r'导演[：:]([\s\S]*?)</span>', html)
        if m:
            director = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 播放列表：站点结构为
        #   <div class="playlist-panel">
        #     <div class="panel-head"><h3>foxyun</h3>...</div>
        #     <ul class="stui-content__playlist clearfix">
        #       <li id="00"><a title="第1集" href="/fox/17111-0-0.html">第1集</a></li>
        #       ...
        #     </ul>
        #   </div>
        play_from = []
        play_url = []
        panel_re = re.compile(
            r'<div\s+class="playlist-panel">[\s\S]*?'
            r'<div\s+class="panel-head">[\s\S]*?<h3>([^<]+)</h3>'
            r'[\s\S]*?'
            r'<ul\s+class="stui-content__playlist[^"]*">([\s\S]*?)</ul>',
            re.S)

        for m in panel_re.finditer(html):
            line = m.group(1).strip()
            ul = m.group(2)
            eps = []
            for li in re.finditer(r'<li[^>]*>\s*<a([^>]*)>([^<]+)</a>', ul):
                attrs = li.group(1)
                ep_name = li.group(2).strip()
                hm = re.search(r'href="([^"]+)"', attrs)
                if not hm:
                    continue
                href = hm.group(1)
                if href.startswith("/"):
                    href = self.site_url + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line)
                play_url.append("#".join(eps))

        self.log("  play_from: %s" % play_from)

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
        url = id if id.startswith("http") else self.site_url + id
        self.log("player: %s" % url)
        html = self._fetch(url)

        # 播放页里有 <script>var now="https://1080p.huyall.com/play/en5QEn4d";...</script>
        m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if m:
            now = m.group(1)
            self.log("  now: %s" % now)
            # now 是另一个播放页地址，交给 TVBox 嗅探
            return {
                "parse": 1,
                "playUrl": "",
                "url": now,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": self.headers,
        }

    # ---------- 工具 ----------
    def _parse_list(self, html):
        videos = []
        if not html:
            return videos
        seen = set()
        # 卡片开始标签：<a class="stui-vodlist__thumb lazyload" href=... title=... data-original=...>
        for m in re.finditer(
                r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'href="([^"]+)"', tag)
            if not hm:
                continue
            href = hm.group(1)
            if href in seen:
                continue
            seen.add(href)
            tm = re.search(r'title="([^"]*)"', tag)
            pm = re.search(r'data-original="([^"]+)"', tag)
            if href.startswith("/"):
                href = self.site_url + href
            videos.append({
                "vod_id": href,
                "vod_name": tm.group(1).strip() if tm else "",
                "vod_pic": pm.group(1).strip() if pm else "",
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        # 站点分页里有：<li class="active num"><a>2/11</a></li>
        m = re.search(r'<li\s+class="active num"><a>(\d+)/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        nums = re.findall(r'page=(\d+)', html)
        if nums:
            try:
                return max(int(x) for x in nums)
            except Exception:
                pass
        return 1

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
