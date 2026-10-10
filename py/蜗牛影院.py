# coding=utf-8
"""
蜗牛影院 woniuys.com | TVBox Python 爬虫
结构已确认：
  - 分类：/wi/{dianying,lianxuju,zongyi,dongman,duanju}.html
  - 排序：/vodshow/{tid}--{sort}-------{year}.html
  - 搜索：/vodsearch/-------------.html?wd={key}
  - 详情：/ni/{id}.html
  - 播放：/vi/{id}-{sid}-{nid}.html
  - player_aaaa.url 即真实 m3u8 直链，from 统一为 bfzym3u8
  - 剧集列表在 div.tab-container > div.tab-content.active > ul > li > a
  - 无多线路（tab-nav 只有一个 button）
"""
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
                print("[woniu]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.woniuys.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/woniu/asset/images/logo.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "lianxuju", "type_name": "电视剧"},
    {"type_id": "zongyi",   "type_name": "综艺"},
    {"type_id": "dongman",  "type_name": "动漫"},
    {"type_id": "duanju",   "type_name": "短剧"},
]

_SORTS = [
    {"n": "最新", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "sort", "name": "排序", "value": _SORTS},
        {"key": "year", "name": "年份", "value": _YEARS},
    ]


# ===================== 正则 =====================
# 列表卡片（首页/分类/搜索 通用）
_RE_CARD = re.compile(
    r'<div class="grid-carditem">\s*'
    r'<a class="link" href="([^"]+)"[^>]*?title="([^"]*)"[^>]*>\s*'
    r'<img[^>]*?(?:data-original|src)="([^"]+)"[^>]*?alt="([^"]*)"[^>]*/?>\s*'
    r'(?:<div class="tag1">([^<]*)</div>)?\s*</a>\s*'
    r'<div class="card-info">\s*'
    r'<h3>([^<]*)</h3>\s*'
    r'<p class="tag2">([^<]*)</p>',
    re.S | re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)

_RE_RATING = re.compile(
    r'<div class="rating"><label>豆瓣</label>([\d.]+)</div>', re.I)
_RE_TAGS = re.compile(r'<div class="tags">([\s\S]*?)</div>', re.I)
_RE_TAG_SPAN = re.compile(r'<span>([^<]*)</span>', re.I)

_RE_META_ITEM = re.compile(
    r'<div class="meta-item"><span class="label">([^<]*)：</span>'
    r'<span>([^<]*)</span></div>', re.I)

_RE_DESC = re.compile(r'<p class="movie-description">([\s\S]*?)</p>', re.I)

_RE_CAST_BLOCK = re.compile(
    r'<div class="movie-cast"><h3>([^<]*)</h3>\s*<ul>([\s\S]*?)</ul></div>',
    re.I)
_RE_CAST_A = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)

_RE_POSTER = re.compile(
    r'<div class="movie-poster">\s*<a[^>]*>\s*<img src="([^"]+)"', re.S | re.I)

_RE_PLAY_BUTTON = re.compile(
    r'<a href="([^"]+)" class="play-button">', re.I)

# player_aaaa（. 不匹配换行，用 [\s\S] 更稳）
_RE_PLAYER_AA = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# 剧集列表：tab-container 内 active 的 ul
_RE_TAB_UL = re.compile(
    r'<div class="tab-content active">\s*<ul>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(
    r'<a href="([^"]+)"[^>]*?title="([^"]*)"[^>]*>([^<]*)</a>', re.I)


class Spider(Spider):

    def getName(self):
        return "蜗牛影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None):
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

    # ---------- 列表 ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href, title, pic, alt, tag1, h3, tag2 = m.groups()
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            name = self._clean(h3) or self._clean(title) or self._clean(alt)
            remarks = self._clean(tag2)
            if tag1:
                remarks = (self._clean(tag1) + " " + remarks).strip()

            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        return videos

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        sort_v = extend.get("sort") or "time"
        year_v = extend.get("year") or ""

        # 已确认的 vodshow 形式：/vodshow/{tid}--{sort}-------{year}.html
        # 页码在 .html 前加 -{page}
        if sort_v == "time" and not year_v:
            # 用分类页更稳
            if page <= 1:
                url = "%s/wi/%s.html" % (self.site_url, tid)
            else:
                url = "%s/wi/%s-%d.html" % (self.site_url, tid, page)
        else:
            base = "%s/vodshow/%s--%s-------%s" % (
                self.site_url, tid, sort_v, year_v)
            if page <= 1:
                url = base + ".html"
            else:
                url = base + "-%d.html" % page

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": 9999, "limit": 24, "total": 999999,
        }

    # ---------- 搜索（已确认接口） ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/-------------.html?wd=%s" % (self.site_url, keyword)
        if page > 1:
            url += "&page=%d" % page
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": 9999, "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
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

        # 名称
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        score = ""
        m = _RE_RATING.search(html)
        if m:
            score = m.group(1)

        remarks = ""
        m = _RE_TAGS.search(html)
        if m:
            spans = _RE_TAG_SPAN.findall(m.group(1))
            remarks = " ".join(self._clean(s) for s in spans if s)

        area = year = ""
        for label, val in _RE_META_ITEM.findall(html):
            label = self._clean(label)
            val = self._clean(val)
            if "地区" in label:
                area = val
            elif "年份" in label:
                year = val

        director = ""
        actor = ""
        for title, body in _RE_CAST_BLOCK.findall(html):
            title = self._clean(title)
            names = _RE_CAST_A.findall(body)
            joined = ", ".join(self._clean(x) for x in names if x)
            if "导演" in title:
                director = joined
            elif "主演" in title:
                actor = joined

        # 剧集：详情页只有“免费观看”按钮，真正的剧集在播放页
        play_from = []
        play_url = []
        m = _RE_PLAY_BUTTON.search(html)
        if m:
            first_play = self._fix_url(m.group(1))
            eps = self._extract_episodes(first_play)
            if eps:
                play_from.append("蜗牛资源")
                play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        if not play_from:
            self.log("  未找到播放入口")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d集" % len(play_url[0].split("#"))),
            "vod_area": area,
            "vod_year": year,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _extract_episodes(self, play_url):
        """访问播放页，提取 tab-container 里的剧集列表"""
        html = self._fetch(play_url)
        if not html:
            return []
        eps = []
        m = _RE_TAB_UL.search(html)
        if m:
            for href, title, text in _RE_EP_A.findall(m.group(1)):
                href = self._fix_url(href.replace("&amp;", "&"))
                ep_name = self._clean(title) or self._clean(text) or "正片"
                eps.append((ep_name, href))
        if not eps:
            # 单集/短剧“全集”兜底
            eps.append(("正片", play_url))
        return eps

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        html = self._fetch(play_page)
        m3u8 = ""

        if html:
            m = _RE_PLAYER_AA.search(html)
            if m:
                raw = m.group(1)
                try:
                    aa = json.loads(raw)
                    m3u8 = aa.get("url", "") or ""
                except Exception:
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if m2:
                        m3u8 = m2.group(1)

        if m3u8:
            m3u8 = m3u8.replace("\\/", "/").replace("&amp;", "&")
            self.log("  m3u8: %s" % m3u8[:160])
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        # 兜底：交给 TVBox 嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
