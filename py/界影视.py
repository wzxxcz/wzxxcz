# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/
# 站点 CDN 已换成 Nginx secure_link(auth_key=时间戳-签名-0-签名), 不再绑 IP。
# 关键: m3u8 里的 ts 分片是相对路径, 需要带上父 URL 的 auth_key query, 否则 401。
# 方案: 全清晰度直出 + 本地代理(重写分片时带上父 URL 的 query)。
from base.spider import Spider
import requests
import re
import json
import hashlib
import time
import uuid
from urllib.parse import quote, unquote, urlparse, parse_qsl
from concurrent.futures import ThreadPoolExecutor

FILTER_LABEL = {
    "filterStatus": "状态", "type": "类型", "class": "剧情",
    "area": "地区", "year": "年份", "lang": "语言",
}
FILTER_ORDER = ["filterStatus", "type", "class", "area", "year", "lang"]


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://yvyeigh.com"
        self.UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": self.UA})
        self.signkey = "cb808529bae6b6be45ecfab29a4889bc"
        self.device_id = str(uuid.uuid4())
        self._cache = {}
        self._filters_cache = None

    def getName(self):
        return "界影视"

    # ---------------- 基础 ----------------
    def _get(self, url, timeout=12):
        r = self.sess.get(url, timeout=timeout)
        r.encoding = "utf-8"
        return r.text

    def _flight(self, url, timeout=12):
        if url in self._cache:
            return self._cache[url]
        html = self._get(url, timeout=timeout)
        blob = ""
        parts = re.findall(
            r'self\.__next_f\.push\(\s*\[\s*1\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]\s*\)',
            html, re.S)
        if not parts:
            parts = re.findall(
                r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
        for p in parts:
            try:
                blob += json.loads('"' + p + '"')
            except Exception:
                blob += p
        self._cache[url] = (html, blob)
        return html, blob

    def _api(self, path, params):
        ts = str(int(time.time() * 1000))
        sp = {k: str(v) for k, v in params.items()}
        q = "&".join("%s=%s" % (k, sp[k]) for k in sorted(sp))
        h = "%s&key=%s&t=%s" % (q, self.signkey, ts)
        sign = hashlib.sha1(hashlib.md5(h.encode()).hexdigest().encode()).hexdigest()
        qs = "&".join("%s=%s" % (k, quote(sp[k], safe="")) for k in sp)
        url = self.host + "/mw-movie" + path + "?" + qs
        r = self.sess.get(url, headers={
            "sign": sign, "t": ts,
            "deviceId": self.device_id, "authorization": "",
        }, timeout=15)
        try:
            return r.json()
        except Exception:
            try:
                return json.loads(r.text)
            except Exception:
                return {"code": -1, "raw": r.text[:500]}

    @staticmethod
    def _jstr(o, key):
        m = re.search(r'"%s":"((?:[^"\\]|\\.)*)"' % key, o)
        if not m:
            return ""
        try:
            return json.loads('"' + m.group(1) + '"')
        except Exception:
            return m.group(1)

    def _parse_vods(self, blob):
        vods = []
        seen = set()
        for m in re.finditer(r'\{[^{}]*?"vodId":(\d+)[^{}]*?\}', blob):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            o = m.group(0)
            name = self._jstr(o, "vodName")
            if not name:
                continue
            vods.append({
                "vod_id": vid, "vod_name": name,
                "vod_pic": self._jstr(o, "vodPic"),
                "vod_remarks": self._jstr(o, "vodRemarks") or self._jstr(o, "vodVersion"),
                "vod_year": self._jstr(o, "vodYear"),
                "vod_area": self._jstr(o, "vodArea"),
            })
        return vods

    def _parse_filters(self, html, tid):
        flist = []
        seen_keys = set()
        rows = re.findall(r'<div class="filter-ul">(.*?)</div>', html, re.S)
        for r in rows:
            links = re.findall(r'href="(/vod/show/id/\d+[^"]*)"[^>]*>([^<]+)</a>', r)
            if len(links) < 2:
                continue
            key = ""
            for u, _n in links:
                km = re.search(r'/id/\d+/([A-Za-z]+)/', u)
                if km and km.group(1) in FILTER_LABEL:
                    key = km.group(1)
                    break
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            vals = [{"n": "全部", "v": ""}]
            have = set()
            for u, n in links:
                n = (n or "").strip()
                if not n or n == "全部":
                    continue
                vm = re.search(r'/id/\d+/%s/([^/"]+)' % key, u)
                v = unquote(vm.group(1)).strip() if vm else n
                if v and v not in have:
                    have.add(v)
                    vals.append({"n": n, "v": v})
            if len(vals) >= 2:
                flist.append({"key": key, "name": FILTER_LABEL[key], "value": vals})
        flist.sort(key=lambda x: FILTER_ORDER.index(x["key"]) if x["key"] in FILTER_ORDER else 99)
        if tid == "1":
            sorts = [{"n": "上映时间", "v": "1"}, {"n": "人气高低", "v": "3"}, {"n": "评分高低", "v": "4"}]
        else:
            sorts = [{"n": "最近更新", "v": "1"}, {"n": "添加时间", "v": "2"},
                     {"n": "人气高低", "v": "3"}, {"n": "评分高低", "v": "4"}]
        flist.append({"key": "sort", "name": "排序", "value": sorts})
        return flist

    def _build_one_filter(self, tid):
        url = "%s/vod/show/id/%s" % (self.host, tid)
        fhtml = ""
        for _try in range(2):
            try:
                if _try:
                    self._cache.pop(url, None)
                fhtml, _ = self._flight(url, timeout=8)
                if fhtml and "filter-ul" in fhtml:
                    break
            except Exception:
                fhtml = ""
        try:
            if fhtml:
                return self._parse_filters(fhtml, tid)
        except Exception:
            pass
        return []

    def homeContent(self, filter):
        try:
            html, blob = self._flight(self.host + "/")
        except Exception:
            html, blob = "", ""
        classes = []
        for m in re.finditer(r'<a[^>]*href="/vod/show/id/(\d+)"[^>]*>(.*?)</a>', html):
            tid, name = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if not name or "最新" in name:
                continue
            if tid not in [c["type_id"] for c in classes]:
                classes.append({"type_id": tid, "type_name": name})
        result = {"class": classes, "list": self._parse_vods(blob)}
        if self._filters_cache is None:
            filters = {}
            if classes:
                tids = [c["type_id"] for c in classes]
                try:
                    with ThreadPoolExecutor(max_workers=min(6, len(tids))) as ex:
                        for tid, fl in zip(tids, ex.map(self._build_one_filter, tids)):
                            filters[tid] = fl
                except Exception:
                    for c in classes:
                        filters.setdefault(c["type_id"], [])
            self._filters_cache = filters
        result["filters"] = self._filters_cache
        return result

    def categoryContent(self, tid, pg, filter, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        url = "%s/vod/show/id/%s" % (self.host, tid)
        for k in FILTER_ORDER + ["sort", "sortBy"]:
            v = extend.get(k)
            if v:
                v = quote(unquote(str(v).strip(), encoding="utf-8"), safe="~")
                if v:
                    url += "/%s/%s" % (k, v)
        pg = int(pg) if str(pg).isdigit() else 1
        if pg > 1:
            url += "/page/%d" % pg
        try:
            html, blob = self._flight(url, timeout=12)
        except Exception:
            html, blob = "", ""
        vods = self._parse_vods(blob)
        pagecount = 1
        m = re.search(r'"totalCount":(\d+)', blob)
        if m:
            pagecount = max(1, (int(m.group(1)) + 47) // 48)
        elif len(vods) >= 48:
            pagecount = pg + 1
        return {"list": vods, "page": pg, "pagecount": pagecount, "limit": 48, "total": 999999}

    def detailContent(self, ids):
        vid = ids[0]
        try:
            _html, blob = self._flight("%s/detail/%s" % (self.host, vid), timeout=12)
        except Exception:
            blob = ""
        name = self._jstr(blob, "vodName")
        pic = self._jstr(blob, "vodPic")
        actor = self._jstr(blob, "vodActor")
        director = self._jstr(blob, "vodDirector")
        area = self._jstr(blob, "vodArea")
        year = self._jstr(blob, "vodYear")
        lang = self._jstr(blob, "vodLang")
        vclass = self._jstr(blob, "vodClass")
        score = self._jstr(blob, "vodScore") or self._jstr(blob, "vodDoubanScore")
        remarks = self._jstr(blob, "vodRemarks") or self._jstr(blob, "vodVersion")
        content = self._jstr(blob, "vodContent")
        content = re.sub(r'<[^>]+>', '', content).strip()
        eps = re.findall(r'\{"nid":(\d+),"name":"((?:[^"\\]|\\.)*)"', blob)
        eps = [(nid, n.replace("$", "").replace("#", "")) for nid, n in eps]

        # 预取清晰度列表(仅用于列出线路名)
        res_list = []
        if eps:
            try:
                data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": eps[0][0]})
                if isinstance(data, dict) and data.get("code") == 200:
                    res_list = (data.get("data") or {}).get("list", []) or []
            except Exception:
                pass
        # 按分辨率从高到低, 不过滤 needLogin, 全部列出
        if res_list:
            res_list = sorted(res_list, key=lambda it: -(int(it.get("resolution", 0) or 0)))
        play_from = [it.get("resolutionName", "默认") for it in res_list] or ["默认"]

        urls = []
        for _r in play_from:
            urls.append("#".join("%s$%s@%s" % (n, vid, nid) for nid, n in eps))

        vod = {
            "vod_id": vid, "vod_name": name, "vod_pic": pic,
            "vod_actor": actor, "vod_director": director,
            "vod_area": area, "vod_year": year, "vod_lang": lang,
            "vod_class": vclass, "vod_score": score, "vod_remarks": remarks,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    # ---------------- play ----------------
    def _norm_url(self, u):
        if not u:
            return ""
        u = str(u).strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def playerContent(self, flag, id, vipFlags):
        """实时拿所选清晰度的 m3u8 直链, 全部走本地代理(重写分片时带上 auth_key)"""
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        s = str(id or "")
        if "|" in s:
            s = s.split("|", 1)[0]
        if "@" not in s:
            return {"parse": 0, "url": "", "header": header}
        vid, nid = s.split("@", 1)
        m = re.search(r'\d+', nid)
        nid = m.group(0) if m else nid

        target_url = ""
        try:
            api_data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": nid})
            if isinstance(api_data, dict) and api_data.get("code") == 200:
                res_list = (api_data.get("data") or {}).get("list", []) or []
                # 严格按用户所选 flag 匹配
                for item in res_list:
                    if item.get("resolutionName") == flag:
                        target_url = (item.get("url") or item.get("playUrl")
                                      or item.get("videoUrl") or item.get("fileUrl")
                                      or item.get("src") or "")
                        if target_url:
                            break
                # 匹配不到: 取分辨率最高的
                if not target_url and res_list:
                    best = sorted(res_list,
                                  key=lambda it: -(int(it.get("resolution", 0) or 0)))[0]
                    target_url = (best.get("url") or best.get("playUrl")
                                  or best.get("videoUrl") or best.get("fileUrl")
                                  or best.get("src") or "")
        except Exception:
            pass

        target_url = self._norm_url(target_url)
        if not target_url:
            return {"parse": 0, "url": "", "header": header}

        low = target_url.lower()
        if not (".m3u8" in low or ".mp4" in low or ".flv" in low or ".ts" in low):
            return {"parse": 1, "url": target_url, "header": header}

        # m3u8 走本地代理
        proxy_url = "proxy://do=py&type=m3u8&url=" + quote(target_url, safe="")
        return {"parse": 0, "url": proxy_url, "header": header}

    # ---------------- localProxy ----------------
    def localProxy(self, param):
        """本地代理:
        - 拉 m3u8 带 Referer/UA;
        - 关键: 重写分片时, 如果分片是相对路径且父 URL 有 query(auth_key),
          要把父 URL 的 query 拼上去, 否则 Nginx secure_link 会 401;
        - ts/key 二进制透传。
        """
        try:
            if isinstance(param, str):
                param = dict(parse_qsl(param.lstrip("?")))
            if not isinstance(param, dict):
                param = {}
            u = param.get("url", "") or ""
            u = unquote(u)
            if not u:
                return [404, "text/plain", b"no url", {}]

            r = self.sess.get(u, headers={
                "User-Agent": self.UA,
                "Referer": self.host + "/",
            }, timeout=15, allow_redirects=True)
            content = r.content
            ct = (r.headers.get("Content-Type") or "").lower()

            is_m3u8 = ("mpegurl" in ct or u.lower().endswith(".m3u8")
                       or ".m3u8?" in u.lower()
                       or content[:7] == b"#EXTM3U")

            if is_m3u8:
                try:
                    text = content.decode("utf-8", "ignore")
                except Exception:
                    text = content.decode("latin1", "ignore")

                parsed = urlparse(u)
                scheme_host = "%s://%s" % (parsed.scheme, parsed.netloc)
                # 目录
                if "/" in parsed.path:
                    base_dir = scheme_host + parsed.path.rsplit("/", 1)[0] + "/"
                else:
                    base_dir = scheme_host + "/"
                # 父 URL 的 query(含 auth_key)
                parent_query = parsed.query or ""

                def _to_abs(rel):
                    if rel.startswith("http://") or rel.startswith("https://"):
                        return rel
                    if rel.startswith("//"):
                        return parsed.scheme + ":" + rel
                    if rel.startswith("/"):
                        return scheme_host + rel
                    return base_dir + rel

                def _proxy_wrap(abs_url, add_parent_query):
                    # 如果分片本身没有 query, 且父 URL 有 auth_key, 就补上
                    if add_parent_query and parent_query:
                        p2 = urlparse(abs_url)
                        if not p2.query:
                            sep = "&" if "?" in abs_url else "?"
                            abs_url = abs_url + sep + parent_query
                    return "proxy://do=py&type=ts&url=" + quote(abs_url, safe="")

                new_lines = []
                for line in text.split("\n"):
                    ls = line.strip()
                    if not ls:
                        new_lines.append(line)
                        continue
                    if ls.startswith("#"):
                        # 处理 #EXT-X-KEY / #EXT-X-MAP 里的 URI="..."
                        if 'URI="' in ls:
                            def _repl(m):
                                uri = m.group(1)
                                abs_u = _to_abs(uri)
                                return 'URI="' + _proxy_wrap(abs_u, True) + '"'
                            ls = re.sub(r'URI="([^"]+)"', _repl, ls)
                        new_lines.append(ls)
                        continue
                    # 普通分片行
                    abs_u = _to_abs(ls)
                    new_lines.append(_proxy_wrap(abs_u, True))

                new_content = "\n".join(new_lines).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", new_content,
                        {"Access-Control-Allow-Origin": "*"}]

            # ts / key / 其它二进制透传
            return [200, r.headers.get("Content-Type", "application/octet-stream"),
                    content, {"Access-Control-Allow-Origin": "*"}]
        except Exception as e:
            try:
                return [500, "text/plain", ("proxy error: %r" % e).encode("utf-8"), {}]
            except Exception:
                return [500, "text/plain", b"proxy error", {}]

    # ---------------- search ----------------
    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        vods = []
        pagecount = 1
        try:
            data = self._api("/anonymous/video/searchByWord",
                             {"keyword": key, "pageNum": str(pg),
                              "pageSize": "48", "sourceCode": "1"})
            if isinstance(data, dict) and data.get("code") == 200:
                res = (data.get("data") or {}).get("result", {})
                total = res.get("totalCount", 0)
                pagecount = max(1, (total + 47) // 48)
                for it in res.get("list", []):
                    vods.append({
                        "vod_id": str(it.get("vodId", "")),
                        "vod_name": it.get("vodName", ""),
                        "vod_pic": it.get("vodPic", ""),
                        "vod_remarks": it.get("vodRemarks", "") or it.get("vodVersion", ""),
                        "vod_year": it.get("vodYear", ""),
                        "vod_area": it.get("vodArea", ""),
                    })
        except Exception:
            pass
        return {"list": vods, "page": pg, "pagecount": pagecount, "limit": 48, "total": 999999}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    def isVideoFormat(self, url):
        return "m3u8" in url or "mp4" in url

    def manualVideoCheck(self):
        return False
