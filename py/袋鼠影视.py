# -*- coding: utf-8 -*-
import sys
import re
import json
import requests
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

    def init(self, extend=""):
        self.host = "https://dsystv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
        }

    def getName(self):
        return "袋鼠影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 首页 & 筛选 ====================

    def homeContent(self, filter):
        def V(items):
            return [{"n": str(n), "v": str(v)} for n, v in items]

        AREA = [("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
                ("日本", "日本"), ("韩国", "韩国"), ("美国", "美国"), ("英国", "英国"),
                ("法国", "法国"), ("泰国", "泰国"), ("印度", "印度"),
                ("加拿大", "加拿大"), ("西班牙", "西班牙")]
        YEAR = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2011, -1)] + \
               [("其他年份", "more"), ("年份未知", "unknown")]
        YUYAN = [("全部", ""), ("国语", "国语"), ("粤语", "粤语"), ("英语", "英语"),
                 ("日语", "日语"), ("韩语", "韩语"), ("泰语", "泰语"),
                 ("法语", "法语"), ("西班牙语", "西班牙语")]
        LETTER = [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]
        ORDER = [("按时间", "time"), ("按人气", "hit"), ("按推荐", "commend"), ("按评分", "douban")]
        JQ = [("全部", ""), ("剧情", "剧情"), ("喜剧", "喜剧"), ("动作", "动作"), ("爱情", "爱情"),
              ("科幻", "科幻"), ("动画", "动画"), ("悬疑", "悬疑"), ("惊悚", "惊悚"), ("恐怖", "恐怖"),
              ("犯罪", "犯罪"), ("同性", "同性"), ("音乐", "音乐"), ("歌舞", "歌舞"), ("传记", "传记"),
              ("历史", "历史"), ("西部", "西部"), ("奇幻", "奇幻"), ("冒险", "冒险"), ("灾难", "灾难"),
              ("武侠", "武侠"), ("情色", "情色"), ("旅游", "旅游")]

        SUB_MOVIE = [("全部", ""), ("动作片", "5"), ("科幻片", "7"), ("恐怖片", "8"),
                     ("战争片", "9"), ("喜剧片", "10"), ("动画片", "41"),
                     ("剧情片", "12"), ("爱情片", "6"), ("纪录片", "11")]
        SUB_TV = [("全部", ""), ("国产剧", "13"), ("港台剧", "14"), ("欧美剧", "15"),
                  ("日韩剧", "16"), ("海外剧", "42")]
        SUB_ZY = [("全部", ""), ("内地综艺", "29"), ("港台综艺", "30"),
                  ("欧美综艺", "32"), ("日韩综艺", "33")]
        SUB_DM = [("全部", ""), ("国产动漫", "34"), ("日韩动漫", "35"), ("欧美动漫", "36")]
        SUB_DJ = [("全部", ""), ("短剧", "28"), ("微电影", "39"), ("AI漫剧", "45")]

        def build_filters(sub):
            return [
                {"key": "tid",    "name": "类型", "value": V(sub)},
                {"key": "area",   "name": "地区", "value": V(AREA)},
                {"key": "year",   "name": "年份", "value": V(YEAR)},
                {"key": "yuyan",  "name": "语言", "value": V(YUYAN)},
                {"key": "letter", "name": "字母", "value": V(LETTER)},
                {"key": "jq",     "name": "剧情", "value": V(JQ)},
                {"key": "order",  "name": "排序", "value": V(ORDER)},
            ]

        return {
            "class": [
                {"type_id": "1",  "type_name": "电影"},
                {"type_id": "2",  "type_name": "电视剧"},
                {"type_id": "3",  "type_name": "综艺"},
                {"type_id": "4",  "type_name": "动漫"},
                {"type_id": "44", "type_name": "短剧"},
            ],
            "filters": {
                "1":  build_filters(SUB_MOVIE),
                "2":  build_filters(SUB_TV),
                "3":  build_filters(SUB_ZY),
                "4":  build_filters(SUB_DM),
                "44": build_filters(SUB_DJ),
            }
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend
        if isinstance(ext, str):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}

        def valid(v):
            if v is None:
                return False
            return str(v).strip() not in ("", "全部", "0", "None", "null")

        try:
            page_int = int(pg)
        except Exception:
            page_int = 1

        user_sub_tid = str(ext.get("tid")) if valid(ext.get("tid")) else None
        channel_tid = str(tid)

        other_has = False
        for k in ("area", "year", "letter", "yuyan", "jq", "order"):
            if valid(ext.get(k)):
                other_has = True
                break

        # ==================== 核心策略 ====================
        # 静态页方案：/frim/indexXX.html 是真实存在的静态文件，能过 CF
        # 决定用哪个 tid 的静态页
        if user_sub_tid:
            static_tid = user_sub_tid   # 用户选了子类型，走子类型静态页
        else:
            static_tid = channel_tid    # 没选子类型，走频道静态页

        # 场景 1：无筛选 或 只选了类型（无其他筛选）→ 走静态页，能过 CF
        if not other_has:
            url = self.host + "/frim/index" + static_tid + ".html"
            html = self.get(url)
            items = self.parseList(html)
            if items:
                return {
                    "page": page_int, "pagecount": 999, "limit": 24,
                    "total": 999999, "list": items
                }
            # 静态页为空，继续往下走 search.php

        # 场景 2：选了"年份/地区/语言/剧情/排序"→ 必须走 search.php（可能被 CF 拦）
        # 确定 real_tid
        if user_sub_tid:
            real_tid = user_sub_tid
        else:
            CHANNEL_FIRST_SUB = {"2": "13", "3": "29", "4": "34", "44": "28"}
            real_tid = CHANNEL_FIRST_SUB.get(channel_tid, channel_tid)

        parts = []
        if page_int > 1:
            parts.append(("page", str(page_int)))
        parts.append(("searchtype", "5"))
        if other_has:
            order_val = ext.get("order") if valid(ext.get("order")) else "weekhit"
            parts.append(("order", str(order_val)))
        parts.append(("tid", real_tid))
        for k in ("year", "area", "letter", "yuyan", "jq"):
            v = ext.get(k)
            if valid(v):
                parts.append((k, str(v)))

        qs = "&".join("{0}={1}".format(k, quote(str(v))) for k, v in parts)
        url = self.host + "/search.php?" + qs
        html = self.get(url)
        items = self.parseList(html)

        # ★ 降级：search.php 空 → 退回静态页（至少出点数据）
        if not items:
            url2 = self.host + "/frim/index" + static_tid + ".html"
            html2 = self.get(url2)
            items = self.parseList(html2)

        return {
            "page": page_int, "pagecount": 999, "limit": 24,
            "total": 999999, "list": items
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        vid = str(ids[0])
        html = self.get(self.host + "/movie/index" + vid + ".html")

        name = self.clean(self.match(html, r'<h1[^>]*>([\s\S]*?)</h1>'))
        if not name:
            name = self.clean(self.match(html, r'<meta\s+property="og:title"\s+content="([^"]+)"'))
        name = re.sub(r'《|》', '', name)
        name = re.sub(r'\s*全集在线观看.*$', '', name)
        name = re.sub(r'\s*[-|·]\s*袋鼠影视.*$', '', name).strip()

        pic = self.fix(self.match(html, r'<meta\s+property="og:image"\s+content="([^"]+)"'))

        desc = self.clean(self.match(html, r'<div[^>]*class="[^"]*video-plot[^"]*"[^>]*>([\s\S]*?)</div>'))
        if not desc:
            desc = self.clean(self.match(html, r'<meta\s+property="og:description"\s+content="([^"]+)"'))
        if desc:
            desc = self.INTRO_PREFIX + "\n" + desc
        else:
            desc = self.INTRO_PREFIX

        actor = self.clean(self.match(html, r'<li[^>]*data-video-meta="([^"]*)"[^>]*>\s*<span class="text-muted">主演：</span>'))
        director = self.clean(self.match(html, r'<li[^>]*data-video-meta="([^"]*)"[^>]*>\s*<span class="text-muted">导演：</span>'))
        year = self.clean(self.match(html, r'年份：</span>([^<]+)'))
        area = self.clean(self.match(html, r'地区：</span>([^<]+)'))
        lang = self.clean(self.match(html, r'语言：</span>([^<]+)'))
        cate = self.clean(self.match(html, r'类型：</span><a[^>]*>([^<]+)</a>'))
        remarks = self.clean(self.match(html, r'<span class="note textbg">([^<]*)</span>'))

        play_from, play_url = self._extract_play_sources(html)

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
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    def _extract_play_sources(self, html):
        play_from = []
        play_url = []
        for section in re.split(
            r'(?=<div[^>]+class="[^"]*panel[^"]*"[^>]+data-playlist-name=)',
            html
        ):
            name_m = re.search(r'data-playlist-name="([^"]+)"', section)
            if not name_m:
                continue
            name = self.clean(name_m.group(1))

            ul_m = re.search(r'<ul[^>]+class="[^"]*playlistlink[^"]*"[^>]*>([\s\S]*?)</ul>', section)
            if not ul_m:
                ul_m = re.search(r'<ul[^>]*>([\s\S]*?)</ul>', section)
            if not ul_m:
                continue

            ul_content = ul_m.group(1)
            eps = []
            seen = set()
            for m in re.finditer(r'<a\s+title="([^"]+)"[^>]*href="(/play/[^"]+)"', ul_content):
                t = self.clean(m.group(1))
                u = self.fix(m.group(2))
                if t and u and u not in seen:
                    seen.add(u)
                    eps.append("%s$%s" % (t, u))

            if eps:
                play_from.append(name)
                play_url.append("#".join(eps))

        return play_from, play_url

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        try:
            page_int = int(pg)
        except Exception:
            page_int = 1
        url = self.host + "/search.php?searchword=" + quote(key) + "&page=" + str(page_int)
        html = self.get(url)
        return {"list": self.parseList(html), "page": page_int}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self.fix(id)
        html = self.get(url)

        m3u8 = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']')
        if not m3u8:
            m3u8 = self.match(html, r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"')
        if not m3u8:
            m3u8 = self.match(html, r'["\']([^"\']+\.(?:m3u8|mp4|flv)[^"\']*)["\']')
        if not m3u8:
            m3u8 = url

        m3u8 = unquote(m3u8)
        return {
            "parse": 0 if self.isVideoFormat(m3u8) else 1,
            "playUrl": "",
            "url": m3u8,
            "header": self.headers,
        }

    # ==================== 列表解析 ====================

    def parseList(self, html):
        res = []
        seen = set()
        if not html:
            return res

        pattern = r'<a[^>]*class="[^"]*videopic[^"]*"[^>]*href="(/movie/index\d+\.html)"[^>]*title="([^"]+)"[^>]*>([\s\S]*?)</a>'
        for m in re.finditer(pattern, html):
            href = m.group(1)
            name = self.clean(m.group(2))
            inner = m.group(3)

            vid_m = re.search(r'/movie/index(\d+)\.html', href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            if not name:
                am = re.search(r'aria-label="《([^》]+)》', m.group(0))
                if am:
                    name = self.clean(am.group(1))
            if not name:
                continue

            pic = ""
            pm = re.search(r'data-original="([^"]+)"', inner)
            if pm:
                pic = self.fix(pm.group(1))
            else:
                pm = re.search(r'src="([^"]+\.(?:jpg|jpeg|png|webp|gif)[^"]*)"', inner, re.I)
                if pm and "load.gif" not in pm.group(1):
                    pic = self.fix(pm.group(1))

            remarks = ""
            rm = re.search(r'<span\s+class="note textbg">([^<]*)</span>', inner)
            if rm:
                remarks = self.clean(rm.group(1))

            res.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
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
