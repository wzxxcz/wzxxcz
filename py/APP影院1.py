# coding=utf-8
"""
APP影院 MacCMS 蓝幽灵模板 TVBox Python 爬虫
适配详情页 /index.php/vod/detail/id/xxx.html
    播放页 /index.php/vod/play/id/xxx/sid/x/nid/x.html
    真实播放地址在 player_data.url (m3u8 直链)
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

    class _BaseSpider(object):
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

        def fetch(self, url, headers=None, timeout=15, **kw):
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[appmovie]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://app.movie"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/blueghost/img/favicon.ico"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "连续剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "6", "type_name": "动作片"},
    {"type_id": "7", "type_name": "喜剧片"},
    {"type_id": "8", "type_name": "爱情片"},
    {"type_id": "9", "type_name": "科幻片"},
    {"type_id": "10", "type_name": "恐怖片"},
    {"type_id": "11", "type_name": "剧情片"},
    {"type_id": "12", "type_name": "战争片"},
    {"type_id": "20", "type_name": "纪录片"},
    {"type_id": "13", "type_name": "国产剧"},
    {"type_id": "14", "type_name": "港台剧"},
    {"type_id": "15", "type_name": "日韩剧"},
    {"type_id": "16", "type_name": "欧美剧"},
]

_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + [
    {"n": str(y), "v": str(y)} for y in range(2026, 2011, -1)
]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"},
    {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"},
    {"n": "美国", "v": "美国"},
    {"n": "韩国", "v": "韩国"},
    {"n": "日本", "v": "日本"},
    {"n": "泰国", "v": "泰国"},
    {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"},
]

FILTERS = {}
for _tid in ["1", "2", "3", "4", "6", "7", "8", "9", "10", "11", "12",
             "20", "13", "14", "15", "16"]:
    FILTERS[_tid] = [
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]


# ============ 正则 ============
_RE_ITEM = re.compile(
    r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>([\s\S]*?)</li>',
    re.I
)
_RE_DETAIL_HREF = re.compile(
    r'href="([^"]*?/index\.php/vod/detail/id/\d+\.html)"',
    re.I
)
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC_ATTR = re.compile(r'(?:data-original|data-src)="([^"]*)"', re.I)
_RE_REMARK = re.compile(
    r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>',
    re.I
)

# 详情页 / 播放页公共
_RE_H3_TITLE = re.compile(
    r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>',
    re.I
)
_RE_PLAYLIST_UL = re.compile(
    r'<ul[^>]*class="[^"]*stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.I
)
_RE_PLAY_A = re.compile(
    r'<a[^>]*href="([^"]*?/index\.php/vod/play/[^"]+)"[^>]*>([\s\S]*?)</a>',
    re.I
)
_RE_SID = re.compile(r'/sid/(\d+)/')

# 播放页 player_data
_RE_PLAYER_DATA = re.compile(
    r'var\s+player_data\s*=\s*(\{[\s\S]*?\})\s*(?:</script>|;)',
    re.I
)

# 详情页信息
_RE_DETAIL_NAME = re.compile(
    r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>',
    re.I
)
_RE_DETAIL_PIC = re.compile(
    r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"',
    re.I
)
_RE_DETAIL_DESC = re.compile(
    r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>([\s\S]*?)</div>',
    re.I
)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
    re.I
)
_RE_ACTOR = re.compile(
    r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*主演：\s*</span>([^<]+)</p>',
    re.I
)
_RE_DIRECTOR = re.compile(
    r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*导演：\s*</span>([^<]+)</p>',
    re.I
)


class Spider(Spider):

    def getName(self):
        return "APP影院"

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
    def _extract_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for block in _RE_ITEM.findall(html):
            m = _RE_DETAIL_HREF.search(block)
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            name = ""
            mt = _RE_TITLE_ATTR.search(block)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                mt = re.search(r'<a[^>]*>([^<]+)</a>', block, re.I)
                if mt:
                    name = self._clean(mt.group(1))

            pic = ""
            mp = _RE_PIC_ATTR.search(block)
            if mp:
                pic = mp.group(1)

            remark = ""
            mr = _RE_REMARK.search(block)
            if mr:
                remark = self._clean(mr.group(1))

            videos.append({
                "vod_id": href,
                "vod_name": name or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark,
            })

        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        m = re.search(r'<span class="num">\d+/(\d+)</span>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    def _build_show_url(self, tid, pg, extend):
        parts = ["/index.php/vod/show"]

        cls = extend.get("class")
        if cls:
            parts += ["class", urllib.parse.quote(str(cls))]

        area = extend.get("area")
        if area:
            parts += ["area", urllib.parse.quote(str(area))]

        year = extend.get("year")
        if year:
            parts += ["year", str(year)]

        by = extend.get("by")
        if by:
            parts += ["by", str(by)]

        parts += ["id", str(tid)]

        if pg and int(pg) > 1:
            parts += ["page", str(pg)]

        return self.site_url + "/".join(parts) + ".html"

    # ---------- API ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._build_show_url(tid, pg, extend)
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._extract_list(html)
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1

        wd = urllib.parse.quote(key)

        if pg > 1:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (
                self.site_url, pg, wd)
        else:
            url = "%s/index.php/vod/search.html?wd=%s" % (self.site_url, wd)

        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_list(html)
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 24,
            "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def _extract_play_groups(self, html):
        """
        从详情页提取 {sid: {'name': 线路名, 'eps': [(集名, url)]}}
        """
        groups = {}

        # 按 stui-pannel 分块
        blocks = re.split(
            r'<div[^>]*class="[^"]*stui-pannel[^"]*"', html, flags=re.I)

        for block in blocks[1:]:
            # 线路名（取块内第一个 h3.title）
            mt = _RE_H3_TITLE.search(block)
            if not mt:
                continue
            line_name = self._clean(mt.group(1))
            if not line_name or len(line_name) > 20:
                continue

            # 播放列表
            ml = _RE_PLAYLIST_UL.search(block)
            if not ml:
                continue

            eps = []
            for m in _RE_PLAY_A.finditer(ml.group(1)):
                href = m.group(1).replace("&amp;", "&")
                ep_name = self._clean(m.group(2))

                ms = _RE_SID.search(href)
                sid = ms.group(1) if ms else "1"

                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)

                eps.append((sid, ep_name, self._fix_url(href)))

            if not eps:
                continue

            sid = eps[0][0]
            if sid not in groups:
                groups[sid] = {"name": line_name, "eps": []}
            for _, n, u in eps:
                groups[sid]["eps"].append((n, u))

        return groups

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        if isinstance(ids, (list, tuple)):
            vod_id = str(ids[0])
        else:
            vod_id = str(ids)

        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 名称
        name = ""
        m = _RE_DETAIL_NAME.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = name.strip() or vod_id

        # 封面
        pic = ""
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = m.group(1)

        # 简介
        content = ""
        m = _RE_DETAIL_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))

        # 主演 / 导演
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        # 剧集
        groups = self._extract_play_groups(html)
        self.log("  剧集线路: %s" % {k: len(v["eps"]) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        # 线路顺序：sid 数字优先
        def _sid_key(x):
            return int(x) if str(x).isdigit() else 999

        sorted_sids = sorted(groups.keys(), key=_sid_key)

        play_from = []
        play_url = []
        for sid in sorted_sids:
            info = groups[sid]
            play_from.append(info["name"])
            play_url.append("#".join(
                "%s$%s" % (n, u) for n, u in info["eps"]))

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_remarks": "%d条线路" % len(groups),
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page, headers={"Referer": self.site_url + "/"})

        real_url = ""

        if html:
            m = _RE_PLAYER_DATA.search(html)
            if m:
                raw = m.group(1)
                data = None
                try:
                    data = json.loads(raw)
                except Exception:
                    try:
                        data = json.loads(raw.replace("\\/", "/"))
                    except Exception:
                        data = None

                if data:
                    real_url = data.get("url") or ""
                else:
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if m2:
                        real_url = m2.group(1)

            if not real_url:
                # 兜底：HTML 里的 m3u8
                m = re.search(r'(https?://[^"\'\\\s]+?\.m3u8[^"\'\\\s]*)',
                              html, re.I)
                if m:
                    real_url = m.group(1)

        if real_url:
            real_url = (real_url.replace("\\/", "/")
                        .replace("&amp;", "&")
                        .replace("\\u0026", "&"))
            if real_url.startswith("//"):
                real_url = "https:" + real_url

            self.log("  => %s" % real_url[:180])

            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交给 TVBox 嗅探
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

    def localProxy(self, param):
        return [200, "text/plain", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
