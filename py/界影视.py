# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/
# 壳子: webhtv (基于 FongMi, 支持 proxy:// 本地代理)
#
# 【本版核心思路: 无状态重生式代理, 彻底解决历史记录无法播放】
#   playerContent 不返回一次性的 m3u8 URL, 而是返回一个永远有效的代理地址:
#     proxy://do=py&type=m3u8&vid={vid}&nid={nid}&flag={flag}
#   这个地址不含时间戳、不含签名, 无论过多久都有效。
#   当 TVBox 从"历史记录 / 继续播放 / 重启后"进入时, 直接拿这个地址给播放器,
#   播放器请求 → 壳子转本地 HTTP → localProxy 实时重签 URL 拉流 → 完美播放。
#   m3u8 里的分片也重写为同样"重生式"的代理地址(带 vid/nid/flag/idx),
#   每次分片请求都会现签现拉, 保证 auth_key 永不过期。
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
        # m3u8 内存缓存: {(vid,nid,flag): (m3u8_text, base_url, timestamp)}
        # 用于分片请求时快速定位"第 idx 个分片是哪个 URL", 避免每个分片都重新拉 m3u8
        self._m3u8_cache = {}

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
        """分片相对路径 → 绝对 URL, 并补父 URL 的 query (auth_key 关键)"""
        abs_seg = urljoin(m3u8_url, seg)
        p_url = urlparse(m3u8_url)
        p_seg = urlparse(abs_seg)
        if not p_seg.query and p_url.query:
            abs_seg = abs_seg + "?" + p_url.query
        return abs_seg

    def _fetch_urls(self, vid, nid):
        """实时签 URL, 返回 list"""
        play_device_id = str(uuid.uuid4())
        try:
            api_data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": nid},
                                 device_id=play_device_id)
            if isinstance(api_data, dict) and api_data.get("code") == 200:
                return (api_data.get("data") or {}).get("list", []) or []
        except Exception:
            pass
        return []

    def _pick_url(self, res_list, flag):
        """从 res_list 里按 flag 匹配 URL, 匹配不到取最高分辨率"""
        if not res_list:
            return ""
        target_url = ""
        for item in res_list:
            if item.get("resolutionName") == flag:
                target_url = (item.get("url") or item.get("playUrl")
                              or item.get("videoUrl") or item.get("fileUrl")
                              or item.get("src") or "")
                if target_url:
                    break
        if not target_url:
            best = sorted(res_list,
                          key=lambda it: -(int(it.get("resolution", 0) or 0)))[0]
            target_url = (best.get("url") or best.get("playUrl")
                          or best.get("videoUrl") or best.get("fileUrl")
                          or best.get("src") or "")
        return self._norm_url(target_url)

    def _get_m3u8(self, vid, nid, flag):
        """获取 m3u8 文本和 base_url. 优先用 120 秒内存缓存, 过期则重签重拉。"""
        key = (str(vid), str(nid), str(flag))
        now = time.time()
        if key in self._m3u8_cache:
            text, base_url, ts = self._m3u8_cache[key]
            if now - ts < 120:
                return text, base_url
        # 重签重拉
        res_list = self._fetch_urls(vid, nid)
        if not res_list:
            return "", ""
        url = self._pick_url(res_list, flag)
        if not url:
            return "", ""
        try:
            r = self.sess.get(url, headers={
                "User-Agent": self.UA,
                "Referer": self.host + "/",
            }, timeout=15)
            text = r.text
        except Exception:
            return "", ""
        self._m3u8_cache[key] = (text, url, now)
        # 缓存清理
        if len(self._m3u8_cache) > 50:
            old_keys = sorted(self._m3u8_cache.keys(),
                              key=lambda k: self._m3u8_cache[k][2])[:20]
            for k in old_keys:
                self._m3u8_cache.pop(k, None)
        return text, url

    # ---------------- play ----------------
    def playerContent(self, flag, id, vipFlags):
        """返回无状态的"重生式"代理地址, 永远有效。
        无论 TVBox 从历史记录/继续播放/重启后进入, 代理层都能实时重签 URL。
        """
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        s = str(id or "")
        if "|" in s:
            s = s.split("|", 1)[0]
        if "@" not in s:
            return {"parse": 0, "url": "", "header": header}
        vid, nid = s.split("@", 1)
        m = re.search(r'\d+', nid)
        nid = m.group(0) if m else nid
        m2 = re.search(r'\d+', vid)
        vid = m2.group(0) if m2 else vid

        # 返回"重生式"代理地址: 不含一次性 URL, 只带 vid/nid/flag, 永远可重签
        proxy_url = ("proxy://do=py&type=m3u8&vid=%s&nid=%s&flag=%s" % (
            quote(str(vid), safe=""), quote(str(nid), safe=""),
            quote(str(flag or ""), safe="")))
        return {"parse": 0, "url": proxy_url, "header": header}

    # ---------------- localProxy (关键实现) ----------------
    def localProxy(self, param):
        """本地代理, 支持 4 种模式:
        1) type=m3u8 + vid/nid/flag  → 实时签 URL 拉 m3u8, 重写分片为"重生式"代理地址
        2) type=ts   + vid/nid/flag/idx → 从缓存的 m3u8 里解析第 idx 个分片, 拉流返回
        3) type=key  + url            → 直接透传 key 文件
        4) type=ts   + url            → 向后兼容: 直接透传
        """
        try:
            if isinstance(param, str):
                param = dict(parse_qsl(param.lstrip("?")))
            if not isinstance(param, dict):
                param = {}

            typ = param.get("type", "")
            url = unquote(param.get("url", "") or "")
            vid = str(param.get("vid", "") or "")
            nid = str(param.get("nid", "") or "")
            flag = param.get("flag", "") or ""
            idx = str(param.get("idx", "") or "")

            # === 模式 1: m3u8 索引请求 ===
            if typ == "m3u8" and vid and nid:
                text, base_url = self._get_m3u8(vid, nid, flag)
                if not text:
                    return [404, "text/plain", b"no m3u8", {}]
                new_lines = []
                seg_idx = 0
                for line in text.split("\n"):
                    ls = line.strip()
                    if not ls:
                        new_lines.append(line)
                        continue
                    if ls.startswith("#"):
                        # 处理 #EXT-X-KEY / #EXT-X-MAP 里的 URI="..."
                        if 'URI="' in ls:
                            def _repl(m):
                                u = m.group(1)
                                abs_u = self._abs_segment(base_url, u)
                                return 'URI="proxy://do=py&type=key&url=' + quote(abs_u, safe="") + '"'
                            ls = re.sub(r'URI="([^"]+)"', _repl, ls)
                        new_lines.append(ls)
                        continue
                    # 分片行: 用"重生式"代理地址(带 vid/nid/flag/idx)
                    new_lines.append(
                        "proxy://do=py&type=ts&vid=%s&nid=%s&flag=%s&idx=%d" % (
                            quote(vid, safe=""), quote(nid, safe=""),
                            quote(flag, safe=""), seg_idx))
                    seg_idx += 1
                return [200, "application/vnd.apple.mpegurl",
                        "\n".join(new_lines).encode("utf-8"),
                        {"Access-Control-Allow-Origin": "*"}]

            # === 模式 2: ts 分片请求(重生式) ===
            if typ == "ts" and vid and nid and idx != "":
                text, base_url = self._get_m3u8(vid, nid, flag)
                if not text:
                    return [404, "text/plain", b"no m3u8", {}]
                seg_idx = 0
                target_seg = ""
                for line in text.split("\n"):
                    ls = line.strip()
                    if not ls or ls.startswith("#"):
                        continue
                    if seg_idx == int(idx):
                        target_seg = ls
                        break
                    seg_idx += 1
                if not target_seg:
                    return [404, "text/plain", b"no seg", {}]
                abs_seg = self._abs_segment(base_url, target_seg)
                r = self.sess.get(abs_seg, headers={
                    "User-Agent": self.UA,
                    "Referer": self.host + "/",
                }, timeout=15, allow_redirects=True)
                return [200, r.headers.get("Content-Type", "video/mp2t"),
                        r.content, {"Access-Control-Allow-Origin": "*"}]

            # === 模式 3: key 文件透传 ===
            if typ == "key" and url:
                r = self.sess.get(url, headers={
                    "User-Agent": self.UA,
                    "Referer": self.host + "/",
                }, timeout=15, allow_redirects=True)
                return [200, r.headers.get("Content-Type", "application/octet-stream"),
                        r.content, {"Access-Control-Allow-Origin": "*"}]

            # === 模式 4: 老模式 - 直接带 url ===
            if url:
                r = self.sess.get(url, headers={
                    "User-Agent": self.UA,
                    "Referer": self.host + "/",
                }, timeout=15, allow_redirects=True)
                content = r.content
                ct = (r.headers.get("Content-Type") or "").lower()
                is_m3u8 = ("mpegurl" in ct or url.lower().endswith(".m3u8")
                           or ".m3u8?" in url.lower()
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
                            new_lines.append(ls); continue
                        abs_seg = self._abs_segment(url, ls)
                        new_lines.append("proxy://do=py&type=ts&url=" + quote(abs_seg, safe=""))
                    return [200, "application/vnd.apple.mpegurl",
                            "\n".join(new_lines).encode("utf-8"),
                            {"Access-Control-Allow-Origin": "*"}]
                return [200, r.headers.get("Content-Type", "application/octet-stream"),
                        content, {"Access-Control-Allow-Origin": "*"}]

            return [404, "text/plain", b"bad request", {}]
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
