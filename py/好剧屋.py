# coding=utf-8
"""
好剧屋 www.haojuwu1.cc | TVBox Python 爬虫 (V2.2 修正分类URL版)

关键:
  - 域名 www.haojuwu1.cc
  - 播放页 JS 变量 player_aaaa 里直接就是 m3u8 直链
  - parse=0 直链播放
  - V2.2 修复: categoryContent 的 URL 模板 (苹果CMS v10 标准 6 字段)
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
                print("[haojuwu]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.haojuwu1.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/jianbai/statics/img/favicon.ico"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类 =====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "20", "type_name": "短剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "42", "type_name": "其它"},
    {"type_id": "43", "type_name": "体育"},
]

_SORTS = [{"n": "默认", "v": ""},
          {"n": "时间", "v": "time"},
          {"n": "人气", "v": "hits"},
          {"n": "评分", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "泰国", "v": "泰国"}, {"n": "法国", "v": "法国"},
    {"n": "英国", "v": "英国"}, {"n": "德国", "v": "德国"},
    {"n": "其他", "v": "其他"},
]

_FILTERS_MAP = {
    "1":  [("全部", "1"), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"),
           ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"),
           ("记录片", "21"), ("悬疑片", "22"), ("动画片", "23"), ("犯罪片", "24"),
           ("奇幻片", "25"), ("惊悚片", "40"), ("伦理片", "41")],
    "2":  [("全部", "2"), ("国产剧", "13"), ("AI漫剧", "50"), ("香港剧", "14"),
           ("台湾剧", "15"), ("美国剧", "16"), ("韩国剧", "26"), ("日本剧", "27"),
           ("泰国剧", "28"), ("海外剧", "29")],
    "3":  [("全部", "3"), ("大陆综艺", "35"), ("日韩综艺", "36"),
           ("欧美综艺", "37"), ("港台综艺", "38")],
    "4":  [("全部", "4"), ("国产动漫", "30"), ("日韩动漫", "31"),
           ("欧美动漫", "32"), ("港台动漫", "33"), ("海外动漫", "34")],
    "42": [("全部", "42"), ("国创", "48"), ("番剧", "49")],
    "43": [("全部", "43"), ("足球", "44"), ("篮球", "45"),
           ("网球", "46"), ("斯诺克", "47")],
    "20": [("全部", "20")],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "sub", "name": "子类",
         "value": [{"n": n, "v": v} for n, v in _FILTERS_MAP.get(tid, [("全部", tid)])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a\b[^>]*?href="(/voddetail/[^"]+)"[^>]*?title="([^"]*)"[^>]*?>'
    r'[\s\S]{0,600}?'
    r'(?:data-original|src)="([^"]*?)"',
    re.S | re.I)

_RE_CARD2 = re.compile(
    r'<a\b[^>]*?title="([^"]*)"[^>]*?href="(/voddetail/[^"]+)"[^>]*?>'
    r'[\s\S]{0,600}?'
    r'(?:data-original|src)="([^"]*?)"',
    re.S | re.I)

_RE_CARD3 = re.compile(
    r'<div\s+class="stui-vodlist__box">[\s\S]*?'
    r'<a\b[^>]*?href="(/voddetail/[^"]+)"[^>]*?'
    r'(?:title="([^"]*)")?[^>]*?>[\s\S]*?'
    r'(?:data-original|src)="([^"]*?)"',
    re.S | re.I)

_RE_PAGENUM = re.compile(r'<a>(\d+)/(\d+)</a>')

_RE_PLAYER_AA_START = re.compile(r'player_aaaa\s*=\s*(\{)', re.S)

_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*'
    r'data-original="([^"]*)"', re.S | re.I)
_RE_INTRO = re.compile(
    r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.S | re.I)
_RE_INTRO2 = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
_RE_ACTOR = re.compile(r'主演：([\s\S]*?)</p>', re.S | re.I)
_RE_DIRECTOR = re.compile(r'导演：([\s\S]*?)</p>', re.S | re.I)
_RE_EPISODE_LI = re.compile(
    r'<li[^>]*><a[^>]*href="(/vodplay/[^"]+\.html)"[^>]*>([^<]*)</a></li>',
    re.I)
_RE_PLAYLIST_TAB = re.compile(
    r'<li><a\s+href="#(playlist\d+)"\s+data-toggle="tab">([^<]+)</a></li>',
    re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)


def _extract_js_object(html, start_pos):
    """从 start_pos 开始（指向 '{'），匹配平衡大括号，返回完整 JSON 字符串"""
    depth = 0
    i = start_pos
    in_str = False
    quote = ''
    escape = False
    n = len(html)
    while i < n:
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return html[start_pos:i + 1]
        i += 1
    return ""


class Spider(Spider):

    def getName(self):
        return "好剧屋"

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

    def _fetch(self, url, timeout=15, headers=None, method="GET", data=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            if method == "POST":
                rsp = self._sess.post(url, headers=h, data=data,
                                      timeout=timeout, verify=False)
            else:
                rsp = self._sess.get(url, headers=h, timeout=timeout, verify=False)
            rsp.encoding = 'utf-8'
            return rsp.text or ""
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

    # -------- 列表解析 --------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        m1 = _RE_CARD.findall(html)
        self.log("  策略1 (href→title→img): %d 条" % len(m1))

        m2 = []
        if not m1:
            m2raw = _RE_CARD2.findall(html)
            self.log("  策略2 (title→href→img): %d 条" % len(m2raw))
            m2 = [(h, t, p) for (t, h, p) in m2raw]

        m3 = []
        if not m1 and not m2:
            m3raw = _RE_CARD3.findall(html)
            m3 = [(h, t or "", p) for (h, t, p) in m3raw]
            self.log("  策略3 (卡片块): %d 条" % len(m3))

        matches = m1 or m2 or m3

        if not matches:
            self.log("  ⚠️ 三种策略都失败！")
            self.log("  HTML 长度: %d" % len(html))
            self.log("  voddetail 出现次数: %d" % html.count("voddetail"))
            self.log("  stui-vodlist__thumb 出现次数: %d"
                     % html.count("stui-vodlist__thumb"))
            self.log("  data-original 出现次数: %d" % html.count("data-original"))
            idx = html.find("voddetail")
            if idx >= 0:
                self.log("  首个 voddetail 附近 600 字符:")
                self.log(html[max(0, idx - 100):idx + 600])
            return videos

        for href, title, pic in matches:
            href = href.replace("&amp;", "&").strip()
            if href in seen:
                continue
            seen.add(href)

            title = self._clean(title).strip()
            if not title:
                title = href

            pic = self._fix_url(pic) if pic else ""

            videos.append({
                "vod_id":      href,
                "vod_name":    title[:100],
                "vod_pic":     pic or self.default_pic,
                "vod_remarks": "",
            })

        self.log("  ✅ 最终: %d 条" % len(videos))
        return videos

    def _page_count(self, html, default=1):
        if not html:
            return default
        m = _RE_PAGENUM.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return default

    # -------- TVBox 接口 --------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self.log("=== homeVideoContent 开始 ===")
        html = self._fetch(self.site_url + "/")
        self.log("HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("=== 首页返回 %d 条 ===" % len(videos))
        return {"list": videos}

    # ============================================================
    # ← 改动点: categoryContent 的 URL 模板
    # 苹果CMS v10 标准格式:
    #   /vodshow/{type}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
    #   共 6 个字段用 5 个 "-" 分隔, 后面用 "---" 接页码, 再用 "---" 接年份
    # 空字段用 "" 占位, 连续 "-" 会连在一起
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        sub = extend.get("sub") or tid
        sort_field = extend.get("sort_field") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""

        # /vodshow/{type}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
        url = "%s/vodshow/%s-%s-%s-%s-%s-%s---%s---%s.html" % (
            self.site_url,
            sub,          # type_id
            area,         # area   (地区)
            sort_field,   # by     (排序)
            "",           # class  (剧情)
            "",           # lang   (语言)
            "",           # letter (字母)
            page,         # page
            year,         # year
        )
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html, 1)
        self.log("  -> %d 条, 共 %d 页" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/vodsearch/-------------.html" % self.site_url

        html = self._fetch(url, method="POST", data={"wd": key, "submit": ""})
        self.log("search POST: %s (%d 字节)" % (key, len(html)))

        if html.count("voddetail") < 2:
            self.log("  POST 无效，切换 GET")
            enc = urllib.parse.quote(key)
            get_url = "%s/vodsearch/%s-------------.html" % (self.site_url, enc)
            html = self._fetch(get_url)
            self.log("search GET: %s (%d 字节)" % (get_url, len(html)))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, 1)
        return {
            "list": videos, "page": page,
            "pagecount": pagecount, "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO2.search(html)
            if m:
                content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 主演/导演
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        # 剧集（按 sid 分组）
        groups = {}
        for m in _RE_EPISODE_LI.finditer(html):
            play_path = m.group(1)
            ep_name = self._clean(m.group(2))
            mm = re.match(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', play_path)
            if not mm:
                continue
            sid = mm.group(2)
            groups.setdefault(sid, []).append((ep_name, self._fix_url(play_path)))

        if not groups:
            self.log("  ⚠️ 没抓到剧集")
            return {"list": []}

        # 线路名映射
        line_name_map = {}
        for pl_id, pl_name in _RE_PLAYLIST_TAB.findall(html):
            mm = re.match(r'playlist(\d+)', pl_id)
            if mm:
                line_name_map[mm.group(1)] = pl_name

        # 排序：有名字的线优先
        sorted_sids = sorted(groups.keys(),
                             key=lambda s: (0 if s in line_name_map else 1, s))

        play_from = []
        play_url = []
        for sid in sorted_sids:
            eps = groups[sid]
            seen = set()
            uniq = []
            for n, u in eps:
                if u in seen:
                    continue
                seen.add(u)
                uniq.append((n, u))
            alias = line_name_map.get(sid, "线路%s" % sid)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, u) for n, u in uniq))

        self.log("  线路: %d, 集数: %s"
                 % (len(groups), {k: len(v) for k, v in groups.items()}))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": "%d条线路" % len(groups),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real_url = ""
        if html:
            m = _RE_PLAYER_AA_START.search(html)
            if m:
                obj_str = _extract_js_object(html, m.start(1))
                if obj_str:
                    try:
                        obj = json.loads(obj_str)
                        real_url = obj.get("url", "")
                        self.log("  player_aaaa.url = %s" % real_url[:160])
                    except Exception as e:
                        self.log("  JSON 解析失败: %s" % e)
                        mm = re.search(r'"url"\s*:\s*"([^"]+)"', obj_str)
                        if mm:
                            real_url = mm.group(1).replace("\\/", "/")

        if real_url:
            low = real_url.lower()
            if (".m3u8" in low) or (".mp4" in low):
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
                self.log("  => 直链: %s" % real_url[:160])
                return res

        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

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
