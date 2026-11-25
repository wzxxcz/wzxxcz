# coding=utf-8
"""
FreeOK freeokk.lol | TVBox Python 爬虫

通道：MacCMS v10 采集 API 直取（HTML 页面只是外壳，间歇下发异版空壳，不作主通道）。
  接口: /api.php/provide/vod/
    ac=detail&pg=1            首页推荐（全字段，带封面/年份/地区/播放串）
    ac=detail&t=<tid>&pg=<n>  分类库；ac=detail&wd=<词>&pg=<n> 搜索；ac=detail&ids=<id> 详情
  筛选：采集接口仅开放 主分类 t、年代 year、搜索 wd、分页 pg；
        地区/语言/字母/类型子类/排序参数接口忽略，不暴露这些筛选项。
  分页：pagecount / total 直接取 API 真值，不做满页 +1 推算。

分类（API class 实测 1/2/3/4，无第 5 类）: 1 电影 / 2 剧集 / 3 综艺 / 4 动漫。

线路（实测跨多部片稳定，按采集代号配对，不按 sid 位置——sid 顺序每部片不同）:
  固定四条站点前端名:
    bfzym3u8 -> OK超清 | 1080zyk -> OK极速 | dyttm3u8 -> OK无广 | ffm3u8 -> OK高清
  官方外链源(qq/youku/qiyi/iqiyi/mgtv/bilibili…) -> OK自营；
    站点后缀字母(OK自营Q/K/A…)随片变且 API 不返回，统一显示 OK自营。
  线路顺序对齐站点 tab: OK自营 -> OK超清 -> OK极速 -> OK无广 -> OK高清，缺失跳过。
  播放串: vod_play_from 以 $$$ 分线路；vod_play_url 以 $$$ 分线路，线路内 # 分集，单集 集名$链接。

播放判定: .m3u8/.mp4/.flv 直链 -> parse:0（master 取首条子流）；
  官方平台页(v.qq/iqiyi/youku/mgtv/bilibili…) -> parse:1 交壳端嗅探；其余兜底 parse:1。
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
    v4 = [r for r in _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
          if r[0] == socket.AF_INET]
    # 过滤后为空（设备仅 IPv6 / 缺 A 记录）时回退原始结果，避免 getaddrinfo 彻底失败
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

LIMIT = 20                 # API 每页条数
SEG_BYTES = 1900           # 单条选集串 UTF-8 字节上限（壳端 2048B 截断，留余量）
API_CACHE_TTL = 300        # 列表/详情 API 缓存秒数
PLAY_CACHE_TTL = 600       # 播放结果缓存秒数

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

# 年代（API year 参数有效；站点实测 2014~2026）
_YEARS = [str(y) for y in range(2026, 2013, -1)]

# 采集代号 -> 站点前端线路名（跨多部片实测稳定）
LINE_NAME = {
    "bfzym3u8": "OK超清",
    "1080zyk": "OK极速",
    "dyttm3u8": "OK无广",
    "ffm3u8": "OK高清",
}
# 官方外链采集代号：站点统一叫 OK自营（后缀字母 API 不返回）
OFFICIAL_SID = {"qq", "qiyi", "iqiyi", "youku", "mgtv", "bilibili",
                "le", "sohu", "miguvideo"}
# 站点 tab 展示顺序优先级（小在前）
LINE_ORDER = {"OK自营": 0, "OK超清": 1, "OK极速": 2, "OK无广": 3, "OK高清": 4}
# 官方平台域名（parse:1 嗅探判定）
OFFICIAL_DOMAINS = ("v.qq.com", "qq.com", "iqiyi.com", "iqiyipic.com", "youku.com",
                    "mgtv.com", "bilibili.com", "le.com", "sohu.com", "miguvideo.com")

# 筛选组：仅透出接口支持的年代维度
FILTERS = {}
for c in CLASSES:
    FILTERS[c["type_id"]] = [
        {"key": "year", "name": "年代",
         "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in _YEARS]},
    ]


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

    def _http_get(self, url, headers=None, timeout=(6, 12)):
        """自建 Session 优先；异常回退基类 fetch（显式 verify=False，对齐基类签名）。"""
        h = dict(self.headers)
        if headers:
            h.update(headers)
        sess = self._session_get()
        try:
            if sess is not None:
                return sess.get(url, headers=h, timeout=timeout, verify=False)
            to = timeout[1] if isinstance(timeout, tuple) else timeout
            return self.fetch(url, headers=h, timeout=to, verify=False)
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

    def _api(self, **params):
        """采集 API：预热 -> 遍历全域 ×2 轮重试；仅成功响应缓存。返回 dict，空返 {}。"""
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

    # ---------------- 卡片映射 ----------------
    def _row(self, it):
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

    def _rows(self, data):
        out, seen = [], set()
        for it in (data.get("list") or []):
            i = str(it.get("vod_id") or "")
            if not i or i in seen:
                continue
            seen.add(i)
            out.append(self._row(it))
        return out

    # ---------------- 六契约接口 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def _api_retry(self, params):
        """首次取空（抖动/空壳）清会话复位预热后重拉一次，避免空结果锁缓存。"""
        data = self._api(**params)
        if not self._rows(data):
            self._session = None
            self._warmed = False
            data = self._api(**params)
        return data

    def homeVideoContent(self):
        try:
            data = self._api_retry({"ac": "detail", "pg": "1"})
            return {"list": self._rows(data)[:LIMIT]}
        except Exception as e:
            self.log("homeVideoContent 异常:", e)
            return {"list": []}

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
            year = str(extend.get("year") or "").strip()

            params = {"ac": "detail", "t": tid, "pg": str(page)}
            if year:
                params["year"] = year
            data = self._api_retry(params)
            lst = self._rows(data)[:LIMIT]
            self.log("category t=%s page=%d -> %d 条" % (tid, page, len(lst)))
            pc = int(data.get("pagecount") or 1) or 1
            total = int(data.get("total") or (pc * LIMIT))
            return {"list": lst, "page": page, "pagecount": pc,
                    "limit": LIMIT, "total": max(total, len(lst))}
        except Exception as e:
            self.log("categoryContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": LIMIT, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            kw = str(key or "").strip()
            if not kw:
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": LIMIT, "total": 0}
            try:
                page = max(1, int(pg))
            except Exception:
                page = 1
            data = self._api_retry({"ac": "detail", "wd": kw, "pg": str(page)})
            lst = self._rows(data)[:LIMIT]
            pc = int(data.get("pagecount") or 1) or 1
            total = int(data.get("total") or (pc * LIMIT))
            if str(quick) in ("1", "True", "true") and len(lst) > 12:
                lst = lst[:12]
            return {"list": lst, "page": page, "pagecount": pc,
                    "limit": LIMIT, "total": max(total, len(lst))}
        except Exception as e:
            self.log("searchContent 异常:", e)
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": LIMIT, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 / 线路 / 选集 ----------------
    @staticmethod
    def _seg(label, body):
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

    def _line_display(self, sid):
        if sid in LINE_NAME:
            return LINE_NAME[sid]
        if sid in OFFICIAL_SID:
            return "OK自营"
        return sid

    def detailContent(self, ids):
        try:
            raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            mid = re.search(r"(\d+)", str(raw) or "")
            if not mid:
                return {"list": []}
            vid = mid.group(1)
            data = self._api(ac="detail", ids=vid)
            lst = data.get("list") or []
            if not lst:
                return {"list": []}
            it = lst[0]

            froms = [x for x in str(it.get("vod_play_from") or "").split("$$$") if x]
            urls = [x for x in str(it.get("vod_play_url") or "").split("$$$") if x]
            if not froms or not urls:
                return {"list": []}

            # 逐代号分组：集名$链接；丢弃无 http 链接的集
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

            # 站名映射 + 对齐站点 tab 顺序：OK自营 -> OK超清 -> OK极速 -> OK无广 -> OK高清
            def _key(g):
                sid = g[0]
                if sid in LINE_NAME:
                    return LINE_ORDER[LINE_NAME[sid]]
                if sid in OFFICIAL_SID:
                    return LINE_ORDER["OK自营"]
                return 50
            groups.sort(key=_key)

            # 线路名重名去重编号；按字节切段，段名 (1)(2)，froms/urls 一一对应
            names, used = [], set()
            for sid, _eps in groups:
                nm = self._line_display(sid)
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

            # 简介：vod_content 优先 -> vod_blurb 兜底；前缀强制注入
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
        except Exception as e:
            self.log("detailContent 异常:", e)
            return {"list": []}

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
            if not pid.startswith("http"):
                pid = self._fix_url(pid)

            header = {"User-Agent": UA}
            low = pid.split("?")[0].lower()
            host = urllib.parse.urlparse(pid).hostname or ""

            if low.endswith(".m3u8") or low.endswith(".mp4") or low.endswith(".flv"):
                stream = self._resolve_sub_stream(pid, header)
                res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
                self._play_cache[pid] = (now, res)
                self.log("  => 直链: %s" % stream[:160])
                return res

            # 官方平台页 / 其余：交客户端嗅探；仅明确 http 外链才缓存
            if any(d in host for d in OFFICIAL_DOMAINS):
                ref = "https://%s/" % host
                res = {"parse": 1, "playUrl": "", "url": pid,
                       "header": {"User-Agent": UA, "Referer": ref}}
            else:
                res = {"parse": 1, "playUrl": "", "url": pid, "header": header}
            if pid.startswith("http"):
                self._play_cache[pid] = (now, res)
            return res
        except Exception as e:
            self.log("playerContent 异常:", e)
            pid = str(id or "")
            if pid.startswith("http"):
                url = pid
            else:
                url = self._fix_url(pid.split("#")[0].rsplit("$", 1)[-1])
            return {"parse": 1, "playUrl": "", "url": url,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def _resolve_sub_stream(self, url, header):
        """master 多码率 -> 第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
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
        # 退出源/重载时清内存会话与缓存，避免单例残留坏态；字段保留可下次重建
        try:
            self._session = None
            self._api_cache = {}
            self._play_cache = {}
        except Exception:
            pass

    def close(self):
        self.destroy()
