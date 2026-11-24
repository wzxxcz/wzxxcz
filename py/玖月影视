# coding=utf-8
"""
www.rhwf.cn | TVBox Python 爬虫
站点: 玖月影视（MacCMS 模板 style/26，移动端直出 HTML）
线上实证：首页/六分类/筛选组合/详情(电影单集+连续剧多线路)/播放页/搜索结果落盘核对。

已实证路由（audit/rhwf 样本）:
  - 首页:     /
  - 主分类:   /pgctype/<tid>.html
  - 分类分页: /pgctype/<标识>-<page>.html（标识=主 tid 或类型 tid）
  - 筛选:     /pgcshow/<12 槽>.html
              槽0=主 tid/类型 tid；槽4=年份；槽5=字母；其余槽留空
  - 详情:     /pgc/<id>.html
  - 播放:     /pgcplay/<vid>-<sid>-<nid>.html
  - 搜索第1页: /search/<wd>-------------.html
  - 搜索分页:  /search/<wd>--<page>-----------.html

分类导航（线上实证顶部导航，仅 6 项；专题/资讯/明星/话题/地图不进一级分类栏）:
  1 电影 / 2 电视剧 / 3 综艺 / 4 动漫 / 9 短视频 / 51 即将上映

筛选维度（本站实证仅三组，无地区/语言/排序）:
  类型(槽0) / 年份(槽4, 2026~2016) / 字母(槽5, A~Z)
  电影1: 35喜剧片 36动作片 37爱情片 38科幻片 39恐怖片 40剧情片 41战争片
  电视剧2: 42国产剧 43港台剧 44日韩剧 45欧美剧
  综艺3: 46国内综艺 47海外综艺
  动漫4: 48国内动漫 49海外动漫
  短视频9: 57动画短片 58短剧
  即将上映51: 无类型选项

列表卡片（首页/分类/搜索同构，实证）:
  a[href=/pgc/<id>.html] > img[data-src=封面][alt=片名](src 空, onerror 占位 load1.png)
  + div.ys-name6(片名, CSS/HTML 可能截断, 以 img alt 全名为兜底)
  卡片无独立评分字段；副标(HD中字/集数)仅出现在详情线路选集。

详情字段（实证详情页）:
  - 片名 div.ys-name18；更新时间 div.year1(YYYY-MM-DD HH:MM:SS)
  - 导演: div.main-actors2 "导演：" + a；主演: 同组另一 div "主演：" + 多个 a(逗号拼接, 剥 more-actor)
  - 类型: div.ys-style8 "类型：" a；地区: 同组 "地区：" a
  - 简介: div.Synopsis-word > p；兜底 meta[name=description](正文以"剧情介绍："开头, 剥前缀)
  - 海报: a.poster5 > img[data-src]
  - 线路分组: div.list-name23 > div.name-left2 > div.name17(线路名, 按 DOM 顺序保序, 不按 sid 排序)
    紧跟 div.list-number1 > a[href=/pgcplay/<vid>-<sid>-<nid>.html] > div(集名)
    演员表/相关资讯/相关推荐/热门推荐/友情链接等块虽复用 list-name23/name17, 但后跟
    actors-list7 等其他容器, 无 list-number1, 须靠"标题后是否紧跟选集块"隔离, 避免误抓。

播放直链: 播放页内联 player_aaaa JSON(括号深度配对截取)；encrypt:0 取 url 直出 m3u8；
          master m3u8 取首条子流拆分兜底, 失败回退 parse:1 嗅探。

反爬守卫（easy_slide 滑块, 实证 2026-11-23）:
  - 未过守卫时所有文档/静态/接口一律回 59 字节壳: <script src="/_guard/html.js?js=easy_slide_html"></script>。
  - 闭环: GET / 落会话 → GET /_guard/easy_slide.png 一次性 Set-Cookie:
    guard(12 位密钥, key=guard[:8]) / guarddata(服务端持有, 前端不使用, 本地不可解) / guardword(缺口 Y)。
  - 浏览器拖到缺口后本地算 RC4(key=guard[:8]) 加密明文 "<x>x<y>" → base64 → 种 cookie guardret, reload 放行。
  - y=guardword 已知；缺口 x 须从拼图图片识别。服务端严格校验 x/y/RC4 明文, 容差约 ±8px。
  - 已实证无旁路: 所有路径/UA/静态资源/接口均回壳; guarddata 为服务端不透明句柄(RC4/AES/XOR
    多种密钥派生均无可读明文), 本地不可解; 响应头/PNG chunk 不下发坐标。
  - 图像识别分级(均为尽力而为, 不保证通过): 环境有 cv2/numpy 走 piece 形状掩码 + 暗遮罩评分;
    否则纯标准库(zlib 解码调色板 PNG + 形状掩码 + 暗/低饱和评分)兜底。壳子 chaquo 构建期
    requirements 仅 lxml/ujson/pyquery/requests/cachetools/pycryptodome/beautifulsoup4,
    无 PIL/numpy/cv2, 且 getDependence 只能拉 .py 模块、运行时无法补二进制图像库; 纯标准库在
    自然风景拼图(低纹理天空/海面、乌云/山体暗区干扰)上达不到 ±8px 稳定精度。遇壳自动重新取图重试。
  - 壳子端稳定过盾的必要条件: 构建期 requirements.txt 加入 Pillow 并重新打包 APK, 由脚本图像路径识别。
"""
import re
import sys
import json
import time
import base64
import socket
import struct
import zlib
import urllib.parse

sys.path.append('..')

# 云端出口 IPv6 不通/国内 IPv6 不稳：强制 IPv4 解析（壳子本地网络正常时不影响）
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        res = _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        v4 = [x for x in res if x[0] == socket.AF_INET]
        return v4 or res
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

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
                print("[rhwf]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.rhwf.cn"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航，线上实证）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "9",  "type_name": "短视频"},
    {"type_id": "51", "type_name": "即将上映"},
]

_YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
          "2018", "2017", "2016"]
_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
            "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

# 各频道类型选项（槽0=类型 tid, 线上实证）
_TYPE_MAP = {
    "1": [("35", "喜剧片"), ("36", "动作片"), ("37", "爱情片"), ("38", "科幻片"),
          ("39", "恐怖片"), ("40", "剧情片"), ("41", "战争片")],
    "2": [("42", "国产剧"), ("43", "港台剧"), ("44", "日韩剧"), ("45", "欧美剧")],
    "3": [("46", "国内综艺"), ("47", "海外综艺")],
    "4": [("48", "国内动漫"), ("49", "海外动漫")],
    "9": [("57", "动画短片"), ("58", "短剧")],
    "51": [],
}


def _opts(values):
    items = []
    for it in values:
        if isinstance(it, (tuple, list)):
            v, n = it[0], it[1]
        else:
            v = n = it
        items.append({"n": n, "v": v})
    return [{"n": "全部", "v": ""}] + items


def _build_filters(tid):
    dims = []
    types = _TYPE_MAP.get(tid, [])
    if types:
        dims.append({"key": "class", "name": "类型", "value": _opts(types)})
    dims.append({"key": "year", "name": "年份", "value": _opts(_YEARS)})
    dims.append({"key": "letter", "name": "字母", "value": _opts(_LETTERS)})
    return dims


FILTERS = {c["type_id"]: _build_filters(c["type_id"]) for c in CLASSES}

# ===================== 正则 =====================
_RE_HREF = re.compile(r'href="(/pgc/\d+\.html)"', re.I)
_RE_IMG = re.compile(r'<img[^>]*>', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_DSRC = re.compile(r'data-src="([^"]*)"', re.I)
_RE_SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
_RE_NAME6 = re.compile(r'<div[^>]*class="ys-name6"[^>]*>([\s\S]*?)</div>', re.I)

_RE_H1 = re.compile(r'<div[^>]*class="ys-name18"[^>]*>([\s\S]*?)</div>', re.I)
_RE_YEAR1 = re.compile(r'<div[^>]*class="year1"[^>]*>([\s\S]*?)</div>', re.I)
_RE_ACTOR = re.compile(r'<div[^>]*class="main-actors2"[^>]*>([\s\S]*?)</div>', re.I)
_RE_STYLE = re.compile(r'<div[^>]*class="ys-style8"[^>]*>([\s\S]*?)</div>', re.I)
_RE_A = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SPAN = re.compile(r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_MORE = re.compile(r'<span[^>]*class="more-actor"[^>]*>[\s\S]*?</span>', re.I)
_RE_INTRO_P = re.compile(r'Synopsis-word[\s\S]*?<p[^>]*>([\s\S]*?)</p>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_POSTER = re.compile(r'<a[^>]*class="poster5"[^>]*>([\s\S]*?)</a>', re.I)

# 线路分组（标题块 + 紧跟选集块）
_RE_LINE_TITLE = re.compile(
    r'<div[^>]*class="list-name23"[^>]*>([\s\S]*?)</div>\s*</div>', re.I)
_RE_LINE_NAME = re.compile(r'<div[^>]*class="name17"[^>]*>([\s\S]*?)</div>', re.I)
_RE_EP_BLOCK = re.compile(r'<div[^>]*class="list-number1"[^>]*>([\s\S]*?)</div>', re.I)
_RE_EP = re.compile(r'href="(/pgcplay/[^"]+)"[^>]*>\s*<div[^>]*>([\s\S]*?)</div>', re.I)

_RE_SEARCH_PAGE = re.compile(r'/search/[^"]*?-(\d+)-+\.html', re.I)
_RE_TYPE_PAGE = re.compile(r'/pgctype/[^"]*-(\d+)\.html', re.I)


# ===================== 守卫：RC4 / PNG 解码 / 缺口定位 =====================
def _rc4(data, key):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + ord(key[i % len(key)])) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for b in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(b ^ S[(S[i] + S[j]) % 256])
    return bytes(out)


def _decode_png(data):
    """纯标准库解码调色板索引 PNG(非隔行, 8bit colortype 3) → (W,H,plte,trns,img)。"""
    off = 8
    idat = b""
    plte = []
    trns = set()
    W = H = 0
    while off < len(data):
        ln = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8].decode("latin1")
        ch = data[off + 8:off + 8 + ln]
        if typ == "IHDR":
            W, H, bd, ct, _, _, _ = struct.unpack(">IIBBBBB", ch)
        elif typ == "PLTE":
            plte = [tuple(ch[i:i + 3]) for i in range(0, len(ch), 3)]
        elif typ == "tRNS":
            trns = set(ch)
        elif typ == "IDAT":
            idat += ch
        elif typ == "IEND":
            break
        off += 12 + ln
    raw = zlib.decompress(idat)
    stride = W
    prev = [0] * stride
    img = []
    pos = 0
    for y in range(H):
        f = raw[pos]
        pos += 1
        row = list(raw[pos:pos + stride])
        pos += stride
        for x in range(stride):
            a = row[x]
            left = row[x - 1] if x >= 1 else 0
            up = prev[x]
            ul = prev[x - 1] if x >= 1 else 0
            if f == 1:
                row[x] = (a + left) & 255
            elif f == 2:
                row[x] = (a + up) & 255
            elif f == 3:
                row[x] = (a + ((left + up) >> 1)) & 255
            elif f == 4:
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else ul)
                row[x] = (a + pr) & 255
        img.append(row)
        prev = row
    return W, H, plte, trns, img


def _png_feat(plte, trns, img, x, y):
    i = img[y][x]
    if i in trns:
        return None
    r, g, b = plte[i]
    return ((r + g + b) / 3.0, max(r, g, b) - min(r, g, b))


def _gap_x_pure(data, gw, k_sat=0.6):
    """纯标准库兜底：piece 形状掩码约束下, 背景窄带内找暗/低饱和拼图块, 返回缺口 x。"""
    W, H, plte, trns, img = _decode_png(data)
    xs = [x for y in range(H) for x in range(345, W) if img[y][x] not in trns]
    ys = [y for y in range(H) for x in range(345, W) if img[y][x] not in trns]
    if not xs:
        return 0
    px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
    mask = [(y - py0, x - px0) for y in range(py0, py1 + 1)
            for x in range(px0, px1 + 1) if img[y][x] not in trns]
    tw = px1 - px0 + 1
    BG = [[_png_feat(plte, trns, img, x, y) for x in range(340)] for y in range(H)]
    y0 = max(0, gw)
    best = (1e18, 0)
    for x in range(0, max(1, 340 - tw)):
        lum, sat, n = 0.0, 0.0, 0
        for dy, dx in mask:
            by, bx = y0 + dy, x + dx
            if by < H and bx < 340 and BG[by][bx]:
                lum += BG[by][bx][0]
                sat += BG[by][bx][1]
                n += 1
        if n == 0:
            continue
        score = lum / n + k_sat * sat / n
        if score < best[0]:
            best = (score, x)
    return best[1]


def _gap_x_cv2(data, gw):
    """运行环境有 cv2/numpy 时: 提取右侧 piece 形状掩码, 在左半背景滑窗找
    遮罩压暗最明显的位置(内圈亮度 - 外圈环带亮度 最小)。不可用返回 None。
    注意: 自然风景图上暗树林/草地会干扰, 识别为尽力而为, 不保证稳定通过。"""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    try:
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.shape[2] == 4:
            b, g, bl, al = cv2.split(img)
            bgra = cv2.merge([b, g, bl])
        else:
            bgra = img[:, :, :3]
            al = np.full(img.shape[:2], 255, np.uint8)
        gray = cv2.cvtColor(bgra, cv2.COLOR_BGR2GRAY).astype(np.float32)
        pm = al[:, 340:] > 20
        ys, xs = np.where(pm)
        if len(xs) == 0:
            return None
        px0, px1, py0, py1 = xs.min(), xs.max(), ys.min(), ys.max()
        mask = pm[py0:py1 + 1, px0:px1 + 1].astype(np.uint8)
        h, w = mask.shape
        left = gray[:, :340]
        H, W = left.shape
        best = (1e18, 0)
        for y in range(0, H - h):
            for x in range(0, W - w):
                win = left[y:y + h, x:x + w]
                inner = win[mask > 0]
                if inner.size < 20:
                    continue
                ring = []
                for yy in range(max(0, y - 2), min(H, y + h + 2)):
                    for xx in range(max(0, x - 2), min(W, x + w + 2)):
                        if not (y <= yy < y + h and x <= xx < x + w):
                            ring.append(left[yy, xx])
                ring = np.array(ring)
                score = inner.mean() - ring.mean()
                if score < best[0]:
                    best = (score, x)
        return best[1]
    except Exception:
        return None


class Spider(Spider):

    def getName(self):
        return "www.rhwf.cn"

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
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        # 守卫会话：自建 session 保留 guard/guardret Cookie；基类 fetch 不持 jar, 双保险写请求头
        self._guard_session = None
        self._guard_cookie = ""
        self._guard_ok = False

    # ---------------- 守卫会话 ----------------
    def _guard_sess(self):
        if self._guard_session is None:
            try:
                import requests as rq
                sess = rq.Session()
                sess.verify = False
                adapter = rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                sess.mount('https://', adapter)
                sess.mount('http://', adapter)
            except Exception:
                sess = None
            self._guard_session = sess
        return self._guard_session

    @staticmethod
    def _is_shell(text, status=200):
        if not text or len(text) < 80:
            return True
        try:
            if status and int(status) != 200:
                return True
        except Exception:
            pass
        return "_guard/html.js" in text

    def _solve_guard(self):
        """解滑块守卫：取拼图→识别缺口 x→RC4 种 guardret；成功返回 True。"""
        sess = self._guard_sess()
        h = dict(self.headers)
        try:
            # 1. 首访落会话 Cookie
            if sess is not None:
                sess.get(self.site_url + "/", headers=h, timeout=(10, 20))
                rp = sess.get(self.site_url + "/_guard/easy_slide.png?t=%d" % int(time.time() * 1000),
                              headers=dict(h, Referer=self.site_url + "/"), timeout=(10, 20))
                body = rp.content
                ck = sess.cookies.get_dict()
            else:
                r0 = self.fetch(self.site_url + "/", headers=h, timeout=(10, 20))
                rp = self.fetch(self.site_url + "/_guard/easy_slide.png?t=%d" % int(time.time() * 1000),
                                headers=dict(h, Referer=self.site_url + "/"), timeout=(10, 20))
                body = rp.content
                ck = {}
                for c in getattr(rp, "cookies", []):
                    ck[c.name] = c.value
            guard = ck.get("guard", "")
            guardword = ck.get("guardword", "")
            if not guard or not guardword:
                self.log("守卫缺 guard/guardword")
                return False
            gw = int(guardword)

            gx = _gap_x_cv2(body, gw)
            if gx is None:
                gx = _gap_x_pure(body, gw)
            gx = int(round(gx))
            gy = gw

            secret = guard[:8]
            plain = ("%dx%d" % (gx, gy)).encode("utf-8")
            guardret = base64.b64encode(_rc4(plain, secret)).decode("utf-8")
            ck["guardret"] = guardret

            if sess is not None:
                sess.cookies.set("guardret", guardret, domain="www.rhwf.cn", path="/")
                sess.cookies.set("guard", guard, domain="www.rhwf.cn", path="/")
                sess.cookies.set("guardword", guardword, domain="www.rhwf.cn", path="/")
            self._guard_cookie = "; ".join("%s=%s" % (k, v) for k, v in ck.items())
            self.headers["Cookie"] = self._guard_cookie

            # 验证一次
            if sess is not None:
                rv = sess.get(self.site_url + "/", headers=dict(h, Referer=self.site_url + "/"),
                              timeout=(10, 20))
                ok = not self._is_shell(rv.text, getattr(rv, "status_code", 200))
            else:
                rv = self.fetch(self.site_url + "/", headers=dict(h, Referer=self.site_url + "/"),
                                timeout=(10, 20))
                ok = not self._is_shell(rv.text)
            self._guard_ok = ok
            self.log("守卫求解 gx=%d gw=%d 放行=%s" % (gx, gy, ok))
            return ok
        except Exception as e:
            self.log("守卫求解异常", e)
            self._guard_ok = False
            return False

    def _http_get(self, url, headers=None, timeout=15):
        """本站 GET：优先守卫 session 复用 Cookie；遇壳重解后重放一次。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._guard_sess()
        rsp = None
        try:
            if sess is not None:
                rsp = sess.get(url, headers=h, timeout=timeout)
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("GET 异常", url, e)
            rsp = None
        text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
        status = getattr(rsp, "status_code", 200) if rsp is not None else 0

        if self._is_shell(text, status):
            self.log("遇守卫壳, 重新求解")
            if self._solve_guard():
                h["Cookie"] = self._guard_cookie
                try:
                    if sess is not None:
                        rsp = sess.get(url, headers=h, timeout=timeout)
                    else:
                        rsp = self.fetch(url, headers=h, timeout=timeout)
                    text = rsp.text if hasattr(rsp, "text") else ""
                    status = getattr(rsp, "status_code", 200)
                except Exception as e:
                    self.log("重放异常", e)
                    text, status = "", 0
        return rsp

    def _fetch(self, url, headers=None, tries=3):
        last = ""
        for _ in range(tries):
            try:
                rsp = self._http_get(url, headers=headers, timeout=(10, 30))
                status = getattr(rsp, "status_code", 200) if rsp is not None else 0
                text = rsp.text if rsp is not None and hasattr(rsp, "text") else ""
                if not self._is_upstream_error(text, status):
                    return text
                last = text
            except Exception as e:
                self.log("fetch FAIL", url, e)
                last = ""
            time.sleep(1.2)
        return last

    @staticmethod
    def _is_upstream_error(text, status=200):
        if not text or len(text) < 200:
            return True
        try:
            if status and int(status) != 200:
                return True
        except Exception:
            pass
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "error code", "web server is down"))

    # ---------------- 基础工具 ----------------
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
        s = _RE_MORE.sub("", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    @staticmethod
    def _is_placeholder_pic(pic):
        if not pic:
            return True
        low = pic.lower()
        return any(k in low for k in ("load1.png", "load.png", "blank", "logo",
                                      "placeholder", "default", "loading"))

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for block in re.findall(r'<a[^>]*href="/pgc/\d+\.html"[\s\S]*?</a>', html):
            mh = _RE_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            seen.add(href)

            # 片名：img alt 优先（全名），div.ys-name6 文本兜底
            name = ""
            mi = _RE_IMG.search(block)
            if mi:
                ma = _RE_ALT.search(mi.group(0))
                if ma:
                    name = self._clean(ma.group(1))
            if not name:
                mt = _RE_NAME6.search(block)
                if mt:
                    name = self._clean(mt.group(1))
            if not name:
                continue

            pic = ""
            if mi:
                md = _RE_DSRC.search(mi.group(0))
                if md:
                    pic = md.group(1)
                if not pic:
                    ms = _RE_SRC.search(mi.group(0))
                    if ms:
                        pic = ms.group(1)
            if self._is_placeholder_pic(pic):
                pic = ""

            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
                "vod_score": "",
            })
        return videos

    # ---------------- 列表 / 搜索 URL ----------------
    def _list_url(self, tid, extend, page=1):
        extend = extend or {}
        def _val(k):
            v = (extend.get(k) or "").strip()
            return "" if v in ("全部", "none") else v
        cls = _val("class")
        year = _val("year")
        letter = _val("letter")
        page = int(page) if page else 1
        slot0 = cls or tid
        if not any([cls, year, letter]) and page <= 1:
            return "%s/pgctype/%s.html" % (self.site_url, tid)
        if any([cls, year, letter]):
            seg = [slot0, "", "", "", year, letter, "", "", "", "", "", ""]
            seg = "-".join(urllib.parse.quote(x) if not x.isascii() else x for x in seg)
            return "%s/pgcshow/%s.html" % (self.site_url, seg)
        return "%s/pgctype/%s-%d.html" % (self.site_url, slot0, page)

    def _page_count(self, html, page):
        if not html:
            return 1
        pages = [int(x) for x in _RE_TYPE_PAGE.findall(html)]
        pages += [int(x) for x in _RE_SEARCH_PAGE.findall(html)]
        return max(pages) if pages else max(1, page)

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        url = self._list_url(tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._parse_cards(html)
        pagecount = self._page_count(html, page)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key or "").strip())
        if page <= 1:
            url = "%s/search/%s-------------.html" % (self.site_url, kw)
        else:
            url = "%s/search/%s--%d-----------.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html, page)
        self.log("  搜索: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段 ----------------
    def _info_field(self, html, label):
        """在 main-actors2 / ys-style8 块中提取指定标签后的链接文本(逗号拼接)。"""
        for blk in list(_RE_ACTOR.finditer(html)) + list(_RE_STYLE.finditer(html)):
            seg = blk.group(1)
            if ("%s：" % label) not in seg and ("%s:" % label) not in seg:
                continue
            after = re.split(r'%s[：:]' % re.escape(label), seg, 1)[-1]
            links = [self._clean(a) for a in _RE_A.findall(after)]
            links = [x for x in links if x]
            if links:
                return ",".join(links)
            sp = _RE_SPAN.search(after)
            if sp:
                return self._clean(sp.group(1))
            return self._clean(after)
        return ""

    def _parse_lines(self, html):
        """线路分组保 DOM 顺序：name17 标题就近配对其后的 list-number1 选集块；
        演员表/资讯/推荐等复用 name17 但无选集块, 自然不落盘。"""
        html = re.sub(r"<style[\s\S]*?</style>", "", html)
        html = re.sub(r"<script[\s\S]*?</script>", "", html)

        tokens = []
        for m in _RE_LINE_NAME.finditer(html):
            tokens.append((m.start(), "title", self._clean(m.group(1))))
        for m in _RE_EP.finditer(html):
            tokens.append((m.start(), "ep", (m.group(1), self._clean(m.group(2)))))
        tokens.sort(key=lambda t: t[0])

        play_from, play_url = [], []
        cur_line = None
        cur_eps = []
        for _, kind, payload in tokens:
            if kind == "title":
                if cur_line and cur_eps:
                    play_from.append(cur_line)
                    play_url.append("#".join("%s$%s" % (n, h) for n, h in cur_eps))
                cur_line, cur_eps = payload, []
            else:
                if cur_line is None:
                    continue
                href, ep_name = payload
                if not ep_name:
                    ep_name = "第%02d集" % (len(cur_eps) + 1)
                cur_eps.append((ep_name, href))
        if cur_line and cur_eps:
            play_from.append(cur_line)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in cur_eps))
        return play_from, play_url

    def detailContent(self, ids):
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
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报
        pic = ""
        mp = _RE_POSTER.search(html)
        if mp:
            mi = _RE_DSRC.search(mp.group(1)) or _RE_SRC.search(mp.group(1))
            if mi:
                pic = mi.group(1)
        if self._is_placeholder_pic(pic):
            pic = ""
        pic = self._fix_url(pic) or self.default_pic

        # 简介：Synopsis-word>p 优先，meta description 兜底，剥“剧情介绍：”前缀
        content = ""
        mf = _RE_INTRO_P.search(html)
        if mf:
            content = self._clean(mf.group(1))
        if not content:
            mm = _RE_META_DESC.search(html)
            if mm:
                content = self._clean(mm.group(1))
        content = re.sub(r"^(?:影片介绍|简介|剧情介绍)\s*[:：]?\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        actor = self._info_field(html, "主演")
        director = self._info_field(html, "导演")
        classify = self._info_field(html, "类型")
        area = self._info_field(html, "地区")

        # 更新时间（副标兜底）
        remarks = ""
        my = _RE_YEAR1.search(html)
        if my:
            upd = self._clean(my.group(1))
            if upd:
                remarks = "更新：" + upd

        # 线路与选集（保 DOM 顺序）
        play_from, play_url = self._parse_lines(html)
        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": area,
            "vod_year": "",
            "vod_classify": classify,
            "type_name": classify,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        html = self._fetch(play_page, headers=header)
        stream = self._extract_stream(html)

        if stream:
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        return res

    @staticmethod
    def _player_json(html):
        """括号深度配对精确截取 player_aaaa JSON（正确处理嵌套对象）。"""
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
                if str(aa.get("encrypt", "0")) not in ("0", ""):
                    return ""
                if aa.get("url"):
                    return aa["url"].replace("\\/", "/")
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    return m2.group(1).replace("\\/", "/")
        m2 = re.search(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', html, re.I)
        return m2.group(0) if m2 else ""

    def _resolve_sub_stream(self, url, header):
        """master 多码率：取首条子 m3u8 并 urljoin；已是含分片媒体列表/mp4 原样返回。"""
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
                self.log("  master 拉取重试后失败: %s" % err)
                return url
            text = rm.text if hasattr(rm, "text") else (
                rm.content.decode("utf-8", "ignore") if hasattr(rm, "content") else "")
            if "#EXT-X-STREAM-INF" not in text:
                return url
            lines = [ln.strip().replace("\\/", "/") for ln in text.splitlines()]
            for i, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF"):
                    if i + 1 < len(lines):
                        sub = lines[i + 1].strip()
                        if sub and not sub.startswith("#"):
                            sub = urllib.parse.urljoin(url, sub)
                            rs, sub_err = _get(sub)
                            if rs is not None:
                                self.log("  master 解析子流 %s" % sub[:120])
                                return sub
                            self.log("  子流重试后失败: %s" % sub_err)
                            break
        except Exception as e:
            self.log("  子流解析回退: %s" % e)
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
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"})
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, rsp.content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._play_cache = {}

    def close(self):
        self.destroy()

