# -*- coding: utf-8 -*-
# 达达兔影院 https://kshaodj.com/ TVBox 蜘蛛
# MacCMS style1 模板站：5 分类动态；列表 /show/{id}-{area}-{by}-{class}-----{page}---{year}.html；
# 详情 /subject/{id}.html；播放 /start/{id}-{sid}-{nid}.html；
# 播放地址藏在 player_data.url，经 "yMc"+首字母大写混淆的 base64，还原即 m3u8 直链
import re
import json
import base64
import itertools
from urllib.parse import quote, unquote
import requests
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "达达兔影院"

    def init(self, extend=""):
        self.host = "https://kshaodj.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        })
        self._filter_cache = {}
        return {}

    CATS = [
        ("dianying", "电影"),
        ("lianxuju", "连续剧"),
        ("duanju", "短剧"),
        ("dongman", "动漫"),
        ("zongyi", "综艺"),
    ]

    # ---------- 基础 ----------
    def _fetch(self, url, params=None):
        try:
            r = self.session.get(url, params=params, timeout=20)
            if r.status_code != 200:
                return ""
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self.host + (u if u.startswith("/") else "/" + u)

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        vods = []
        seen = set()
        for m in re.finditer(
                r'<li class="(?:vodlist_item|searchlist_item|balist_item)[^"]*"[^>]*>(.*?)</li>',
                html, re.S):
            block = m.group(1)
            am = re.search(r'<a\b[^>]*class="(?:vodlist_thumb|balist_thumb)[^"]*"[^>]*>', block)
            if not am:
                continue
            tag = am.group(0)
            hm = re.search(r'href="(/subject/[^"]+?)(?:\.html)?"', tag)
            tm = re.search(r'title="([^"]*)"', tag)
            sm = re.search(r"url\([\'\"]?([^)\'\"]+)", tag)
            if not hm or not tm:
                continue
            vid = hm.group(1).replace("/subject/", "").strip("/")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            rm = re.search(r'<span class="pic_text[^"]*">([^<]*)</span>', block)
            vods.append({
                "vod_id": vid,
                "vod_name": tm.group(1).strip(),
                "vod_pic": self._abs(sm.group(1).strip() if sm else ""),
                "vod_remarks": (rm.group(1).strip() if rm else ""),
            })
        return vods

    # ---------- 二级分类 ----------
    def _slot_value(self, href, idx):
        try:
            seg = unquote(href).split("/show/", 1)[1].rsplit(".html", 1)[0].split("-")
            return seg[idx] if len(seg) > idx else ""
        except Exception:
            return ""

    def _load_filters(self, cid):
        if cid in self._filter_cache:
            return self._filter_cache[cid]
        html = self._fetch("%s/show/%s-----------.html" % (self.host, cid))
        groups = []

        def opts(block, idx, key, name):
            items = [{"n": "全部", "v": ""}]
            for href, nm in re.findall(
                    r'<a[^>]*href="(/show/[^"]+)"[^>]*>([^<]+)</a>', block):
                v = self._slot_value(href, idx)
                nm = nm.strip()
                if nm and nm != "全部" and all(x["n"] != nm for x in items):
                    items.append({"n": nm, "v": v})
            if len(items) > 1:
                groups.append({"key": key, "name": name, "value": items})

        m = re.search(r'id="hl02".*?</ul>', html, re.S)
        if m:
            opts(m.group(0), 3, "class", "类型")
        m = re.search(r'id="hl03".*?</ul>', html, re.S)
        if m:
            opts(m.group(0), 1, "area", "地区")
        m = re.search(r'id="hl04".*?</ul>', html, re.S)
        if m:
            opts(m.group(0), 11, "year", "年份")
        m = re.search(r'screen_list sx_tz.*?</ul>', html, re.S)
        if m:
            items = [{"n": "全部", "v": ""}]
            for href, nm in re.findall(r'href="(/show/[^"]+)"[^>]*>([^<]+)</a>', m.group(0)):
                v = self._slot_value(href, 2)
                nm = nm.strip()
                if nm and all(x["n"] != nm for x in items):
                    items.append({"n": nm, "v": v})
            if len(items) > 1:
                groups.insert(0, {"key": "by", "name": "排序", "value": items})
        self._filter_cache[cid] = groups
        return groups

    def homeContent(self, filter=False):
        classes = [{"type_id": cid, "type_name": cn} for cid, cn in self.CATS]
        result = {"class": classes}
        if filter:
            filters = {}
            for cid, _ in self.CATS:
                groups = self._load_filters(cid)
                if groups:
                    filters[cid] = groups
            if filters:
                result["filters"] = filters
        return result

    def homeVideoContent(self):
        html = self._fetch(self.host + "/")
        return {"list": self._parse_cards(html), "parse": 0, "jx": 0}

    def _show_url(self, cid, pg, extend):
        area = (extend.get("area") or "") if isinstance(extend, dict) else ""
        by = (extend.get("by") or "") if isinstance(extend, dict) else ""
        cls = (extend.get("class") or "") if isinstance(extend, dict) else ""
        year = (extend.get("year") or "") if isinstance(extend, dict) else ""
        segs = [cid, area, by, cls, "", "", "", "",
                str(pg) if pg > 1 else "", "", "", year]
        return "%s/show/%s.html" % (self.host, "-".join(segs))

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            cid = tid if any(tid == c for c, _ in self.CATS) else "dianying"
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            html = self._fetch(self._show_url(cid, pg, extend or {}))
            vods = self._parse_cards(html)
            pagecount = 1
            m = re.search(r"共有\s*(\d+)\s*页", html)
            if m:
                pagecount = int(m.group(1))
            elif len(vods) < 20:
                pagecount = pg
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[%s] categoryContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    def detailContent(self, ids):
        vods = []
        try:
            vid = (ids[0] if ids else "").strip().strip("/")
            html = self._fetch("%s/subject/%s.html" % (self.host, vid))
            if not html:
                return {"list": []}
            vod = {"vod_id": vid}

            m = re.search(r'<h2 class="title">\s*([^<]+?)\s*</h2>', html, re.S)
            vod["vod_name"] = m.group(1).strip() if m else vid
            m = re.search(r'content_thumb.*?url\([\'\"]?([^)\'\"]+)', html, re.S)
            vod["vod_pic"] = self._abs(m.group(1).strip() if m else "")

            m = re.search(r'<span class="data_style">\s*([^<]+?)\s*</span>', html, re.S)
            vod["vod_remarks"] = m.group(1).strip() if m else ""
            m = re.search(r'<li class="desc[^"]*">(.*?)</li>', html, re.S)
            if m:
                vod["vod_content"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            actors = re.findall(r'/vod/search/actor/[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_actor"] = ",".join(dict.fromkeys(a.strip() for a in actors))[:200]
            directors = re.findall(r'/vod/search/director/[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_director"] = ",".join(dict.fromkeys(d.strip() for d in directors))[:200]

            # 播放源：#NumTab 的 alt 顺序对应 #aaa 内 play_list_box 顺序；
            # 每个 box 有 notfull/full 两份相同 ul，取偶数位去重
            play_from, play_url = [], []
            tm = re.search(
                r'<div class="play_source_tab[^"]*" id="NumTab">(.*?)</div>',
                html, re.S)
            am = re.search(
                r'<div class="play_source" id="aaa">(.*?)</div>\s*<script',
                html, re.S)
            if tm and am:
                sources = re.findall(r'alt="([^"]+)"', tm.group(1))
                uls = re.findall(r'<ul class="content_playlist[^"]*">(.*?)</ul>',
                                 am.group(1), re.S)
                for src, ul in zip(sources, uls[0::2]):
                    eps = []
                    for href, nm in re.findall(
                            r'<a href="(/start/[^"]+)">([^<]*)</a>', ul):
                        nm = nm.strip() or href.rsplit("-", 1)[-1].replace(".html", "")
                        eps.append("%s$%s" % (nm, self._abs(href)))
                    if eps:
                        play_from.append(src)
                        play_url.append("#".join(eps))
            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)
            vods.append(vod)
        except Exception as e:
            print("[%s] detailContent 异常: %s" % (self.getName(), e))
        return {"list": vods}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            html = self._fetch("%s/vod/search.html" % self.host,
                               params={"wd": key})
            vods = self._parse_cards(html)
            return {"list": vods, "page": pg, "pagecount": 1,
                    "limit": 90, "total": len(vods)}
        except Exception as e:
            print("[%s] searchContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ---------- 播放地址还原 ----------
    def _decode_play_url(self, enc):
        """player_data.url 还原：每 12 个 base64 字符插入 yMc+首字母大写"""
        b64 = (enc or "").split("&")[0]
        parts = re.split(r"yMc(.)", b64)
        chunks, marks = parts[::2], parts[1::2]
        if not marks:
            try:
                raw = base64.b64decode(b64 + "=" * (-len(b64) % 4))
                if raw.startswith(b"http"):
                    return raw.decode()
            except Exception:
                pass
            return ""
        options = []
        for mch in marks:
            opts = [mch]
            if mch.isalpha():
                lo = mch.lower()
                if lo != mch:
                    opts.append(lo)
            options.append(opts)
        for combo in itertools.product(*options):
            cand = chunks[0]
            for ch, c in zip(combo, chunks[1:]):
                cand += ch + c
            try:
                raw = base64.b64decode(cand + "=" * (-len(cand) % 4))
            except Exception:
                continue
            if (raw.startswith(b"http") and b".m3u8" in raw
                    and all(32 <= x < 127 for x in raw)):
                return raw.decode()
        return ""

    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            pid = (id or "").strip()
            if not pid:
                return result
            if pid.startswith("http") and ".m3u8" in pid:
                result["url"] = pid
            else:
                page_url = pid if pid.startswith("http") else self._abs(pid)
                html = self._fetch(page_url)
                m = re.search(r'let player_data=\{.*?"url":"([^"]+)"', html)
                if m:
                    url = self._decode_play_url(m.group(1))
                    if url:
                        result["url"] = url
            if result["url"]:
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
            return result
        except Exception as e:
            print("[%s] playerContent 异常: %s" % (self.getName(), e))
            return result

    def isVideoFormat(self, url):
        return bool(url) and ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", ""]
