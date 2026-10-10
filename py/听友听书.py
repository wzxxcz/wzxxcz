import re, json, uuid, traceback

try:
    import requests as _rq
    _has_rq = True
except:
    _has_rq = False
    _rq = None

import urllib.request as _ur
import urllib.parse as _up


class Spider:
    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = "https://laopaoaappi.oobyvy.vip"
        if isinstance(extend, dict):
            self.host = str(extend.get("host", self.host) or self.host)
        self.base = self.host + "/api/h5/listening"
        try:
            self.session = str(uuid.uuid4())
        except:
            self.session = "00000000-0000-4000-8000-000000000000"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "accept": "application/json",
            "content-type": "application/json",
            "origin": "https://tingyou.fm",
            "referer": "https://tingyou.fm/",
            "x-listening-session": self.session,
            "x-listening-timezone": "Asia/Shanghai",
            "accept-encoding": "gzip, deflate, br",
            "connection": "keep-alive",
        }

    def getName(self):
        return "听友听书"

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(mp4|m3u8|flv|avi|mkv|ts)(\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def action(self, action):
        return None

    def _fetch(self, method, path, data=None):
        url = self.base + path
        if _has_rq:
            try:
                if method == "GET":
                    r = _rq.get(url, headers=self.headers, timeout=15)
                else:
                    r = _rq.post(url, headers=self.headers, json=data, timeout=15)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except:
                        return {}
            except:
                pass
        try:
            req_data = None
            hdrs = dict(self.headers)
            if method == "POST" and data is not None:
                req_data = json.dumps(data).encode("utf-8")
            req = _ur.Request(url, data=req_data, headers=hdrs, method=method)
            with _ur.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    try:
                        return json.loads(resp.read().decode("utf-8"))
                    except:
                        return {}
            return {}
        except:
            return {}

    def _get(self, path):
        return self._fetch("GET", path)

    def _post(self, path, data=None):
        return self._fetch("POST", path, data)

    def _norm_id(self, ids):
        try:
            if isinstance(ids, list) and len(ids) > 0:
                s = str(ids[0])
            else:
                s = str(ids or "")
            s = s.split("$$$")[0]
            return s.strip()
        except:
            return ""

    def homeContent(self, filter=None):
        classes = []
        filters = {}
        try:
            f = self._get("/filters")
            cats = f.get("categories", []) if isinstance(f, dict) else []
            for c in cats:
                try:
                    cid = str(c.get("id", ""))
                    cnm = str(c.get("name", ""))
                    if cid and cnm:
                        classes.append({"type_id": cid, "type_name": cnm})
                except:
                    continue
            sorts = f.get("sorts", []) if isinstance(f, dict) else []
            sv = []
            for s in sorts:
                try:
                    sv.append({"n": str(s.get("name", "")), "v": str(s.get("key", ""))})
                except:
                    continue
            for c in classes:
                filters[c["type_id"]] = [{"key": "sort", "name": "排序", "value": sv}] if sv else []
        except:
            pass
        if not classes:
            classes = [{"type_id": "2", "type_name": "有声小说"}]
        if not filters:
            filters = {}
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent(tid="2", pg=1)

    def categoryContent(self, tid=None, pg=1, filter=None, extend=None):
        try:
            pg = int(pg or 1)
        except:
            pg = 1
        if pg < 1:
            pg = 1
        section = "hot"
        try:
            if isinstance(extend, dict) and extend.get("sort"):
                section = str(extend.get("sort"))
            elif isinstance(extend, str) and extend:
                section = extend
        except:
            pass
        try:
            if isinstance(filter, dict) and filter.get("sort"):
                section = str(filter.get("sort"))
        except:
            pass
        # 把 tid 作为 category 参数传入
        path = "/rank?section={0}&page={1}".format(section, pg)
        if tid:
            path += "&category={0}".format(tid)
        d = self._get(path)
        if not isinstance(d, dict):
            d = {}
        items = d.get("items", []) or d.get("list", []) or []
        videos = []
        seen = set()
        for it in items:
            try:
                if not isinstance(it, dict):
                    continue
                vid = str(it.get("id", ""))
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append({
                    "vod_id": vid,
                    "vod_name": str(it.get("title", "")),
                    "vod_pic": str(it.get("cover_url", "")),
                    "vod_remarks": "{0}集".format(it.get("count", "")),
                })
            except:
                continue
        pagecount = pg + 1 if len(videos) >= 20 else pg
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 30, "total": 999999}

    def detailContent(self, ids):
        aid = self._norm_id(ids)
        if not aid:
            return {"list": []}
        d = self._get("/album/{0}".format(aid))
        if not isinstance(d, dict):
            d = {}
        vod = {
            "vod_id": str(d.get("id", aid)),
            "vod_name": str(d.get("title", "")),
            "vod_pic": str(d.get("cover_url", "")),
            "vod_actor": str(d.get("teller", "")),
            "vod_director": str(d.get("author", "")),
            "vod_content": str(d.get("synopsis", "") or d.get("description", "") or ""),
            "vod_remarks": "{0}集".format(d.get("count", "")),
        }
        ch = self._get("/chapters/{0}".format(aid))
        chapters = []
        try:
            if isinstance(ch, dict):
                chapters = ch.get("chapters", []) or []
        except:
            pass
        play_list = []
        for c in chapters:
            try:
                if not isinstance(c, dict):
                    continue
                idx = c.get("index", 0)
                title = str(c.get("title", "")).replace("#", "").replace("$", "")
                play_list.append("{0}${1}:{2}".format(title, aid, idx))
            except:
                continue
        if play_list:
            vod["vod_play_from"] = "听友"
            vod["vod_play_url"] = "#".join(play_list)
        else:
            vod["vod_play_from"] = ""
            vod["vod_play_url"] = ""
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg or 1)
        except:
            pg = 1
        if pg < 1:
            pg = 1
        key = str(key or "")
        d = self._post("/search", {"keyword": key, "page": pg})
        if not isinstance(d, dict):
            d = {}
        items = d.get("items", []) or d.get("list", []) or d.get("results", []) or []
        videos = []
        seen = set()
        for it in items:
            try:
                if not isinstance(it, dict):
                    continue
                vid = str(it.get("id", ""))
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append({
                    "vod_id": vid,
                    "vod_name": str(it.get("title", "")),
                    "vod_pic": str(it.get("cover_url", "")),
                    "vod_remarks": "{0}集".format(it.get("count", "")),
                })
            except:
                continue
        return {"list": videos, "page": pg}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ""
        try:
            raw = ids
            if isinstance(raw, list) and len(raw) > 0:
                raw = raw[0]
            raw = str(raw or "").split("$$$")[0].strip()
            if ":" in raw:
                aid, idx = raw.rsplit(":", 1)
                idx = int(idx)
            else:
                aid, idx = raw, 1
            d = self._post("/play", {"album_id": str(aid), "chapter_idx": idx})
            if isinstance(d, dict):
                url = str(d.get("play_url", "") or "")
        except:
            url = ""
        hdr = {"User-Agent": self.ua, "Referer": "https://tingyou.fm/"}
        if url and url.startswith("http"):
            return {"parse": 0, "url": url, "header": hdr}
        return {"parse": 0, "url": "", "header": hdr, "msg": "获取播放地址失败"}

    def localProxy(self, param):
        try:
            url = param.get("url", "") if isinstance(param, dict) else ""
            if not url:
                return [400, "text/plain", "", {}]
            req = _ur.Request(url, headers={"User-Agent": self.ua, "Referer": "https://tingyou.fm/"})
            with _ur.urlopen(req, timeout=15) as resp:
                data = resp.read()
                return [200, "application/octet-stream", data, {}]
        except:
            return [500, "text/plain", "", {}]
