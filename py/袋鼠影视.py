# -*- coding: utf-8 -*-
"""
袋鼠影视 dsystv.com | TVBox Python 爬虫
基于真实站点 HTML 结构，参照豆花电影结构
"""
import re
import sys
import json
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[dsy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://dsystv.com"
UA = ("Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 "
      "Mobile Safari/537.36")

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "44", "type_name": "短剧"},
]

# 子类型（用于筛选）
SUB_TYPES = {
    "1":  [("全部", ""), ("动作片", "5"), ("科幻片", "7"), ("恐怖片", "8"),
           ("战争片", "9"), ("喜剧片", "10"), ("动画片", "41"),
           ("剧情片", "12"), ("爱情片", "6"), ("纪录片", "11")],
    "2":  [("全部", ""), ("国产剧", "13"), ("港台剧", "14"),
           ("欧美剧", "15"), ("日韩剧", "16"), ("海外剧", "42")],
    "3":  [("全部", ""), ("内地综艺", "29"), ("港台综艺", "30"),
           ("欧美综艺", "32"), ("日韩综艺", "33")],
    "4":  [("全部", ""), ("国产动漫", "34"), ("日韩动漫", "35"), ("欧美动漫", "36")],
    "44": [("全部", ""), ("短剧", "28"), ("微电影", "39"), ("AI漫剧", "45")],
}

_JQ = ["剧情", "喜剧", "动作", "爱情", "科幻", "动画", "悬疑", "惊悚", "恐怖",
       "犯罪", "同性", "音乐", "歌舞", "传记", "历史", "西部", "奇幻", "冒险",
       "灾难", "武侠", "情色", "旅游"]
_AREA = ["大陆", "香港", "台湾", "日本", "韩国", "美国", "英国", "法国",
         "泰国", "印度", "加拿大", "西班牙"]
_YEAR = [str(y) for y in range(2026, 2011, -1)] + ["more", "unknown"]
_YUYAN = ["国语", "粤语", "英语", "日语", "韩语", "泰语", "法语", "西班牙语"]
_LETTER = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]
_ORDER = [("按时间", "time"), ("按人气", "hit"),
          ("按推荐", "commend"), ("按评分", "douban")]


def _build_filters(tid):
    sub = SUB_TYPES.get(str(tid), [("全部", "")])
    return [
        {"key": "tid",    "name": "类型",
         "value": [{"n": n, "v": v} for n, v in sub]},
        {"key": "jq",     "name": "剧情",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _JQ]},
        {"key": "area",   "name": "地区",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _AREA]},
        {"key": "year",   "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _YEAR]},
        {"key": "yuyan",  "name": "语言",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _YUYAN]},
        {"key": "letter", "name": "字母",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _LETTER]},
        {"key": "order",  "name": "排序", "value": _ORDER},
    ]


FILTERS = {c["type_id"]: _build_filters(c["type_id"]) for c in CLASSES}


class Spider(Spider):

    def getName(self):
        return "袋鼠影视"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }

    # -------- 基础工具 --------

    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    # -------- 首页 --------

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    # -------- 分类 --------

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        def valid(v):
            return v is not None and str(v).strip() not in ("", "全部", "0", "None")

        # 用户在"类型"里选的子类会覆盖频道 tid
        real_tid = extend.get("tid") if valid(extend.get("tid")) else str(tid)

        # 收集筛选参数（顺序按站点真实 URL）
        filter_params = []
        for k in ("area", "year", "letter", "yuyan", "jq"):
            v = extend.get(k)
            if valid(v):
                filter_params.append((k, str(v)))

        has_filter = len(filter_params) > 0 or (real_tid != str(tid))

        if not has_filter and page == 1:
            # 无筛选 + 第 1 页 → 静态分类页
            url = "%s/frim/index%s.html" % (self.site_url, tid)
        else:
            # 有筛选 / 翻页 → search.php
            order = extend.get("order") if valid(extend.get("order")) else "weekhit"
            parts = [("searchtype", "5"), ("order", str(order)), ("tid", str(real_tid))]
            parts.extend(filter_params)
            if page > 1:
                parts.append(("page", str(page)))
            qs = "&".join("%s=%s" % (k, urllib.parse.quote(str(v)))
                          for k, v in parts)
            url = "%s/search.php?%s" % (self.site_url, qs)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("  最终: %d 条" % len(videos))

        return {
            "list": videos,
            "page": page,
            "pagecount": 999,
            "limit": 24,
            "total": 999999,
        }

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in re.finditer(r'<a\s+class="videopic"[^>]*>[\s\S]*?</a>',
                             html, re.S | re.I):
            block = m.group(0)
            href_m = re.search(r'href="(/movie/index\d+\.html)"', block)
            if not href_m:
                continue
            href = href_m.group(1)
            if href in seen:
                continue
            seen.add(href)

            name_m = re.search(r'title="([^"]+)"', block)
            name = self._clean(name_m.group(1)) if name_m else ""
            if not name:
                al_m = re.search(r'aria-label="《([^》]+)》', block)
                if al_m:
                    name = self._clean(al_m.group(1))
            if not name:
                continue

            pic = ""
            for img_m in re.finditer(r'(?:data-original|data-src)="([^"]+)"', block):
                p = img_m.group(1)
                if "load.gif" not in p and "nopic" not in p and "templets" not in p:
                    pic = self._fix_url(p)
                    break
            if not pic:
                for img_m in re.finditer(r'<img[^>]+src="([^"]+)"', block):
                    p = img_m.group(1)
                    if "load.gif" not in p and "templets" not in p:
                        pic = self._fix_url(p)
                        break

            remarks_m = re.search(
                r'<span\s+class="[^"]*note[^"]*"[^>]*>([^<]*)</span>', block)
            remarks = self._clean(remarks_m.group(1)) if remarks_m else ""

            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return videos

    # -------- 详情 --------

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
            if m:
                name = self._clean(m.group(1))
        name = re.sub(r'《|》', '', name)
        name = re.sub(r'\s*全集在线观看.*$', '', name)
        name = re.sub(r'\s*[-|·]\s*袋鼠影视.*$', '', name).strip()

        # 封面
        pic = ""
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = re.search(r'<div[^>]*class="[^"]*video-plot[^"]*"[^>]*>([\s\S]*?)</div>',
                      html, re.I)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"',
                          html, re.I)
            if m:
                content = self._clean(m.group(1))

        # 元信息
        actor = director = year = area = lang = cate = ""
        m = re.search(r'<li[^>]+data-video-meta="([^"]*)"[^>]*><span class="text-muted">主演：</span>', html)
        if m: actor = self._clean(m.group(1))
        m = re.search(r'<li[^>]+data-video-meta="([^"]*)"[^>]*><span class="text-muted">导演：</span>', html)
        if m: director = self._clean(m.group(1))
        m = re.search(r'年份：</span>([^<]+)', html)
        if m: year = self._clean(m.group(1))
        m = re.search(r'地区：</span>([^<]+)', html)
        if m: area = self._clean(m.group(1))
        m = re.search(r'语言：</span>([^<]+)', html)
        if m: lang = self._clean(m.group(1))
        m = re.search(r'类型：</span><a[^>]*>([^<]+)</a>', html)
        if m: cate = self._clean(m.group(1))

        remarks = ""
        m = re.search(r'<span class="note textbg">([^<]*)</span>', html)
        if m:
            remarks = self._clean(m.group(1))

        # 播放线路
        play_from, play_url = self._extract_play_sources(html, vod_id)
        self.log("  from=%s, urls=%d" % (play_from, len(play_url)))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "type_name": cate,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _extract_play_sources(self, html, vid):
        panels = []

        for section in re.split(
                r'(?=<div[^>]+class="[^"]*panel[^"]*"[^>]+data-playlist-name=)',
                html):
            name_m = re.search(r'data-playlist-name="([^"]+)"', section)
            if not name_m:
                continue
            name = self._clean(name_m.group(1))
            idx_m = re.search(r'data-playlist-index="(\d+)"', section)
            idx = int(idx_m.group(1)) if idx_m else 0

            eps = self._extract_episodes(section, vid)
            if eps:
                panels.append((idx, name, eps))

        panels.sort(key=lambda x: x[0])
        froms = [p[1] for p in panels]
        urls = ["#".join(p[2]) for p in panels]
        return froms, urls

    def _extract_episodes(self, section, vid):
        eps = []
        seen = set()
        for m in re.finditer(r'<a\s+title="([^"]+)"[^>]+href="(/play/[^"]+)"',
                             section):
            t = self._clean(m.group(1))
            u = self._fix_url(m.group(2))
            if t and u and u not in seen:
                seen.add(u)
                eps.append("%s$%s" % (t, u))
        return eps

    # -------- 搜索 --------

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page, "pagecount": 999,
            "limit": 24, "total": 999,
        }

    # -------- 播放 --------

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        html = self._fetch(play_page)
        self.log("  HTML 长度: %d" % len(html))

        url = ""
        m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            url = m.group(1)

        if not url:
            m = re.search(r'player_aaaa\s*=\s*\{[^}]*"url"\s*:\s*"([^"]+)"', html)
            if m:
                url = m.group(1)

        if not url:
            m = re.search(r'["\']([^"\']+(?:m3u8|mp4|flv)[^"\']*)["\']', html)
            if m:
                url = m.group(1)

        if not url:
            url = play_page

        url = urllib.parse.unquote(url)

        return {
            "parse": 0 if self.isVideoFormat(url) else 1,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|mov|ts)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", "", ""]

    def destroy(self):
        pass
