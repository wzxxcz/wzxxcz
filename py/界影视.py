# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/
# 播放: 签名 API /mw-movie/anonymous/v2/video/episode/url
#
# 【本版 4 道防线, 目标: 不管用户怎么操作都能播蓝光/高清】
#   ① 时间戳防缓存: detailContent 的每条选集 id 结尾带 @时间戳,
#      逼 TVBox 每次重新调 playerContent, 不会复用磁盘缓存的旧 URL。
#   ② 每次实时重签: playerContent 里用全新 device_id + 最新时间戳重新签 URL,
#      保证返回的 m3u8 一定是当前有效的。
#   ③ 裸请求探测: 模拟播放器"只带 UA / 不带 Referer"去请求,
#      m3u8 索引 + 第一个分片都返回 200 才算"可播"。
#   ④ 自动降级 + 代理兜底: 所选清晰度失效就自动降级到下一档;
#      直连失败时自动切到本地代理(重写分片时带上父 URL 的 auth_key)。
from base.spider import Spider
import requests
import re
import json
import hashlib
import time
import uuid
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qsl
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

    def _api(self, path, params, device_id=None):
        ts = str(int(time.time() * 1000))
        sp = {k: str(v) for k, v in params.items()}
        q = "&".join("%s=%s" % (k, sp[k]) for k in sorted(sp))
        h = "%s&key=%s&t=%s" % (q, self.signkey, ts)
        sign = hashlib.sha1(hashlib.md5(h.encode()).hexdigest().encode()).hexdigest()
        qs = "&".join("%s=%s" % (k, quote(sp[k], safe="")) for k in sp)
        url = self.host + "/mw-movie" + path + "?" + qs
        did = device_id if device_id else self.device_id
        r = self.sess.get(url, headers={
            "sign": sign, "t": ts,
            "deviceId": did, "authorization": "",
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

        # 预取清晰度列表(仅列出线路名, 播放时才签 URL)
        res_list = []
        if eps:
            try:
                data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": eps[0][0]})
                if isinstance(data, dict) and data.get("code") == 200:
                    res_list = (data.get("data") or {}).get("list", []) or []
            except Exception:
                pass
        if res_list:
            res_list = sorted(res_list, key=lambda it: -(int(it.get("resolution", 0) or 0)))
        play_from = [it.get("resolutionName", "默认") for it in res_list] or ["默认"]

        # 时间戳防缓存: 每条选集 id 结尾带 @ts, 逼 TVBox 每次都重新调 playerContent
        ts = str(int(time.time()))
        urls = []
        for _r in play_from:
            ep_line = []
            for nid, n in eps:
                ep_line.append("%s$%s@%s@%s" % (n, vid, nid, ts))
            urls.append("#".join(ep_line))

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

    # ---------------- URL 工具 ----------------
    def _norm_url(self, u):
        if not u:
            return ""
        u = str(u).strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _abs_segment(self, m3u8_url, seg):
        """把 m3u8 里的分片路径拼成绝对 URL, 并把父 URL 的 query 补上"""
        abs_seg = urljoin(m3u8_url, seg)
        p_url = urlparse(m3u8_url)
        p_seg = urlparse(abs_seg)
        if not p_seg.query and p_url.query:
            abs_seg = abs_seg + "?" + p_url.query
        return abs_seg

    def _verify_playable(self, url):
        """裸请求探测: 只带 UA, 不带 Referer —— 模拟播放器直连。
        m3u8: 索引和第一个分片都要 200; mp4/flv: 一次 200 即可。
        """
        if not url:
            return False
        try:
            low = url.lower()
            if any(low.endswith(ext) or (ext + "?") in low
                   for ext in (".mp4", ".flv")):
                r = self.sess.get(url, headers={"User-Agent": self.UA},
                                  timeout=6, stream=True)
                ok = (r.status_code == 200)
                try: r.close()
                except Exception: pass
                return ok

            r = self.sess.get(url, headers={"User-Agent": self.UA}, timeout=6)
            if r.status_code != 200:
                return False
            if b"#EXTM3U" not in r.content:
                return False

            text = r.text
            first_seg = None
            for line in text.split("\n"):
                ls = line.strip()
                if ls and not ls.startswith("#"):
                    first_seg = ls
                    break
            if not first_seg:
                return True  # 空 m3u8, 至少索引有效

            abs_seg = self._abs_segment(url, first_seg)
            r2 = self.sess.get(abs_seg, headers={"User-Agent": self.UA},
                               timeout=6, stream=True)
            ok = (r2.status_code == 200)
            try: r2.close()
            except Exception: pass
            return ok
        except Exception:
            return False

    # ---------------- play ----------------
    def playerContent(self, flag, id, vipFlags):
        """4 道防线一起上, 保证任何入口都能播。"""
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        flag_clean = re.sub(r'\[.*?\]$', '', str(flag or "")).strip()

        s = str(id or "")

        # 情形 A: id 是 http(s) URL —— 某些壳"继续播放"会直接传 URL
        if s.startswith("http://") or s.startswith("https://"):
            if self._verify_playable(s):
                return {"parse": 0, "url": s, "header": header}
            # 过期 URL 没法反推 vid/nid, 走代理兜底再试一次
            proxy_url = "proxy://do=py&type=m3u8&url=" + quote(s, safe="")
            return {"parse": 0, "url": proxy_url, "header": header}

        # 情形 B: id 是 vid@nid 或 vid@nid@ts
        if "|" in s:
            s = s.split("|", 1)[0]
        parts = s.split("@")
        if len(parts) < 2:
            return {"parse": 0, "url": "", "header": header}
        vid = re.search(r'\d+', parts[0])
        nid = re.search(r'\d+', parts[1])
        if not vid or not nid:
            return {"parse": 0, "url": "", "header": header}
        vid, nid = vid.group(0), nid.group(0)

        # 每次播放都用全新 device_id + 最新时间戳签 URL
        play_device_id = str(uuid.uuid4())
        res_list = []
        try:
            api_data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": nid},
                                 device_id=play_device_id)
            if isinstance(api_data, dict) and api_data.get("code") == 200:
                res_list = (api_data.get("data") or {}).get("list", []) or []
        except Exception:
            pass

        if not res_list:
            return {"parse": 0, "url": "", "header": header}

        # 按分辨率降序(蓝光优先)
        res_list = sorted(res_list, key=lambda it: -(int(it.get("resolution", 0) or 0)))

        def _get_url(it):
            return (it.get("url") or it.get("playUrl") or it.get("videoUrl")
                    or it.get("fileUrl") or it.get("src") or "")

        # 候选顺序: 用户所选优先, 其余按分辨率降序
        candidates = []
        for it in res_list:
            rn = it.get("resolutionName", "")
            if rn == flag or rn == flag_clean:
                u = self._norm_url(_get_url(it))
                if u:
                    candidates.append(u)
                break
        for it in res_list:
            u = self._norm_url(_get_url(it))
            if u and u not in candidates:
                candidates.append(u)

        if not candidates:
            return {"parse": 0, "url": "", "header": header}

        # 逐个探测, 第一个"裸请求可播"的胜出
        best = ""
        for u in candidates:
            if self._verify_playable(u):
                best = u
                break

        # 直连全失败: 强制用本地代理(重写分片时带 auth_key)
        if not best:
            proxy_url = "proxy://do=py&type=m3u8&url=" + quote(candidates[0], safe="")
            return {"parse": 0, "url": proxy_url, "header": header}

        low = best.lower()
        if any(k in low for k in ('.m3u8', '.mp4', '.flv', '.ts')):
            return {"parse": 0, "url": best, "header": header}
        return {"parse": 1, "url": best, "header": header}

    # ---------------- localProxy (代理兜底) ----------------
    def localProxy(self, param):
        """本地代理: 拉 m3u8 带 Referer/UA, 重写分片时补父 URL 的 auth_key, ts 二进制透传。
        param 兼容 dict / query string。
        """
        try:
            if isinstance(param, str):
                param = dict(parse_qsl(param.lstrip("?")))
            if not isinstance(param, dict):
                param = {}
            u = unquote(param.get("url", "") or "")
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

                new_lines = []
                for line in text.split("\n"):
                    ls = line.strip()
                    if not ls:
                        new_lines.append(line); continue
                    if ls.startswith("#"):
                        if 'URI="' in ls:
                            def _repl(m):
                                uri = m.group(1)
                                abs_u = self._abs_segment(u, uri)
                                return 'URI="proxy://do=py&type=ts&url=' + quote(abs_u, safe="") + '"'
                            ls = re.sub(r'URI="([^"]+)"', _repl, ls)
                        new_lines.append(ls); continue
                    abs_seg = self._abs_segment(u, ls)
                    new_lines.append("proxy://do=py&type=ts&url=" + quote(abs_seg, safe=""))

                return [200, "application/vnd.apple.mpegurl",
                        "\n".join(new_lines).encode("utf-8"),
                        {"Access-Control-Allow-Origin": "*"}]

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
        u = (url or "").lower()
        return "m3u8" in u or "mp4" in u

    def manualVideoCheck(self):
        return False
