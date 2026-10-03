# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/ (Next.js App Router 前端)
# 列表/详情: 服务端渲染 RSC flight 数据, 直接解析 {"vodId":...} JSON
# 播放: 签名 API /mw-movie/anonymous/v2/video/episode/url
#
# 修复历史:
#   2026-10-03 第二轮: homeContent 并发抓 filters + 缓存; localProxy 返回 None;
#                       type 用数字 id; 分类/搜索空结果兜底。
#   2026-10-04 第三轮: _flight 正则放宽。
#   2026-10-04 第四轮: playerContent 强化(字段多尝试 + Referer 用详情页 + parse 自适应)。
#   2026-10-04 第五轮: detail 预取清晰度, player 按 flag 精准匹配。
#   2026-10-04 第六轮: 修复播放失败的 2 个核心 bug:
#       ① detail 里 id 去掉 "|res_name" 后缀(flag 本身就是清晰度名, 拼了反而让 nid 参数错);
#       ② playerContent 里对 id 残留 "|" 做切分; 按 URL 后缀自适应 parse; 输出调试日志。
from base.spider import Spider
import requests
import re
import json
import hashlib
import time
import uuid
from urllib.parse import quote, unquote
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
        """抓取 Next.js RSC flight 数据, 返回 (html, blob)"""
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
        # 签名: sign=SHA1(MD5("k1=v1&k2=v2...(key 排序)&key=signkey&t=毫秒戳"))
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
            pic = self._jstr(o, "vodPic")
            remarks = self._jstr(o, "vodRemarks") or self._jstr(o, "vodVersion")
            year = self._jstr(o, "vodYear")
            area = self._jstr(o, "vodArea")
            vods.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_year": year,
                "vod_area": area,
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

    # ---------------- home ----------------
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

    # ---------------- category ----------------
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

    # ---------------- detail ----------------
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

        # 预取清晰度列表(取第 1 集)
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
            play_from = [it.get("resolutionName", "默认") for it in res_list]
        else:
            play_from = ["默认"]

        # 每条线路都列出全部集数, id 只拼 "vid@nid", 清晰度靠 flag 区分
        # (原来拼 "|res_name" 会让 playerContent 拿到脏 nid 导致 API 请求失败)
        urls = []
        for _res in play_from:
            ep_line = []
            for nid, n in eps:
                ep_line.append("%s$%s@%s" % (n, vid, nid))
            urls.append("#".join(ep_line))

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_lang": lang,
            "vod_class": vclass,
            "vod_score": score,
            "vod_remarks": remarks,
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
        """按清晰度 flag 请求对应播放地址"""
        header = {"User-Agent": self.UA, "Referer": self.host + "/", "Origin": self.host}

        s = str(id or "")
        # 兼容旧版 id 里残留的 "|清晰度" 后缀, 直接切掉
        if "|" in s:
            s = s.split("|", 1)[0]
        if "@" not in s:
            return {"parse": 0, "url": "", "header": header}

        vid, nid = s.split("@", 1)
        # nid 只保留数字, 防止脏字符进签名
        m = re.search(r'\d+', nid)
        nid = m.group(0) if m else nid

        header["Referer"] = "%s/detail/%s" % (self.host, vid)

        target_url = ""
        try:
            api_data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": nid})
            try:
                print("[界影视] playerContent API: %s" %
                      json.dumps(api_data, ensure_ascii=False)[:1500])
            except Exception:
                pass
            if isinstance(api_data, dict) and api_data.get("code") == 200:
                res_list = (api_data.get("data") or {}).get("list", []) or []
                # 按 flag 匹配清晰度
                for item in res_list:
                    if item.get("resolutionName") == flag:
                        target_url = (item.get("url") or item.get("playUrl")
                                      or item.get("videoUrl") or item.get("fileUrl")
                                      or item.get("src") or "")
                        if target_url:
                            break
                # 匹配不到就取第一条
                if not target_url and res_list:
                    it = res_list[0]
                    target_url = (it.get("url") or it.get("playUrl")
                                  or it.get("videoUrl") or it.get("fileUrl")
                                  or it.get("src") or "")
        except Exception as e:
            try:
                print("[界影视] playerContent 异常: %r" % e)
            except Exception:
                pass

        target_url = self._norm_url(target_url)
        try:
            print("[界影视] playerContent 选中 URL: %s" % target_url)
        except Exception:
            pass

        if not target_url:
            return {"parse": 0, "url": "", "header": header}

        low = target_url.lower()
        # 直链给 parse:0, 非直链交给 TVBox 嗅探
        parse = 0 if any(k in low for k in ('.m3u8', '.mp4', '.flv', '.ts')) else 1
        return {"parse": parse, "url": target_url, "header": header}

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

    def localProxy(self, param):
        return None
