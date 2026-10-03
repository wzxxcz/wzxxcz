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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
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
            am = re.search(
                r'<a\b[^>]*class="(?:vodlist_thumb|balist_thumb)[^"]*"[^>]*>',
                block)
            if not am:
                continue
            tag = am.group(0)
            hm = re.search(r'href="(/subject/[^"]+?)(?:\.html)?"', tag)
            tm = re.search(r'title="([^"]*)"', tag)
            if not hm or not tm:
                continue
            vid = hm.group(1).replace("/subject/", "").strip("/")
            if not vid or vid in seen:
                continue
            seen.add(vid)

            # 图片：优先 data-original，其次 style url()，再 src
            sm = re.search(r'data-original="([^"]+)"', tag)
            if not sm:
                sm = re.search(r"url\([\'\"]?([^)\'\"]+)", tag)
            if not sm:
                sm = re.search(r'data-src="([^"]+)"', tag)
            if not sm:
                sm = re.search(r'src="([^"]+)"', tag)

            # 备注：在 li 块内查找
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
            seen_v = {""}
            for href, nm in re.findall(
                    r'<a[^>]*href="(/show/[^"]+)"[^>]*>([^<]+)</a>', block):
                v = self._slot_value(href, idx)
                nm = nm.strip()
                if nm and nm != "全部" and v not in seen_v:
                    seen_v.add(v)
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
            seen_v = {""}
            for href, nm in re.findall(r'href="(/show/[^"]+)"[^>]*>([^<]+)</a>', m.group(0)):
                v = self._slot_value(href, 2)
                nm = nm.strip()
                if nm and v not in seen_v:
                    seen_v.add(v)
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
        ext = extend if isinstance(extend, dict) else {}
        area = (ext.get("area") or "").strip()
        by = (ext.get("by") or "").strip()
        cls = (ext.get("class") or "").strip()
        year = (ext.get("year") or "").strip()
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
            url = self._show_url(cid, pg, extend or {})
            html = self._fetch(url)
            vods = self._parse_cards(html)
            pagecount = 1
            m = re.search(r"共有\s*(\d+)\s*页", html)
            if m:
                pagecount = int(m.group(1))
            else:
                allp = re.findall(r'[?&/]page[/=](\d+)', html)
                if allp:
                    pagecount = max(int(p) for p in allp)
                elif len(vods) < 20:
                    pagecount = pg
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[%s] categoryContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ---------- 简介提取（强化） ----------
    def _extract_desc(self, html):
        desc = ""
        patterns = [
            r'<li\s+class="[^"]*desc[^"]*"[^>]*>(.*?)</li>',
            r'<div[^>]*class="[^"]*(?:content_desc|content-desc|vod-content|vod_content|detail-content|desc|sketch)[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*(?:desc|content|detail)[^"]*"[^>]*>(.*?)</p>',
            r'<span[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</span>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m and m.group(1).strip():
                desc = m.group(1)
                break

        # 兜底：从"剧情介绍/简介/剧情"关键词开始
        if not desc:
            m = re.search(
                r'(?:剧情介绍|简介|剧情)[：:]\s*(?:</span>)?\s*(?:<p[^>]*>|<div[^>]*>)?(.*?)'
                r'(?:</div>|</p>|<div|详情|立即播放|$)',
                html, re.S)
            if m:
                desc = m.group(1)

        if not desc:
            return ""

        # 去 HTML 标签
        desc = re.sub(r'<[^>]+>', '', desc)
        # 替换 HTML 实体
        desc = (desc.replace('&nbsp;', ' ').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'")
                    .replace('&lt;', '<').replace('&gt;', '>'))
        # 强制切断底部导航 / 播放列表误抓文本
        for stop_word in ['详情', '立即播放', '报错', '收藏', '扫一扫',
                          '排序', '播放地址', '第01集', '第1集', '百度网盘',
                          '版权声明', '免责声明']:
            if stop_word in desc:
                desc = desc.split(stop_word)[0]
        # 清理空白
        desc = re.sub(r'\s+', ' ', desc).strip()
        return desc[:2000]

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vods = []
        try:
            vid = (ids[0] if ids else "").strip().strip("/")
            if not vid:
                return {"list": []}
            html = self._fetch("%s/subject/%s.html" % (self.host, vid))
            if not html:
                return {"list": []}

            vod = {"vod_id": vid}

            # 标题
            m = re.search(r'<h2 class="title">\s*([^<]+?)\s*</h2>', html, re.S)
            if not m:
                m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
            if not m:
                m = re.search(r'<h[12][^>]*>(.*?)</h[12]>', html, re.S)
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else vid

            # 封面
            m = re.search(r'content_thumb.*?url\([\'\"]?([^)\'\"]+)', html, re.S)
            if not m:
                m = re.search(r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"', html)
            vod["vod_pic"] = self._abs(m.group(1).strip() if m else "")

            # 备注（豆瓣分或状态）
            m = re.search(r'<span class="data_style">\s*([^<]+?)\s*</span>', html, re.S)
            vod["vod_remarks"] = m.group(1).strip() if m else ""

            # ===================== 简介 =====================
            vod["vod_content"] = self._extract_desc(html)
            # ==================================================

            # 演员 / 导演（兼容多种路径）
            actors = re.findall(r'/search/actor/[^"]*"[^>]*>([^<]+)</a>', html)
            if not actors:
                actors = re.findall(r'/vod/search/actor[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_actor"] = ",".join(dict.fromkeys(a.strip() for a in actors if a.strip()))[:200]

            directors = re.findall(r'/search/director/[^"]*"[^>]*>([^<]+)</a>', html)
            if not directors:
                directors = re.findall(r'/vod/search/director[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_director"] = ",".join(dict.fromkeys(d.strip() for d in directors if d.strip()))[:200]

            # 年份 / 地区 / 类型 / 语言（从字段区抓）
            def _field(label):
                pat = r'{}[：:]\s*(?:</span>)?\s*(?:<a[^>]*>)?(.*?)(?:</a>|<br|<p|</div|</li|</span>|$)'.format(label)
                mm = re.search(pat, html, re.S)
                if mm:
                    t = re.sub(r'<[^>]+>', '', mm.group(1))
                    return t.replace('&nbsp;', ' ').strip()
                return ""

            vod["vod_year"] = _field("年份") or _field("年代")
            vod["vod_area"] = _field("地区")
            vod["vod_lang"] = _field("语言")
            tname = _field("类型")
            if tname:
                vod["type_name"] = tname

            # 播放源
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

            # 兜底：直接扫全页所有 /start/ 链接
            if not play_from:
                all_eps = re.findall(
                    r'<a[^>]*href="(/start/(\d+)-([a-z0-9]+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                    html)
                groups = {}
                for href, _vid, sid, _nid, nm in all_eps:
                    groups.setdefault(sid, []).append(
                        ("%s$%s" % (nm.strip() or "正片", self._abs(href))))
                for sid in sorted(groups.keys()):
                    play_from.append("线路%s" % sid)
                    play_url.append("#".join(x[0] for x in groups[sid]))

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

    # ---------- 播放地址还原（保留原算法） ----------
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
            if "$" in pid:
                pid = pid.split("$")[-1]
            if not pid:
                return result
            if pid.startswith("http") and ".m3u8" in pid:
                result["url"] = pid
            else:
                page_url = pid if pid.startswith("http") else self._abs(pid)
                html = self._fetch(page_url)
                # 兼容 let / var / const / 无声明
                m = re.search(
                    r'(?:let|var|const)?\s*player_data\s*=\s*\{.*?"url"\s*:\s*"([^"]+)"',
                    html, re.S)
                if m:
                    url = self._decode_play_url(m.group(1))
                    if url:
                        result["url"] = url
                # 兜底：直接从 HTML 里找 m3u8
                if not result["url"]:
                    mm = re.search(r'(https?:[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
                    if mm:
                        result["url"] = mm.group(1).replace("\\/", "/")
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
