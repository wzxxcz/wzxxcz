# -*- coding: utf-8 -*-
# 极速追剧 (jisuzhuiju.com) TVBox 蜘蛛
# 常规影视站: 电视剧/电影/动漫/综艺/短剧
# 列表走 /filter?channel=N 分页; 详情 /detail/{id}.html;
# 播放经服务端 API /api/play-url?vodId=&playFrom=&index= 解析出 m3u8 直链
# 本文件含站点抓取逻辑, 请勿外传
from base.spider import Spider as _Spider
import re
import json
import requests
from urllib.parse import quote, unquote


class Spider(_Spider):
    def init(self, extend=""):
        self.host = "https://jisuzhuiju.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        })
        self.cates = [
            ("1", "电视剧"),
            ("2", "电影"),
            ("3", "动漫"),
            ("4", "综艺"),
            ("5", "短剧"),
        ]

    def _fetch(self, url):
        r = self.session.get(url, timeout=20)
        r.encoding = "utf-8"
        return r.text

    def _parse_cards(self, html):
        items = []
        seen = set()
        for m in re.finditer(
                r'<a href="/detail/(\d+)\.html"[^>]*>.*?'
                r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*?)(?:封面图片)?".*?'
                r'<p class="vod-title[^"]*">(.*?)</p>',
                html, re.S):
            vid, pic, _alt, title = m.group(1), m.group(2), m.group(3), m.group(4)
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title or vid in seen:
                continue
            seen.add(vid)
            sub = ""
            sm = re.search(r'<p class="vod-subtitle[^"]*">(.*?)</p>',
                           m.group(0), re.S)
            if sm:
                sub = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": sub,
            })
        return items

    def _fetch_filters(self, tid):
        # 动态抓取某频道的二级筛选项: 类型/地区/年份 (type 值各频道不同)
        import html as htmlmod
        from urllib.parse import unquote
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
        return filters

    def homeContent(self, filter=False):
        result = {
            "class": [{"type_id": cid, "type_name": name}
                      for cid, name in self.cates],
        }
        if filter:
            filters = {}
            for cid, _name in self.cates:
                fs = self._fetch_filters(cid)
                if fs:
                    filters[cid] = fs
            if filters:
                result["filters"] = filters
        return result

    def homeVideoContent(self):
        try:
            return {"list": self._parse_cards(self._fetch(self.host + "/"))}
        except Exception:
            return {"list": []}

    def _get_extend(self, extend, key):
        # 兼容 dict 与 JSON 字符串两种 extend
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
        url = ("{0}/filter?channel={1}&type={2}&area={3}&year={4}"
               "&sort=hot&page={5}".format(
                   self.host, tid, quote(ftype, safe=""),
                   quote(farea, safe=""), quote(fyear, safe=""), pg))
        try:
            html = self._fetch(url)
        except Exception:
            return {"list": [], "page": pg, "pagecount": 0,
                    "limit": 12, "total": 0}
        items = self._parse_cards(html)
        pagecount = pg + 1 if len(items) >= 12 else pg
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 12, "total": pagecount * 12}

    def detailContent(self, ids):
        vid = re.search(r"(\d+)", ids[0]).group(1)
        try:
            html = self._fetch("{0}/detail/{1}.html".format(self.host, vid))
        except Exception:
            return {"list": []}
        # JSON-LD 取元数据
        title, pic, desc, actor, director, year, genre = "", "", "", "", "", "", ""
        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        if m:
            try:
                tv = json.loads(m.group(1))["@graph"][1]
                title = tv.get("name", "")
                pic = tv.get("image", "")
                desc = tv.get("description", "")
                actor = tv.get("actor", "")
                director = tv.get("director", "")
                year = str(tv.get("datePublished", ""))
                genre = tv.get("genre", "")
            except Exception:
                pass
        if not title:
            tm = re.search(r'<h1 class="detail-title">(.*?)</h1>', html, re.S)
            title = tm.group(1).strip() if tm else ""
        # 线路 tab: label -> playFrom
        tabs = re.findall(r'data-target="(source-\d+)">([^<]+)</button>', html)
        play_from, play_url = [], []
        for tid, label in tabs:
            pm = re.search(
                r'id="%s".{0,600}?href="/vodplay/\d+-([a-z0-9]+)-\d+\.html"'
                % tid, html, re.S)
            if not pm:
                continue
            play_from.append(label.strip())
            em = re.search(r'id="%s"(.*?)(?:id="source-|\Z)' % tid, html, re.S)
            eps = re.findall(
                r'href="/vodplay/\d+-[a-z0-9]+-(\d+)\.html"[^>]*>([^<]{1,16})</a>',
                em.group(1), re.S) if em else []
            play_url.append("#".join(
                "{0}${1}|{2}|{3}".format(name.strip(), vid, pm.group(1), idx)
                for idx, name in eps))
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_year": year,
            "vod_area": "",
            "vod_remarks": genre,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg=1):
        url = "{0}/search?q={1}".format(self.host, quote(key))
        try:
            html = self._fetch(url)
        except Exception:
            return {"list": []}
        return {"list": self._parse_cards(html)}

    def playerContent(self, flag, id, vipFlags):
        # id: vid|playFrom|index
        try:
            vid, play_from, index = id.split("|")
            api = ("{0}/api/play-url?vodId={1}&playFrom={2}&index={3}"
                   .format(self.host, vid, play_from, index))
            r = self.session.get(api, timeout=20)
            data = r.json()
            url = data.get("url", "")
            if url:
                return {"parse": 0, "url": url,
                        "header": {"Referer": self.host + "/"}}
        except Exception:
            pass
        return {"parse": 0, "url": ""}

    def localProxy(self, param):
        return None
