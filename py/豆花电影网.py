# coding=utf-8
"""
豆花电影网 dhvideo.cc | TVBox Python 爬虫 (V2 稳健版)
修复: 列表页正则过严导致匹配为空的问题
"""
import re
import sys
import json
import time
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
                print("[douhua]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ============================================================
#  常量
# ============================================================
HOST = "https://dhvideo.cc"
SION_ID = "6ac4b6643b9fea31774d1157"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/douhua/douhua.me.png"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

_SORTS = [
    {"n": "热度最高", "v": "play_hot"},
    {"n": "豆瓣评分", "v": "group_douban"},
]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
    {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "泰国", "v": "泰国"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "澳大利亚", "v": "澳大利亚"},
]

_FILTERS_MAP = {
    "dianying":  ["全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
                  "悬疑", "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争",
                  "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片"],
    "dianshiju": ["全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
                  "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
                  "武侠", "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装"],
    "zongyi":    ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
                  "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
                  "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技",
                  "爱情", "犯罪", "家庭", "历史"],
    "dongman":   ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
                  "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
                  "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园"],
    "duanju":    ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
                  "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
                  "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史",
                  "动画", "战争"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ============================================================
#  正则（改进版）
# ============================================================
# 第一步：先匹配 <a href="/movie/xxx-xxx.html..."> ... </a>
_RE_A_BLOCK = re.compile(
    r'<a\s+href="(/(?:movie|tv)/[^"]+?)"[^>]*>(.*?)</a>',
    re.S | re.I)

# 第二步：在块内匹配 <img alt="..." data-src="...">
_RE_IMG_ALT_FIRST = re.compile(
    r'<img[^>]*?alt="([^"]+)"[^>]*?(?:data-src|src)="([^"]+)"',
    re.S | re.I)
_RE_IMG_SRC_FIRST = re.compile(
    r'<img[^>]*?(?:data-src|src)="([^"]+)"[^>]*?alt="([^"]+)"',
    re.S | re.I)

# 备注
_RE_REMARK = re.compile(
    r'<span class="bg-black/60[^>]*>\s*([^<]+?)\s*</span>', re.I)

# 详情页剧集
_RE_EPISODE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*?data-origin="([^"]+)"[^>]*?data-title="([^"]+)"',
    re.S | re.I)

# 播放页 aa
_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)

# 标题 / 封面 / 简介
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)
_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)

# 元信息
_RE_DIRECTOR = re.compile(
    r'<span class="text-\[#2e2e2e\] font-bold">导演</span>\s*'
    r'<span[^>]*>([^<]+)</span>', re.S)
_RE_ACTOR = re.compile(
    r'<span class="text-\[#2e2e2e\] font-bold">主演</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.S)
_RE_SCORE = re.compile(r'vk-badge">\s*([\d.]+)\s*</div>')
_RE_HOT = re.compile(r'([\d,]+)\s*\(电视剧排名:\s*(\d+),\s*总排名:\s*(\d+)\)')
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)

_LINE_PRIORITY = ["vip", "1080zyk", "wztv", "bfzym3u8", "dyttm3u8",
                  "ffm3u8", "lzm3u8", "modum3u8", "jsm3u8", "mtm3u8"]
_LINE_ALIAS = {
    "vip": "VIP线路", "modum3u8": "魔都M3U8", "jsm3u8": "极速M3U8",
    "mtm3u8": "茅台M3U8", "1080zyk": "1080资源", "lzm3u8": "量子M3U8",
    "bfzym3u8": "暴风资源", "dyttm3u8": "电影天堂", "ffm3u8": "非凡M3U8",
    "wztv": "王者TV",
}


# ============================================================
#  Spider
# ============================================================
class Spider(Spider):

    def getName(self):
        return "豆花电影"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.sion_id  = self.extend.get("sion_id") or SION_ID
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s sid=%s" % (self.site_url, self.sion_id))

    # ---------------- 网络 ----------------
    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch fail: %s - %s" % (url, e))
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
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析（改进版） ----------------
    def _extract_videos(self, html):
        """两步解析: 先抓 <a> 块, 再在块内抓 <img>"""
        videos = []
        seen = set()
        if not html:
            return videos

        blocks = _RE_A_BLOCK.findall(html)
        self.log("  _extract_videos: 找到 %d 个 <a> 块" % len(blocks))

        for href, inner in blocks:
            href = href.replace("&amp;", "&")
            if not href or href in seen:
                continue

            # 去掉 href 里 ?sion_id=xxx 之后的参数（保留原样也可以）
            # 如果 inner 为空（放映厅的空 <a>），跳过
            if not inner.strip():
                continue

            # 找 img（两种属性顺序都试）
            name = ""
            pic = ""
            m = _RE_IMG_ALT_FIRST.search(inner)
            if m:
                name, pic = m.group(1), m.group(2)
            else:
                m = _RE_IMG_SRC_FIRST.search(inner)
                if m:
                    pic, name = m.group(1), m.group(2)

            if not name:
                # 没有 img 就跳过（不是卡片）
                continue

            name = self._clean(name)
            if not name:
                continue

            # 备注
            remark = ""
            rm = _RE_REMARK.search(html[html.find(href) + len(href):
                                        html.find(href) + len(href) + 500]
                                   if html.find(href) >= 0 else "")
            if not rm:
                rm = _RE_REMARK.search(inner)
            if rm:
                remark = self._clean(rm.group(1))

            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark[:30],
            })

        self.log("  _extract_videos: 解析出 %d 条视频" % len(videos))
        if not videos and html:
            self.log("  ⚠️ 未解析到视频, HTML 前 300 字符: %s" % html[:300])
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = "%s/?sion_id=%s" % (self.site_url, self.sion_id)
        self.log("homeVideoContent: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % (len(html) if html else 0))
        videos = self._extract_videos(html) if html else []
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        params = {
            "page": page - 1,
            "sort_field": extend.get("sort_field") or "play_hot",
            "sion_id": self.sion_id,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]

        query = urllib.parse.urlencode(params)
        url = "%s/%s.html?%s" % (self.site_url, tid, query)
        self.log("categoryContent: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % (len(html) if html else 0))
        videos = self._extract_videos(html) if html else []
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/s?name=%s&sion_id=%s&page=%d" % (
            self.site_url, keyword, self.sion_id, page - 1)
        self.log("searchContent: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % (len(html) if html else 0))
        videos = self._extract_videos(html) if html else []
        pagecount = self._page_count(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detailContent: %s" % url)

        html = self._fetch(url)
        if not html:
            self.log("  HTML 空")
            return {"list": []}
        self.log("  HTML 长度: %d" % len(html))

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC_ID.search(html)
        if m:
            pic = self.site_url + m.group(0)

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = "🍊资源抓取自豆花电影网，请勿相信视频中的广告。\n" + content

        # 元信息
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        hot_info = ""
        m = _RE_HOT.search(html)
        if m:
            hot_info = "热度%s (排名%s)" % (m.group(1), m.group(2))

        # 剧集
        groups = {}
        for m in _RE_EPISODE.finditer(html):
            href, origin, ep_name = m.group(1), m.group(2), m.group(3)
            href = href.replace("&amp;", "&")
            if href.startswith("/"):
                href = self.site_url + href
            groups.setdefault(origin, []).append((ep_name.strip(), href))

        self.log("  剧集分组: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            self.log("  ⚠️ 未找到剧集, 检查 data-origin 属性")
            return {"list": []}

        sorted_origins = sorted(
            groups.keys(),
            key=lambda x: (_LINE_PRIORITY.index(x)
                           if x in _LINE_PRIORITY else 999)
        )

        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            alias = _LINE_ALIAS.get(origin, origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": hot_info or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("playerContent: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        api_url = self._extract_api_m3u8(html) if html else ""
        self.log("  api_url = %s" % (api_url[:160] if api_url else "EMPTY"))

        if api_url:
            if api_url.startswith("/"):
                api_url = self.site_url + api_url
            box_page = self._resolve_to_box_page(api_url, referer=play_page)
            if box_page:
                if ".m3u8" in box_page:
                    res = {
                        "parse": 0, "playUrl": "", "url": box_page,
                        "header": {"User-Agent": UA, "Referer": play_page},
                    }
                    self._play_cache[play_page] = (now, res)
                    self.log("  => 直链 m3u8")
                    return res
                res = {
                    "parse": 1, "playUrl": "", "url": box_page,
                    "header": {"User-Agent": UA, "Referer": play_page},
                }
                self._play_cache[play_page] = (now, res)
                self.log("  => 嗅探 box 页")
                return res

        res = {
            "parse": 1, "playUrl": "", "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_api_m3u8(self, html):
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            m2 = re.search(r'(/api/m3u8\?[^"\'\\\s]+)', html)
            if m2:
                return m2.group(1).replace("&amp;", "&")
            return ""
        raw = m.group(1)
        raw = (raw.replace("\\\\u0026", "&")
                  .replace("\\u0026", "&")
                  .replace("\\\\u0022", '"')
                  .replace("\\u0022", '"')
                  .replace("\\/", "/"))
        try:
            aa = json.loads(raw)
            return aa.get("url", "")
        except Exception as e:
            self.log("aa parse fail: %s" % e)
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""

    def _resolve_to_box_page(self, api_url, referer=None):
        try:
            rsp = self.fetch(api_url, headers={
                "User-Agent": UA,
                "Referer": referer or (self.site_url + "/"),
                "Accept": "text/html,application/json,*/*",
            }, timeout=12, allow_redirects=False)
        except Exception as e:
            self.log("resolve fail: %s" % e)
            return ""

        loc = ""
        if hasattr(rsp, "headers"):
            loc = (rsp.headers.get("Location", "") or
                   rsp.headers.get("location", ""))
        if loc:
            loc = loc.replace("&amp;", "&")
            if loc.startswith("//"):
                loc = "https:" + loc
            self.log("  302 -> %s" % loc[:160])
            return loc

        text = ""
        try:
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
        except Exception:
            pass

        if "#EXTM3U" in text:
            self.log("  body 是 m3u8")
            return api_url

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                u = (data.get("url") or data.get("playUrl") or
                     data.get("play_url") or "")
                if u:
                    if u.startswith("//"):
                        u = "https:" + u
                    elif u.startswith("/"):
                        u = self.site_url + u
                    return u
        except Exception:
            pass
        return ""

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ul = url.lower()
                if ".png" in ul:
                    ctype = "image/png"
                elif ".webp" in ul:
                    ctype = "image/webp"
                elif ".gif" in ul:
                    ctype = "image/gif"
                else:
                    ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
