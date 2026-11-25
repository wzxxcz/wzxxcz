# coding=utf-8
"""
脚本文件: spider_freeokk.py
FreeOK freeokk.lol | TVBox Python 爬虫

站点形态（线上快照实证，MacCMS v10 模板）:
  - 首页:   /
  - 分类库:  /show/<12 段空槽>.html   （服务端直出六维筛选 + 分页，每页 40）
  - 详情:   /detail/<id>.html
  - 播放:   /play/<vid>-<sid>-<nid>.html   （player_aaaa 变量取可播地址）
  - 搜索:   HTML /search/ 页不下发结果（异步接口），搜索直接走采集 API wd。

双通道策略（一致性优先，防空箱兜底）:
  - 主通道 HTML：分类/首页/详情走服务端页面，筛选维度、线路展示名（含自营后缀字母，
    如 OK自营Q）、线路顺序、选集与网站页面完全一致。
  - 兜底 API：HTML 间歇下发异版空壳/超时无卡片时，自动回退采集 API
    /api.php/provide/vod/（JSON 直取），避免壳子分类空箱；API 仅支持 tid/year/wd/pg，
    地区/类型/语言/字母/排序在回退路径降级（主通道 HTML 生效）。

show slug 12 段槽位（中文 percent-encode）:
  段0=tid / 段1=地区 / 段2=排序 time·hits·score / 段3=类型 / 段4=语言 /
  段5=字母(A~Z；0-9 落段5=0、段6=9) / 段8=页码 / 段11=年代；段7、9~10 空段占位。

分类（顶部导航实证）: 1 电影 / 2 剧集 / 3 综艺 / 4 动漫（无第 5 类、无短剧）。

线路（详情页 .module-tab-item DOM 序，与 #panelN 选集块按 DOM 序一一对应）:
  OK自营Q(自营外链) → OK超清 → OK极速 → OK无广 → OK高清；展示名原样取 DOM span，不重排、不删减。
  采集代号（API 兜底用）: bfzym3u8=OK超清 / 1080zyk=OK极速 / dyttm3u8=OK无广 /
  ffm3u8=OK高清；qq/qiyi/iqiyi/youku/mgtv/bilibili/le/sohu/miguvideo=OK自营。

播放判定: .m3u8/.mp4/.flv 直链 → parse:0（master 取首条子流）；
  官方平台页(v.qq/iqiyi/youku/mgtv/bilibili…) → parse:1 交壳端嗅探；其余兜底 parse:1。
"""
import re
import sys
import json
import time
import base64
import socket
import urllib.parse

sys.path.append('..')

# ---- 强制 IPv4：禁用 IPv6（云端出口 IPv6 不稳）；过滤后为空回退原始解析 ----
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    v4 = [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
          if r[0] == socket.AF_INET]
    return v4 or _orig_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

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
                print("[freeok]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站专属配置 =====================
HOSTS = [
    "https://freeokk.lol",   # 主用
    "https://www.freeokk.pro",
    "https://www.freeok.ink",
    "https://freeokk.top",  # 末位兜底，间歇 503
]
HOST = HOSTS[0]
API = "/api.php/provide/vod/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
DEFAULT_PIC = ""
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_LIMIT = 40            # HTML 每页条数
API_LIMIT = 20             # API 每页条数
SEG_BYTES = 1900           # 单条选集串 UTF-8 字节上限（壳端 2048B 截断，留余量）
API_CACHE_TTL = 300
PLAY_CACHE_TTL = 600

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

# 类型（URL 段3，各分类站点库内实际标签，页面实证 2026-11-25）
_TYPES = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪", "动画",
          "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春", "文艺", "微电影",
          "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情",
          "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺",
          "生活", "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
          "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智", "励志", "其他"],
}

# 地区（URL 段1，站点原文，各分类不同）
_AREAS = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
          "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["大陆", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
}

# 语言（URL 段4，站点原文）
_LANGS = {
    "1": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    "2": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "3": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "4": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
}

# 年代（URL 段11，站点实证 2014~2026）
_YEARS = [str(y) for y in range(2026, 2013, -1)]

# 字母（URL 段5；0-9 选项本身含连字符，落段5=0、段6=9）
_LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["0-9"]

# 排序（URL 段2；展示名取网站原文）
_SORTS = [("时间排序", "time"), ("人气排序", "hits"), ("评分排序", "score")]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


# 筛选组：展示顺序对齐站点 PC 库展开：类型 → 地区 → 语言 → 年代 → 字母 → 排序
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "type", "name": "类型", "value": _opts(_TYPES.get(tid, []))},
        {"key": "area", "name": "地区", "value": _opts(_AREAS.get(tid, []))},
        {"key": "lang", "name": "语言", "value": _opts(_LANGS.get(tid, []))},
        {"key": "year", "name": "年代", "value": _opts(_YEARS)},
        {"key": "letter", "name": "字母", "value": _opts(_LETTERS)},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]

# 采集代号 -> 站点前端固定线路名（API 兜底命名用；HTML 主通道直接取 DOM 展示名）
LINE_NAME = {
    "bfzym3u8": "OK超清",
    "1080zyk": "OK极速",
    "dyttm3u8": "OK无广",
    "ffm3u8": "OK高清",
}
# 官方外链采集代号：站点统一叫 OK自营（后缀字母 API 不返回，HTML DOM 才有）
OFFICIAL_SID = {"qq", "qiyi", "iqiyi", "youku", "mgtv", "bilibili",
                "le", "sohu", "miguvideo"}
# 站点 tab 展示顺序优先级（API 兜底重排对齐站点）
LINE_ORDER = {"OK自营": 0, "OK超清": 1, "OK极速": 2, "OK无广": 3, "OK高清": 4}
# 官方平台域名（parse:1 嗅探判定）
OFFICIAL_DOMAINS = ("v.qq.com", "qq.com", "iqiyi.com", "iqiyipic.com", "youku.com",
                    "mgtv.com", "bilibili.com", "le.com", "sohu.com", "miguvideo.com")

# ===================== 正则 =====================
# 列表/首页卡片：a.module-poster-item[href=/detail/<id>.html][title]
_RE_POSTER_A = re.compile(
    r'<a\s+href="(/detail/\d+\.html)"[^>]*title="([^"]*)"[^>]*class="module-poster-item[^"]*"[\s\S]*?</a>',
    re.S | re.I)
# 搜索卡片：div.module-card-item
_RE_CARD = re.compile(
    r'<div class="module-card-item module-item">([\s\S]*?)</div>\s*(?=<div class="module-card-item|$)',
    re.S | re.I)
_RE_CARD_HREF = re.compile(r'href="(/detail/\d+\.html)"', re.I)
_RE_CARD_CLASS = re.compile(r'module-card-item-class">([^<]*)<', re.I)
_RE_CARD_TITLE = re.compile(r'module-card-item-title">[\s\S]*?<strong>([\s\S]*?)</strong>', re.S | re.I)
# 首页轮播 banner：div.swiper-slide > a.banner[href][style=background:url(封面)]
_RE_BANNER = re.compile(
    r'<div class="swiper-slide">\s*<a href="(/detail/\d+\.html)" class="banner"[^>]*'
    r'style="background:\s*url\(([^)]+)\)[^>]*>\s*</a>\s*'
    r'<div class="mobile-v-info">\s*<div class="v-title">\s*<span>([\s\S]*?)</span>'
    r'[\s\S]*?<div class="v-ins">([\s\S]*?)</div>',
    re.S | re.I)
# 排行榜列表：序号 + 片名 + 状态（无封面）
_RE_PAPER = re.compile(
    r'<a href="(/detail/\d+\.html)">\s*<div class="module-paper-item-num[^"]*">\d+</div>\s*'
    r'<div class="module-paper-item-info">\s*<span class="module-paper-item-infotitle">([\s\S]*?)</span>\s*'
    r'<p>([\s\S]*?)</p>', re.S | re.I)
_RE_NOTE = re.compile(r'module-item-note">([^<]*)<', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:data-original|src)="([^"]*)"[^>]*?(?:alt="([^"]*)")?', re.S | re.I)
_RE_IMG_ALT = re.compile(r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-original|src)="([^"]*)"', re.S | re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_INTRO = re.compile(r'module-info-introduction-content">([\s\S]*?)</div>', re.S | re.I)
_RE_POSTER = re.compile(
    r'<div class="module-info-poster">[\s\S]*?<img[^>]*?(?:data-original|src)="([^"]*)"', re.S | re.I)

_RE_TAG = re.compile(r'<div class="module-info-tag">([\s\S]*?)</div>\s*</div>', re.S | re.I)
_RE_TAG_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

_RE_FIELD = re.compile(
    r'module-info-item-title">([^<]*?)：</span>\s*<div class="module-info-item-content">([\s\S]*?)</div>',
    re.S | re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 线路 tab（DOM 序）与 panel 选集块
_RE_TAB = re.compile(
    r'<(div|a)\b[^>]*class="[^"]*module-tab-item(?:\s|")[^"]*"[^>]*>([\s\S]*?)</\1>',
    re.S | re.I)
_RE_TAB_VALUE = re.compile(r'data-dropdown-value="([^"]+)"', re.I)
_RE_TAB_SPAN = re.compile(r'<span>([^<]+)</span>', re.I)
_RE_TAB_SMALL = re.compile(r'<small[\s\S]*?</small>', re.I)
_RE_PANEL = re.compile(
    r'<div class="module-list[^"]*tab-list[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-list|$)',
    re.S | re.I)
_RE_EP = re.compile(
    r'<a\s+class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.S | re.I)
_RE_EP_TITLE = re.compile(r'title="([^"]*)"', re.I)

_RE_PAGE_BLOCK = re.compile(r'<div id="page">([\s\S]*?)</div>\s*(?=<div|$)', re.S | re.I)

_RE_UPSTREAM = re.compile(
    r'upstream connect error|connection timeout|connection reset|bad gateway|'
    r'service unavailable|reset reason', re.I)
_RE_DIRECT = re.compile(r'\.(m3u8|mp4|flv)(\?|$)', re.I)


class Spider(Spider):

    # ---------------- 基础 ----------------
    def getName(self):
        return "FreeOK"

    def init(self, extend=""):
        # 整体 try 兜底：init 在框架 computeIfAbsent 窗口同步执行，装配异常不外抛，
        # 避免被缓存成 SpiderNull 永久空箱；init 内不发同步网络请求。
        try:
            self.extend = {}
            if extend:
                if isinstance(extend, str):
                    try:
                        self.extend = json.loads(extend) if extend else {}
                    except Exception:
                        self.extend = {}
                elif isinstance(extend, dict):
                    self.extend = extend
            self.hosts = list(self.extend.get("hosts") or HOSTS)
            self.site_url = (self.extend.get("site") or self.hosts[0]).rstrip("/")
            self._host_idx = 0
            for i, h in enumerate(self.hosts):
                if h.rstrip("/") == self.site_url:
                    self._host_idx = i
                    break
            self.headers = {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": self.site_url + "/",
                "Upgrade-Insecure-Requests": "1",
            }
            self.default_pic = DEFAULT_PIC
            self._session = None
            self._warmed = False
            self._api_cache = {}
            self._play_cache = {}
        except Exception as e:
            self.log("init 初始化异常(已兜底, 不阻断)", e)
            self.extend = getattr(self, "extend", {}) or {}
            self.hosts = list(HOSTS)
            self.site_url = HOST
            self._host_idx = 0
            self.headers = {"User-Agent": UA, "Referer": HOST + "/"}
            self.default_pic = DEFAULT_PIC
            self._session = None
            self._warmed = False
            self._api_cache = {}
            self._play_cache = {}

    def getDependence(self):
        return []

    def log(self, *a, **kw):
        try:
            print("[freeok]", *a)
        except Exception:
            pass

    # ---------------- 会话 / 域轮换 ----------------
    def _session_get(self):
        if self._session is None:
            try:
                import requests as _rq
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            except Exception as e:
                self.log("自建 Session 失败:", e)
                self._session = None
        return self._session

    def _switch_host(self):
        for _ in range(len(self.hosts) - 1):
            self._host_idx = (self._host_idx + 1) % len(self.hosts)
            cand = self.hosts[self._host_idx].rstrip("/")
            if cand != self.site_url:
                self.site_url = cand
                self.headers["Referer"] = self.site_url + "/"
                self._session = None
                self._warmed = False
                self.log("轮换域名 ->", self.site_url)
                return True
        return False

    def _warm_up(self):
        """首次请求前先打首页，建立 Session 连接/会话 cookie；失败不阻断主链路。"""
        if self._warmed:
            return
        try:
            self._http_get(self.site_url + "/", timeout=(6, 10))
            self._warmed = True
        except Exception as e:
            self.log("预热失败:", e)

    def _http_get(self, url, headers=None, timeout=(8, 15)):
        """基类 fetch 优先（走壳子封装网络栈/代理/DNS 适配）；异常回退自建 Session。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        to = timeout[1] if isinstance(timeout, tuple) else timeout
        try:
            return self.fetch(url, headers=h, timeout=to, verify=False)
        except Exception as e:
            self.log("基类 fetch 异常, 回退 Session:", url, repr(e)[:120])
        sess = self._session_get()
        try:
            if sess is not None:
                return sess.get(url, headers=h, timeout=timeout, verify=False)
            self.log("Session 亦不可用:", url)
            return None
        except Exception as e:
            self.log("GET 异常:", url, repr(e)[:120])
            return None

    @staticmethod
    def _parse_json(raw):
        """剥 BOM/空白后解析 JSON；失败正则兜底提取首个 JSON 对象。"""
        if not raw:
            return None
        raw = raw.lstrip("﻿").strip()
        try:
            return json.loads(raw)
        except Exception:
            pass
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None

    def _is_bad(self, text, status=200, url=""):
        if not text:
            return True
        if status and int(status) in (403, 502, 503, 500, 404):
            return True
        if len(text) < 200 and _RE_UPSTREAM.search(text.lower()):
            return True
        if len(text) < 300 and not re.search(r"module-|detail/|player_aaaa", text):
            return True
        if re.search(r"<title>404", text):
            return True
        # 列表/搜索异版缓存：短页且无任何详情链接、无播放变量，判坏跨域重试
        if len(text) < 4000 and "/detail/" not in text and "player_aaaa" not in text:
            return True
        # 播放页异版大壳：有选集/推荐 DOM 但缺播放器变量，专项判坏触发重放/跨域
        if "/play/" in url and "player_aaaa" not in text:
            return True
        return False

    # ---------------- HTML 通道 ----------------
    def _fetch_html(self, path, tries=2):
        """预热 -> 遍历全域 ×tries 轮；取首个非坏响应文本，坏壳返 ""。"""
        self._warm_up()
        last = ""
        n = len(self.hosts)
        abs_url = path.startswith("http")
        for round_i in range(tries):
            for step in range(n):
                idx = (self._host_idx + step) % n
                base = self.hosts[idx].rstrip("/")
                target = path if abs_url else base + path
                rsp = self._http_get(target)
                text, status = "", 0
                if rsp is not None:
                    try:
                        text = rsp.content.decode("utf-8", "replace")
                        status = getattr(rsp, "status_code", 200)
                    except Exception as e:
                        self.log("响应读取异常:", repr(e)[:80])
                if not self._is_bad(text, status, target):
                    if idx != self._host_idx:
                        self._host_idx = idx
                        self.site_url = base
                        self.headers["Referer"] = base + "/"
                    self.log("HTML 成功 %s len=%d" % (base, len(text)))
                    return text
                last = text
            if round_i < tries - 1:
                self._session = None
                self._warmed = False
                time.sleep(0.6 * (round_i + 1))
        self.log("HTML 全部域失败:", path)
        return ""

    # ---------------- API 兜底通道 ----------------
    def _api(self, **params):
        """采集 API：预热 -> 遍历全域 ×2 轮；仅成功响应缓存。返回 dict，空返 {}。"""
        params.setdefault("ac", "detail")
        key = "q|" + "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
        hit = self._api_cache.get(key)
        if hit and time.time() < hit[0]:
            return hit[1]

        self._warm_up()
        data = {}
        n = len(self.hosts)
        for attempt in range(2):
            for step in range(n):
                idx = (self._host_idx + step) % n
                base = self.hosts[idx].rstrip("/")
                url = base + API + "?" + urllib.parse.urlencode(params)
                rsp = self._http_get(url)
                raw, status = "", 0
                if rsp is not None:
                    try:
                        raw = rsp.content.decode("utf-8", "replace")
                        status = getattr(rsp, "status_code", 200)
                    except Exception as e:
                        self.log("响应读取异常:", repr(e)[:80])
                data = self._parse_json(raw)
                if isinstance(data, dict) and ("list" in data or data.get("code") in (1, "1")):
                    if idx != self._host_idx:
                        self._host_idx = idx
                        self.site_url = base
                        self.headers["Referer"] = base + "/"
                    self.log("API 成功 %s list=%d" % (base, len(data.get("list") or [])))
                    self._api_cache[key] = (time.time() + API_CACHE_TTL, data)
                    return data
                data = {}
                time.sleep(0.4)
            if attempt == 0:
                self._session = None
                self._warmed = False
        self.log("API 全部域失败:", params)
        return {}

    # ---------------- 工具 ----------------
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
        s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
        s = re.sub(r"<!--[\s\S]*?-->", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _clean_score(self, v):
        try:
            f = float(v)
            return "" if f <= 0 else str(f)
        except Exception:
            return ""

    def _clean_status(self, text):
        if not text:
            return ""
        text = re.sub(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?", "", text)
        text = re.sub(r"\s+/\s*", " ", text)
        return self._clean(text)

    # ---------------- 卡片解析（HTML） ----------------
    def _parse_cards(self, html):
        videos, seen = [], set()
        if not html:
            return videos

        # 1) 列表/首页：a.module-poster-item
        for m in _RE_POSTER_A.finditer(html):
            href, title = m.group(1), self._clean(m.group(2))
            if href in seen:
                continue
            block = m.group(0)
            if not title:
                mt = re.search(r'module-poster-item-title">([\s\S]*?)</div>', block)
                title = self._clean(mt.group(1)) if mt else ""
            if not title:
                continue
            seen.add(href)
            mp = _RE_IMG.search(block)
            pic = self._fix_url(mp.group(1)) if mp else self.default_pic
            mn = _RE_NOTE.search(block)
            remarks = self._clean(mn.group(1)) if mn else ""
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remarks,
                "vod_subtitle": "",
            })

        # 2) 搜索：div.module-card-item
        for block in _RE_CARD.findall(html):
            mh = _RE_CARD_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            mt = _RE_CARD_TITLE.search(block)
            title = self._clean(mt.group(1)) if mt else ""
            if not title:
                mi = _RE_IMG_ALT.search(block)
                title = self._clean(mi.group(1)) if mi else ""
            if not title:
                continue
            seen.add(href)
            mc = _RE_CARD_CLASS.search(block)
            subtitle = self._clean(mc.group(1)) if mc else ""
            mp = _RE_IMG_ALT.search(block) or _RE_IMG.search(block)
            pic = self._fix_url(mp.group(2 if mp.lastindex >= 2 else 1)) if mp else self.default_pic
            mn = _RE_NOTE.search(block)
            remarks = self._clean(mn.group(1)) if mn else ""
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })

        # 3) 首页轮播 banner
        for m in _RE_BANNER.finditer(html):
            href, bg, title = m.group(1), m.group(2), self._clean(m.group(3))
            if href in seen or not title:
                continue
            seen.add(href)
            pic = self._fix_url(bg.strip("'\" ")) or self.default_pic
            remarks, subtitle = "", ""
            mins = m.group(4)
            ps = [self._clean(p) for p in re.findall(r"<p>([\s\S]*?)</p>", mins)]
            ps = [p for p in ps if p]
            if ps:
                remarks = ps[0]
            if len(ps) > 1:
                subtitle = ps[1]
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })

        # 4) 排行榜：module-paper-item（无封面）
        for m in _RE_PAPER.finditer(html):
            href, title, status = m.group(1), self._clean(m.group(2)), self._clean(m.group(3))
            if href in seen or not title:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": self.default_pic,
                "vod_remarks": status,
                "vod_subtitle": "",
            })
        return videos

    # ---------------- API 兜底卡片 ----------------
    def _api_row(self, it):
        return {
            "vod_id": str(it.get("vod_id") or ""),
            "vod_name": self._clean(it.get("vod_name") or "")[:100],
            "vod_pic": it.get("vod_pic") or self.default_pic,
            "vod_remarks": self._clean(it.get("vod_remarks") or ""),
            "vod_year": str(it.get("vod_year") or "")[:4],
            "vod_area": self._clean(it.get("vod_area") or ""),
            "vod_class": self._clean(it.get("vod_class") or it.get("type_name") or ""),
            "vod_subtitle": self._clean(it.get("vod_sub") or ""),
        }

    def _api_rows(self, data):
        out, seen = [], set()
        for it in (data.get("list") or []):
            i = str(it.get("vod_id") or "")
            if not i or i in seen:
                continue
            seen.add(i)
            out.append(self._api_row(it))
        return out

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            html = self._fetch_html("/")
            videos = self._parse_cards(html)
            if videos:
                return {"list": videos}
            # HTML 空壳兜底 API 推荐
            data = self._api(ac="detail", pg="1")
            return {"list": self._api_rows(data)[:API_LIMIT]}
        except Exception as e:
            self.log("homeVideoContent 异常:", e)
            return {"list": []}

    def _filter_slug(self, tid, extend, page=1):
        """构造 /show/ 12 段空槽 URL。"""
        seg = [""] * 12
        seg[0] = str(tid)
        if extend.get("area"):
            seg[1] = extend["area"]
        if extend.get("sort"):
            seg[2] = extend["sort"]
        if extend.get("type"):
            seg[3] = extend["type"]
        if extend.get("lang"):
            seg[4] = extend["lang"]
        if extend.get("letter"):
            lv = str(extend["letter"])
            if lv == "0-9":
                seg[5], seg[6] = "0", "9"
            else:
                seg[5] = lv
        seg[8] = str(page) if page and page > 1 else ""
        if extend.get("year"):
            seg[11] = str(extend["year"])
        parts = [urllib.parse.quote(x, safe="") for x in seg]
        return "/show/" + "-".join(parts) + ".html"

    def _page_count(self, html):
        """#page 块内 /show/ slug 段8 最大页码=真实总页；无分页块返回 1。"""
        if not html:
            return 1
        block = _RE_PAGE_BLOCK.search(html)
        scope = block.group(1) if block else html
        pages = []
        for slug in re.findall(r'/show/([^"\s]+)\.html', scope):
            seg = slug.split("-")
            if len(seg) > 8 and seg[8].isdigit():
                pages.append(int(seg[8]))
        return max(1, max(pages)) if pages else 1

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = str(tid or "").strip() or CLASSES[0]["type_id"]
            try:
                page = max(1, int(pg))
            except Exception:
                page = 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend) if extend else {}
                except Exception:
                    extend = {}
            extend = extend or {}
            for k in list(extend.keys()):
                if extend[k] in ("", None, "全部"):
                    del extend[k]

            # 主通道：HTML 服务端筛选
            path = self._filter_slug(tid, extend, page)
            html = self._fetch_html(path)
            videos = self._parse_cards(html)
            if videos:
                pc = self._page_count(html)
                self.log("category HTML t=%s page=%d -> %d 条, 总页 %d" % (tid, page, len(videos), pc))
                return {"list": videos, "page": page, "pagecount": pc,
                        "limit": PAGE_LIMIT, "total": pc * PAGE_LIMIT}

            # 兜底 API（仅 tid/year/pg 生效，其余筛选降级）
            params = {"ac": "detail", "t": tid, "pg": str(page)}
            if extend.get("year"):
                params["year"] = extend["year"]
            data = self._api(**params)
            lst = self._api_rows(data)[:API_LIMIT]
            pc = int(data.get("pagecount") or 1) or 1
            total = int(data.get("total") or (pc * API_LIMIT))
            self.log("category API t=%s page=%d -> %d 条" % (tid, page, len(lst)))
            return {"list": lst, "page": page, "pagecount": pc,
                    "limit": API_LIMIT, "total": max(total, len(lst))}
        except Exception as e:
            self.log("categoryContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": PAGE_LIMIT, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        # HTML /search/ 不下发结果，搜索直接走 API wd
        try:
            kw = str(key or "").strip()
            if not kw:
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": API_LIMIT, "total": 0}
            try:
                page = max(1, int(pg))
            except Exception:
                page = 1
            data = self._api(ac="detail", wd=kw, pg=str(page))
            lst = self._api_rows(data)[:API_LIMIT]
            pc = int(data.get("pagecount") or 1) or 1
            total = int(data.get("total") or (pc * API_LIMIT))
            if str(quick) in ("1", "True", "true") and len(lst) > 12:
                lst = lst[:12]
            return {"list": lst, "page": page, "pagecount": pc,
                    "limit": API_LIMIT, "total": max(total, len(lst))}
        except Exception as e:
            self.log("searchContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": API_LIMIT, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段（HTML） ----------------
    def _field_items(self, plain):
        items = {}
        for m in _RE_FIELD.finditer(plain):
            title = self._clean(m.group(1)).rstrip("：:")
            body = m.group(2)
            links = [self._clean(a) for a in _RE_A.findall(body)]
            links = [x for x in links if x]
            items[title] = ", ".join(links) if links else self._clean(body)
        return items

    def _tab_name(self, inner):
        """线路名：span 优先；否则剥掉 <small> 计数后取纯文本（保留自营后缀字母）。"""
        ms = _RE_TAB_SPAN.search(inner)
        if ms:
            return self._clean(ms.group(1))
        t = _RE_TAB_SMALL.sub("", inner)
        return self._clean(re.sub(r"<[^>]+>", "", t))

    def _seg(self, label, body):
        """选集串按字节上限切段；未超限原样返回。返回 [(子线路名, 选集串), ...]。"""
        eps = [x for x in str(body or "").split("#") if x.strip()]
        chunks, cur, size = [], [], 0
        for seg in eps:
            b = len(seg.encode("utf-8")) + 1
            if cur and size + b > SEG_BYTES:
                chunks.append(cur)
                cur, size = [], 0
            cur.append(seg)
            size += b
        if cur:
            chunks.append(cur)
        if len(chunks) <= 1:
            return [(label, body)]
        return [("%s(%d)" % (label, i + 1), "#".join(c))
                for i, c in enumerate(chunks)]

    def _parse_lines(self, html):
        """线路 tab（DOM 序）与 panel 选集块按顺序一一对应。
        返回 (play_from, play_url)；选集标识为 /play/<vid>-<sid>-<nid>.html。"""
        tabs = []
        # 优先取站点 data-dropdown-value 展示名（含自营后缀字母，属性直出、配对精确）
        for mv in _RE_TAB_VALUE.findall(html):
            name = self._clean(mv)
            if name and name not in tabs:
                tabs.append(name)
        # 兜底：tab 块内 span 文本
        if not tabs:
            for _tag, inner in _RE_TAB.findall(html):
                name = self._tab_name(inner)
                if name and name not in tabs:
                    tabs.append(name)
        panels = _RE_PANEL.findall(html)

        play_from, play_url = [], []
        count = min(len(tabs), len(panels))
        for i in range(count):
            block = panels[i]
            eps, seen = [], set()
            for me in _RE_EP.finditer(block):
                href, inner = me.group(1), me.group(2)
                if href in seen:
                    continue
                seen.add(href)
                ep_name = self._clean(re.sub(r"<[^>]+>", "", inner))
                if not ep_name:
                    mt = _RE_EP_TITLE.search(me.group(0))
                    if mt:
                        ep_name = re.sub(r"^播放", "", self._clean(mt.group(1))).strip()
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            line_name = tabs[i] or ("线路%d" % (i + 1))
            base, k = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, k)
                k += 1
            body = "#".join("%s$%s" % (n, h) for n, h in eps)
            for sub_label, sub_body in self._seg(line_name, body):
                play_from.append(sub_label)
                play_url.append(sub_body)
        return play_from, play_url

    # ---------------- 详情（API 兜底） ----------------
    def _api_line_display(self, sid):
        if sid in LINE_NAME:
            return LINE_NAME[sid]
        if sid in OFFICIAL_SID:
            return "OK自营"
        return sid

    def _api_detail(self, vid):
        data = self._api(ac="detail", ids=vid)
        lst = data.get("list") or []
        if not lst:
            return {"list": []}
        it = lst[0]

        froms = [x for x in str(it.get("vod_play_from") or "").split("$$$") if x]
        urls = [x for x in str(it.get("vod_play_url") or "").split("$$$") if x]
        if not froms or not urls:
            return {"list": []}

        groups = []
        for sid, seg in zip(froms, urls):
            eps = []
            for item in seg.split("#"):
                if "$" not in item:
                    continue
                nm, u = item.split("$", 1)
                u = u.strip()
                if not u.startswith("http"):
                    continue
                eps.append((self._clean(nm) or "第%d集" % (len(eps) + 1), u))
            if eps:
                groups.append((sid, eps))
        if not groups:
            return {"list": []}

        def _key(g):
            sid = g[0]
            if sid in LINE_NAME:
                return LINE_ORDER[LINE_NAME[sid]]
            if sid in OFFICIAL_SID:
                return LINE_ORDER["OK自营"]
            return 50
        groups.sort(key=_key)

        names, used = [], set()
        for sid, _eps in groups:
            nm = self._api_line_display(sid)
            if nm in used:
                k = 2
                while "%s%d" % (nm, k) in used:
                    k += 1
                nm = "%s%d" % (nm, k)
            used.add(nm)
            names.append(nm)

        seg_froms, seg_urls = [], []
        for idx, (_sid, eps) in enumerate(groups):
            base_nm = names[idx]
            body = "#".join("%s$%s" % (n, u) for n, u in eps)
            for sub_label, sub_body in self._seg(base_nm, body):
                seg_froms.append(sub_label)
                seg_urls.append(sub_body)

        content = self._clean(it.get("vod_content") or it.get("vod_blurb") or "")
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        vod = {
            "vod_id": vid,
            "vod_name": self._clean(it.get("vod_name") or "")[:100],
            "vod_pic": it.get("vod_pic") or self.default_pic,
            "vod_content": content,
            "vod_actor": self._clean(it.get("vod_actor") or ""),
            "vod_director": self._clean(it.get("vod_director") or ""),
            "vod_score": self._clean_score(it.get("vod_score")),
            "vod_remarks": self._clean(it.get("vod_remarks") or ""),
            "vod_area": self._clean(it.get("vod_area") or ""),
            "vod_year": str(it.get("vod_year") or "")[:4],
            "vod_lang": self._clean(it.get("vod_lang") or ""),
            "vod_class": self._clean(it.get("vod_class") or it.get("type_name") or ""),
            "vod_subtitle": self._clean(it.get("vod_sub") or ""),
            "vod_play_from": "$$$".join(seg_froms),
            "vod_play_url": "$$$".join(seg_urls),
        }
        return {"list": [vod]}

    def detailContent(self, ids):
        try:
            raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            mid = re.search(r"(\d+)", str(raw) or "")
            if not mid:
                return {"list": []}
            vid = mid.group(1)

            # 主通道：HTML 详情页（线路原名/顺序/选集链接）
            html = self._fetch_html("/detail/%s.html" % vid)
            if html:
                play_from, play_url = self._parse_lines(html)
                if play_from:
                    vod = self._build_detail_from_html(html, vid, play_from, play_url)
                    if vod:
                        return {"list": [vod]}

            # 兜底 API
            self.log("detail HTML 无线路，回退 API:", vid)
            return self._api_detail(vid)
        except Exception as e:
            self.log("detailContent 异常:", e)
            return {"list": []}

    def _build_detail_from_html(self, html, vid, play_from, play_url):
        # 片名
        name = ""
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("-")[0].split("_")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vid

        # 标签：年份 / 地区 / 类型
        year, area, classify = "", "", ""
        mt = _RE_TAG.search(html)
        if mt:
            tags = [self._clean(a) for a in _RE_TAG_A.findall(mt.group(1))]
            tags = [x for x in tags if x]
            if len(tags) >= 1:
                year = tags[0]
            if len(tags) >= 2:
                area = tags[1]
            if len(tags) >= 3:
                classify = tags[2]

        # 海报
        pic = self.default_pic
        mp = _RE_POSTER.search(html)
        if mp:
            pic = self._fix_url(mp.group(1)) or self.default_pic

        # 简介：introduction-content p 优先 → meta description 兜底
        content = ""
        mc = _RE_INTRO.search(html)
        if mc:
            content = self._clean(mc.group(1))
        if not content:
            md = _RE_META_DESC.search(html)
            if md:
                content = self._clean(md.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        plain = re.sub(r"<!--[\s\S]*?-->", "", html)
        fields = self._field_items(plain)
        director = fields.get("导演", "")
        actor = fields.get("主演", "")
        status = fields.get("连载", "") or fields.get("备注", "")
        status = self._clean_status(status)

        subtitle = ""
        mt2 = re.search(r"》([^-《》]+?)-", html)
        if mt2:
            subtitle = self._clean(mt2.group(1))

        remarks = status or ("%d条线路" % len(play_from))
        return {
            "vod_id": vid,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks,
            "vod_area": area,
            "vod_year": year,
            "vod_lang": "",
            "vod_class": classify,
            "vod_subtitle": subtitle,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        try:
            pid = str(id or "").split("#")[0].rsplit("$", 1)[-1].strip()
            now = int(time.time())
            if pid in self._play_cache:
                ts, res = self._play_cache[pid]
                if now - ts < PLAY_CACHE_TTL:
                    return res

            if not pid:
                return {"parse": 1, "playUrl": "", "url": "",
                        "header": {"User-Agent": UA}}

            header = {"User-Agent": UA, "Referer": self.site_url + "/"}
            stream = ""

            if pid.startswith("http"):
                # API 兜底：标识本身就是直链/外链 URL
                stream = pid
            elif "/play/" in pid:
                # HTML 主通道：拉播放页取 player_aaaa.url
                play_page = self._fix_url(pid)
                html = self._fetch_html(play_page)
                stream = self._extract_stream(html)
                if not stream:
                    stream = play_page
            else:
                stream = self._fix_url(pid)

            low = stream.split("?")[0].lower()
            host = urllib.parse.urlparse(stream).hostname or ""

            if _RE_DIRECT.search(low):
                stream = self._resolve_sub_stream(stream, header)
                res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
                self._play_cache[pid] = (now, res)
                self.log("  => 直链: %s" % stream[:160])
                return res

            if any(d in host for d in OFFICIAL_DOMAINS):
                ref = "https://%s/" % host
                res = {"parse": 1, "playUrl": "", "url": stream,
                       "header": {"User-Agent": UA, "Referer": ref}}
            else:
                res = {"parse": 1, "playUrl": "", "url": stream, "header": header}
            if stream.startswith("http"):
                self._play_cache[pid] = (now, res)
            return res
        except Exception as e:
            self.log("playerContent 异常:", e)
            pid = str(id or "")
            url = pid if pid.startswith("http") else self._fix_url(pid.split("#")[0].rsplit("$", 1)[-1])
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def _player_json(self, html):
        """player_aaaa JSON 括号深度配对精确截取（正确处理嵌套对象/转义）。"""
        i = html.find("player_aaaa")
        if i < 0:
            return ""
        j = html.find("{", i)
        if j < 0:
            return ""
        depth, instr, esc = 0, False, False
        for k in range(j, len(html)):
            c = html[k]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                instr = not instr
                continue
            if instr:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return html[j:k + 1]
        return ""

    def _decrypt_url(self, url, enc):
        """按 encrypt 解密：0/空 明文；1 base64；2 urlencode 后 base64。失败回退明文。"""
        if not url:
            return ""
        try:
            enc = str(enc)
            if enc in ("0", ""):
                return url.replace("\\/", "/")
            if enc == "1":
                pad = "=" * (-len(url) % 4)
                return base64.b64decode(url + pad).decode("utf-8", "ignore")
            if enc == "2":
                raw = urllib.parse.unquote(url)
                pad = "=" * (-len(raw) % 4)
                return base64.b64decode(raw + pad).decode("utf-8", "ignore")
        except Exception as e:
            self.log("  解密失败 enc=%s: %s" % (enc, repr(e)[:80]))
        return url.replace("\\/", "/")

    def _extract_stream(self, html):
        if not html:
            return ""
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw.replace("\\/", "/"))
                if aa.get("url"):
                    return self._decrypt_url(aa["url"], aa.get("encrypt", "0"))
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mu:
                    return mu.group(1).replace("\\/", "/")
        return ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率→第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
        if not url or ".mp4" in url.lower() or ".flv" in url.lower():
            return url

        def _get(target):
            last = None
            for _ in range(2):
                try:
                    rs = self._http_get(target, headers=header, timeout=(6, 12))
                    if rs is not None and getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?") if rs is not None else "none")
                except Exception as e:
                    last = e
            return None, last

        try:
            rm, err = _get(url)
            if err is not None:
                return url
            text = rm.text if hasattr(rm, "text") else ""
            if "#EXT-X-STREAM-INF" not in text:
                return url
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        return sub
                    break
        except Exception as e:
            self.log("子流解析回退:", e)
        return url

    # ---------------- 其余契约 ----------------
    def localProxy(self, param):
        # 封面中转：图床不带站点 Referer（部分图床带站点 Referer 会 403）；空 body 返 404 空壳
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
                return [404, "text/plain", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self._http_get(url, headers={"User-Agent": UA, "Accept": "image/*,*/*;q=0.8"})
            if rsp is None:
                return [404, "text/plain", b"", ""]
            content = rsp.content
            if not content:
                return [404, "text/plain", b"", ""]
            ctype = (rsp.headers.get("Content-Type") or "image/jpeg").split(";")[0]
            if content[:4] == b"\x89PNG":
                ctype = "image/png"
            elif content[:4] == b"\xff\xd8\xff\xe0" or content[:3] == b"\xff\xd8\xff":
                ctype = "image/jpeg"
            return [rsp.status_code if rsp.status_code in (200, 206) else 200, ctype, content, ""]
        except Exception:
            return [404, "text/plain", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self._session = None
            self._api_cache = {}
            self._play_cache = {}
            self._warmed = False
        except Exception:
            pass

    def close(self):
        self.destroy()
