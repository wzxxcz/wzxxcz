# -*- coding: utf-8 -*-
import sys
import re
from urllib.parse import quote, unquote
sys.path.append('..')
from base.spider import Spider

# 优先用 curl_cffi（能过 Cloudflare），失败则退回 requests
try:
    from curl_cffi import requests as http_requests
    HAS_CFFI = True
except ImportError:
    import requests as http_requests
    HAS_CFFI = False

try:
    import requests as _plain_requests
    _plain_requests.packages.urllib3.disable_warnings()
except Exception:
    pass


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://dsystv.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def getName(self):
        return "袋鼠影视"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 首页 & 筛选 ====================

    def homeContent(self, filter):
        AREA = [("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"), ("日本", "日本"),
                ("韩国", "韩国"), ("美国", "美国"), ("英国", "英国"), ("法国", "法国"), ("泰国", "泰国"),
                ("印度", "印度"), ("加拿大", "加拿大"), ("西班牙", "西班牙")]
        YUYAN = [("全部", ""), ("国语", "国语"), ("粤语", "粤语"), ("英语", "英语"), ("日语", "日语"),
                 ("韩语", "韩语"), ("泰语", "泰语"), ("法语", "法语"), ("西班牙语", "西班牙语")]
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

        def build(type_items):
            return [
                {"key": "tid",    "name": "类型", "value": V(type_items)},
                {"key": "jq",     "name": "剧情", "value": V(JQ)},
                {"key": "area",   "name": "地区", "value": V(AREA)},
                {"key": "year",   "name": "年份", "value": V(YEAR)},
                {"key": "yuyan",  "name": "语言", "value": V(YUYAN)},
                {"key": "letter", "name": "字母", "value": V(LETTER)},
                {"key": "order",  "name": "排序", "value": V(ORDER)},
            ]

        MOVIE = [("全部", ""), ("动作片", "5"), ("科幻片", "7"), ("恐怖片", "8"), ("战争片", "9"),
                 ("喜剧片", "10"), ("动画片", "41"), ("剧情片", "12"), ("爱情片", "6"), ("纪录片", "11")]
        TV = [("全部", ""), ("国产剧", "13"), ("港台剧", "14"), ("欧美剧", "15"), ("日韩剧", "16"), ("海外剧", "42")]
        ZY = [("全部", ""), ("内地综艺", "29"), ("港台综艺", "30"), ("欧美综艺", "32"), ("日韩综艺", "33")]
        DM = [("全部", ""), ("国产动漫", "34"), ("日韩动漫", "35"), ("欧美动漫", "36")]
        DJ = [("全部", ""), ("短剧", "28"), ("微电影", "39"), ("AI漫剧", "45")]

        return {
            "class": [
                {"type_id": "1",  "type_name": "电影"},
                {"type_id": "2",  "type_name": "电视剧"},
                {"type_id": "3",  "type_name": "综艺"},
                {"type_id": "4",  "type_name": "动漫"},
                {"type_id": "44", "type_name": "短剧"},
            ],
            "filters": {
                "1":  build(MOVIE),
                "2":  build(TV),
                "3":  build(ZY),
                "4":  build(DM),
                "44": build(DJ),
            }
        }

    def homeVideoContent(self):
        return {"list": self.parseList(self.get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend or {}
        real_tid = str(ext.get("tid") or tid)

        parts = [("searchtype", "5"), ("tid", real_tid), ("page", str(pg))]
        for k in ("jq", "area", "year", "yuyan", "letter", "order"):
            v = ext.get(k)
            if v:
                parts.append((k, str(v)))

        qs = "&".join("{0}={1}".format(k, quote(v)) for k, v in parts)
        html = self.get(self.host + "/search.php?" + qs)
        return {
            "page": int(pg),
            "pagecount": 999,
            "limit": 24,
            "total": 999999,
            "list": self.parseList(html)
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(self.host + "/movie/index" + vid + ".html")

        name = self.clean(
            self.match(html, r'<h1[^>]*>(.*?)</h1>') or
            self.match(html, r'<meta property="og:title" content="(.*?)"')
        )
        name = re.sub(r'《|》', '', name)
        name = re.sub(r'\s*全集在线观看.*$', '', name)
        name = re.sub(r'\s*[-|·]\s*袋鼠影视.*$', '', name).strip()

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

    # ==================== 多线路播放解析 ====================

    def extractPlaySources(self, html, vid):
        play_from = []
        play_url = []

        panels = []
        for section in re.split(
            r'(?=<div[^>]+class=["\'][^"\']*panel[^"\']*["\'][^>]+data-playlist-name=)',
            html
        ):
            name = self.match(section, r'data-playlist-name=["\']([^"\']+)["\']')
            if not name:
                continue
            name = self.clean(name)
            idx = self.match(section, r'data-playlist-index=["\'](\d+)["\']') or "0"

            ul_content = (
                self.match(section, r'<ul[^>]+class=["\'][^"\']*playlistlink[^"\']*["\'][^>]*>([\s\S]*?)</ul>') or
                self.match(section, r'<ul[^>]*>([\s\S]*?)</ul>')
            )
            eps = self.extractEpisodes(ul_content) if ul_content else []

            if not eps:
                playlist_url = self.match(section, r'data-playlist-url=["\']([^"\']+)["\']')
                if playlist_url:
                    playlist_url = self.fix(playlist_url.replace('&amp;', '&'))
                    eps = self.extractEpisodes(self.get(playlist_url))

            if eps:
                panels.append((int(idx), name, eps))

        panels.sort(key=lambda x: x[0])
        for _idx, name, eps in panels:
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

    def extractEpisodes(self, html):
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

        headers = dict(self.headers)
        headers["Referer"] = id if id.startswith("http") else self.host + id

        return {
            "parse": 0 if self.isVideoFormat(url) else 1,
            "playUrl": "",
            "url": url,
            "header": headers
        }

    # ==================== 列表解析 ====================

    def parseList(self, html):
        res = []
        seen = set()
        if not html:
            return res

        for m in re.finditer(r'<a\s[^>]*class=["\'][^"\']*videopic[^"\']*["\'][^>]*>[\s\S]*?</a>', html, re.S):
            block = m.group(0)

            vid_m = re.search(r'href=["\']/movie/index(\d+)\.html["\']', block)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            name = self.match(block, r'title=["\']([^"\']+)["\']')
            if not name:
                name = self.match(block, r'aria-label=["\']《?([^"\'》]+)》?["\']')
            name = self.clean(name)
            if not name:
                continue

            pics = re.findall(r'(?:data-original|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', block, re.I)
            if not pics:
                pics = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', block, re.I)
            pic = ""
            for p in pics:
                if "load.gif" not in p and "nopic" not in p and "logo" not in p and "templets" not in p:
                    pic = self.fix(p)
                    break

            remarks = self.clean(
                self.match(block, r'<span[^>]+class=["\'][^"\']*note[^"\']*["\'][^>]*>(.*?)</span>') or
                self.match(block, r'<span[^>]+class=["\'][^"\']*textbg[^"\']*["\'][^>]*>(.*?)</span>')
            )

            res.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        return res

    # ==================== 工具方法 ====================

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        return "正在Destroy"

    def get(self, url):
        try:
            if HAS_CFFI:
                r = http_requests.get(url, headers=self.headers, impersonate="chrome", timeout=20)
            else:
                r = http_requests.get(url, headers=self.headers, timeout=15, verify=False)
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
