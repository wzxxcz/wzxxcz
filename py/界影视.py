# -*- coding: utf-8 -*-
# 站点: 界影视 https://yvyeigh.com/ (Next.js App Router 前端)
# 列表/详情: 服务端渲染 RSC flight 数据, 直接解析 {"vodId":...} JSON
# 播放: 签名 API /mw-movie/anonymous/v2/video/episode/url (签名算法由前端 JS 还原)
# 二级分类: /vod/show/id/{tid} 页 filter-ul 行, 片段 /class/x/area/y/year/z/lang/w, 排序 sort/sortBy
#
# 修复(2026-10-03 第二轮):
#   根因: homeContent 里为了构建二级分类按钮, 对 6 个分类页【同步串行】各发一次 HTTP 抓取,
#         TV 端在弱网/慢机上会整体超时, 首页/分类列表直接空 -> 表现为"首页/分类列表加载失败"。
#   ① homeContent 不再串行阻塞: 用线程池并发抓各分类 filters, 且只抓一次后缓存;
#         单个分类抓取失败只跳过该组按钮, 不影响首页主体列表与其它分类;
#         抓 filters 期间首页主体(轮播/最新片)先返回, 不再被 6 次串行请求拖垮。
#   ② 分类页每个请求独立 timeout(8s)+重试一次; 抓不到 filters 时该分类给个空过滤组占位, 不报错。
#   ③ type 行取值从 href 提取数字 id(如 /2/type/14 取 14), 不用中文名, 避免筛选 URL 拼错。
#   ④ localProxy 原来返回 list [200,"video/2",None,""] 与 base 契约不符, 改为安全 dict。
#   ⑤ 分类/搜索空结果兜底: 抓取异常时返回空列表而非抛错, 避免整页白屏。
#
# 修复(2026-10-04 第三轮):
#   ⑥ _flight 的 RSC 正则放宽: 兼容 self.__next_f.push([1, "..."]) 中
#      "[1," 与 '"' 之间可能存在的空白, 且不强制结尾紧贴 </script>;
#      匹配不到时回退原严格正则。修复"首页/分类列表啥也没有"的根因。
#
# 修复(2026-10-04 第四轮):
#   ⑦ playerContent 强化:
#      - 播放地址字段多尝试: url / playUrl / videoUrl / fileUrl / src; 兼容 data 直接是 URL 字符串;
#      - 相对路径补全: //xxx -> https://xxx, /xxx -> host+/xxx;
#      - Referer 改为详情页 URL(很多站按详情页做防盗链), UA 同步带上;
#      - URL 明显不是视频文件时自动改为 parse:1, 交给 TVBox 嗅探;
#      - 取不到 URL 时返回空串, 避免播放器一直转圈。
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
        self._filters_cache = None   # 二级分类按钮只构建一次, 避免每次进首页都串行抓 6 个分类页

    def getName(self):
        return "界影视"

    # ---------------- 基础 ----------------
    def _get(self, url, timeout=12):
        r = self.sess.get(url, timeout=timeout)
        r.encoding = "utf-8"
        return r.text

    def _flight(self, url, timeout=12):
        """抓取 Next.js RSC flight 数据, 返回 (html, blob)。
        正则放宽: 兼容 push([1, "..."]) 中 "[1," 与引号之间的空白, 不强制结尾紧贴 </script>。
        """
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
        q = "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
        h = "%s&key=%s&t=%s" % (q, self.signkey, ts)
        sign = hashlib.sha1(hashlib.md5(h.encode()).hexdigest().encode()).hexdigest()
        qs = "&".join("%s=%s" % (k, quote(str(params[k]), safe="")) for k in params)
        url = self.host + "/mw-movie" + path + "?" + qs
        r = self.sess.get(url, headers={
            "sign": sign, "t": ts,
            "deviceId": self.device_id, "authorization": "",
        }, timeout=15)
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
                # 取该 key 对应的 href 段值:
                #  type 是数字 id (如 /type/14), class/area/year/lang 是中文 (如 /class/古装)
                vm = re.search(r'/id/\d+/%s/([^/"]+)' % key, u)
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

    def _build_one_filter(self, tid):
        """抓单个分类页的二级分类按钮; 失败返回空列表, 不影响其它分类。"""
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

        # 二级分类按钮: 并发构建 + 只构建一次。
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
                # 先 unquote 再 quote：兼容客户端原文/预编码两种传参
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
        # 取第一集的清晰度列表作为播放源
        res_list = []
        if eps:
            try:
                data = self._api("/anonymous/v2/video/episode/url",
                                 {"clientType": "1", "id": vid, "nid": eps[0][0]})
                if isinstance(data, dict) and data.get("code") == 200:
                    res_list = (data.get("data") or {}).get("list", [])
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
    def _norm_url(self, u):
        """相对地址补全为绝对地址"""
        if not u:
            return ""
        u = str(u).strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def playerContent(self, flag, id, vipFlags):
        """播放:
        1) 从签名 API 拿清晰度列表, 按 flag(清晰度名) 匹配 URL;
        2) 字段多尝试: url / playUrl / videoUrl / fileUrl / src;
           兼容 data 直接就是 URL 字符串的情况;
        3) 相对路径补全;
        4) Referer 用详情页 URL(防盗链常按详情页校验), UA 同步;
        5) URL 明显不是视频文件时, 自动改为 parse:1 交给 TVBox 嗅探;
        6) 取不到 URL 时返回空串, 避免播放器一直转圈。
        """
        if "@" not in str(id or ""):
            return {"parse": 0, "url": "", "header": {}}
        vid, nid = str(id).split("@", 1)

        # 用详情页做 Referer, 很多站点的防盗链认详情页
        detail_url = "%s/detail/%s" % (self.host, vid)
        header = {
            "User-Agent": self.UA,
            "Referer": detail_url,
            "Origin": self.host,
        }

        url = ""
        try:
            data = self._api("/anonymous/v2/video/episode/url",
                             {"clientType": "1", "id": vid, "nid": nid})
            if isinstance(data, dict):
                # 常规结构: {code:200, data:{list:[{resolutionName, url}, ...]}}
                if data.get("code") == 200:
                    d = data.get("data") or {}
                    # data 直接是 URL 字符串
                    if isinstance(d, str) and d.startswith("http"):
                        url = d
                    else:
                        lst = d.get("list") or []
                        if lst:
                            # 先按清晰度名匹配
                            for it in lst:
                                if it.get("resolutionName") == flag:
                                    url = (it.get("url") or it.get("playUrl")
                                           or it.get("videoUrl") or it.get("fileUrl")
                                           or it.get("src") or "")
                                    if url:
                                        break
                            # 匹配不到就用第一条
                            if not url:
                                it = lst[0]
                                url = (it.get("url") or it.get("playUrl")
                                       or it.get("videoUrl") or it.get("fileUrl")
                                       or it.get("src") or "")
                        # data 里可能有顶层 url 字段
                        if not url and isinstance(d, dict):
                            url = (d.get("url") or d.get("playUrl")
                                   or d.get("videoUrl") or d.get("fileUrl") or "")
                # 兼容 code != 200 但返回了 url 的情况
                if not url:
                    url = data.get("url") or data.get("playUrl") or ""
        except Exception:
            url = ""

        url = self._norm_url(url)

        if not url:
            return {"parse": 0, "url": "", "header": header}

        # 明显不是视频文件时, 交给 TVBox 嗅探
        u = url.lower()
        is_direct = any(k in u for k in (".m3u8", ".mp4", ".flv", ".ts"))
        parse = 0 if is_direct else 1
        return {"parse": parse, "url": url, "header": header}

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
        # 与 base.spider 契约一致: 无本地代理时返回 None
        return None
