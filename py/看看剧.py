# coding=utf-8
"""
看看剧 kkju.app (kankanju.app) | TVBox Python 爬虫

站点形态：Vue SPA，数据走后端 REST API（baseURL /api/app）。
安全校验：每个请求带 X-Device-ID / X-Platform / X-Timestamp / X-Nonce /
X-Signature / X-App-Version 头，签名为双层 HMAC-SHA256：
  1) deriveKey = HMAC_SHA256(salt, deviceId).hexdigest()
  2) signature = HMAC_SHA256(deriveKey(utf8), signingString).hexdigest()
  signingString = method \n path \n sortedQuery \n timestamp \n nonce \n appVersion \n [bodyHash]
  bodyHash = SHA256(body 文本).hexdigest()（仅非 GET）。

播放链路：详情 /videos/{id} 返回 playGroups[]（线路）→ playUrls[]（选集）；
真正直链由 POST /play/token {videoId, episode(0基), groupCode} 换取
data.playUrl（m3u8/mp4）、data.format、data.headers。
"""
import re
import sys
import json
import time
import hmac
import hashlib
import uuid
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
                print("[kkju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.kkju.app"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""
API_PREFIX = "/api/app"
APP_VERSION = "web"
# 差分/反编译实证的签名盐值（逐站固定，勿照搬其它站）
_SIGN_SALT = b"cms_device_salt_v1_2024cms_app_sign_key_v1_2024_secure"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_SIZE = 28

# 筛选维度：契约 key -> 站点参数名 / 展示名
_FILTER_DEFS = [
    ("class", "类型"),
    ("area",  "地区"),
    ("year",  "年份"),
    ("lang",  "语言"),
]


class Spider(Spider):

    # ---------- 基础 ----------
    def getName(self):
        return "看看剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
        }
        self.default_pic = DEFAULT_PIC
        # 匿名设备 ID：每次启动生成一个稳定值即可，服务端不做账号绑定
        self.device_id = "web-" + str(uuid.uuid4())
        self._play_cache = {}
        self._classes = None
        self._filters = None

    # ---------- 签名与请求 ----------
    def _sorted_query(self, params):
        if not params:
            return ""
        items = sorted((k, str(v)) for k, v in params.items() if v is not None)
        return "&".join("%s=%s" % (k, v) for k, v in items)

    def _sign_headers(self, method, path, raw_query, body_text):
        ts = str(int(time.time()))
        nonce = str(uuid.uuid4())
        derive = hmac.new(_SIGN_SALT, self.device_id.encode(),
                          hashlib.sha256).hexdigest()
        parts = [method, API_PREFIX + path, raw_query, ts, nonce, APP_VERSION]
        body_hash = ""
        if body_text is not None:
            body_hash = hashlib.sha256(body_text.encode()).hexdigest()
            parts.append(body_hash)
        msg = "\n".join(parts)
        sig = hmac.new(derive.encode(), msg.encode(),
                       hashlib.sha256).hexdigest()
        h = {
            "X-Device-ID": self.device_id,
            "X-Platform": "web",
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Signature": sig,
            "X-App-Version": APP_VERSION,
        }
        if body_hash:
            h["X-Body-Hash"] = body_hash
        return h

    def _api(self, method, path, params=None, payload=None):
        method = method.upper()
        params = params or {}
        raw_query = self._sorted_query(params)
        body_text = None
        if payload is not None:
            body_text = json.dumps(payload, separators=(",", ":"),
                                   ensure_ascii=False)
        sign = self._sign_headers(method, path, raw_query, body_text)
        headers = dict(self.headers)
        headers.update(sign)

        url = self.site_url + API_PREFIX + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        try:
            if method == "POST":
                rsp = self.fetch(url, headers=headers, method="POST",
                                 data=body_text.encode("utf-8"), timeout=20) \
                    if self._supports_method() else self._post(url, headers, body_text)
            else:
                rsp = self.fetch(url, headers=headers, timeout=20)
        except Exception as e:
            self.log("api FAIL", method, path, e)
            return None

        text = ""
        if hasattr(rsp, "text"):
            text = rsp.text or ""
        elif hasattr(rsp, "content"):
            text = rsp.content.decode("utf-8", "ignore")
        if not text:
            return None
        try:
            data = json.loads(text)
        except Exception:
            self.log("api 非 JSON", path, text[:120])
            return None
        if isinstance(data, dict) and data.get("code") not in (200, None):
            self.log("api code", data.get("code"), data.get("message"), path)
            return None
        return data.get("data") if isinstance(data, dict) else data

    def _supports_method(self):
        return False

    def _post(self, url, headers, body_text):
        # 兜底：基类 fetch 仅 GET 时，用 session 直接 POST
        sess = getattr(self, "_sess", None)
        if sess is None:
            return None
        h = dict(headers)
        h["Content-Type"] = "application/json"
        return sess.post(url, headers=h, data=body_text.encode("utf-8"),
                         timeout=20, verify=False)

    # ---------- 工具 ----------
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

    def _pic(self, item):
        pic = item.get("picSlide") or item.get("pic") or ""
        return pic or self.default_pic

    def _remarks(self, item):
        rk = self._clean(item.get("remarks") or "")
        if rk:
            return rk
        total = item.get("total") or 0
        serial = item.get("serial") or 0
        is_end = item.get("isEnd")
        if total:
            return ("全%d集" % total) if is_end else ("更新至第%d集" % serial)
        return ""

    def _card(self, item):
        vid = str(item.get("id") or "")
        return {
            "vod_id": vid,
            "vod_name": self._clean(item.get("name") or "")[:100] or vid,
            "vod_pic": self._pic(item),
            "vod_remarks": self._remarks(item),
            "vod_subtitle": self._clean(item.get("subTitle") or ""),
        }

    @staticmethod
    def _as_list(data):
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list") or data.get("records") or []
        return []

    # ---------- 分类 / 筛选 ----------
    def _load_classes(self):
        if self._classes is not None:
            return self._classes
        data = self._api("GET", "/categories")
        classes = []
        if isinstance(data, list):
            for c in data:
                if c.get("status") not in (1, None):
                    continue
                classes.append({
                    "type_id": str(c.get("id")),
                    "type_name": self._clean(c.get("name") or ""),
                })
        self._classes = classes
        return classes

    def _load_filters(self):
        if self._filters is not None:
            return self._filters
        filters = {}
        for c in self._load_classes():
            cid = c["type_id"]
            detail = self._api("GET", "/categories/" + cid)
            f = {}
            if isinstance(detail, dict):
                f = detail.get("filters") or {}
            dims = []
            for key, label in _FILTER_DEFS:
                opts = f.get(key) or []
                value = [{"n": "全部", "v": ""}]
                for opt in opts:
                    value.append({"n": self._clean(opt), "v": self._clean(opt)})
                dims.append({"key": key, "name": label, "value": value})
            filters[cid] = dims
        self._filters = filters
        return filters

    def homeContent(self, filter=False):
        return {"class": self._load_classes(), "filters": self._load_filters()}

    def homeVideoContent(self):
        data = self._api("GET", "/videos/recent", {"limit": PAGE_SIZE})
        videos = [self._card(x) for x in self._as_list(data)]
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        params = {"page": page, "page_size": PAGE_SIZE}
        for key, _label in _FILTER_DEFS:
            val = extend.get(key)
            if val not in ("", None, "全部"):
                params[key] = val
        data = self._api("GET", "/categories/%s/videos" % tid, params)
        items = self._as_list(data)
        videos = [self._card(x) for x in items]
        total = data.get("total", 0) if isinstance(data, dict) else 0
        pagecount = 1
        if total:
            pagecount = (int(total) + PAGE_SIZE - 1) // PAGE_SIZE
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": total or len(videos),
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = str(key or "").strip()
        params = {"keyword": keyword, "page": page, "page_size": PAGE_SIZE}
        data = self._api("GET", "/videos/search", params)
        videos = [self._card(x) for x in self._as_list(data)]
        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": PAGE_SIZE,
            "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        data = self._api("GET", "/videos/" + vod_id)
        if not data:
            return {"list": []}

        name = self._clean(data.get("name") or "") or vod_id
        pic = self._pic(data)
        sub_title = self._clean(data.get("subTitle") or "")
        actor = self._clean(data.get("actor") or "")
        director = self._clean(data.get("director") or "")
        score = self._clean(str(data.get("doubanScore") or ""))
        remarks = self._remarks(data)

        content = self._clean(data.get("content") or "")
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 线路 playGroups（按接口数组原序，不重排）
        play_from, play_url = [], []
        for group in data.get("playGroups") or []:
            code = str(group.get("code") or "")
            gname = self._clean(group.get("name") or code)
            eps = group.get("playUrls") or []
            if not eps:
                continue
            ep_strs = []
            for idx, ep in enumerate(eps):
                ep_name = self._clean(ep.get("name") or "")
                if not ep_name:
                    ep_name = "第%d集" % (idx + 1)
                # 内部标识：videoId@episodeIndex(0基)@groupCode
                token_id = "%s@%d@%s" % (vod_id, idx, code)
                ep_strs.append("%s$%s" % (ep_name, token_id))
            play_from.append(gname)
            play_url.append("#".join(ep_strs))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_subtitle": sub_title,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        token_id = str(id or "")
        now = int(time.time())
        if token_id in self._play_cache:
            ts, res = self._play_cache[token_id]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        res = {"parse": 1, "playUrl": "", "url": self.site_url + "/",
               "header": header}

        parts = token_id.split("@")
        if len(parts) != 3:
            self.log("播放标识异常:", token_id)
            self._play_cache[token_id] = (now, res)
            return res
        video_id, ep_idx, group_code = parts[0], parts[1], parts[2]
        try:
            episode = int(ep_idx)
        except Exception:
            episode = 0

        data = self._api("POST", "/play/token",
                         payload={"videoId": int(video_id),
                                  "episode": episode,
                                  "groupCode": group_code})
        if not data:
            self._play_cache[token_id] = (now, res)
            return res

        play_url = (data.get("playUrl") or "").strip()
        if not play_url:
            self._play_cache[token_id] = (now, res)
            return res

        # 线路自带的 Referer / UA（若有）
        extra = data.get("headers") or {}
        if isinstance(extra, dict):
            ref = extra.get("referer") or extra.get("Referer")
            if ref:
                header["Referer"] = ref
            uagent = extra.get("userAgent") or extra.get("User-Agent")
            if uagent:
                header["User-Agent"] = uagent

        # needParse / parseApi 表示还需二次解析，壳子侧嗅探兜底
        need_parse = bool(data.get("needParse"))
        parse_api = (data.get("parseApi") or "").strip()
        if need_parse or parse_api:
            res = {"parse": 1, "playUrl": "", "url": play_url, "header": header}
            self._play_cache[token_id] = (now, res)
            return res

        res = {"parse": 0, "playUrl": "", "url": play_url, "header": header}
        self._play_cache[token_id] = (now, res)
        self.log("直链:", play_url[:120])
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
            if url.startswith("/"):
                url = self.site_url + url
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
