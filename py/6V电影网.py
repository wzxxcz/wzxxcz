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
        self.host = "https://www.6vdyw.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
        }

    def getName(self):
        return "6V电影网"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 首页 & 筛选 ====================

    def homeContent(self, filter):
        def V(items):
            return [{"n": str(n), "v": str(v)} for n, v in items]

        AREA = [("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
                ("美国", "美国"), ("法国", "法国"), ("英国", "英国"), ("日本", "日本"),
                ("韩国", "韩国"), ("德国", "德国"), ("泰国", "泰国"), ("印度", "印度"),
                ("意大利", "意大利"), ("西班牙", "西班牙"), ("加拿大", "加拿大"), ("其他", "其他")]

        YEAR = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2009, -1)]

        ORDER = [("按时间", "time"), ("按人气", "hits"), ("按评分", "score")]

        SUB_MOVIE = [("全部", "1"), ("喜剧", "喜剧"), ("爱情", "爱情"), ("恐怖", "恐怖"),
                     ("动作", "动作"), ("科幻", "科幻"), ("剧情", "剧情"), ("战争", "战争"),
                     ("警匪", "警匪"), ("犯罪", "犯罪"), ("动画", "动画"), ("奇幻", "奇幻"),
                     ("武侠", "武侠"), ("冒险", "冒险"), ("枪战", "枪战"), ("悬疑", "悬疑"),
                     ("惊悚", "惊悚"), ("经典", "经典"), ("青春", "青春"), ("文艺", "文艺"),
                     ("古装", "古装"), ("历史", "历史"), ("运动", "运动"), ("儿童", "儿童")]

        SUB_TV = [("全部", "7"), ("美剧", "6"), ("韩剧", "13"), ("泰剧", "2"),
                  ("中剧", "7"), ("日剧", "14"), ("港剧", "8")]

        SUB_ZY = [("全部", "4")]
        SUB_DM = [("全部", "9")]
        SUB_DJ = [("全部", "3")]

        def build_filters(sub):
            return [
                {"key": "tid",   "name": "类型", "value": V(sub)},
                {"key": "area",  "name": "地区", "value": V(AREA)},
                {"key": "year",  "name": "年份", "value": V(YEAR)},
                {"key": "order", "name": "排序", "value": V(ORDER)},
            ]

        return {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "7", "type_name": "电视剧"},
                {"type_id": "4", "type_name": "综艺"},
                {"type_id": "9", "type_name": "动漫"},
                {"type_id": "3", "type_name": "短剧"},
            ],
            "filters": {
                "1": build_filters(SUB_MOVIE),
                "7": build_filters(SUB_TV),
                "4": build_filters(SUB_ZY),
                "9": build_filters(SUB_DM),
                "3": build_filters(SUB_DJ),
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

        # 用户选的子类型覆盖频道 tid（filters 的 value 里就是网站真实的 tid）
        user_sub_tid = str(ext.get("tid")) if valid(ext.get("tid")) else None
        real_tid = user_sub_tid if user_sub_tid else str(tid)

        # 6V电影网的分类页 URL 规则：
        # 第1页：/html/{tid}.html
        # 第N页：/html/{tid}-{N}.html
        if page_int == 1:
            url = self.host + "/html/" + real_tid + ".html"
        else:
            url = self.host + "/html/" + real_tid + "-" + str(page_int) + ".html"

        html = self.get(url)
        return {
            "page": page_int, "pagecount": 999, "limit": 24,
            "total": 999999, "list": self.parseList(html)
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        vid = str(ids[0])
        # ids 里传入的是 /mov/xxx.html，直接拼接
        if vid.startswith("http"):
            url = vid
        elif vid.startswith("/"):
            url = self.host + vid
        else:
            url = self.host + "/mov/" + vid + ".html"

        html = self.get(url)

        name = self.clean(self.match(html, r'<h1[^>]*class="detail-title"[^>]*>([\s\S]*?)</h1>'))
        name = re.sub(r'《|》', '', name)
        name = re.sub(r'\s*免费在线观看.*$', '', name).strip()
        if not name:
            name = self.clean(self.match(html, r'<title>([\s\S]*?)</title>'))
            name = re.sub(r'\s*[-|·].*$', '', name).strip()

        pic = self.fix(self.match(html, r'<div[^>]*class="detail-cover"[^>]*>\s*<img[^>]*src="([^"]+)"'))

        desc = self.clean(self.match(html, r'<div[^>]*class="detail-content"[^>]*>[\s\S]*?<p>([\s\S]*?)</p>'))
        if desc:
            desc = self.INTRO_PREFIX + "\n" + desc
        else:
            desc = self.INTRO_PREFIX

        actor = self.clean(self.match(html, r'<strong>\s*主演：\s*</strong>\s*<span>([\s\S]*?)</span>'))
        actor = re.sub(r'\s+', ' ', actor).strip()

        director = self.clean(self.match(html, r'<strong>\s*导演：\s*</strong>\s*<span>([\s\S]*?)</span>'))
        director = re.sub(r'\s+', ' ', director).strip()

        year = self.clean(self.match(html, r'<strong>\s*年份：\s*</strong>\s*<span>[\s\S]*?>([^<]+)</a>'))
        area = self.clean(self.match(html, r'<strong>\s*地区：\s*</strong>\s*<span>[\s\S]*?>([^<]+)</a>'))
        cate = self.clean(self.match(html, r'<strong>\s*类型：\s*</strong>\s*<span>[\s\S]*?>([^<]+)</a>'))
        remarks = self.clean(self.match(html, r'<strong>\s*状态：\s*</strong>\s*<span>([^<]+)</span>'))

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

        # 6V 结构：
        # <div class="episode-tabs"><div class="episode-tab active" data-index="1">6vyun</div></div>
        # <div class="episode-list" data-tab="1">
        #   <a href="/vod/18973-1-1.html" class="episode-item" title="第1集">第1集</a>
        #   ...
        # </div>
        for tab in re.finditer(
                r'<div[^>]+class="episode-tab[^"]*"[^>]+data-index="(\d+)"[^>]*>([^<]+)</div>',
                html):
            idx = tab.group(1)
            name = self.clean(tab.group(2))
            marker = 'data-tab="%s"' % idx
            start = html.find(marker, tab.end())
            if start == -1:
                continue
            next_list = html.find('<div class="episode-list"', start + 1)
            end_sec = html.find('</section>', start)
            ends = [e for e in (next_list, end_sec) if e != -1]
            end = min(ends) if ends else len(html)
            block = html[start:end]

            eps = []
            seen = set()
            for m in re.finditer(
                    r'<a\s+href="([^"]+)"[^>]*class="episode-item[^"]*"[^>]*title="([^"]+)"',
                    block):
                u = self.fix(m.group(1))
                t = self.clean(m.group(2))
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
        # 6V 搜索 URL：/vodsearch/{关键词}-------------.html
        url = self.host + "/vodsearch/" + quote(key) + "-------------.html"
        html = self.get(url)
        return {"list": self.parseList(html), "page": page_int}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self.fix(id)
        html = self.get(url)

        # 6V 播放页里有：
        # <script>var player_aaaa={..., "url":"https:\/\/hn.bfvvs.com\/play\/bkRQA9xa", ...}</script>
        m3u8 = self.match(html, r'"url"\s*:\s*"([^"]+)"')
        if m3u8:
            m3u8 = m3u8.replace("\\/", "/")
            m3u8 = unquote(m3u8)

        if not m3u8:
            m3u8 = self.match(html, r'var\s+now\s*=\s*["\']([^"\']+)["\']')
        if not m3u8:
            m3u8 = url

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

        # 6V 卡片结构：
        # <a href="/mov/100491.html" title="假面骑士零一真实×时间劇場版" class="vod-link">
        #   <div class="vod-cover">
        #     <img src="https://hongniuzyimage.com/cover/xxx.jpg" alt="...">
        #     ...
        #   </div>
        #   <div class="vod-info">
        #     <h3 class="vod-title">...</h3>
        #     <div class="vod-meta"><span>正片</span><span class="vod-remarks">9.0分</span></div>
        #   </div>
        # </a>
        pattern = r'<a\s+href="(/mov/\d+\.html)"\s+title="([^"]+)"\s+class="vod-link">([\s\S]*?)</a>'
        for m in re.finditer(pattern, html):
            href = m.group(1)
            name = self.clean(m.group(2))
            inner = m.group(3)

            vid_m = re.search(r'/mov/(\d+)\.html', href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            pic = ""
            pm = re.search(r'<img[^>]*src="([^"]+)"', inner)
            if pm:
                pic = self.fix(pm.group(1))

            remarks = ""
            rm = re.search(r'<div class="vod-meta">\s*<span>([^<]*)</span>', inner)
            if rm:
                remarks = self.clean(rm.group(1))

            res.append({
                "vod_id": "/mov/" + vid + ".html",
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
