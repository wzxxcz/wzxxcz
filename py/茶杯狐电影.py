# coding=utf-8
# TVBox 茶杯狐电影爬虫
import sys
import re
import json
import time
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self):
            pass

try:
    import requests
except ImportError:
    requests = None

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass


class Spider(BaseSpider):

    def __init__(self):
        self.host = "https://www.cupfoxdy.com"
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def getName(self):
        return "茶杯狐电影"

    def init(self, extend=""):
        if requests is None:
            self._log("requests 模块缺失, 无法使用")
            return
        self.session = requests.Session()
        try:
            self.session.verify = False
        except Exception:
            pass
        self.session.headers.update(self.headers)
        self._log("init done:", self.host)

    # ---------- 网络 ----------
    def _log(self, *args):
        try:
            self.log(*args)
        except Exception:
            try:
                print("[cupfox]", *args)
            except Exception:
                pass

    def _get(self, url, timeout=15):
        if self.session is None:
            if requests is None:
                return ""
            self.session = requests.Session()
            try:
                self.session.verify = False
            except Exception:
                pass
            self.session.headers.update(self.headers)
        try:
            r = self.session.get(url, timeout=timeout)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception as e:
            self._log("GET fail:", url, str(e))
            return ""

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": "1",  "type_name": "电影"},
            {"type_id": "2",  "type_name": "电视剧"},
            {"type_id": "3",  "type_name": "综艺"},
            {"type_id": "4",  "type_name": "动漫"},
            {"type_id": "25", "type_name": "短剧"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        html = self._get(self.host + "/")
        return {"list": self._parse_list(html)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1:
            url = "%s/cup/%s.html" % (self.host, tid)
        else:
            url = ("%s/search.php?page=%d&searchtype=5&tid=%s&order=time"
                   % (self.host, page, tid))
        self._log("category:", url)
        html = self._get(url)
        videos = self._parse_list(html)
        pagecount = self._parse_pagecount(html)
        self._log("  -> %d 条, 共 %d 页" % (len(videos), pagecount))
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        k = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (self.host, k, page)
        self._log("search:", url)
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": self._parse_pagecount(html),
            "limit": 24,
            "total": 9999,
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = vod_id if vod_id.startswith("http") else self.host + vod_id
        self._log("detail:", url)
        html = self._get(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1\s+class="title">([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = m.group(1).split("_")[0].split("-")[0].strip()

        # 海报
        pic = ""
        m = re.search(r'id="js-poster-img"[^>]*?data-original="([^"]+)"', html)
        if not m:
            m = re.search(r'data-original="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
        if m:
            pic = m.group(1)

        # 简介
        content = ""
        m = re.search(r'<span\s+class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if not m:
            m = re.search(r'<span\s+class="detail-sketch">([\s\S]*?)</span>', html)
        if m:
            content = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        # 主演
        actor = ""
        m = re.search(r"主演：([\s\S]*?)</span>", html)
        if m:
            actor = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        # 导演
        director = ""
        m = re.search(r"导演：([\s\S]*?)</span>", html)
        if m:
            director = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        # 播放列表 —— 每个 <h3>线路名</h3> + <ul class="stui-content__playlist clearfix">
        play_from = []
        play_url = []
        panel_re = re.compile(
            r'<h3>([^<]+)</h3>[\s\S]{0,300}?'
            r'<ul\s+class="stui-content__playlist[^"]*">([\s\S]*?)</ul>',
            re.S)
        for m in panel_re.finditer(html):
            line_name = m.group(1).strip()
            ul_html = m.group(2)
            eps = re.findall(
                r'<li[^>]*>\s*<a[^>]*?href="([^"]+)"[^>]*>([^<]+)</a>\s*</li>',
                ul_html)
            if not eps:
                continue
            ep_list = []
            for href, ep_name in eps:
                if href.startswith("/"):
                    href = self.host + href
                ep_list.append("%s$%s" % (ep_name.strip(), href))
            play_from.append(line_name)
            play_url.append("#".join(ep_list))

        if not play_from:
            self._log("  ! 没有解析到播放列表")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
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
        url = id if id.startswith("http") else self.host + id
        self._log("player:", url)
        html = self._get(url)
        m = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if m:
            now = m.group(1)
            self._log("  now:", now)
            # now 是播放页地址(不是直链), 让 TVBox 走嗅探
            return {
                "parse": 1,
                "playUrl": "",
                "url": now,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
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
        if not html:
            return []
        videos = []
        seen = set()
        # 拿到所有卡片起始标签
        tags = re.findall(
            r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*lazyload[^"]*"[^>]*>',
            html)
        for tag in tags:
            hm = re.search(r'href="([^"]+)"', tag)
            if not hm:
                continue
            href = hm.group(1)
            if href in seen:
                continue
            seen.add(href)
            tm = re.search(r'title="([^"]*)"', tag)
            pm = re.search(r'data-original="([^"]+)"', tag)
            title = tm.group(1).strip() if tm else ""
            pic = pm.group(1).strip() if pm else ""
            if href.startswith("/"):
                href = self.host + href
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return videos

    def _parse_pagecount(self, html):
        if not html:
            return 1
        m = re.search(r'<li class="active num"><a>(\d+)/(\d+)</a></li>', html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(x) for x in pages)
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
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass
