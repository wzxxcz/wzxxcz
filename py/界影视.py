# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/ (Next.js App Router 前端)
# 列表/详情: 服务端渲染 RSC flight 数据, 直接解析 {"vodId":...} JSON
# 播放: 签名 API /mw-movie/anonymous/v2/video/episode/url (签名算法由前端 JS 还原)
# 二级分类: /vod/show/id/{tid} 页 filter-ul 行, 片段 /class/x/area/y/year/z/lang/w, 排序 sort/sortBy
# 修复(2026-10-03): 电视剧无二级分类按钮 -> ①homeContent 始终构建 filters(不依赖客户端 filter 参数);
#   分类页抓取失败自动重试一次, 避免偶发失败导致整组按钮缺失;
#   ②type 行取值改为从 href 提取数字 id(如/2/type/14 取 14), 原来误用中文名导致筛选 URL 错误
from base.spider import Spider
import requests
import re
import json
import hashlib
import time
import uuid
from urllib.parse import quote, unquote

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

    def getName(self):
        return "界影视"

    # ---------------- 基础 ----------------
    def _get(self, url, timeout=20):
        r = self.sess.get(url, timeout=timeout)
        r.encoding = "utf-8"
        return r.text

    def _flight(self, url):
        if url in self._cache:
            return self._cache[url]
        html = self._get(url)
        pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
        blob = ""
        for p in pushes:
            try:
                blob += json.loads('"' + p + '"')
            except Exception:
                pass
        self._cache[url] = (html, blob)
        return html, blob

    def _api(self, path, params):
        # 签名: sign=SHA1(MD5("k1=v1&k2=v2...(key 排序)&key=signkey&t=毫秒戳"))
        ts = str(int(time.time() * 1000))
        q = "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
        h = "%s&key=%s&t=%s" % (q, self.signkey, ts)
        sign = hashlib.sha1(hashlib.md5(h.encode()).hexdigest().encode()).hexdigest()
        qs = "&".join("%s=%s" % (k, quote(str(params[k]), safe="")) for k in params)
        url = self.host + "/mw-movie" + path + "?" + qs
        r = self.sess.get(url, headers={
            "sign": sign, "t": ts,
            "deviceId": self.device_id, "authorization": "",
        }, timeout=20)
        return r.json()

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
                vm = re.search(r'/id/\d+/[A-Za-z]+/([^"]+)$', u)
                v = unquote(vm.group(1)).strip() if vm else n
                if v and v not in have:
                    have.add(v)
                    vals.append({"n": n, "v": v})
            if len(vals) >= 2:
                flist.append({"key": key, "name": FILTER_LABEL[key], "value": vals})
        flist.sort(key=lambda x: FILTER_ORDER.index(x["key"]) if x["key"] in FILTER_ORDER else 99)
        # 排序: 电影=上映时间, 其他=最近更新/添加时间
        if tid == "1":
            sorts = [{"n": "上映时间", "v": "1"}, {"n": "人气高低", "v": "3"}, {"n": "评分高低", "v": "4"}]
        else:
            sorts = [{"n": "最近更新", "v": "1"}, {"n": "添加时间", "v": "2"},
                     {"n": "人气高低", "v": "3"}, {"n": "评分高低", "v": "4"}]
        flist.append({"key": "sort", "name": "排序", "value": sorts})
        return flist

    # ---------------- home ----------------
    def homeContent(self, filter):
        html, blob = self._flight(self.host + "/")
        classes = []
        for m in re.finditer(r'<a[^>]*href="/vod/show/id/(\d+)"[^>]*>(.*?)</a>', html):
            tid, name = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if not name or "最新" in name:
                continue
            if tid not in [c["type_id"] for c in classes]:
                classes.append({"type_id": tid, "type_name": name})
        result = {"class": classes, "list": self._parse_vods(blob)}
        # 二级分类按钮: 不依赖客户端是否传 filter, 始终构建 filters;
        # 单个分类页抓取失败时重试一次, 避免某个分类(如电视剧)偶发失败导致整组按钮缺失
        filters = {}
        for c in classes:
            tid = c["type_id"]
            url = "%s/vod/show/id/%s" % (self.host, tid)
            fhtml = ""
            for _try in range(2):
                try:
                    if _try:
                        self._cache.pop(url, None)
                    fhtml, _ = self._flight(url)
                    if fhtml and "filter-ul" in fhtml:
                        break
                except Exception:
                    fhtml = ""
            try:
                if fhtml:
                    filters[tid] = self._parse_filters(fhtml, tid)
            except Exception:
                pass
        result["filters"] = filters
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
                # 先 unquote 再 quote：兼容客户端原文/预编码两种传参，避免双重编码导致服务端匹配不到过滤条件
                v = quote(unquote(str(v).strip(), encoding="utf-8"), safe="~")
                if v:
                    url += "/%s/%s" % (k, v)
        pg = int(pg) if str(pg).isdigit() else 1
        if pg > 1:
            url += "/page/%d" % pg
        html, blob = self._flight(url)
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
        _html, blob = self._flight("%s/detail/%s" % (self.host, vid))
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
        # 取第一集的清晰度列表作为播放源
        res_list = []
        if eps:
            try:
                data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": eps[0][0]})
                if data.get("code") == 200:
                    res_list = data["data"].get("list", [])
            except Exception:
                pass
        if res_list:
            play_from = [it.get("resolutionName", "默认") for it in res_list]
        else:
            play_from = ["默认"]
        urls = []
        for _r in play_from:
            urls.append(["%s$%s@%s" % (n, vid, nid) for nid, n in eps])
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
            "vod_play_url": "$$$".join(["#".join(u) for u in urls]),
        }
        return {"list": [vod]}

    # ---------------- play ----------------
    def playerContent(self, flag, id, vipFlags):
        vid, nid = id.split("@")
        url = ""
        try:
            data = self._api("/anonymous/v2/video/episode/url",
                             {"clientType": "1", "id": vid, "nid": nid})
            if data.get("code") == 200:
                lst = data["data"].get("list", [])
                for it in lst:
                    if it.get("resolutionName") == flag:
                        url = it.get("url", "")
                        break
                if not url and lst:
                    url = lst[0].get("url", "")
        except Exception:
            pass
        return {"parse": 0, "url": url,
                "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}

    # ---------------- search ----------------
    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        vods = []
        pagecount = 1
        try:
            data = self._api("/anonymous/video/searchByWord",
                             {"keyword": key, "pageNum": str(pg),
                              "pageSize": "48", "sourceCode": "1"})
            if data.get("code") == 200:
                res = data["data"].get("result", {})
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
        return [200, "video/2", None, ""]
