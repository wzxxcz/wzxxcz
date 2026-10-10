# coding=utf-8
"""
6V电影网 6vdyw.com | TVBox Python 爬虫
所有解析规则来自你提供的真实 HTML
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


HOST = "https://www.6vdyw.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 按网站导航栏 HTML 原文：
# /html/1.html 电影  /html/6.html 美剧  /html/13.html 韩剧
# /html/2.html 泰剧  /html/7.html 中剧  /html/14.html 日剧
# /html/3.html 短剧  /html/8.html 港剧  /html/15.html 纪录片
# /html/4.html 综艺
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "6",  "type_name": "美剧"},
    {"type_id": "13", "type_name": "韩剧"},
    {"type_id": "2",  "type_name": "泰剧"},
    {"type_id": "7",  "type_name": "中剧"},
    {"type_id": "14", "type_name": "日剧"},
    {"type_id": "3",  "type_name": "短剧"},
    {"type_id": "8",  "type_name": "港剧"},
    {"type_id": "15", "type_name": "纪录片"},
    {"type_id": "4",  "type_name": "综艺"},
]


class Spider(Spider):

    def getName(self):
        return "6V电影网"

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
        self._play_cache = {}

    # ============ 网络：requests 优先，TVBox fetch 兜底 ============
    def _fetch(self, url):
        if _HAS_REQUESTS:
            try:
                r = requests.get(url, headers=self.headers, timeout=15, verify=False)
                r.encoding = "utf-8"
                if r.text:
                    return r.text
            except Exception:
                pass
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
                return c.decode("utf-8", "ignore") if isinstance(c, bytes) else str(c)
            if isinstance(rsp, bytes):
                return rsp.decode("utf-8", "ignore")
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
        s = re.sub(r"<[^>]+>", "", s)
        return s.replace("&nbsp;", " ").replace("\xa0", " ").strip()

    # ============ 列表解析 ============
    def _extract_videos(self, html):
        """
        你给的 HTML 原文：
        <a href="/mov/100491.html" title="假面骑士零一真实×时间劇場版" class="vod-link">
          <div class="vod-cover">
            <img src="https://hongniuzyimage.com/cover/xxx.jpg" alt="..."
        """
        videos = []
        seen = set()
        if not html:
            return videos
        pattern = re.compile(
            r'<a href="([^"]+)" title="([^"]*)" class="vod-link">'
            r'<div class="vod-cover"><img src="([^"]*)"',
            re.S)
        for m in pattern.finditer(html):
            href, title, pic = m.groups()
            if href in seen:
                continue
            seen.add(href)
            if not href.startswith("http"):
                href = self.site_url + href
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title),
                "vod_pic": pic.strip(),
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html, tid):
        """
        你给的 HTML 原文：
        <a href="/html/1-1464.html" class="page-item" >尾页</a>
        """
        if not html:
            return 1
        nums = re.findall(r'/html/%s-(\d+)\.html' % re.escape(tid), html)
        if nums:
            try:
                return max(int(x) for x in nums)
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
        page = int(pg) if pg else 1
        # 你给的 HTML 原文：
        # 第一页：/html/1.html
        # 第二页起：/html/1-2.html
        if page == 1:
            url = "%s/html/%s.html" % (self.site_url, tid)
        else:
            url = "%s/html/%s-%d.html" % (self.site_url, tid, page)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html, tid)
        return {"list": videos, "page": page, "pagecount": pc,
                "limit": 24, "total": pc * 24}

    # ============ 搜索 ============
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        # 你给的 canonical：
        # https://www.6vdyw.com/vodsearch/%E8%80%81%E8%88%85-------------.html
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/%s-------------.html" % (self.site_url, keyword)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos, "page": page, "pagecount": 1,
                "limit": 24, "total": 999}

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

        # 标题：<h1 class="detail-title">《老舅》免费在线观看</h1>
        name = ""
        m = re.search(r'<h1 class="detail-title">([^<]+)</h1>', html)
        if m:
            name = self._clean(m.group(1))
            name = (name.replace("《", "").replace("》", "")
                        .replace("免费在线观看", "").strip())
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0]).strip()
        name = name or vid

        # 封面：<div class="detail-cover"><img src="..." alt="...">
        pic = ""
        m = re.search(r'<div class="detail-cover"><img src="([^"]*)"', html)
        if m:
            pic = m.group(1).strip()

        # 简介：<div class="detail-content"><h2>...</h2><p>...</p></div>
        content = ""
        m = re.search(r'<div class="detail-content">[\s\S]*?<p>([\s\S]*?)</p>', html)
        if m:
            content = self._clean(m.group(1))

        # 主演：<strong>主演：</strong><span>...</span>
        actor = ""
        m = re.search(r'<strong>主演：</strong><span>([\s\S]*?)</span>', html)
        if m:
            actor = self._clean(re.sub(r'<[^>]+>', '', m.group(1)))
            actor = re.sub(r'\s+', ' ', actor).strip()

        # 导演：<strong>导演：</strong><span>...</span>
        director = ""
        m = re.search(r'<strong>导演：</strong><span>([\s\S]*?)</span>', html)
        if m:
            director = self._clean(re.sub(r'<[^>]+>', '', m.group(1)))
            director = re.sub(r'\s+', ' ', director).strip()

        # 播放列表
        # 你给的 HTML 原文：
        # <div class="episode-tabs"><div class="episode-tab active" data-index="1">6vyun</div></div>
        # <div class="episode-list" data-tab="1">
        #   <a href="/vod/18973-1-1.html" class="episode-item" target="_self" title="第1集">第1集</a>
        #   ...
        # </div>
        play_from = []
        play_url = []
        for tab in re.finditer(
                r'<div class="episode-tab[^"]*"[^>]*data-index="(\d+)"[^>]*>([^<]+)</div>',
                html):
            idx = tab.group(1)
            line_name = tab.group(2).strip()

            # 找对应的 episode-list
            marker = 'data-tab="%s"' % idx
            start = html.find(marker, tab.end())
            if start == -1:
                continue
            # 结束位置：下一个 episode-list 或 </section>
            next_list = html.find('<div class="episode-list"', start + 1)
            end_sec = html.find('</section>', start)
            ends = [e for e in (next_list, end_sec) if e != -1]
            end = min(ends) if ends else len(html)
            block = html[start:end]

            eps = []
            for a in re.finditer(
                    r'<a href="([^"]+)" class="episode-item[^"]*"[^>]*title="([^"]+)"',
                    block):
                href = a.group(1)
                ep_name = a.group(2)
                if not href.startswith("http"):
                    href = self.site_url + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line_name)
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
        # 你给的 HTML 原文：
        # <script>var player_aaaa={..., "url":"https:\/\/hn.bfvvs.com\/play\/bkRQA9xa", ...}</script>
        m = re.search(r'"url":"([^"]+)"', html)
        if m:
            play_url = m.group(1).replace("\\/", "/")
            res = {
                "parse": 1,           # maccms 的 /play/xxx 是播放页，交给 TVBox 嗅探
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
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
