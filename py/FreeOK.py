# coding=utf-8
"""
FreeOK freeokk.lol | TVBox Python 爬虫
站点结构（线上快照实证，MacCMS 模板）:
  - 首页:   /
  - 分类入口: /type/<tid>.html            （首页模块，仅首屏 40 条）
  - 完整库:  /show/<12 段空槽>.html        （筛选 + 分页）
  - 详情:   /detail/<id>.html
  - 播放:   /play/<vid>-<sid>-<nid>.html
  - 搜索:   /search/<关键词>-------------.html （14 段槽，13 连字符，与 show 不同）

  show slug 12 段槽位:
    段0=tid / 段1=地区 / 段2=排序 time·hits·score / 段3=类型 / 段4=语言 /
    段5=字母(A~Z；0-9 落段5=0、段6=9) / 段7 空 / 段8=页码 / 段9~10 空 / 段11=年代；中文 percent-encode

  卡片(列表/首页): a.module-poster-item[href=/detail/<id>.html][title]
      .module-item-note=备注(HD国语/更新至xx集)；img.lazy data-original/alt 封面；
      .module-poster-item-title=片名
  卡片(搜索): div.module-card-item
      .module-card-item-class=分类(副标题)；a.module-card-item-poster[href]；note；
      img data-original/alt；.module-card-item-title>strong=片名

  详情: h1 片名；.module-info-tag 内 a=年份/地区/类型；
      简介 .module-info-introduction-content>p 优先 → meta description 兜底；
      .module-info-item title「导演：/主演：/更新：/连载：/备注：」后 <a> 列表或 content；
      海报 .module-info-poster 内 img data-original；站点无数字豆瓣评分，score 返空。
  线路: .module-tab-item span=线路名（DOM 序），与 .module-list.tab-list#panelN 按顺序一一对应；
      块内 a.module-play-list-link[href=/play/..][title] > span=集名；
      「立即播放」主按钮不在选集块内，不纳入。
  播放: var player_aaaa={花括号配平 JSON}，encrypt=0/空取 url；
      url 为 m3u8/mp4 直链 → parse:0；网页外链(爱优腾等) → parse:1 交客户端嗅探；兜底 parse:1。

  分页: #page 块内 /show/ slug 段8 最大页码=真实总页；每页 40 张。

站点防护（实证）:
  - 间歇 ReadTimeout/上游小页，重试即恢复；首页下发会话 Cookie，后续复用同一 Session。
  - 主备域名（顺序即轮换顺序，均为同站镜像，2026-11-25 实测）:
      freeokk.lol(主用最稳) → www.freeokk.pro → www.freeok.ink → freeokk.top(末位兜底,实测间歇 503)
  - 强制 IPv4；自建 Session 优先 + 基类 fetch 回退；遇障重放后轮换主备。
"""
import re
import sys
import json
import time
import socket
import urllib.parse

sys.path.append('..')

# ---- 强制 IPv4：禁用 IPv6（云端出口 IPv6 不稳）----
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            if r[0] == socket.AF_INET]


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
    "https://freeokk.lol",   # 用户指定主用，实测云端直连最稳
    "https://www.freeokk.pro",
    "https://www.freeok.ink",
    "https://freeokk.top",  # 末位兜底，实测间歇 503
]
HOST = HOSTS[0]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_LIMIT = 40

# ===================== 分类（对齐站点顶部导航）=====================
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

# 排序（URL 段2）
_SORTS = [("最新更新", "time"), ("人气最高", "hits"), ("评分最高", "score")]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    # 展示顺序对齐站点 PC 库展开筛选：类型 → 地区 → 语言 → 年代 → 字母；排序在末行
    FILTERS[tid] = [
        {"key": "type", "name": "类型", "value": _opts(_TYPES.get(tid, []))},
        {"key": "area", "name": "地区", "value": _opts(_AREAS.get(tid, []))},
        {"key": "lang", "name": "语言", "value": _opts(_LANGS.get(tid, []))},
        {"key": "year", "name": "年代", "value": _opts(_YEARS)},
        {"key": "letter", "name": "字母", "value": _opts(_LETTERS)},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]


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
# 首页轮播 banner：div.swiper-slide > a.banner[href=/detail/..][style=background:url(封面)]
#   + div.mobile-v-info > .v-title>span 片名；.v-ins>p 状态/主演
_RE_BANNER = re.compile(
    r'<div class="swiper-slide">\s*<a href="(/detail/\d+\.html)" class="banner"[^>]*'
    r'style="background:\s*url\(([^)]+)\)[^>]*>\s*</a>\s*'
    r'<div class="mobile-v-info">\s*<div class="v-title">\s*<span>([\s\S]*?)</span>'
    r'[\s\S]*?<div class="v-ins">([\s\S]*?)</div>',
    re.S | re.I)
# 排行榜列表：a > module-paper-item-num(序号) + module-paper-item-info>span 片名 >p 状态（无封面）
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
_RE_INTRO = re.compile(
    r'module-info-introduction-content">([\s\S]*?)</div>', re.S | re.I)
_RE_POSTER = re.compile(
    r'<div class="module-info-poster">[\s\S]*?<img[^>]*?(?:data-original|src)="([^"]*)"', re.S | re.I)

# 详情标签行：年份/地区/类型
_RE_TAG = re.compile(r'<div class="module-info-tag">([\s\S]*?)</div>\s*</div>', re.S | re.I)
_RE_TAG_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 详情元信息项：标题「导演：」后 content
_RE_FIELD = re.compile(
    r'module-info-item-title">([^<]*?)：</span>\s*<div class="module-info-item-content">([\s\S]*?)</div>',
    re.S | re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 线路 tab（DOM 序）与 panel 选集块；兼容 div/a 标签、class 前置属性；
# 精确匹配 module-tab-item 边界，排除 module-tab-items-box / module-tab-title 容器
_RE_TAB = re.compile(
    r'<(div|a)\b[^>]*class="[^"]*module-tab-item(?:\s|")[^"]*"[^>]*>([\s\S]*?)</\1>',
    re.S | re.I)
_RE_TAB_SPAN = re.compile(r'<span>([^<]+)</span>', re.I)
_RE_TAB_SMALL = re.compile(r'<small[\s\S]*?</small>', re.I)
_RE_PANEL = re.compile(
    r'<div class="module-list[^"]*tab-list[^"]*"[^>]*>([\s\S]*?)(?=<div class="module-list|$)',
    re.S | re.I)
_RE_EP = re.compile(
    r'<a\s+class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.S | re.I)
_RE_EP_TITLE = re.compile(r'title="([^"]*)"', re.I)

# 分页 #page 块
_RE_PAGE_BLOCK = re.compile(r'<div id="page">([\s\S]*?)</div>\s*(?=<div|$)', re.S | re.I)

# 上游网关故障纯文本小页
_RE_UPSTREAM = re.compile(
    r'upstream connect error|connection timeout|connection reset|bad gateway|'
    r'service unavailable|reset reason', re.I)
_RE_DIRECT = re.compile(r'\.(m3u8|mp4)(\?|$)', re.I)


class Spider(Spider):

    def getName(self):
        return "FreeOK"

    # ---------------- 基础 ----------------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.hosts = list(HOSTS)
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self._host_idx = 0
        for i, h in enumerate(self.hosts):
            if h.rstrip("/") == self.site_url:
                self._host_idx = i
                break

        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._session = None
        self._warmed = False
        self._play_cache = {}

    def getDependence(self):
        return []

    def log(self, *a, **kw):
        try:
            print("[freeok]", *a)
        except Exception:
            pass

    # ---------------- 会话 / 主备轮换 ----------------
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

    def _is_bad(self, text, status=200):
        if not text:
            return True
        if status and int(status) in (403, 502, 503, 500, 404):
            return True
        if len(text) < 200 and _RE_UPSTREAM.search(text.lower()):
            return True
        # 间歇故障小壳 / nginx 404 空页：200 但无正文结构，判坏触发重试轮换
        if len(text) < 300 and not re.search(r"module-|detail/|player_aaaa", text):
            return True
        if re.search(r"<title>404", text):
            return True
        # 列表/搜索异版缓存：短页且无任何详情链接、无播放变量，判坏跨域重试
        if len(text) < 4000 and "/detail/" not in text and "player_aaaa" not in text:
            return True
        return False

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
        if self._warmed:
            return
        try:
            self._http_get(self.site_url + "/", timeout=12)
            self._warmed = True
        except Exception as e:
            self.log("预热失败:", e)

    def _http_get(self, url, headers=None, timeout=12):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._session_get()
        rsp = None
        try:
            if sess is not None:
                rsp = sess.get(url, headers=h, timeout=(8, timeout))
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("GET 异常:", url, repr(e)[:120])
            rsp = None

        text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200) if rsp is not None else 0

        if self._is_bad(text, status):
            # 重新落会话后直接重放目标一次（不再先打首页预热，减少抖动期开销）
            self._session = None
            sess2 = self._session_get()
            try:
                if sess2 is not None:
                    rsp = sess2.get(url, headers=h, timeout=(8, timeout))
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else ""
                status = getattr(rsp, "status_code", 200)
            except Exception as e:
                self.log("重放异常:", repr(e)[:120])
                text, status = "", 0
        return rsp

    def _fetch(self, url, timeout=15, headers=None, tries=2):
        """跨域遍历重试：当前 host 起依次轮换主备；每个 host 内部由 _http_get
        落会话重放一次。抖动/503/故障小壳时落到最稳域名，取首个非坏响应。"""
        last = ""
        n = len(self.hosts)
        for round_i in range(tries):
            for step in range(n):
                idx = (self._host_idx + step) % n
                host = self.hosts[idx].rstrip("/")
                target = self._rebase_url(url, host)
                try:
                    rsp = self._http_get(target, headers=headers, timeout=timeout)
                    text = rsp.text if rsp is not None and hasattr(rsp, "text") else (
                        rsp.content.decode("utf-8", "ignore")
                        if rsp is not None and hasattr(rsp, "content") else "")
                    status = getattr(rsp, "status_code", 200) if rsp is not None else 0
                    if not self._is_bad(text, status):
                        # 成功 host 记为当前主域，后续请求跟随最稳域名
                        if idx != self._host_idx:
                            self._host_idx = idx
                            self.site_url = host
                            self.headers["Referer"] = host + "/"
                        return text
                    last = text
                except Exception as e:
                    self.log("fetch FAIL", target, repr(e)[:120])
                    last = ""
            if round_i < tries - 1:
                time.sleep(1.0 * (round_i + 1))
        return ""

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

    def _rebase_url(self, url, base):
        if not url:
            return url
        for h in self.hosts:
            if url.startswith(h):
                return base + url[len(h):]
        if url.startswith("http"):
            return url
        return base + (url if url.startswith("/") else "/" + url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<!--[\s\S]*?-->", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _clean_status(self, text):
        """状态角标：去掉更新日期时间，保留清晰度/集数状态文本。"""
        if not text:
            return ""
        text = re.sub(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?", "", text)
        text = re.sub(r"\s+/\s*", " ", text)
        return self._clean(text)

    def _try_json(self, text):
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", str(text), re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    # ---------------- 卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
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

        # 3) 首页轮播 banner：a.banner + mobile-v-info
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

        # 4) 排行榜：module-paper-item（序号 + 片名 + 状态，无封面）
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

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            self._warm_up()
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            return {"list": self._parse_cards(html)}
        except Exception as e:
            self.log("homeVideoContent 异常:", e)
            return {"list": []}

    def _filter_slug(self, tid, extend, page=1):
        """构造 /show/ 12 段空槽 URL。
        段0=tid / 段1=地区 / 段2=排序 / 段3=类型 / 段4=语言 /
        段5=字母(0-9 落段5=0、段6=9) / 段8=页码 / 段11=年代，段7、9~10 空段占位。"""
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

    def _fetch_list(self, url):
        """列表/搜索页：首次取空（变体缓存/空壳）时清会话重取一次。"""
        html = self._fetch(url)
        if not self._parse_cards(html):
            self._session = None
            self._warmed = False
            html = self._fetch(url)
        return html

    def categoryContent(self, tid, pg, filter, extend):
        try:
            self._warm_up()
            page = int(pg) if pg else 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            extend = extend or {}
            for k in list(extend.keys()):
                if extend[k] in ("", None, "全部"):
                    del extend[k]

            if extend or page > 1:
                url = self.site_url + self._filter_slug(tid, extend, page)
            else:
                url = self.site_url + "/show/" + str(tid) + "-----------.html"

            self.log("category: %s" % url)
            html = self._fetch_list(url)
            self.log("  HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            pagecount = self._page_count(html)
            self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": PAGE_LIMIT, "total": pagecount * PAGE_LIMIT,
            }
        except Exception as e:
            self.log("categoryContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": PAGE_LIMIT, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            self._warm_up()
            page = int(pg) if pg else 1
            raw_kw = str(key or "").strip()
            if not raw_kw:
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": PAGE_LIMIT, "total": 0}
            q = urllib.parse.quote(raw_kw)
            # 搜索路由为 14 槽（13 连字符，与 /show/ 的 12 段不同）：段0=关键词，段8=页码
            seg = [""] * 14
            seg[0] = q
            seg[8] = str(page) if page > 1 else ""
            slug = "-".join(seg)
            url = self.site_url + "/search/" + slug + ".html"
            self.log("search: %s" % url)
            html = self._fetch_list(url)
            self.log("  HTML 长度: %d" % len(html))
            videos = self._parse_cards(html)
            pagecount = self._page_count(html)
            total = len(videos)
            return {"list": videos, "page": page, "pagecount": pagecount,
                    "limit": PAGE_LIMIT, "total": total}
        except Exception as e:
            self.log("searchContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": PAGE_LIMIT, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _field_items(self, plain):
        """提取详情 .module-info-item 项：{标题: 清洗后内容}。"""
        items = {}
        for m in _RE_FIELD.finditer(plain):
            title = self._clean(m.group(1)).rstrip("：:")
            body = m.group(2)
            links = [self._clean(a) for a in _RE_A.findall(body)]
            links = [x for x in links if x]
            items[title] = ", ".join(links) if links else self._clean(body)
        return items

    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vod_id = str(ids[0])
            url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
            self.log("detail: %s" % url)

            html = self._fetch(url)
            if not html:
                return {"list": []}

            # 片名
            name = ""
            mh = _RE_H1.search(html)
            if mh:
                name = self._clean(mh.group(1))
            if not name:
                mt = re.search(r"<title>(.*?)</title>", html, re.S)
                if mt:
                    name = self._clean(mt.group(1).split("-")[0].split("_")[0])
            name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

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

            # 剥 HTML 注释后提取元信息
            plain = re.sub(r"<!--[\s\S]*?-->", "", html)
            fields = self._field_items(plain)
            director = fields.get("导演", "")
            actor = fields.get("主演", "")
            # 状态：连载(更新至第N集/已完结) > 备注；更新项仅为日期，不进 remarks
            status = fields.get("连载", "") or fields.get("备注", "")
            status = self._clean_status(status)

            # 大类（电影/剧集/综艺/动漫）从 <title>《片名》大类- 提取作副标题
            subtitle = ""
            mt2 = re.search(r"》([^-《》]+?)-", html)
            if mt2:
                subtitle = self._clean(mt2.group(1))

            # ===== 线路与选集 =====
            play_from, play_url = self._parse_lines(html)
            if not play_from:
                self.log("  未解析到选集")
                return {"list": []}

            remarks = status or ("%d条线路" % len(play_from))

            return {"list": [{
                "vod_id": vod_id,
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
                "type_name": classify,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]}
        except Exception as e:
            self.log("detailContent 异常:", e)
            return {"list": []}

    def _tab_name(self, inner):
        """线路名：span 优先；否则剥掉 <small> 计数后取纯文本。"""
        ms = _RE_TAB_SPAN.search(inner)
        if ms:
            return self._clean(ms.group(1))
        t = _RE_TAB_SMALL.sub("", inner)
        return self._clean(re.sub(r"<[^>]+>", "", t))

    def _parse_lines(self, html):
        """线路 tab（DOM 序）与 panel 选集块按顺序一一对应。
        页面存在隐藏 mobile-tab-box 与可见 playSwiper 双份 tab，保序去重；
        返回 (play_from, play_url)。"""
        tabs = []
        for _tag, inner in _RE_TAB.findall(html):
            name = self._tab_name(inner)
            if name and name not in tabs:
                tabs.append(name)
        panels = _RE_PANEL.findall(html)

        play_from, play_url = [], []
        count = min(len(tabs), len(panels))
        for i in range(count):
            block = panels[i]
            eps = []
            seen = set()
            for me in _RE_EP.finditer(block):
                href, inner = me.group(1), me.group(2)
                if href in seen:
                    continue
                seen.add(href)
                # 优先 span 集名（第N集）；title 兜底并剥「播放<片名>」前缀
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
            # 重名线路去重编号
            base, k = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, k)
                k += 1
            body = "#".join("%s$%s" % (n, h) for n, h in eps)
            for sub_label, sub_body in self._seg(line_name, body):
                play_from.append(sub_label)
                play_url.append(sub_body)
        return play_from, play_url

    # 单条 play_url 的 UTF-8 字节上限（客户端单条超 2048B 会截断长剧选集）
    SEG_BYTES = 1900

    def _seg(self, label, body):
        """选集串按字节上限切段；未超限原样返回。返回 [(子线路名, 选集串), ...]。"""
        eps = [x for x in str(body or "").split("#") if x.strip()]
        chunks, cur, size = [], [], 0
        for seg in eps:
            b = len(seg.encode("utf-8")) + 1
            if cur and size + b > self.SEG_BYTES:
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

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        try:
            play_page = id if str(id).startswith("http") else self._fix_url(id)
            now = int(time.time())
            if play_page in self._play_cache:
                ts, res = self._play_cache[play_page]
                if now - ts < 600:
                    return res

            header = {"User-Agent": UA, "Referer": self.site_url + "/"}
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

            if stream and _RE_DIRECT.search(stream.lower()):
                stream = self._resolve_sub_stream(stream, header)
                res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链: %s" % stream[:160])
                return res

            # 提取不到直链（网页外链/无直链）：交客户端嗅探播放页
            target = stream if stream.startswith("http") else play_page
            res = {"parse": 1, "playUrl": "", "url": target, "header": header}
            self._play_cache[play_page] = (now, res)
            return res
        except Exception as e:
            self.log("playerContent 异常:", e)
            header = {"User-Agent": UA, "Referer": self.site_url + "/"}
            return {"parse": 1, "playUrl": "",
                    "url": str(id) if str(id).startswith("http") else self._fix_url(id),
                    "header": header}

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

    def _extract_stream(self, html):
        if not html:
            return ""
        raw = self._player_json(html)
        if raw:
            try:
                aa = json.loads(raw.replace("\\/", "/"))
                if str(aa.get("encrypt", "0")) in ("0", "") and aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mu:
                    return mu.group(1).replace("\\/", "/")
        return ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率→第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
        if not url or ".mp4" in url.lower():
            return url

        def _get(target):
            last = None
            for _ in range(2):
                try:
                    rs = self.fetch(target, headers=header, timeout=10)
                    if getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?"))
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
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"})
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
