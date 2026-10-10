# -*- coding: utf-8 -*-
import sys
import re
import requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://dsystv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host
        }

    def getName(self):
        return "袋鼠影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 首页 & 筛选 ====================

    def _common_filters(self):
        AREA = [("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
                ("日本", "日本"), ("韩国", "韩国"), ("美国", "美国"), ("英国", "英国"),
                ("法国", "法国"), ("泰国", "泰国"), ("印度", "印度"),
                ("加拿大", "加拿大"), ("西班牙", "西班牙")]
        YUYAN = [("全部", ""), ("国语", "国语"), ("粤语", "粤语"), ("英语", "英语"),
                 ("日语", "日语"), ("韩语", "韩语"), ("泰语", "泰语"),
                 ("法语", "法语"), ("西班牙语", "西班牙语")]
        YEAR = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2011, -1)] + \
               [("其他年份", "more"), ("年份未知", "unknown")]
        LETTER = [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]
        ORDER = [("按时间", "time"), ("按人气", "hit"), ("按推荐", "commend"), ("按评分", "douban")]
        JQ = [("全部", ""), ("剧情", "剧情"), ("喜剧", "喜剧"), ("动作", "动作"), ("爱情", "爱情"),
              ("科幻", "科幻"), ("动画", "动画"), ("悬疑", "悬疑"), ("惊悚", "惊悚"), ("恐怖", "恐怖"),
              ("犯罪", "犯罪"), ("同性", "同性"), ("音乐", "音乐"), ("歌舞", "歌舞"), ("传记", "传记"),
              ("历史", "历史"), ("西部", "西部"), ("奇幻", "奇幻"), ("冒险", "冒险"), ("灾难", "灾难"),
              ("武侠", "武侠"), ("情色", "情色"), ("旅游", "旅游")]

        def V(items):
            return [{"n": n, "v": v} for n, v in items]

        return [
            {"key": "jq",     "name": "剧情", "value": V(JQ)},
            {"key": "area",   "name": "地区", "value": V(AREA)},
            {"key": "year",   "name": "年份", "value": V(YEAR)},
            {"key": "yuyan",  "name": "语言", "value": V(YUYAN)},
            {"key": "letter", "name": "字母", "value": V(LETTER)},
            {"key": "order",  "name": "排序", "value": V(ORDER)},
        ]

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1",  "type_name": "电影"},
                {"type_id": "2",  "type_name": "电视剧"},
                {"type_id": "3",  "type_name": "综艺"},
                {"type_id": "4",  "type_name": "动漫"},
                {"type_id": "44", "type_name": "短剧"},
            ],
            "filters": {
                "1":  self._common_filters(),
                "2":  self._common_filters(),
                "3":  self._common_filters(),
                "4":  self._common_filters(),
                "44": self._common_filters(),
            }
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend or {}

        def valid(v):
            if v is None:
                return False
            s = str(v).strip()
            return s not in ("", "全部", "0", "None")

        # 收集有效筛选参数（不含 tid）
        params = []
        for k in ("jq", "area", "year", "yuyan", "letter", "order"):
            v = ext.get(k)
            if valid(v):
                params.append((k, str(v)))

        has_filter = len(params) > 0

        # 无筛选 + 第 1 页 → 走原始能跑的路径
        if not has_filter and str(pg) == "1":
            url = self.host + "/frim/index" + str(tid) + ".html"
        else:
            # 有筛选或翻页 → 走 search.php
            all_parts = [("searchtype", "5"), ("tid", str(tid)), ("page", str(pg))] + params
            qs = "&".join("{0}={1}".format(k, quote(str(v))) for k, v in all_parts)
            url = self.host + "/search.php?" + qs

        html = self.get(url)
        return {
            "page": int(pg),
            "pagecount": 999,
            "limit": 24,
            "total": 999999,
            "list": self.parseList(html)
        }

    # ==================== 详情（保持原样） ====================

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(self.host + "/movie/index" + vid + ".html")

        name = self.clean(
            self.match(html, r'<h1[^>]*>(.*?)</h1>') or
            self.match(html, r'<meta property="og:title" content="(.*?)"')
        )
        name = name.replace("全集在线观看 - 国产剧 | 袋鼠影视", "").replace("全集在线观看 - 袋鼠影视", "").replace("《", "").replace("》", "").strip()

        pic = self.fix(
            self.match(html, r'<meta property="og:image" content="(.*?)"') or
            self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+(?:data-original|data-src)=["\']([^"\']+)') or
            self.match(html, r'<a[^>]+class="[^"]*videopic[^"]*"[\s\S]*?<img[^>]+src=["\']([^"\']+)')
        )

        desc = self.clean(
            self.match(html, r'<div[^>]*class=["\'][^"\']*video-plot[^"\']*["\'][^>]*>([\s\S]*?)</div>') or
            self.match(html, r'<div class="plot"[^>]*>\s*<p>(.*?)</p>') or
            self.match(html, r'<meta property="og:description" content="(.*?)"')
        )

        actor = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">主演：')
        director = self.match(html, r'<li[^>]+data-video-meta=["\']([^"\']*)["\'][^>]*><span class="text-muted">导演：')
        year = self.clean(self.match(html, r'年份：</span>([^<]+)'))
        area = self.clean(self.match(html, r'地区：</span>([^<]+)'))
        lang = self.clean(self.match(html, r'语言：</span>([^<]+)'))
        cate = self.clean(self.match(html, r'类型：</span><a[^>]*>(.*?)</a>'))
        remarks = self.clean(self.match(html, r'<span class="note textbg">(.*?)</span>'))

        play_from, play_url = self.extractPlaySources(html, vid)

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "type_name": cate,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }]
        }

    def extractPlaySources(self, html, vid):
        play_from = []
        play_url = []

        panel_sections = re.split(
            r'(?=<div[^>]+class=["\'][^"\']*panel[^"\']*["\'][^>]+data-playlist-name=)',
            html
        )
        for section in panel_sections:
            name = self.match(section, r'data-playlist-name=["\']([^"\']+)["\']')
            if not name:
                continue
            name = self.clean(name)

            ul_content = (
                self.match(section, r'<ul[^>]+class=["\'][^"\']*playlistlink[^"\']*["\'][^>]*>([\s\S]*?)</ul>') or
                self.match(section, r'<ul[^>]*>([\s\S]*?)</ul>')
            )
            eps = self.extractEpisodes(ul_content, vid) if ul_content else []

            if not eps:
                playlist_url = self.match(section, r'data-playlist-url=["\']([^"\']+)["\']')
                if playlist_url:
                    playlist_url = self.fix(playlist_url.replace('&amp;', '&'))
                    eps = self.extractEpisodes(self.get(playlist_url), vid)

            if eps:
                key = name if name not in play_from else name + str(len(play_from) + 1)
                play_from.append(key)
                play_url.append("#".join(eps))

        if not play_url:
            playlist_sections = re.split(
                r'(?=<div[^>]+class=["\'][^"\']*playlist[^"\']*["\'][^>]*>)',
                html
            )
            for i, section in enumerate(playlist_sections):
                ul_content = self.match(section, r'<ul[^>]*>([\s\S]*?)</ul>')
                if not ul_content:
                    continue
                eps = self.extractEpisodes(ul_content, vid)
                if not eps:
                    continue
                name = self.clean(
                    self.match(section, r'data-playlist-name=["\']([^"\']+)["\']') or
                    self.match(section, r'<a[^>]+class=["\'][^"\']*option[^"\']*["\'][^>]*title=["\']([^"\']+)["\']') or
                    self.match(section, r'<span class="playlist-line-name">([^<]+)</span>')
                ) or ("线路" + str(i + 1))
                key = name if name not in play_from else name + str(len(play_from) + 1)
                play_from.append(key)
                play_url.append("#".join(eps))

        if not play_url:
            eps = []
            seen = set()
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/' + vid + r'-[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
                u = self.fix(m.group(1))
                t = self.clean(m.group(2)) or "播放"
                if u and u not in seen:
                    seen.add(u)
                    eps.append(t + "$" + u)
            if eps:
                play_from.append("默认")
                play_url.append("#".join(eps))

        return play_from, play_url

    def extractEpisodes(self, html, vid=""):
        eps = []
        seen = set()
        if not html:
            return eps

        for m in re.finditer(r'<a[^>]+title=["\']([^"\']+)["\'][^>]+href=["\']([^"\']*?/play/[^"\']+)["\']', html, re.S):
            t = self.clean(m.group(1))
            u = self.fix(m.group(2))
            if t and u and u not in seen:
                seen.add(u)
                eps.append(t + "$" + u)

        if not eps:
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
                t = self.clean(m.group(2))
                u = self.fix(m.group(1))
                if t and u and u not in seen:
                    seen.add(u)
                    eps.append(t + "$" + u)

        return eps

    # ==================== 搜索 & 播放 ====================

    def searchContent(self, key, quick, pg="1"):
        url = self.host + "/search.php?searchword=" + quote(key) + "&page=" + str(pg)
        html = self.get(url)
        return {"list": self.parseList(html), "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        html = self.get(id)

        url = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']')
        if not url:
            url = self.match(html, r'player_aaaa\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"')
        if not url:
            url = self.match(html, r'["\']([^"\']+(?:m3u8|mp4|flv|avi|mkv|mov|ts)[^"\']*)["\']')
        if not url:
            url = self.match(html, r'<(?:iframe|embed|source|video)[^>]+src=["\']([^"\']+)["\']')

        url = unquote(url) if url else id

        return {
            "parse": 0 if self.isVideoFormat(url) else 1,
            "playUrl": "",
            "url": url,
            "header": self.headers
        }

    # ==================== 列表解析 ====================

    def parseList(self, html):
        res = []
        seen = set()
        for m in re.finditer(r'<a[^>]+class=["\'][^"\']*videopic[^"\']*["\'][^>]+href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\']([\s\S]{0,1200}?)</a>', html or "", re.S):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            item = m.group(0)
            name = self.clean(m.group(2))
            pics = re.findall(r'(?:data-original|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            if not pics:
                pics = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', item, re.I)
            pic = ""
            for p in pics:
                if "load.gif" not in p and "nopic" not in p and "logo" not in p and "templets" not in p:
                    pic = self.fix(p)
                    break
            remarks = self.clean(self.match(item, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>') or self.match(item, r'<span[^>]+class=["\'][^"\']*textbg[^"\']*["\'][^>]*>(.*?)</span>'))
            if name:
                res.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        if not res:
            for m in re.finditer(r'href=["\']/movie/index(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\'][\s\S]{0,1200}?<img[^>]+([^>]+)>', html or "", re.S):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                img = m.group(3)
                pic = self.match(img, r'(?:data-original|data-src)=["\']([^"\']+)["\']') or self.match(img, r'src=["\']([^"\']+)["\']')
                if "load.gif" in pic or "templets" in pic:
                    pic = ""
                res.append({
                    "vod_id": vid,
                    "vod_name": self.clean(m.group(2)),
                    "vod_pic": self.fix(pic),
                    "vod_remarks": ""
                })
        return res

    # ==================== 工具方法 ====================

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def match(self, text, rule):
        m = re.search(rule, text or "", re.S)
        return m.group(1) if m else ""

    def clean(self, text):
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", text or "").replace("&nbsp;", " ")).strip()

    def fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url
