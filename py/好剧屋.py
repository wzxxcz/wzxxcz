# coding=utf-8
"""
AI搜剧 TVBox Python 爬虫
站点：http://dysou.de5.net/
作者说明：
  - 列表/详情：直接爬 HTML，不改目标服务器
  - 搜索：内联目标站前端使用的 14 个采集源 API，并发搜索
  - 播放：调用目标站现成接口 api/source_concurrent.php 取 m3u8
"""
import re
import sys
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                    pool_connections=20, pool_maxsize=20, max_retries=0)
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
DEFAULT_PIC = HOST + "/assets/images/no-image.jpg"

# ================= 分类 =================
# type_id 对应你站的文件名，例如 hot_movie.php
CLASSES = [
    {"type_id": "hot_movie", "type_name": "电影"},
    {"type_id": "hot_tv",    "type_name": "电视剧"},
    {"type_id": "variety",   "type_name": "综艺"},
    {"type_id": "jp",        "type_name": "短剧"},
    {"type_id": "dm",        "type_name": "动漫"},
]

# ================= 内联的采集源 API（和你站前端 window.apiSiteList 一致） =================
API_SITES = [
    {"key": "dyttzy",  "name": "天堂 HD",  "api": "http://caiji.dyttzyapi.com/api.php/provide/vod"},
    {"key": "heimuer", "name": "豪华 HD",  "api": "https://hhzyapi.com/api.php/provide/vod"},
    {"key": "ruyi",    "name": "如意 HD",  "api": "https://cj.rycjapi.com/api.php/provide/vod"},
    {"key": "bfzy",    "name": "暴风 HD",  "api": "https://bfzyapi.com/api.php/provide/vod"},
    {"key": "tyyszy",  "name": "天涯 HD",  "api": "https://tyyszy.com/api.php/provide/vod"},
    {"key": "ffzy",    "name": "非凡 HD",  "api": "http://ffzy5.tv/api.php/provide/vod"},
    {"key": "zy360",   "name": "360资源",  "api": "https://360zy.com/api.php/provide/vod"},
    {"key": "wolong",  "name": "西瓜 HD",  "api": "https://caiji.xgzyapi.com/api.php/provide/vod/"},
    {"key": "jisu",    "name": "极速 HD",  "api": "https://jszyapi.com/api.php/provide/vod"},
    {"key": "dbzy",    "name": "量子 HD",  "api": "https://cj.lziapi.com/api.php/providedown/vod/"},
    {"key": "mdzy",    "name": "魔都 HD",  "api": "https://mdzyapi.com/api.php/provide/vod/"},
    {"key": "wujin",   "name": "无尽 HD",  "api": "https://api.wujinapi.me/api.php/provide/vod"},
    {"key": "ikun",    "name": "新浪 HD",  "api": "https://api.xinlangapi.com/xinlangapi.php/provide/vod/"},
    {"key": "mzzy",    "name": "速播 HD",  "api": "https://subocj.com/api.php/provide/vod"},
]

# 采集站 source key -> 中文名
SOURCE_NAME = {s["key"]: s["name"] for s in API_SITES}


# ================= 正则 =================
# 列表卡片： <a href="detail.php?wd=xxx" class="video-card-link"> ... <img src="..." alt="xxx"
_RE_CARD = re.compile(
    r'href="detail\.php\?wd=([^"]+)"[^>]*class="video-card-link"[^>]*>'
    r'[\s\S]{0,400}?'
    r'<img[^>]*?src="([^"]+)"[^>]*?alt="([^"]*)"',
    re.S | re.I)

# 兼容 alt 在 src 前面
_RE_CARD2 = re.compile(
    r'href="detail\.php\?wd=([^"]+)"[^>]*class="video-card-link"[^>]*>'
    r'[\s\S]{0,400}?'
    r'<img[^>]*?alt="([^"]*)"[^>]*?src="([^"]+)"',
    re.S | re.I)

# 详情页元素
_RE_TITLE  = re.compile(r'<div class="detail-title">[\s\S]*?</i>\s*([^<]+)</div>', re.I)
_RE_POSTER = re.compile(r'<img\s+src="([^"]+)"\s+class="detail-poster"', re.I)
_RE_DESC   = re.compile(r'<div class="detail-desc">([\s\S]*?)</div>', re.I)
_RE_BADGES = re.compile(r'<span class="detail-badge"[^>]*>([^<]+)</span>', re.I)
_RE_YEAR   = re.compile(r'<span class="detail-badge"[^>]*>(\d{4})</span>', re.I)

# 详情页里的“播放”按钮： <a href="play.php?source=xxx&id=xxx&from=xxx&episode=0"
_RE_PLAY_BTN = re.compile(
    r'href="play\.php\?source=([^&]+)&id=([^&]+)&from=([^&]+)&episode=(\d+)"',
    re.I)


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self._play_cache = {}
        self.log("init: host=%s" % self.host)

    # ==================== 工具 ====================
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

    def _fetch(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    # ==================== 列表页解析 ====================
    def _extract_videos(self, html):
        """从列表页 HTML 中提取卡片"""
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            wd, pic, alt = m.group(1), m.group(2), m.group(3)
            wd = urllib.parse.unquote(wd)
            if wd in seen:
                continue
            seen.add(wd)
            videos.append({
                "vod_id": wd,
                "vod_name": self._clean(alt) or wd,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": "",
            })

        if not videos:
            for m in _RE_CARD2.finditer(html):
                wd, alt, pic = m.group(1), m.group(2), m.group(3)
                wd = urllib.parse.unquote(wd)
                if wd in seen:
                    continue
                seen.add(wd)
                videos.append({
                    "vod_id": wd,
                    "vod_name": self._clean(alt) or wd,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": "",
                })

        self.log("  解析到 %d 个卡片" % len(videos))
        return videos

    # ==================== 首页 ====================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        # 用首页 HTML
        html = self._fetch(self.host + "/index.php")
        videos = self._extract_videos(html)
        self.log("home: %d 条" % len(videos))
        return {"list": videos}

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 你站的分类页 JS 用 ?ajax=1&page=N 加载，但首屏 HTML 里就有静态卡片
        # 走 ajax=1 拿 JSON 更稳定
        url = "%s/%s.php?ajax=1&page=%d" % (self.host, tid, page)
        self.log("category: %s" % url)

        text = self._fetch(url)
        videos = []
        has_more = False

        # 先尝试 JSON
        try:
            data = json.loads(text)
            items = data.get("list") or []
            for item in items:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                poster = item.get("poster") or ""
                pic = self._fix_url(poster)
                videos.append({
                    "vod_id": title,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": item.get("rate") or "",
                })
            has_more = len(videos) >= 12
        except Exception:
            # 不是 JSON，按 HTML 解析
            videos = self._extract_videos(text)
            has_more = len(videos) >= 12

        pagecount = page + 1 if has_more else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ==================== 搜索（内联 14 个采集源） ====================
    def _search_one(self, site, keyword, page=1):
        url = site["api"] + "?ac=detail&wd=" + urllib.parse.quote(keyword) + "&pg=" + str(page)
        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": site["api"],
            }, timeout=10)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
            items = data.get("list") or []
            out = []
            for item in items:
                name = (item.get("vod_name") or "").strip()
                if not name:
                    continue
                out.append({
                    "vod_id": "%s|%s|%s" % (
                        site["key"],
                        str(item.get("vod_id") or ""),
                        name
                    ),
                    "vod_name": name,
                    "vod_pic": item.get("vod_pic") or "",
                    "vod_remarks": item.get("vod_remarks") or "",
                    "source": site["key"],
                    "source_name": site["name"],
                    "vod_time": item.get("vod_time") or "",
                    "raw_id": item.get("vod_id"),
                })
            return out
        except Exception as e:
            self.log("  search %s fail: %s" % (site["key"], e))
            return []

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        self.log("search: %s page=%d" % (key, page))

        # 并发跑 14 个源
        all_results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(self._search_one, s, key, 1) for s in API_SITES]
            for f in as_completed(futures, timeout=15):
                try:
                    all_results.extend(f.result())
                except Exception:
                    pass

        # 去重：同名 + 同源
        seen = set()
        unique = []
        for item in all_results:
            k = item["vod_name"] + "_" + item["source"]
            if k in seen:
                continue
            seen.add(k)
            unique.append(item)

        # 按时间倒序
        def _t(x):
            v = x.get("vod_time") or ""
            try:
                return time.mktime(time.strptime(v, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                return 0
        unique.sort(key=_t, reverse=True)

        # 处理图片 URL
        for item in unique:
            pic = item.get("vod_pic") or ""
            item["vod_pic"] = self._fix_url(pic)

        # 分页
        limit = 24
        total = len(unique)
        pagecount = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit

        return {
            "list": unique[start:end],
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ==================== 详情 ====================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])

        # vod_id 可能是：
        #  - "wd=影片名" 形式（分类/首页来的）
        #  - "source|raw_id|name" 形式（搜索来的）
        #  - 直接是影片名
        if "|" in vod_id:
            parts = vod_id.split("|", 2)
            source = parts[0]
            raw_id = parts[1]
            name = parts[2]
            return self._detail_by_source(source, raw_id, name)
        else:
            name = vod_id
            return self._detail_by_name(name)

    def _detail_by_name(self, name):
        """抓 detail.php?wd=xxx 页面 HTML"""
        url = "%s/detail.php?wd=%s" % (self.host, urllib.parse.quote(name))
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = ""
        m = _RE_TITLE.search(html)
        if m:
            title = self._clean(m.group(1))
        if not title:
            title = name

        # 封面
        pic = ""
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_DESC.search(html)
        if m:
            content = self._clean(m.group(1))

        # 年 / 地区
        badges = _RE_BADGES.findall(html)
        year = ""
        area = ""
        if len(badges) >= 2:
            year = badges[0].strip()
            area = badges[1].strip()

        # 从 HTML 里找 play.php 按钮，拿 source / id / from
        play_btns = _RE_PLAY_BTN.findall(html)
        if not play_btns:
            # 没找到播放按钮，返回空
            return {"list": [{
                "vod_id": name,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_year": year,
                "vod_area": area,
                "vod_play_from": "",
                "vod_play_url": "",
            }]}

        # 用第一个播放按钮的 source + id
        source = play_btns[0][0]
        raw_id = play_btns[0][1]

        # 调用目标站现成的 source_concurrent.php 拿所有线路和 m3u8
        play_info = self._fetch_source_concurrent(title, raw_id, "")

        return {"list": [{
            "vod_id": name,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_year": year,
            "vod_area": area,
            "vod_play_from": play_info.get("from", ""),
            "vod_play_url": play_info.get("url", ""),
        }]}

    def _detail_by_source(self, source, raw_id, name):
        """用 source + raw_id 直接查"""
        # 调目标站接口，一次拿全源
        play_info = self._fetch_source_concurrent(name, raw_id, "")

        # 拿封面：从第一个采集源拉
        pic = ""
        info = self._fetch_from_source(source, raw_id)
        if info:
            pic = info.get("vod_pic") or ""
            name = info.get("vod_name") or name

        return {"list": [{
            "vod_id": "%s|%s|%s" % (source, raw_id, name),
            "vod_name": name,
            "vod_pic": self._fix_url(pic),
            "vod_content": info.get("vod_content") if info else "",
            "vod_year": info.get("vod_year") if info else "",
            "vod_area": info.get("vod_area") if info else "",
            "vod_play_from": play_info.get("from", ""),
            "vod_play_url": play_info.get("url", ""),
        }]}

    def _fetch_from_source(self, source_key, raw_id):
        """直接从采集源拉一条详情"""
        site = next((s for s in API_SITES if s["key"] == source_key), None)
        if not site:
            return None
        url = site["api"] + "?ac=detail&ids=" + urllib.parse.quote(str(raw_id))
        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": site["api"]}, timeout=10)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
            if data.get("list"):
                return data["list"][0]
        except Exception as e:
            self.log("fetch_from_source fail: %s" % e)
        return None

    def _fetch_source_concurrent(self, vod_name, vod_id, vod_type):
        """调用目标站 api/source_concurrent.php，拿到所有源的 m3u8"""
        url = "%s/api/source_concurrent.php?vod_name=%s&vod_id=%s&type=%s" % (
            self.host,
            urllib.parse.quote(vod_name),
            urllib.parse.quote(str(vod_id)),
            urllib.parse.quote(vod_type or ""),
        )
        self.log("source_concurrent: %s" % url)

        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": self.host + "/",
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=25)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
        except Exception as e:
            self.log("source_concurrent fail: %s" % e)
            return {"from": "", "url": ""}

        if data.get("code") != 200 or not data.get("data"):
            return {"from": "", "url": ""}

        src_map = data["data"]

        from_list = []
        url_list = []

        for src_key, src_data in src_map.items():
            play_lists = src_data.get("play_lists") or {}
            for from_key, eps in play_lists.items():
                if not isinstance(eps, list) or not eps:
                    continue
                # 只保留 m3u8
                m3u8_eps = [e for e in eps if isinstance(e.get("url"), str)
                            and ".m3u8" in e["url"].lower()]
                if not m3u8_eps:
                    continue

                line_name = SOURCE_NAME.get(src_key, src_key)

                # 集名$source|m3u8链接
                ep_strs = []
                for ep in m3u8_eps:
                    ep_name = ep.get("name") or "正片"
                    ep_url = ep.get("url") or ""
                    if not ep_url:
                        continue
                    ep_strs.append("%s$%s|%s" % (ep_name, src_key, ep_url))

                if not ep_strs:
                    continue

                from_list.append(line_name)
                url_list.append("#".join(ep_strs))

        return {
            "from": "$$$".join(from_list),
            "url": "$$$".join(url_list),
        }

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        """id 格式： source|m3u8_url"""
        url = id
        if "|" in url:
            url = url.split("|", 1)[1]

        url = self._fix_url(url)

        self.log("player: %s" % url[:120])

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self.host + "/",
            },
        }

    # ==================== 其他 ====================
    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
