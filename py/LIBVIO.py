# coding=utf-8
"""
LIBVIO libvio.host | TVBox Python 爬虫
站点结构（线上快照实证 2026-11-26，MacCMS stui_default 模板，HTML 直出）:
  - 首页:   /
  - 主分类: /type/<tid>.html           （第 1 页）
            /type/<tid>-<page>.html    （分页）
  - 筛选:   /show/<tid>-<11 段空槽>.html
            剥离 tid 后 11 段：seg1=地区 seg2=类型 seg3=语言
            seg6=页码 seg10=年代年份，其余空段占位；中文段 percent-encode
  - 详情:   /detail/<vid>.html
  - 播放:   /w/<vid>-<sid>-<nid>.html
  - 搜索:   /search/-------------.html?wd=<关键词>（GET，单页返回，无分页）

  - 卡片(首页/分类/搜索同构): ul.stui-vodlist > li > div.stui-vodlist__box
            a.stui-vodlist__thumb[href=/detail/<id>.html][title=片名]
            [data-original=封面]；span.pic-text=备注(集数/状态)；
            span.pic-tag-top=评分角标；每片封面 a 与标题 a 同 href，取封面 a 去重
  - 详情:   h1.title 片名；.vod-poster img[data-original] 海报；
            .vod-meta meta-item 顺序：类型(逗号串) / 地区 / 年份 / 上映日期 /
            集数 / 更新日期 / 主演：… / 导演：…；评分 .score(x.x分)；
            简介 span.detail-content(全文) > span.detail-sketch(摘要) >
            meta description 兜底；站点不展示又名/副标题，vod_subtitle 留空
  - 线路:   div.playlist-panel，h3=线路名(网站展示名)，顺序=面板 DOM 序；
            ul.stui-content__playlist li a[href=/w/..][集名]；
            netdisk-list 网盘外链面板(夸克/迅雷/百度/UC)不纳入播放源
  - 播放:   播放页 player_aaaa JSON（花括号配平）；
            from=vr2(BD5播放) url 为明文 http 直链；
            from=ty_new1(BD播放) url 为加密串，走两步中转：
              1) 壳页 /vid/ty4.php?url=<rawUrl原样>&next=<link_next>&id=<vid>&nid=<nid>
                 壳内 window.LIBVIO_CFG={parseUrl, rawUrl, sid}
              2) POST parseUrl，头 Content-Type:application/json、X-LV-S:sid，
                 body {"url":rawUrl,"sid":sid} → JSON {url:直链, fatal, msg}
            master 多码率取首条子 m3u8；未命中兜底 parse:1 交客户端嗅探

站点防护（实证）:
  - envoy js-pow 浏览器校验盾：首访 403。
      · TLS/UA 指纹不过 → 44B 纯文本 "403 Forbidden: browser verification required"
        （无挑战页，Python 层无法解，记日志换域兜底）；
      · 指纹过 → 20317B 挑战页，内联 var TS/SIG/DIFF/MODE；
        枚举 nonce 使 sha256(SIG+str(nonce)) 前缀匹配 DIFF，
        种 Cookie __cdn_pow=<TS>_<MODE>_<nonce>_<SIG> 后重放放行。
  - 采集 API /api.php/provide/vod/ 返回 closed（已关闭），只走 HTML 通道。
  - 主备域名（顺序即轮换顺序，2026-11-26 实测；停放页/503 未写入）:
      libvio.host → www.libvio.to → libviobd.com → www.libviobd.com
"""
import re
import sys
import json
import time
import hashlib
import socket
import threading
import urllib.parse

sys.path.append('..')

# ---- 强制 IPv4：禁用 IPv6（出口 IPv6 不稳）----
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            if r[0] == socket.AF_INET]


socket.getaddrinfo = _ipv4_getaddrinfo

try:
    import requests as _requests
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
except ImportError:
    _requests = None

try:
    from base.spider import Spider
except ImportError:
    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None and _requests is not None:
                self._session = _requests.Session()
                self._session.verify = False
                adapter = _requests.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, headers=None, data=None, json=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.post(url, headers=headers, data=data, json=json,
                                 timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[libvio]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站专属配置 =====================
HOSTS = [
    "https://libvio.host",
    "https://www.libvio.to",
    "https://libviobd.com",
    "https://www.libviobd.com",
]
# 未写入：libvio.io / www.libvio.host 为域名停放页；libvio.app / libvio.me /
#         www.iioo.com 实测 503 upstream；libvio.to 为“备用网址·未启用”停放页。
HOST = HOSTS[0]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_LIMIT = 12  # 站点每页实际片数（封面 a 去重后实证 12）

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "剧集"},
    {"type_id": "4",  "type_name": "番剧"},
    {"type_id": "15", "type_name": "日韩"},
    {"type_id": "16", "type_name": "欧美"},
]

# 类型（show 槽 seg2，各分类站点库内实际标签，页面实证，去重保序）
_TYPES = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
          "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
          "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
          "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
          "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智",
          "励志", "其他"],
    "15": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
           "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "惊悚", "其他"],
    "16": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
           "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
}

# 地区（show 槽 seg1，站点原文，逐分类实证）
_AREAS = {
    "1": ["中国大陆", "中国香港", "中国台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["中国大陆", "中国台湾", "中国香港", "韩国", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "4": ["中国", "日本", "欧美", "其他"],
    "15": ["日本", "韩国"],
    "16": ["美国", "英国", "德国", "加拿大", "其他"],
}

# 年代（show 槽 seg10，站点实证 1998~2026 倒序）
_YEARS = [str(y) for y in range(2026, 1997, -1)]


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    # 主页筛选区实证仅透出：类型 → 地区 → 年份（语言为进入类型后的二级筛选，主页不列）
    FILTERS[tid] = [
        {"key": "type", "name": "类型", "value": _opts(_TYPES.get(tid, []))},
        {"key": "area", "name": "地区", "value": _opts(_AREAS.get(tid, []))},
        {"key": "year", "name": "年份", "value": _opts(_YEARS)},
    ]


# ===================== 正则 =====================
# 卡片封面 a（天然去重，避开 h4 标题重复链接）；整块含内部备注/评分 span
_RE_CARD = re.compile(
    r'<a\s+class="stui-vodlist__thumb[^"]*"\s+'
    r'href="(/detail/\d+\.html)"\s+'
    r'title="([^"]*)"\s+'
    r'data-original="([^"]*)"[\s\S]*?</a>', re.I)
_RE_CARD_FALLBACK = re.compile(
    r'<a\s+class="stui-vodlist__thumb[^"]*"[^>]*href="(/detail/\d+\.html)"[^>]*>', re.I)
_RE_REMARK = re.compile(r'<span class="pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_SCORE_TAG = re.compile(r'<span class="pic-tag[^"]*"[^>]*>([\s\S]*?)</span>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(
    r'<img[^>]*id="js-poster-img"[^>]*data-original="([^"]+)"', re.I)
_RE_POSTER_BG = re.compile(
    r'id="js-backdrop"[^>]*data-src="([^"]+)"', re.I)
_RE_META = re.compile(r'<span class="meta-item">([^<]*)</span>', re.I)
_RE_INTRO_FULL = re.compile(
    r'<span\s+class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_SKETCH = re.compile(
    r'<span\s+class="detail-sketch"[^>]*>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_SCORE = re.compile(r'<span class="score">([\d.]+)\s*分</span>', re.I)

# 线路面板（播放: playlist-panel；网盘: playlist-panel netdisk-panel）/ 选集
_RE_PANEL = re.compile(
    r'<div class="playlist-panel([^"]*)">([\s\S]*?)(?=<div class="playlist-panel[^"]*">|$)',
    re.I)
_RE_PANEL_NAME = re.compile(r'<h3>([\s\S]*?)</h3>', re.I)
_RE_EP = re.compile(
    r'<li[^>]*>\s*<a\s+href="(/w/\d+-\d+-\d+\.html)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放变量 / 配置
_RE_AA_VAR = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_CFG_VAR = re.compile(r'window\.LIBVIO_CFG\s*=\s*(\{[\s\S]*?\});', re.I)

# PoW 挑战
_RE_POW = re.compile(
    r'var\s+TS\s*=\s*"([^"]*)",\s*SIG\s*=\s*"([^"]*)",\s*'
    r'DIFF\s*=\s*"([^"]*)",\s*MODE\s*=\s*"([^"]*)";', re.I)
_RE_POW_PAGE = re.compile(r'x-cdn-challenge|js-pow|browser verification', re.I)

# 分页页码（分类 /type/<tid>-<page>.html；筛选 /show/<slug>-<page>-.html）
_RE_TYPE_PAGE = re.compile(r'/type/\d+-(\d+)\.html')
_RE_SHOW_PAGE = re.compile(r'/show/[^"]*-(\d+)-[^"]*\.html')

# 直链
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)

# 线路 from → 中转壳路径映射（player.js 实证）
_PROXY_PATH = {
    "ty_new1": "/vid/ty4.php",
    "vr2": "/vid/plyr/vr2.php",
}


class Spider(Spider):

    # ---------- 基础 ----------
    def log(self, *a, **kw):
        try:
            parts = []
            for x in a:
                if isinstance(x, (dict, list)):
                    parts.append(json.dumps(x, ensure_ascii=False))
                else:
                    parts.append(str(x))
            print("[libvio]", " ".join(parts))
        except Exception:
            pass

    def getName(self):
        return "LIBVIO"

    def getDependence(self):
        return []

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
        self._http = self._build_http()
        self._pow_cookie = ""
        self._pow_lock = threading.Lock()
        self._play_cache = {}

    # ---------- 自建 Session（双轨：自建优先，异常回退壳子基类）----------
    def _build_http(self):
        if _requests is None:
            return None
        try:
            sess = _requests.Session()
            sess.verify = False
            adapter = _requests.adapters.HTTPAdapter(
                pool_connections=10, pool_maxsize=10, max_retries=0)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
            return sess
        except Exception as e:
            self.log("自建 Session 不可用,回退基类:", e)
            return None

    def _request(self, method, url, headers=None, body=None, timeout=20):
        method = method.upper()
        h = dict(self.headers)
        if headers:
            h.update(headers)
        if self._pow_cookie:
            h["Cookie"] = self._pow_cookie
        if self._http is not None:
            try:
                if method == "POST":
                    return self._http.post(url, headers=h, data=body,
                                           timeout=timeout, verify=False)
                return self._http.get(url, headers=h, timeout=timeout, verify=False)
            except Exception as e:
                self.log("自建请求失败,回退基类:", method, url[:60], repr(e)[:100])
        # 回退壳子基类
        if method == "POST":
            return self.post(url, headers=h, data=body, timeout=timeout)
        return self.fetch(url, headers=h, timeout=timeout)

    @staticmethod
    def _body(rsp):
        if rsp is None:
            return ""
        if hasattr(rsp, "text") and rsp.text:
            return rsp.text
        if hasattr(rsp, "content"):
            return rsp.content.decode("utf-8", "ignore")
        return str(rsp)

    @staticmethod
    def _status(rsp):
        return getattr(rsp, "status_code", 200) if rsp is not None else 0

    # ---------- PoW 盾闭环 ----------
    def _solve_pow(self, html):
        m = _RE_POW.search(html or "")
        if not m:
            return None
        ts, sig, diff, mode = m.group(1), m.group(2), m.group(3), m.group(4)
        self.log("PoW: sig=%s diff=%s" % (sig[:16], diff))
        start = time.time()
        prefix_b = sig.encode()
        max_iter = 65536 * 32
        for i in range(max_iter):
            if hashlib.sha256(prefix_b + str(i).encode()).hexdigest().startswith(diff):
                cost = time.time() - start
                self.log("PoW 破解成功: nonce=%d 耗时=%.2fs" % (i, cost))
                return "%s=%s_%s_%s_%s" % ("__cdn_pow", ts, mode, i, sig)
            if i % 200000 == 0 and time.time() - start > 60:
                self.log("PoW 超时放弃")
                return None
        self.log("PoW 未在范围内破解")
        return None

    def _is_bad(self, text, status=200):
        if not text:
            return True
        if status and int(status) in (403, 502, 503, 500, 404):
            # 挑战页（js-pow）不算坏，交由 PoW 闭环
            if _RE_POW_PAGE.search(text) and _RE_POW.search(text):
                return False
            return True
        low = text.lower()
        if "upstream connect error" in low or "connection timeout" in low:
            return True
        if "browser verification required" in low and len(text) < 200:
            return True
        return False

    def _switch_host(self):
        for _ in range(len(self.hosts) - 1):
            self._host_idx = (self._host_idx + 1) % len(self.hosts)
            cand = self.hosts[self._host_idx].rstrip("/")
            if cand != self.site_url:
                self.site_url = cand
                self.headers["Referer"] = self.site_url + "/"
                self._http = self._build_http()
                self._pow_cookie = ""
                self.log("轮换域名 ->", self.site_url)
                return True
        return False

    def _fetch(self, url, timeout=20, headers=None, tries=2):
        last = ""
        for i in range(tries):
            try:
                rsp = self._request("GET", url, headers=headers, timeout=timeout)
                text = self._body(rsp)
                status = self._status(rsp)

                # js-pow 挑战页 → 解 PoW 种 cookie 重放
                if _RE_POW.search(text):
                    with self._pow_lock:
                        cookie = self._solve_pow(text)
                    if cookie:
                        self._pow_cookie = cookie
                        if self._http is not None:
                            try:
                                ck, cv = cookie.split("=", 1)
                                self._http.cookies.set(ck, cv, domain="", path="/")
                            except Exception:
                                pass
                        rsp2 = self._request("GET", url, headers=headers, timeout=timeout)
                        text2 = self._body(rsp2)
                        if not self._is_bad(text2, self._status(rsp2)):
                            return text2
                        text = text2
                    else:
                        last = text
                        continue

                if not self._is_bad(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, repr(e)[:120])
                last = ""
            if i < tries - 1:
                time.sleep(1.0 * (i + 1))

        # 多次遇障：轮换主备域名再取一次
        if self._switch_host():
            new_url = self._rebase_url(url, self.site_url)
            try:
                rsp = self._request("GET", new_url, headers=headers, timeout=timeout)
                text = self._body(rsp)
                if not self._is_bad(text, self._status(rsp)):
                    return text
            except Exception as e:
                self.log("轮换后重试失败:", repr(e)[:120])
        return last

    # ---------- 工具 ----------
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
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_CARD.finditer(html):
            href, name, pic = m.group(1), m.group(2), m.group(3)
            if href in seen:
                continue
            seen.add(href)
            block = m.group(0)
            mr = _RE_REMARK.search(block)
            remarks = self._clean(mr.group(1)) if mr else ""
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(name)[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
                "vod_subtitle": "",
            })
        if videos:
            return videos

        # 兜底：封面属性缺失时按 href 提取，片名/封面留空由详情补
        for href in _RE_CARD_FALLBACK.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": href.split("/")[-1].split(".")[0],
                "vod_pic": self.default_pic,
                "vod_remarks": "",
                "vod_subtitle": "",
            })
        return videos

    def _page_count(self, html, videos, page):
        if not html:
            return 1
        # 优先分页块内真实尾页页码（站点“尾页”按钮带真实总页）
        pages = [int(x) for x in _RE_TYPE_PAGE.findall(html)]
        pages += [int(x) for x in _RE_SHOW_PAGE.findall(html)]
        if pages:
            return max(pages)
        # 滑动窗口兜底：满页视为尚有下一页，不足一页即末页
        n = len(videos)
        if n == 0:
            return 1
        if n >= PAGE_LIMIT:
            return page + 1
        return page

    # ---------- 筛选 slug（实证 12 段：段0=tid 段1=地区 段3=类型 段6=页码 段11=年份）----------
    def _show_slug(self, tid, type_="", area="", year="", page=1):
        seg = [""] * 12
        seg[0] = tid
        seg[1] = area
        seg[3] = type_
        seg[6] = str(page) if page and page > 1 else ""
        seg[11] = year
        return "/show/%s.html" % "-".join(seg)

    # ---------- 首页 / 分类 / 搜索 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            return {"list": self._parse_cards(html)}
        except Exception as e:
            self.log("homeVideoContent FAIL:", repr(e)[:120])
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
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

            type_ = extend.get("type", "")
            area = extend.get("area", "")
            year = extend.get("year", "")

            if not any([type_, area, year]):
                # 主类导航路由；翻页对齐站点分页按钮
                if page > 1:
                    url = "%s/type/%s-%d.html" % (self.site_url, tid, page)
                else:
                    url = "%s/type/%s.html" % (self.site_url, tid)
            else:
                url = self.site_url + self._show_slug(
                    tid, type_=type_, area=area, year=year, page=page)

            self.log("category: %s" % url)
            html = self._fetch(url)
            videos = self._parse_cards(html)
            pagecount = self._page_count(html, videos, page)
            self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
            return {
                "list": videos, "page": page, "pagecount": pagecount,
                "limit": PAGE_LIMIT, "total": pagecount * PAGE_LIMIT,
            }
        except Exception as e:
            self.log("categoryContent FAIL:", repr(e)[:120])
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": PAGE_LIMIT, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            keyword = urllib.parse.quote(str(key or "").strip())
            url = "%s/search/-------------.html?wd=%s" % (self.site_url, keyword)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._parse_cards(html)
            return {
                "list": videos, "page": page,
                "pagecount": self._page_count(html, videos, page),
                "limit": PAGE_LIMIT, "total": len(videos),
            }
        except Exception as e:
            self.log("searchContent FAIL:", repr(e)[:120])
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": PAGE_LIMIT, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def _extract_json_obj(self, text, var):
        if not text:
            return ""
        i = text.find(var)
        if i < 0:
            return ""
        i = text.find("{", i)
        if i < 0:
            return ""
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return text[i:j + 1]
        return ""

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

            # 封面
            pic = self.default_pic
            mp = _RE_POSTER.search(html)
            if mp:
                pic = self._fix_url(mp.group(1))
            if not pic:
                mp = _RE_POSTER_BG.search(html)
                if mp:
                    pic = self._fix_url(mp.group(1))

            # 简介（全文 > 摘要 > meta description）
            content = ""
            mi = _RE_INTRO_FULL.search(html)
            if mi:
                content = self._clean(mi.group(1))
            if not content:
                mi = _RE_INTRO_SKETCH.search(html)
                if mi:
                    content = self._clean(mi.group(1))
            if not content:
                mi = _RE_META_DESC.search(html)
                if mi:
                    content = self._clean(mi.group(1))
            content = re.sub(r"^(剧情简介|简介)[：:]\s*", "", content)
            content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

            # 元信息（meta-item 顺序实证：类型 / 地区 / 年份 / 上映 / 集数 / 更新 / 主演 / 导演）
            metas = [self._clean(x) for x in _RE_META.findall(html)]
            classify, area, year, actor, director = "", "", "", "", ""
            remarks = ""
            for idx, meta in enumerate(metas):
                if meta.startswith("主演："):
                    actor = re.sub(r"\s*,\s*", ", ", self._clean(meta[3:]))
                elif meta.startswith("导演："):
                    director = self._clean(meta[3:])
                elif idx == 0:
                    classify = meta
                elif idx == 1:
                    area = meta
                elif idx == 2:
                    my = re.search(r"(\d{4})", meta)
                    year = my.group(1) if my else meta
                elif meta.startswith("共") and "集" in meta:
                    remarks = meta
                elif meta.startswith("更新"):
                    remarks = (remarks + " " + meta).strip() if remarks else meta

            # 评分
            score = ""
            ms = _RE_SCORE.search(html)
            if ms:
                score = ms.group(1)

            # ===== 线路与选集（面板 DOM 序；netdisk-panel 网盘外链面板排除）=====
            play_from, play_url = [], []
            for panel in _RE_PANEL.finditer(html):
                panel_cls, block = panel.group(1), panel.group(0)
                if "netdisk" in panel_cls.lower():
                    continue
                mn = _RE_PANEL_NAME.search(block)
                line_name = self._clean(mn.group(1)) if mn else ""
                eps = []
                seen_ep = set()
                for me in _RE_EP.finditer(block):
                    ep_href, ep_name = me.group(1), self._clean(me.group(2))
                    if ep_href in seen_ep:
                        continue
                    seen_ep.add(ep_href)
                    if not ep_name:
                        ep_name = "第%d集" % (len(eps) + 1)
                    eps.append((ep_name, ep_href))
                if not eps:
                    continue
                base, dup = line_name, 2
                while line_name in play_from:
                    line_name = "%s(%d)" % (base, dup)
                    dup += 1
                play_from.append(line_name)
                play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

            if not play_from:
                self.log("  未解析到选集")
                return {"list": []}

            if not remarks:
                remarks = "%d条线路" % len(play_from)

            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name[:100],
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_score": score,
                "vod_remarks": remarks,
                "vod_class": classify,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": "",
                "vod_subtitle": "",
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]}
        except Exception as e:
            self.log("detailContent FAIL:", repr(e)[:120])
            return {"list": []}

    # ---------- 播放 ----------
    def _parse_player_aaaa(self, html):
        if not html:
            return {}
        raw = self._extract_json_obj(html, "player_aaaa")
        if not raw:
            m = _RE_AA_VAR.search(html)
            raw = m.group(1) if m else ""
        if not raw:
            return {}
        try:
            return json.loads(raw.replace("\\/", "/").replace("\\u0026", "&"))
        except Exception:
            return {}

    def _resolve_master(self, url):
        if not url or not url.lower().split("?")[0].endswith(".m3u8"):
            return url
        try:
            rsp = self._request("GET", url, headers={"User-Agent": UA,
                                                     "Referer": self.site_url + "/"})
            body = self._body(rsp)
            if "#EXT-X-STREAM-INF" in body:
                lines = [l.strip() for l in body.splitlines()
                         if l.strip() and not l.strip().startswith("#")]
                if lines:
                    sub = urllib.parse.urljoin(url, lines[0])
                    self.log("  master -> 子流: %s" % sub[:120])
                    return sub
        except Exception as e:
            self.log("  master 解析失败,回退 master:", repr(e)[:80])
        return url

    def _resolve_encrypted(self, aa, referer=""):
        """加密线路：壳页 LIBVIO_CFG → POST parse.php 取真实直链。"""
        raw_url = aa.get("url", "")
        from_ = aa.get("from", "")
        vid = aa.get("id", "")
        nid = aa.get("nid", "")
        link_next = aa.get("link_next", "")

        proxy_path = _PROXY_PATH.get(from_, "/vid/%s.php" % from_)
        # url 原样拼接（浏览器实证：base64 含 / + =，编码后中转页返 Error）
        proxy = "%s%s?url=%s&next=%s&id=%s&nid=%s" % (
            self.site_url, proxy_path, raw_url,
            urllib.parse.quote(link_next or "", safe="/"), vid, nid)
        self.log("  中转壳: %s" % proxy[:120])
        shell = self._fetch(proxy, headers={"Referer": referer})
        if not shell:
            return ""

        raw_cfg = self._extract_json_obj(shell, "window.LIBVIO_CFG")
        if not raw_cfg:
            m = _RE_CFG_VAR.search(shell)
            raw_cfg = m.group(1) if m else ""
        if not raw_cfg:
            return ""
        try:
            cfg = json.loads(raw_cfg.replace("\\u0026", "&"))
        except Exception as e:
            self.log("  配置解析失败:", repr(e)[:80])
            return ""

        parse_url = self._fix_url(cfg.get("parseUrl", ""))
        sid = cfg.get("sid", "") or aa.get("sid", "")
        cfg_raw = cfg.get("rawUrl", "") or raw_url
        if not parse_url:
            return ""

        payload = json.dumps({"url": cfg_raw, "sid": sid})
        headers = {
            "Content-Type": "application/json",
            "X-LV-S": sid,
            "Referer": proxy,
        }
        rsp = self._request("POST", parse_url, headers=headers,
                            body=payload.encode("utf-8"), timeout=20)
        text = self._body(rsp)
        self.log("  parse.php 状态: %s 长度: %d" % (self._status(rsp), len(text)))
        try:
            data = json.loads(text)
            if data.get("fatal"):
                self.log("  parse fatal: %s" % data.get("msg", ""))
                return ""
            return data.get("url", "")
        except Exception:
            # 兜底：裸 m3u8/mp4 正则
            m = _RE_STREAM.search(text)
            return m.group(0) if m else ""

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        try:
            html = self._fetch(play_page, headers=header)
            aa = self._parse_player_aaaa(html)

            direct = aa.get("url", "") or ""
            if direct.startswith("http"):
                direct = self._resolve_master(direct)
                res = {"parse": 0, "playUrl": "", "url": direct, "header": header}
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链: %s" % direct[:160])
                return res

            # 加密线路走两步中转
            real = self._resolve_encrypted(aa, referer=play_page)
            if real.startswith("http"):
                real = self._resolve_master(real)
                res = {"parse": 0, "playUrl": "", "url": real, "header": header}
                self._play_cache[play_page] = (now, res)
                self.log("  => 中转直链: %s" % real[:160])
                return res
        except Exception as e:
            self.log("playerContent FAIL:", repr(e)[:120])

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    # ---------- 其余契约 ----------
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
            rsp = self._request("GET", url, headers={"User-Agent": UA,
                                                     "Referer": self.site_url + "/"})
            content = rsp.content if hasattr(rsp, "content") else b""
            ctype = getattr(rsp.headers, "get", lambda *a: "image/jpeg")(
                "Content-Type", "image/jpeg") if hasattr(rsp, "headers") else "image/jpeg"
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or str(url).startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
