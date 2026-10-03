# -*- coding: utf-8 -*-
# 极速追剧 (jisuzhuiju.com) TVBox 蜘蛛
# 列表 /filter?channel=N 分页; 详情 /detail/{id}.html; 播放 /api/play-url
from base.spider import Spider as _Spider
import re
import json
import base64
import requests
from urllib.parse import quote, unquote, parse_qs
import urllib.request


class Spider(_Spider):
    def init(self, extend=""):
        self.host = "https://jisuzhuiju.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.cates = [
            ("1", "电视剧"),
            ("2", "电影"),
            ("3", "动漫"),
            ("4", "综艺"),
            ("5", "短剧"),
        ]
        self._filters_cache = None
        try:
            self.proxy_base = self.getProxyUrl(local=True)
        except Exception:
            self.proxy_base = ""

    # ---------------- 基础请求 ----------------
    def _fetch(self, url, referer=None):
        headers = {}
        if referer:
            headers["Referer"] = referer
        r = self.session.get(url, timeout=20, headers=headers or None)
        r.encoding = "utf-8"
        return r.text

    # ---------------- 图片本地代理包装 ----------------
    def _wrap_pic(self, url):
        if not url:
            return ""
        if not self.proxy_base:
            return url
        try:
            b64 = base64.b64encode(url.encode()).decode()
            return "{}&m=img&u={}".format(self.proxy_base, b64)
        except Exception:
            return url

    # ---------------- 列表解析 ----------------
    def _parse_cards(self, html):
        items = []
        seen = set()

        for m in re.finditer(
                r'<a\s[^>]*href="/detail/(\d+)\.html"[^>]*>(.*?)</a>',
                html, re.S):
            vid = m.group(1)
            body = m.group(2)
            if vid in seen:
                continue

            tm = re.search(
                r'<p[^>]*class="[^"]*vod-title[^"]*"[^>]*>(.*?)</p>',
                body, re.S)
            if not tm:
                tm = re.search(r'title="([^"]+)"', m.group(0))
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
            if not title:
                continue

            pm = re.search(
                r'<img[^>]*?(?:data-original|data-src|src)="([^"]+)"', body)
            pic = pm.group(1) if pm else ""
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.host + pic

            sm = re.search(
                r'<p[^>]*class="[^"]*vod-subtitle[^"]*"[^>]*>(.*?)</p>',
                body, re.S)
            sub = re.sub(r"<[^>]+>", "", sm.group(1)).strip() if sm else ""

            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._wrap_pic(pic),
                "vod_remarks": sub,
            })

        if not items:
            for m in re.finditer(
                    r'href="/detail/(\d+)\.html"[^>]*>.*?<img[^>]*src="([^"]+)"',
                    html, re.S):
                vid, pic = m.group(1), m.group(2)
                if vid in seen:
                    continue
                tpart = html[m.end():m.end() + 800]
                tm = re.search(
                    r'<p[^>]*class="[^"]*vod-title[^"]*"[^>]*>(.*?)</p>',
                    tpart, re.S)
                title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
                if not title:
                    continue
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.host + pic
                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._wrap_pic(pic),
                    "vod_remarks": "",
                })
        return items

    # ---------------- 分页数解析 ----------------
    def _parse_pagecount(self, html, pg):
        pages = []
        for m in re.finditer(r'[?&]page=(\d+)', html):
            try:
                pages.append(int(m.group(1)))
            except Exception:
                pass
        m = re.search(
            r'href="[^"]*[?&]page=(\d+)"[^>]*>\s*(?:末页|尾页)', html)
        if m:
            try:
                pages.append(int(m.group(1)))
            except Exception:
                pass
        return max(pages) if pages else pg

    # ---------------- 筛选项 ----------------
    def _fetch_filters(self, tid):
        import html as htmlmod
        try:
            html = htmlmod.unescape(
                self._fetch("{0}/filter?channel={1}".format(self.host, tid)))
        except Exception:
            return []
        rows = re.findall(
            r'<span class="filter-label">(.*?)</span>\s*'
            r'<div class="filter-options">(.*?)</div>', html, re.S)
        label_key = {"类型": "type", "地区": "area", "年份": "year"}
        filters = []
        for label, opts in rows:
            key = label_key.get(label.strip())
            if not key:
                continue
            values = [{"n": "全部", "v": ""}]
            seen_v = {""}
            for m in re.finditer(
                    r'href="/filter\?channel=\d+[^"]*?&%s=([^"&]*)[^"]*"[^>]*>([^<]+)</a>'
                    % key, opts):
                v = unquote(m.group(1))
                n = m.group(2).strip()
                if v not in seen_v:
                    seen_v.add(v)
                    values.append({"n": n, "v": v})
            if len(values) > 1:
                filters.append({"key": key, "name": label.strip(),
                                "value": values})
        filters.append({
            "key": "sort", "name": "排序",
            "value": [
                {"n": "最新", "v": "new"},
                {"n": "最热", "v": "hot"},
                {"n": "评分", "v": "score"},
            ]
        })
        return filters

    def homeContent(self, filter=False):
        result = {
            "class": [{"type_id": cid, "type_name": name}
                      for cid, name in self.cates],
        }
        if filter:
            if self._filters_cache is None:
                fs_all = {}
                for cid, _name in self.cates:
                    fs = self._fetch_filters(cid)
                    if fs:
                        fs_all[cid] = fs
                self._filters_cache = fs_all
            result["filters"] = self._filters_cache
        return result

    def homeVideoContent(self):
        try:
            return {"list": self._parse_cards(self._fetch(self.host + "/"))}
        except Exception:
            return {"list": []}

    def _get_extend(self, extend, key):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                return ""
        v = (extend or {}).get(key, "")
        return unquote(v) if isinstance(v, str) else ""

    def categoryContent(self, tid, pg, filter=False, extend={}):
        pg = int(pg)
        ftype = self._get_extend(extend, "type")
        farea = self._get_extend(extend, "area")
        fyear = self._get_extend(extend, "year")
        fsort = self._get_extend(extend, "sort") or "hot"
        url = ("{0}/filter?channel={1}&type={2}&area={3}&year={4}"
               "&sort={5}&page={6}".format(
                   self.host, tid, quote(ftype, safe=""),
                   quote(farea, safe=""), quote(fyear, safe=""),
                   quote(fsort, safe=""), pg))
        try:
            html = self._fetch(url)
        except Exception:
            return {"list": [], "page": pg, "pagecount": 0,
                    "limit": 12, "total": 0}
        items = self._parse_cards(html)
        pagecount = self._parse_pagecount(html, pg)
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 12, "total": pagecount * 12}

    # ---------------- 详情（简介已重点加固） ----------------
    def detailContent(self, ids):
        vid = re.search(r"(\d+)", ids[0]).group(1)
        try:
            html = self._fetch("{0}/detail/{1}.html".format(self.host, vid))
        except Exception:
            return {"list": []}

        title = pic = desc = actor = director = year = genre = ""
        lang = area = ""

        # 1) 解析 JSON-LD
        for m in re.finditer(
                r'<script type="application/ld\+json">(.*?)</script>',
                html, re.S):
            try:
                obj = json.loads(m.group(1))
            except Exception:
                continue
            candidates = []
            if isinstance(obj, dict):
                if isinstance(obj.get("@graph"), list):
                    candidates.extend(obj["@graph"])
                else:
                    candidates.append(obj)
            elif isinstance(obj, list):
                candidates.extend(obj)
            for tv in candidates:
                if not isinstance(tv, dict):
                    continue
                if not title and tv.get("name"):
                    title = str(tv["name"])
                if not pic and tv.get("image"):
                    img = tv["image"]
                    if isinstance(img, list):
                        img = img[0] if img else ""
                    if isinstance(img, dict):
                        img = img.get("url", "")
                    pic = img or pic
                if not desc and tv.get("description"):
                    desc = str(tv["description"])
                if not actor and tv.get("actor"):
                    a = tv["actor"]
                    if isinstance(a, list):
                        actor = "/".join(
                            x.get("name", "") if isinstance(x, dict) else str(x)
                            for x in a)
                    elif isinstance(a, dict):
                        actor = a.get("name", "")
                    else:
                        actor = str(a)
                if not director and tv.get("director"):
                    d = tv["director"]
                    if isinstance(d, list):
                        director = "/".join(
                            x.get("name", "") if isinstance(x, dict) else str(x)
                            for x in d)
                    elif isinstance(d, dict):
                        director = d.get("name", "")
                    else:
                        director = str(d)
                if not year and tv.get("datePublished"):
                    year = str(tv["datePublished"])[:4]
                if not genre and tv.get("genre"):
                    g = tv["genre"]
                    if isinstance(g, list):
                        genre = "/".join(str(x) for x in g)
                    else:
                        genre = str(g)

        # 2) HTML 兜底
        if not title:
            tm = re.search(
                r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>(.*?)</h1>',
                html, re.S)
            if not tm:
                tm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""

        if not pic:
            pm = re.search(
                r'<img[^>]*class="[^"]*detail-pic[^"]*"[^>]*src="([^"]+)"',
                html)
            if not pm:
                pm = re.search(
                    r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"', html)
            if pm:
                pic = pm.group(1)
        if pic:
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.host + pic
            pic = self._wrap_pic(pic)

        # ================= 简介强化提取区 =================
        if not desc:
            # 1. 优先匹配特定容器类名 (兼容 ocean/苹果/极速等模板)
            dm = re.search(
                r'<div[^>]*class="[^"]*(?:detail-desc|vod-content|vod_content|detail-content|desc|content)[^"]*"[^>]*>(.*?)</div>',
                html, re.S)
            if not dm:
                # 2. 匹配 "剧情介绍" / "简介" 关键词后面的内容
                dm = re.search(
                    r'(?:剧情介绍|简介|剧情)[：:]\s*(?:</span>)?\s*(?:<p[^>]*>|<div[^>]*>)?(.*?)(?:</div>|</p>|<div|详情|立即播放|$)', 
                    html, re.S)
            
            if dm:
                desc = dm.group(1)
                # 剔除 HTML 标签
                desc = re.sub(r"<[^>]+>", "", desc)
                # 替换常见的 HTML 实体
                desc = desc.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
                
                # 【核心】强制切断底部导航和剧集列表文本
                for stop_word in ['详情', '立即播放', '报错', '收藏', '扫一扫', '排序', '播放地址', '第01集', '第1集']:
                    if stop_word in desc:
                        desc = desc.split(stop_word)[0]
                
                # 清理多余空白
                desc = re.sub(r'\s+', ' ', desc).strip()
        # ===================================================

        # 3) 线路 tab + 剧集
        tabs = re.findall(
            r'data-target="(source-\d+)">([^<]+)</button>', html)
        play_from, play_url = [], []
        for tid, label in tabs:
            em = re.search(r'id="%s"(.*?)(?:id="source-|\Z)' % tid,
                           html, re.S)
            if not em:
                continue
            seg = em.group(1)
            eps = re.findall(
                r'href="/vodplay/\d+-([a-z0-9]+)-(\d+)\.html"[^>]*>([^<]{1,32})</a>',
                seg, re.S)
            if not eps:
                continue
            play_from.append(label.strip())
            play_url.append("#".join(
                "{0}${1}|{2}|{3}".format(
                    re.sub(r"<[^>]+>", "", name).strip(),
                    vid, pf, idx)
                for pf, idx, name in eps))

        # 4) 兜底
        if not play_from:
            all_eps = re.findall(
                r'href="/vodplay/(\d+)-([a-z0-9]+)-(\d+)\.html"[^>]*>([^<]{1,32})</a>',
                html, re.S)
            groups = {}
            for _vid, pf, idx, name in all_eps:
                groups.setdefault(pf, []).append((idx, name))
            for pf, lst in groups.items():
                play_from.append(pf)
                play_url.append("#".join(
                    "{0}${1}|{2}|{3}".format(
                        re.sub(r"<[^>]+>", "", name).strip(),
                        vid, pf, idx)
                    for idx, name in lst))

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_remarks": genre,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick=False, pg=1):
        pg = int(pg)
        url = "{0}/search?q={1}&page={2}".format(
            self.host, quote(key), pg)
        try:
            html = self._fetch(url)
        except Exception:
            return {"list": []}
        items = self._parse_cards(html)
        pagecount = self._parse_pagecount(html, pg)
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 12, "total": pagecount * 12}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags=None):
        if isinstance(id, list):
            id = id[0]
        if "$" in id:
            id = id.split("$")[-1]
        try:
            vid, play_from, index = id.split("|")
        except Exception:
            return {"parse": 0, "url": "", "header": {}}

        api = ("{0}/api/play-url?vodId={1}&playFrom={2}&index={3}"
               .format(self.host, vid, play_from, index))
        try:
            r = self.session.get(api, timeout=20)
            data = r.json()
            url = data.get("url", "") or \
                (data.get("data", {}) or {}).get("url", "")
            if url:
                if url.startswith("//"):
                    url = "https:" + url
                header = {
                    "User-Agent": self.session.headers.get("User-Agent", ""),
                    "Referer": "{0}/vodplay/{1}-{2}-{3}.html".format(
                        self.host, vid, play_from, index),
                }
                if ".m3u8" in url or ".mp4" in url:
                    return {"parse": 0, "url": url, "header": header}
                return {"parse": 1, "url": url, "header": header}
        except Exception:
            pass
        return {"parse": 0, "url": "", "header": {}}

    # ---------------- 本地代理（图片） ----------------
    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                q = parse_qs(param)
                param = {k: v[0] for k, v in q.items() if v}
        if isinstance(param, dict) and param.get("m") == "img":
            try:
                url = base64.b64decode(param.get("u", "")).decode()
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self.session.headers.get("User-Agent", ""),
                        "Referer": self.host + "/",
                    })
                data = urllib.request.urlopen(req, timeout=15).read()
                mime = "image/jpeg"
                lu = url.lower()
                if ".webp" in lu:
                    mime = "image/webp"
                elif ".png" in lu:
                    mime = "image/png"
                elif ".gif" in lu:
                    mime = "image/gif"
                return [200, {"Content-Type": mime}, data]
            except Exception:
                return [404, {"Content-Type": "text/plain"}, b""]
        return [200, {"Content-Type": "text/plain"}, b""]
