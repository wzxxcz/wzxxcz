# -*- coding: utf-8 -*-
"""
电影侠 (dyxia / hhkan.tv) — 影视+ Python 源

样本：base.apk 3.5.0
SHA256：E4D22427E118B655EFCC8029E6AE97FCF1AB5D5A67B571B40FF89291F9A62E26

═══════════════════ 协议全貌（全部实测确认） ═══════════════════

【域名池】从 /v5/config/appInit.capi 下发（APK 内无硬编码）
    cache: vcache.srnffc.cn / vcache.ybsdkl.cn / vcache.shkjbd.com /
           vcache.mjrlin.cn / vcache.kvod14.com / 43.248.100.70:51020
    logic: vlogic.srnffc.cn / vlogic.ybsdkl.cn / ... / 43.248.100.70:51010
    game : sblogic.kvod14.com / 182.237.0.22:51310 / 103.147.224.35:51310
    sign : https://v-sign.obs.cn-south-1.myhuaweicloud.com/check.txt

【响应加密】AES-256-CBC + PKCS#7（appInit.capi 除外，它是明文结构）
    key = b"ayt5wy5afwmwrpb1" + b"9k9s3psx3dymyd0n"
    iv  = b"b3t069ijy7pirw0j"
    来源：libjake.so!jni_mOpApi @0x5b84 的三条 ldr q0/q1 指令

【请求签名】HMAC-SHA1（名字叫 md5，实际是 hmac，输出 20B）
    key = b"ksggsr4tp6difdo1c3im8fqd3g"        (26 字节)
    签名源 = "get|{path}|{query原文}|{TS}|{关键header}|"
    关键 header = appId / deviceCreatedAt / deviceId / st / userId（按此顺序）
    sign = hex(hmac_sha1(key, 签名源))          -> 40 字符
    header: TS = 毫秒时间戳, sign = 上述值
    来源：libjake.so!jni_signMd5 @0x58ec（key 由 3 段常量拼成 26 字节）

【两个坑】
    1. 必须带 Accept-Encoding: identity，否则密文被 gzip 无法解密
    2. 签名源里的 query 用「解码后的原文」，URL 里用编码形式

【错误码字典】
    40005 = Api Not Found      路径不存在
    40105 = sign error         签名错误
    40401 = 请重新初始化         路径存在但需要 init 会话
    200   = 成功

【接口清单】
    GET /v5/config/appInit.capi            初始化（域名池 + 分类配置），返回**扁平结构**
    GET /v6/vod/home.capi                  首页（21 个内容块 + banner）
    GET /vod/channel/list.capi             分类（channelId/sort/category/year/area/language/next）
    GET /v2/vod/detail.capi                详情（playSources 含 18 线路 + 每集带签名 m3u8）
    GET /v2/vod/episodes.capi              剧集
    GET /vod/rankingVods.capi              排行榜
    GET /v3/vod/specialTopics.capi         专题
    GET /vod/search/hotVods.capi           热搜榜

【播放链路】
    详情接口直接返回带 sign/timestamp 的完整 m3u8，直接用。
    注意 CDN 有 302 调度：142.248.97.160:21302 -> 208.69.102.160:11302
    必须走重定向后的节点，请求原节点会返回 3 字节 "OK\\n"（通配响应）。
"""
import base64
import hashlib
import hmac as hmaclib
import json
import random
import re
import socket
import string
import time
from urllib.parse import quote, unquote, urljoin, urlparse

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util.Padding import unpad

# ═══════════════ 常量（逆向所得） ═══════════════
_AES_KEY = b"ayt5wy5afwmwrpb1" + b"9k9s3psx3dymyd0n"
_AES_IV = b"b3t069ijy7pirw0j"
_MAC_KEY = b"ksggsr4tp6difdo1c3im8fqd3g"

_PKG = "com.dyxiaD13962260701.t005905"
_APP_ID = "dyxia"
_UA = "okhttp/4.12.0"

# 默认域名（appInit 会覆盖）
_DEFAULT_HOST = "https://vcache.ybsdkl.cn"
_LOGIC_HOST = "https://vlogic.ybsdkl.cn"

# 签名参与项（顺序敏感！）
_SIGN_KEYS = ["appId", "deviceCreatedAt", "deviceId", "st", "userId"]

# 初始化拿到的域名池（appInit 填充）
_HOSTS_CACHE = []
_HOSTS_LOGIC = []
_IMG_GROUPS = {}


class Spider(BaseSpider):
    def getName(self):
        return "电影侠"

    # ═══════════════ 初始化 ═══════════════
    def init(self, extend=""):
        self.sess = requests.Session()
        self.sess.trust_env = False
        self.sess.verify = False          # ★ CDN 证书五花八门，全局关校验
        self.timeout = 20
        self.host = _DEFAULT_HOST
        self.host_logic = _LOGIC_HOST

        # 设备指纹（服务端据此建账号；持久化以免每次变化）
        self.device_id = "".join(random.choice(string.hexdigits.lower())
                                 for _ in range(32))
        self.device_created_at = str(int(time.time() * 1000))
        self.user_id = ""
        self.user_token = ""
        self.user_created_at = ""

        # 分类配置（appInit 填充）
        self.vod_tabs = []
        self.channel_query = {}
        self.img_groups = {}
        self._home_cache = None
        self._home_ts = 0

        # extend 支持：https://域名  或  proxy=7897 或  纯端口号
        if extend:
            for p in re.split(r"[,，;\s]+", extend):
                p = p.strip()
                if not p:
                    continue
                if p.startswith("proxy="):
                    port = p.split("=", 1)[1].strip()
                    if port.isdigit():
                        self.sess.proxies = {
                            "http": "http://127.0.0.1:%s" % port,
                            "https": "http://127.0.0.1:%s" % port,
                        }
                        print("[dyx] 使用代理 127.0.0.1:%s" % port)
                elif p.isdigit():
                    self.sess.proxies = {
                        "http": "http://127.0.0.1:%s" % p,
                        "https": "http://127.0.0.1:%s" % p,
                    }
                    print("[dyx] 使用代理 127.0.0.1:%s" % p)
                elif p.startswith("http"):
                    self.host = p.rstrip("/")

        # 页面请求头（某些源需要）
        self.src_headers = {}
        self._init_app()

    def _headers(self, need_sign=False, ts=None):
        h = {
            "User-Agent": _UA,
            "Accept-Encoding": "identity",     # ★ 必须，否则密文无法解密
            "appId": _APP_ID,
            "os": "android",
            "appVersion": "3.5.0",
            "sdkVersion": "0.2.0",
            "package": _PKG,
            "channelId": "v1",
            "st": "1",
            "deviceId": self.device_id,
            "deviceCreatedAt": self.device_created_at,
            "deviceInfo": "android",
            "X-CDN": "1",
        }
        if self.user_id:
            h["X-USER"] = "1"
            h["userId"] = self.user_id
            h["userCreatedAt"] = self.user_created_at or "0"
            h["X-Token"] = self.user_token or ""
        return h

    def _sign(self, method, path, pairs, headers, ts):
        """HMAC-SHA1 签名。

        签名源 = method | path | query(原文) | TS | 关键header | ""
        注意：query 用原文（不 URL 编码）；多参数需排序。
        """
        items = ["%s=%s" % (k, v) for k, v in pairs]
        if len(items) > 1:
            items = sorted(items)
        qs = "&".join(items)
        hdr = "&".join("%s=%s" % (k, headers[k]) for k in _SIGN_KEYS if headers.get(k))
        src = "%s|%s|%s|%s|%s|" % (method.lower(), path, qs, ts, hdr)
        return hmaclib.new(_MAC_KEY, src.encode("utf-8"), hashlib.sha1).hexdigest()

    # ═══════════════ 底层请求 ═══════════════
    @staticmethod
    def _decrypt(raw):
        if not raw or len(raw) % 16 != 0:
            return None
        try:
            pt = unpad(AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV).decrypt(raw), 16)
        except Exception:
            return None
        try:
            return json.loads(pt.decode("utf-8"))
        except Exception:
            return None

    def _api(self, path, params=None, host=None, method="GET", raw_ok=False, body=None):
        """带签名的 .capi 请求。

        raw_ok=True 时返回解密后的完整 JSON（用于 appInit 这种扁平结构）。
        """
        pairs = []
        if params:
            for k, v in params.items():
                if v is not None and v != "":
                    pairs.append((k, str(v)))
        hdrs = self._headers()
        ts = str(int(time.time() * 1000))
        hdrs["TS"] = ts
        hdrs["sign"] = self._sign(method, path, pairs, hdrs, ts)

        # URL 用编码形式
        url = (host or self.host).rstrip("/") + path
        if pairs:
            url += "?" + "&".join("%s=%s" % (k, quote(v, safe="")) for k, v in pairs)
        try:
            if method == "POST":
                r = self.sess.post(url, headers=hdrs, data=body or "", timeout=self.timeout)
            else:
                r = self.sess.get(url, headers=hdrs, timeout=self.timeout)
        except Exception:
            return None
        j = self._decrypt(r.content)
        if not j:
            return None
        if raw_ok:
            return j
        if j.get("code") not in (200, "200"):
            return None
        return j.get("data")

    def _init_app(self):
        """拉初始化配置：域名池 + 分类定义。"""
        j = self._api("/v5/config/appInit.capi", raw_ok=True)
        if not j or "urls" not in j:
            return
        urls = j.get("urls") or {}
        caches = urls.get("cache") or []
        logics = urls.get("logic") or []
        if caches:
            self.host = caches[0]
            self._host_pool = caches
        if logics:
            self.host_logic = logics[0]
        # 图片 CDN 组
        for g in (j.get("groups") or []):
            gid = g.get("id")
            doms = [d.get("domain") for d in (g.get("url") or []) if d.get("domain")]
            if gid and doms:
                self.img_groups[gid] = doms
        # 分类
        self.vod_tabs = j.get("vodTabs") or []
        cq = {}
        for item in (j.get("channelListQuery") or []):
            cid = item.get("channelId")
            q = {}
            for it in (item.get("items") or []):
                q[it.get("query")] = [x.get("id") for x in (it.get("data") or [])]
            if cid is not None:
                cq[str(cid)] = q
        self.channel_query = cq
        # 源请求头
        for sh in (j.get("sourceHeader") or []):
            sid = sh.get("siteId")
            if sid:
                self.src_headers[sid] = sh.get("header") or {}
        # ★ 匿名注册：拿 userId + token（搜索等接口需要会话）
        self._anon_login()

    def _anon_login(self):
        """POST /user/anonymous -> {id, token, ...}"""
        try:
            j = self._api("/user/anonymous", method="POST", raw_ok=True, body="")
            d = (j or {}).get("data") or {}
            uid = d.get("id")
            tok = d.get("token")
            if uid and tok:
                self.user_id = str(uid)
                self.user_token = str(tok)
                self.user_created_at = str(d.get("createdAt") or self.device_created_at)
        except Exception:
            pass

    # ═══════════════ 分类 ═══════════════
    def _classes(self):
        """分类列表。type_id 为 "<type>:<channelId>"。

        跳过 type=home（影视+ 壳子自带「推荐」，避免重复）。
        """
        out = []
        for t in self.vod_tabs:
            name = t.get("text")
            cid = t.get("channelId")
            typ = (t.get("type") or "category").lower()
            if not name or cid is None:
                continue
            if typ == "home":          # ★ 壳子自带推荐，跳过
                continue
            out.append({"type_id": "%s:%s" % (typ, cid), "type_name": str(name)})
        if out:
            return out
        # 兜底
        for typ, cid, nm in (("category", 1, "电影"), ("category", 2, "剧集"),
                             ("category", 3, "动漫"), ("category", 4, "综艺纪录"),
                             ("category", 6, "短剧"), ("netflix", 1000, "Netflix")):
            out.append({"type_id": "%s:%d" % (typ, cid), "type_name": nm})
        return out

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        result["class"] = self._classes()
        # 过滤器（来自 channelListQuery）
        filters = {}
        for tid, q in self.channel_query.items():
            opts = []
            for key, ids in q.items():
                if not ids:
                    continue
                vals = [{"n": i if i else "全部", "v": i} for i in ids[:40] if i is not None]
                if vals:
                    opts.append({"key": key, "name": key, "value": vals})
            if opts:
                filters["category:%s" % tid] = opts
        result["filters"] = filters
        return result

    # ═══════════════ 首页 ═══════════════
    def _home(self):
        if self._home_cache and time.time() - self._home_ts < 300:
            return self._home_cache
        d = self._api("/v6/vod/home.capi")
        if d:
            self._home_cache = d
            self._home_ts = time.time()
        return self._home_cache or {}

    @staticmethod
    def _pick_base(group, groups):
        """选一个可用性最高的图片域名，结果缓存。

        appInit 的 groups 池里，域名分三类（实测）：
          1. .cn 域名 / 纯 IP   —— 直连可用，未挂代理也稳
          2. 纯 IP 节点         —— 无 DNS 依赖，抗 DNS 污染最强
          3. kvod7.com / dsty25-29.com —— DNS 解析到海外 IP，
             大陆网络下 gaierror（DNS 被拦），挂代理才可用

        所以策略：按服务端给的权重顺序逐个做 DNS 可达性过滤，取第一个
        能解析的；全挂时退到纯 IP 节点（无 DNS 依赖），再退到硬兜底。
        这样挂代理和不挂代理都能自适应。
        """
        hit = Spider._img_base_cache.get(group)
        if hit:
            return hit

        doms = groups.get(group) or []
        pool, seen = [], set()
        for d in doms:
            d = str(d).rstrip("/")
            if d and d not in seen:
                seen.add(d)
                pool.append(d)
        if not pool:
            pool = [Spider._IMG_FALLBACK.get(group, "https://vres.mppcdrr.cn/vod1")]

        alive, raw_ip = [], []
        for d in pool:
            try:
                host = urlparse(d).hostname
            except Exception:
                continue
            if not host:
                continue
            try:
                socket.getaddrinfo(host, None)
            except Exception:
                continue
            # 纯 IP 节点无 DNS 依赖，只在域名全网挂时兜底
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
                raw_ip.append(d)
            else:
                alive.append(d)

        chosen = (alive or raw_ip or pool)[0]
        Spider._img_base_cache[group] = chosen
        return chosen

    @staticmethod
    def _pic(path, group, groups):
        """拼接图片地址。

        groups 里的 domain 已含完整前缀（如 https://vres.mppcdrr.cn/vod1），
        所以只需 base + path；旧逻辑又叠一层 group 名会 404。
        imagePath 也可能是外部完整 URL（豆瓣等），原样返回。
        """
        if not path:
            return ""
        if path.startswith("http") or path.startswith("//"):
            return path
        base = Spider._pick_base(group, groups)
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    _img_base_cache = {}

    # 池子全废时的硬兜底（纯 IP，不走 DNS）
    _IMG_FALLBACK = {
        "vod1": "https://103.39.111.180:51050/vod1",
        "units": "https://103.39.111.180:51050/vod1",
        "sres": "https://103.39.111.180:51051/vod1",
    }

    @staticmethod
    def _label_text(v):
        """字段可能是 str / list[dict] / dict，统一成可读文本。"""
        if not v:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return str(v.get("name") or v.get("id") or "")
        if isinstance(v, list):
            return ",".join(str(x.get("name") or x) if isinstance(x, dict) else str(x)
                            for x in v)
        return str(v)

    def _vod(self, it):
        if not isinstance(it, dict):
            return None
        vid = it.get("id")
        title = it.get("title")
        if vid is None or not title:
            return None
        bits = []
        for k in ("topRightLabel", "topLeftLabel", "bottomLabel"):
            v = it.get(k)
            if isinstance(v, str) and v.strip():
                bits.append(v.strip())
        labels = it.get("labels")
        if isinstance(labels, list):
            for lb in labels[:2]:
                if isinstance(lb, dict) and lb.get("name"):
                    bits.append(str(lb["name"]))
        if it.get("playCount"):
            bits.append("%s次播放" % it["playCount"])
        if it.get("score"):
            bits.append("%s分" % it["score"])
        return {
            "vod_id": str(vid),
            "vod_name": str(title),
            "vod_pic": self._pic(it.get("imagePath") or "", it.get("imageGroup") or "vod1",
                                 self.img_groups),
            "vod_year": Spider._label_text(it.get("year")),
            "vod_remarks": " · ".join(bits[:3]),
        }

    def homeVideoContent(self):
        d = self._home()
        out, seen = [], set()
        for blk in (d.get("blocks") or []):
            for it in (blk.get("data") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    out.append(v)
        return {"list": out[:80]}

    # ═══════════════ 分类内容 ═══════════════
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        ex = extend if isinstance(extend, dict) else {}
        videos, seen = [], set()

        if tid.startswith("netflix:"):
            # ★ Netflix 走话题接口，展平各话题的视频
            d = self._api("/v2/vod/netflixNewWatch.capi")
            for blk in ((d or {}).get("items") or []):
                for it in (blk.get("data") or []):
                    v = self._vod(it)
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)
            pagecount = 1
        elif tid.startswith("ch:") or tid.startswith("category:"):
            cid = tid.split(":", 1)[1]
            params = {"channelId": cid, "sort": ex.get("sort") or "latest"}
            for k in ("category", "year", "area", "language"):
                if ex.get(k):
                    params[k] = ex[k]
            if page > 1:
                params["next"] = "page=%d" % page
            d = self._api("/vod/channel/list.capi", params)
            if d:
                # 过滤必须客户端确认（服务端有时忽略）
                want = {k: ex.get(k) for k in ("category", "year", "area", "language")
                        if ex.get(k)}
                for it in (d.get("items") or []):
                    v = self._vod(it)
                    if not v:
                        continue
                    if want:
                        labs = it.get("labels") or []
                        names = [str(x.get("name")) for x in labs if isinstance(x, dict)]
                        ok = True
                        for wk, wv in want.items():
                            if wk == "category" and wv and wv not in names:
                                ok = False
                            if wk == "year" and wv and str(it.get("year") or "") != str(wv):
                                ok = False
                        if not ok:
                            continue
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)
                nxt = d.get("next")
                pagecount = 9999 if nxt else page
            else:
                pagecount = page
        elif tid == "ranking":
            d = self._api("/vod/rankingVods.capi", {"rankingId": ex.get("rankingId") or "weekrank_dy"})
            for it in ((d or {}).get("items") or (d or {}).get("list") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    videos.append(v)
            pagecount = 1
        elif tid == "topic":
            d = self._api("/v3/vod/specialTopics.capi")
            for it in ((d or {}).get("items") or (d or {}).get("list") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    videos.append(v)
            pagecount = 1
        else:
            # 兜底：首页数据
            for blk in (self._home().get("blocks") or []):
                for it in (blk.get("data") or []):
                    v = self._vod(it)
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)
            pagecount = 1

        n = len(videos)
        return {
            "list": videos,
            "page": page,
            "pagecount": int(pagecount),
            "limit": n or 20,
            "total": int(n),
        }

    # ═══════════════ 详情 ═══════════════
    def detailContent(self, array):
        result = {"list": []}
        try:
            vid = array[0]
            if isinstance(vid, dict):
                vid = vid.get("vod_id") or vid.get("id")
            vid = str(vid)
            j = self._api("/v2/vod/detail.capi", {"vodId": vid})
            if not j or not j.get("id"):
                return result

            video = {
                "vod_id": vid,
                "vod_name": j.get("title") or "",
                "vod_pic": self._pic(j.get("imagePath") or "",
                                     j.get("imageGroup") or "vod1", self.img_groups),
                "type_name": j.get("channelName") or "",
                "vod_year": Spider._label_text(j.get("year")),
                "vod_area": Spider._label_text(j.get("area")),
                "vod_actor": Spider._label_text(j.get("actors")),
                "vod_director": Spider._label_text(j.get("directors")),
                "vod_remarks": j.get("scoreText") or (("%s分" % j["score"]) if j.get("score") else ""),
                "vod_content": (j.get("summary") or "").strip(),
            }

            froms, urls = [], []
            for src in (j.get("playSources") or []):
                eps = src.get("list") or []
                if not eps:
                    continue
                ep_strs = []
                for ep in eps:
                    token = "%s|%s|%s" % (vid, src.get("siteId") or "", ep.get("id") or "")
                    ep_strs.append("%s$%s" % (ep.get("title") or "正片", token))
                if ep_strs:
                    froms.append(src.get("name") or src.get("siteId") or "线路")
                    urls.append("#".join(ep_strs))
            if urls:
                video["vod_play_from"] = "$$$".join(froms)
                video["vod_play_url"] = "$$$".join(urls)
            result["list"] = [video]
        except Exception:
            pass
        return result

    # ═══════════════ 搜索 ═══════════════
    def searchContent(self, key, quick, pg="1"):
        """真实搜索接口 /vod/search/query（需匿名会话，_anon_login 已建立）。"""
        result = {"list": [], "page": 1}
        kw = (key or "").strip()
        if not kw:
            return result
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        params = {"channelId": "", "k": kw, "next": ""}
        if page > 1:
            params["next"] = "page=%d" % page
        d = self._api("/vod/search/query", params)
        if not d:
            # 会话失效则重新注册一次再试
            self._anon_login()
            d = self._api("/vod/search/query", params)
        if not d:
            return result
        for it in (d.get("items") or []):
            v = self._vod(it)
            if v:
                # 搜索结果标题带 <font> 高亮标签，清掉
                v["vod_name"] = re.sub(r"<[^>]+>", "", v["vod_name"]).strip()
                result["list"].append(v)
        result["page"] = page
        return result

    # ═══════════════ 日志（排查播放问题用） ═══════════════
    def _log(self, msg):
        try:
            import os
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dyx_cfg")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "play.log"), "a", encoding="utf-8") as f:
                f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
        except Exception:
            pass

    def _resolve_redirect(self, url, depth=0):
        """跟随 CDN 的 302 调度，返回最终节点 URL。

        调度前节点对 m3u8/ts 的请求会 302 到同参数的另一节点；
        分片必须落在最终节点上，否则返回 "OK\n"。
        """
        if not url or depth > 4:
            return url
        try:
            r = self.sess.get(url, headers={"User-Agent": _UA, "Range": "bytes=0-0"},
                              timeout=10, verify=False, allow_redirects=False)
            loc = r.headers.get("Location")
            if loc:
                self._log("302: %s -> %s" % (url.split("/")[2], loc.split("/")[2]))
                return self._resolve_redirect(loc, depth + 1)
        except Exception as e:
            self._log("302 probe fail: %s" % e)
        return url

    # ═══════════════ 播放 ═══════════════
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "url": "", "header": {"User-Agent": _UA}}
        try:
            parts = str(id).split("|")
            if len(parts) < 3:
                self._log("playerContent: id 格式不对 -> %s" % str(id)[:80])
                return result
            vod_id, site_id, ep_id = parts[0], parts[1], parts[2]
            # 重新取详情，拿新鲜签名（sign/timestamp 有时效）
            j = self._api("/v2/vod/detail.capi", {"vodId": vod_id})
            for src in ((j or {}).get("playSources") or []):
                if str(src.get("siteId")) != str(site_id):
                    continue
                for ep in (src.get("list") or []):
                    if str(ep.get("id")) != str(ep_id):
                        continue
                    pus = ep.get("playUrls") or []
                    if not pus:
                        continue
                    raw = pus[0].get("url") or ""
                    if not raw:
                        continue
                    # ★ 解析 302 调度，把最终节点地址交给播放器
                    final = self._resolve_redirect(raw)
                    self._log("playerContent: %s -> %s" % (vod_id, final.split("/")[2]))
                    # 有 getProxyUrl 时仍走代理（改写分片更稳），否则直连最终节点
                    wrapped = self._wrap_proxy(final, "type=m3u8")
                    result["url"] = wrapped or final
                    return result
            self._log("playerContent: 未匹配到剧集 %s" % str(id)[:80])
        except Exception as e:
            self._log("playerContent ERR: %s" % e)
        return result

    # ═══════════════ 代理（m3u8 改写） ═══════════════
    def _wrap_proxy(self, url, extra=""):
        if not url:
            return url
        getter = getattr(self, "getProxyUrl", None)
        if not callable(getter):
            return url
        try:
            base = getter() or ""
        except Exception:
            return url
        if not base:
            return url
        b64 = base64.b64encode(url.encode("utf-8")).decode("ascii")
        sep = "&" if "?" in base else "?"
        out = base + sep + "url=" + quote(b64)
        if extra:
            out += "&" + extra.lstrip("&")
        return out

    def _decode_proxy_param(self, param):
        if not param:
            return ""
        if isinstance(param, dict):
            s = param.get("url") or param.get("Url") or ""
        else:
            s = str(param)
        s = str(s).strip()
        if "url=" in s[:24]:
            s = s.split("url=", 1)[1].split("&", 1)[0]
        try:
            s = unquote(s)          # ★ 必须先 unquote 再 b64decode
        except Exception:
            pass
        if s.startswith("http"):
            return s
        for pad in (0, 1, 2, 3):
            try:
                d = base64.b64decode(s + "=" * pad, validate=False).decode("utf-8")
                if d.startswith("http"):
                    return d
            except Exception:
                pass
        return ""

    def _rewrite_m3u8(self, body, base_url):
        """改写 m3u8 内所有相对路径为代理 URL。

        base_url 必须是**已跟随 302 之后**的地址（由调用方传入 r.url），
        否则分片会落在调度前的节点上，返回 3 字节 "OK\n"。
        这里不再额外发请求探测，避免拖慢首次响应。
        """
        final_base = base_url
        out = []
        for line in body.splitlines():
            raw = line.rstrip("\r")
            s = raw.strip()
            if not s:
                out.append(raw)
                continue
            if s.startswith("#"):
                if 'URI="' in s:
                    def _rep(m):
                        ku = urljoin(final_base, m.group(1))
                        return 'URI="%s"' % (self._wrap_proxy(ku, "type=media") or ku)
                    s = re.sub(r'URI="([^"]+)"', _rep, s)
                out.append(s)
                continue
            u = s
            if u.startswith("//"):
                u = "https:" + u
            elif not u.lower().startswith("http"):
                u = urljoin(final_base, u)
            out.append(self._wrap_proxy(u, "type=media") or u)
        return "\n".join(out)

    def localProxy(self, param):
        url = self._decode_proxy_param(param)
        if not url:
            return [500, "text/plain", "bad param", ""]
        typ = ""
        if isinstance(param, dict):
            typ = str(param.get("type") or "").lower()
        hdr = {"User-Agent": _UA, "Accept": "*/*"}
        try:
            low = url.lower().split("?", 1)[0]
            r = self.sess.get(url, headers=hdr, timeout=self.timeout, verify=False,
                              allow_redirects=True)   # ★ 跟随 302 调度
            if r.status_code not in (200, 206):
                return [r.status_code, "text/plain", "upstream fail", ""]
            if typ == "m3u8" or low.endswith(".m3u8"):
                body = r.content.decode("utf-8", "ignore")
                if "#EXTM3U" in body:
                    body = self._rewrite_m3u8(body, r.url or url)
                return [200, "application/vnd.apple.mpegurl", body, ""]
            if low.endswith(".key"):
                return [200, "application/octet-stream", r.content, ""]
            return [200, "video/MP2T", r.content, ""]
        except Exception as e:
            return [500, "text/plain", "proxy error: %s" % e, ""]

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4)(\?|$)", url or "", re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.sess.close()
        except Exception:
            pass


# ═══════════════ 自测 ═══════════════
if __name__ == "__main__":
    import sys
    import urllib3
    urllib3.disable_warnings()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sp = Spider()
    sp.init("")
    print("=" * 66)
    print("host      :", sp.host)
    print("host_logic:", sp.host_logic)
    print("图片组    :", {k: v[:1] for k, v in list(sp.img_groups.items())[:4]})
    print("频道数    :", len(sp.vod_tabs))

    print("\n[2] homeContent")
    hc = sp.homeContent(True)
    print("    分类:", [c["type_name"] for c in hc["class"]][:12])
    print("    过滤器:", len(hc.get("filters") or {}), "个频道")

    print("\n[3] homeVideoContent")
    hv = sp.homeVideoContent()["list"]
    print("    条数:", len(hv))
    for v in hv[:4]:
        print(f"      {v['vod_id']:<8} {v['vod_name'][:22]:<24} {v['vod_remarks'][:18]}")

    print("\n[4] categoryContent 电影(ch:1)")
    cc = sp.categoryContent("ch:1", 1, False, {})
    print(f"    条数={len(cc['list'])} pagecount={cc['pagecount']}")
    for v in cc["list"][:3]:
        print(f"      {v['vod_id']:<8} {v['vod_name'][:24]}")

    print("\n[4b] 第2页")
    cc2 = sp.categoryContent("ch:1", 2, False, {})
    print(f"    条数={len(cc2['list'])} 首条={cc2['list'][0]['vod_name'] if cc2['list'] else '-'}")

    if not hv:
        sys.exit(0)

    vid = hv[0]["vod_id"]
    print(f"\n[5] detailContent vodId={vid}")
    dc = sp.detailContent([vid])
    v = (dc.get("list") or [{}])[0]
    print(f"    剧名: {v.get('vod_name')}  年份: {v.get('vod_year')}")
    froms = (v.get("vod_play_from") or "").split("$$$")
    print(f"    线路数: {len(froms)}  前3: {froms[:3]}")
    pu = v.get("vod_play_url") or ""
    if pu:
        first = pu.split("$$$")[0].split("#")[0]
        print(f"    首集: {first[:110]}")

    print(f"\n[6] playerContent")
    if pu:
        token = pu.split("$$$")[0].split("#")[0].split("$")[-1]
        pc = sp.playerContent("", token, None)
        u = pc.get("url") or ""
        print(f"    url: {u[:120]}")
        raw = sp._decode_proxy_param(u) or u
        r = sp.sess.get(raw, headers={"User-Agent": _UA}, timeout=25, verify=False,
                        allow_redirects=True)
        print(f"    -> {r.status_code} {len(r.content)}B "
              f"{'✓ #EXTM3U' if b'#EXTM3U' in r.content else '✗'}")
        if b"#EXTM3U" in r.content:
            ts = [l.strip() for l in r.text.splitlines()
                  if l.strip() and not l.strip().startswith("#")]
            print(f"    分片数: {len(ts)}  最终节点: {(r.url or '').split('/')[2]}")
            if ts:
                tu = urljoin(r.url or raw, ts[0])
                rr = sp.sess.get(tu, headers={"User-Agent": _UA, "Range": "bytes=0-8191"},
                                 timeout=25, verify=False, allow_redirects=True)
                ok = rr.content[:1] == b"\x47"
                print(f"    首分片: {rr.status_code} {len(rr.content)}B "
                      f"{'✓ MPEG-TS' if ok else '✗ ' + repr(rr.content[:20])}")

    print(f"\n[7] searchContent('兰香')")
    se = sp.searchContent("兰香", False, "1")
    print(f"    命中: {len(se['list'])}")
    for x in se["list"][:3]:
        print(f"      {x['vod_name']}")
