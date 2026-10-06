# coding=utf-8
"""
目标站: 云途影视 (gw7.cc)
CMS: 苹果CMS v10 (海螺模板)
"""
import re
import sys
import json
import time
import base64
import urllib.parse

sys.path.append('..')

# ===== 兼容导入 =====
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
            pass

    Spider = _BaseSpider


HOST = "https://www.gw7.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/user/default.png"


# ============================================================
# 预编译正则
# ============================================================
_RE_VODLIST = re.compile(
    r'<a[^>]*class="[^"]*vodlist_thumb[^"]*"[^>]*'
    r'href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*'
    r'title="([^"]+)"[^>]*'
    r'(?:data-original|data-src|src)="([^"]+)"[^>]*>'
    r'.*?<span class="pic_text[^"]*">\s*([^<]*)\s*</span>',
    re.DOTALL)

# 宽松列表（兜底）：只靠 detail/id 链接
_RE_VODLIST_LOOSE = re.compile(
    r'<a[^>]*href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*'
    r'title="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL)

_RE_TITLE = re.compile(r'title="([^"]+)"')
_RE_ALT = re.compile(r'alt="([^"]+)"')
_RE_IMG = re.compile(
    r'(?:data-original|data-src|data-lazy|lay-src|src)="([^"]+)"', re.I)
_RE_PIC_TEXT = re.compile(
    r'<span[^>]*class="[^"]*pic_text[^"]*"[^>]*>\s*([^<]{1,20})\s*</span>')

# 详情页
_RE_DETAIL_TITLE = re.compile(
    r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', re.DOTALL)
_RE_DETAIL_PIC = re.compile(
    r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"')
_RE_DETAIL_DIRECTOR = re.compile(r'导演[：:]\s*(.*?)</(?:p|div|li)>', re.DOTALL)
_RE_DETAIL_ACTOR = re.compile(r'主演[：:]\s*(.*?)</(?:p|div|li)>', re.DOTALL)
_RE_DETAIL_YEAR = re.compile(r'年份[：:]\s*<a[^>]*>(\d{4})</a>')
_RE_DETAIL_AREA = re.compile(r'地区[：:]\s*<a[^>]*>(.*?)</a>', re.DOTALL)
_RE_DETAIL_TYPE = re.compile(r'类型[：:]\s*<a[^>]*>(.*?)</a>', re.DOTALL)
_RE_DETAIL_LANG = re.compile(r'语言[：:]\s*<a[^>]*>(.*?)</a>', re.DOTALL)

# 播放链接：/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
_RE_PLAY_LINK = re.compile(
    r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"'
    r'[^>]*>(.*?)</a>', re.DOTALL)

# 播放变量
_RE_M3U8 = re.compile(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', re.I)
_RE_MP4 = re.compile(r'https?://[^\s"\'<>\\]+\.mp4[^\s"\'<>\\]*', re.I)

# 简介：多层兜底（class 从精准到宽松）
_INTRO_PATTERNS = [
    # 海螺模板：sketch / vod_content
    r'<div[^>]*class="[^"]*\bsketch\b[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<span[^>]*class="[^"]*\bsketch\b[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<p[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</p>',
    r'<span[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</span>',
    # 通用：detail-sketch / detail-content
    r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*class="[^"]*vod-detail-content[^"]*"[^>]*>([\s\S]*?)</div>',
    # 通用：content / desc / #desc / #content
    r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<p[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>([\s\S]*?)</p>',
    r'<div[^>]*class="[^"]*\bdesc\b[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*intro[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*content[^"]*"[^>]*>([\s\S]*?)</div>',
    # “剧情介绍：”段落
    r'(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*</[^>]+>\s*<[^>]*>([\s\S]{10,2000}?)</',
    r'(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*([\s\S]{10,2000}?)(?:<br|\n\n|</p>|</div>|$)',
]


class Spider(Spider):

    def getName(self):
        return "云途影视"

    # ========== 初始化 ==========
    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._filters = None
        self._home_cache = []
        self._home_cache_time = 0
        self._play_cache = {}

    # ========== 网络 ==========
    def _fetch(self, url, timeout=15):
        """优先走 self.fetch（壳子自带连接池/重试），失败再退到 urllib"""
        try:
            try:
                rsp = self.fetch(url, headers=self.headers, timeout=timeout)
                if hasattr(rsp, 'text'):
                    txt = rsp.text
                elif hasattr(rsp, 'content'):
                    txt = rsp.content.decode('utf-8', 'ignore')
                else:
                    txt = str(rsp)
                if txt:
                    return txt
            except TypeError:
                rsp = self.fetch(url, headers=self.headers)
                if hasattr(rsp, 'text'):
                    return rsp.text
                if hasattr(rsp, 'content'):
                    return rsp.content.decode('utf-8', 'ignore')
        except Exception:
            pass

        # 兜底：urllib
        try:
            import ssl
            import urllib.request
            req = urllib.request.Request(url, headers=self.headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            try:
                self.log(f"请求失败: {url} - {e}")
            except Exception:
                pass
            return ""

    # ========== 工具 ==========
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url, url)
        return url

    def _clean(self, s):
        if not s:
            return ''
        s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
        s = re.sub(r'<[^>]+>', '', s)
        s = (s.replace('&nbsp;', ' ').replace('\xa0', ' ')
               .replace('&amp;', '&').replace('&quot;', '"')
               .replace('&#39;', "'").replace('&lt;', '<')
               .replace('&gt;', '>'))
        s = re.sub(r'[ \t\r\f\v]+', ' ', s)
        s = re.sub(r'\n{2,}', '\n', s)
        return s.strip()

    def _extract_referer(self, url):
        try:
            if "://" in url:
                scheme = url.split("://")[0]
                host = url.split("://")[1].split("/")[0]
                return scheme + "://" + host + "/"
        except Exception:
            pass
        return self.site_url + "/"

    # ========== 列表解析 ==========
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 精确正则
        for m in _RE_VODLIST.finditer(html):
            href, vid, title, pic, note = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self._fix_url(pic.strip()),
                "vod_remarks": (note or '').strip() or "HD",
            })

        # 宽松兜底
        if not videos:
            for m in _RE_VODLIST_LOOSE.finditer(html):
                href, vid, title, inner = m.groups()
                if vid in seen:
                    continue
                title = (title or '').strip()
                if not title:
                    tm = _RE_ALT.search(inner)
                    if tm:
                        title = tm.group(1).strip()
                if not title:
                    continue

                pic = ""
                pm = _RE_IMG.search(inner)
                if pm:
                    pic = pm.group(1).strip()
                # 备注
                note = ""
                rm = _RE_PIC_TEXT.search(inner)
                if rm:
                    note = rm.group(1).strip()

                seen.add(vid)
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": note or "HD",
                })
        return videos

    def _get_pagecount(self, html):
        if not html:
            return 1
        m = re.search(
            r'href="/index\.php/vod/(?:type|show|search)/[^"]*/page/(\d+)\.html"[^>]*>尾页',
            html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        return 1

    # ========== 筛选器 ==========
    def _get_filters(self):
        if self._filters is not None:
            return self._filters

        movie_classes = [
            {"n": "全部", "v": ""}, {"n": "动作", "v": "动作"},
            {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
            {"n": "恐怖", "v": "恐怖"}, {"n": "科幻", "v": "科幻"},
            {"n": "剧情", "v": "剧情"}, {"n": "战争", "v": "战争"},
            {"n": "警匪", "v": "警匪"}, {"n": "犯罪", "v": "犯罪"},
            {"n": "动画", "v": "动画"}, {"n": "奇幻", "v": "奇幻"},
            {"n": "武侠", "v": "武侠"}, {"n": "冒险", "v": "冒险"},
            {"n": "枪战", "v": "枪战"}, {"n": "悬疑", "v": "悬疑"},
            {"n": "惊悚", "v": "惊悚"}, {"n": "经典", "v": "经典"},
            {"n": "青春", "v": "青春"}, {"n": "文艺", "v": "文艺"},
            {"n": "微电影", "v": "微电影"}, {"n": "古装", "v": "古装"},
            {"n": "历史", "v": "历史"}, {"n": "运动", "v": "运动"},
            {"n": "农村", "v": "农村"}, {"n": "儿童", "v": "儿童"},
            {"n": "网络电影", "v": "网络电影"},
        ]
        tv_classes = [
            {"n": "全部", "v": ""}, {"n": "古装", "v": "古装"},
            {"n": "战争", "v": "战争"}, {"n": "青春偶像", "v": "青春偶像"},
            {"n": "喜剧", "v": "喜剧"}, {"n": "家庭", "v": "家庭"},
            {"n": "犯罪", "v": "犯罪"}, {"n": "动作", "v": "动作"},
            {"n": "奇幻", "v": "奇幻"}, {"n": "剧情", "v": "剧情"},
            {"n": "历史", "v": "历史"}, {"n": "经典", "v": "经典"},
            {"n": "乡村", "v": "乡村"}, {"n": "情景", "v": "情景"},
            {"n": "商战", "v": "商战"}, {"n": "网剧", "v": "网剧"},
            {"n": "其他", "v": "其他"},
        ]
        zongyi_classes = [
            {"n": "全部", "v": ""}, {"n": "选秀", "v": "选秀"},
            {"n": "情感", "v": "情感"}, {"n": "访谈", "v": "访谈"},
            {"n": "播报", "v": "播报"}, {"n": "旅游", "v": "旅游"},
            {"n": "音乐", "v": "音乐"}, {"n": "美食", "v": "美食"},
            {"n": "纪实", "v": "纪实"}, {"n": "曲艺", "v": "曲艺"},
            {"n": "生活", "v": "生活"}, {"n": "游戏互动", "v": "游戏互动"},
            {"n": "财经", "v": "财经"}, {"n": "求职", "v": "求职"},
        ]
        dongman_classes = [
            {"n": "全部", "v": ""}, {"n": "情感", "v": "情感"},
            {"n": "科幻", "v": "科幻"}, {"n": "热血", "v": "热血"},
            {"n": "推理", "v": "推理"}, {"n": "搞笑", "v": "搞笑"},
            {"n": "冒险", "v": "冒险"}, {"n": "萝莉", "v": "萝莉"},
            {"n": "校园", "v": "校园"}, {"n": "动作", "v": "动作"},
            {"n": "机战", "v": "机战"}, {"n": "运动", "v": "运动"},
            {"n": "战争", "v": "战争"}, {"n": "少年", "v": "少年"},
            {"n": "少女", "v": "少女"}, {"n": "社会", "v": "社会"},
            {"n": "原创", "v": "原创"}, {"n": "亲子", "v": "亲子"},
            {"n": "益智", "v": "益智"}, {"n": "励志", "v": "励志"},
            {"n": "其他", "v": "其他"},
        ]
        areas = [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
            {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
            {"n": "美国", "v": "美国"}, {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"}, {"n": "德国", "v": "德国"},
            {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
            {"n": "其他", "v": "其他"},
        ]
        langs = [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
            {"n": "粤语", "v": "粤语"}, {"n": "英语", "v": "英语"},
            {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"},
            {"n": "泰语", "v": "泰语"}, {"n": "法语", "v": "法语"},
            {"n": "德语", "v": "德语"}, {"n": "其他", "v": "其他"},
        ]
        years = [{"n": "全部", "v": ""}]
        for y in range(2026, 1999, -1):
            years.append({"n": str(y), "v": str(y)})
        sorts = [
            {"n": "时间", "v": "time"},
            {"n": "人气", "v": "hits"},
            {"n": "评分", "v": "score"},
        ]

        def make(class_list):
            return [
                {"key": "class", "name": "类型", "value": class_list},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "lang", "name": "语言", "value": langs},
                {"key": "year", "name": "年份", "value": years},
                {"key": "by", "name": "排序", "value": sorts},
            ]

        self._filters = {
            "1": make(movie_classes),
            "2": make(tv_classes),
            "3": make(zongyi_classes),
            "4": make(dongman_classes),
        }
        return self._filters

    # ========== 首页 ==========
    def homeContent(self, filter=False):
        categories = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
        ]
        # 走缓存，避免重复请求首页
        videos = self.homeVideoContent().get("list", [])
        return {
            "class": categories,
            "list": videos[:30],
            "filters": self._get_filters(),
        }

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 600:
            return {"list": self._home_cache}

        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html) if html else []
        self._home_cache = videos
        self._home_cache_time = now
        return {"list": videos}

    # ========== 分类 ==========
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
            if extend[k] == "" or extend[k] is None:
                del extend[k]

        paths = [f"id/{tid}"]
        has_filter = False

        if extend.get("class"):
            paths.append(f"class/{urllib.parse.quote(extend['class'])}")
            has_filter = True
        if extend.get("area"):
            paths.append(f"area/{urllib.parse.quote(extend['area'])}")
            has_filter = True
        if extend.get("lang"):
            paths.append(f"lang/{urllib.parse.quote(extend['lang'])}")
            has_filter = True
        if extend.get("year"):
            paths.append(f"year/{extend['year']}")
            has_filter = True
        by = extend.get("by", "time")
        if by and by != "time":
            paths.append(f"by/{by}")
            has_filter = True

        path_type = "show" if has_filter else "type"
        base_path = f"/index.php/vod/{path_type}/" + "/".join(paths)
        if page == 1:
            url = f"{self.site_url}{base_path}.html"
        else:
            url = f"{self.site_url}{base_path}/page/{page}.html"

        html = self._fetch(url)

        if not html or not self._extract_videos(html):
            if has_filter:
                fb_path = f"/index.php/vod/type/" + "/".join(paths)
                fb_url = (f"{self.site_url}{fb_path}.html" if page == 1
                          else f"{self.site_url}{fb_path}/page/{page}.html")
                fb_html = self._fetch(fb_url)
                if fb_html and self._extract_videos(fb_html):
                    html = fb_html

        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html) if html else 1

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)

        if page == 1:
            url = f"{self.site_url}/index.php/vod/search/wd/{keyword}.html"
        else:
            url = f"{self.site_url}/index.php/vod/search/wd/{keyword}/page/{page}.html"

        html = self._fetch(url)
        if not html or not self._extract_videos(html):
            get_url = f"{self.site_url}/index.php/vod/search.html?wd={keyword}"
            if page > 1:
                get_url += f"&page={page}"
            html2 = self._fetch(get_url)
            if html2 and self._extract_videos(html2):
                html = html2

        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html) if html else 1
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ========== 简介提取 ==========
    def _extract_content(self, html):
        if not html:
            return ""

        def _clean_text(s):
            t = self._clean(s)
            t = re.sub(r'^(?:剧情介绍|内容介绍|故事简介|简介|详情)\s*[:：]?\s*', '', t)
            t = re.sub(r'\s*(?:详情请|请收藏|本网站|更多精彩|更多内容).*$', '', t)
            return t.strip()

        # 1) 各类 content 容器
        for pat in _INTRO_PATTERNS:
            try:
                mm = re.search(pat, html, re.S | re.I)
            except Exception:
                continue
            if not mm:
                continue
            raw = mm.group(1) if mm.groups() else mm.group(0)
            txt = _clean_text(raw)
            if txt and len(txt) >= 15 and not txt.startswith('{'):
                return txt[:1200]

        # 2) meta description 兜底
        mm = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            html, re.I)
        if not mm:
            mm = re.search(
                r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
        if mm:
            raw = self._clean(mm.group(1))
            raw = re.sub(r'^.*?为你提供[^，,。]*[，,。]\s*', '', raw)
            raw = re.sub(r'^.*?(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*', '', raw)
            raw = re.sub(r'^[^，,。]{0,20}剧情介绍\s*[:：]\s*', '', raw)
            if raw and len(raw) >= 15:
                return raw[:1200]

        return ""

    # ========== JSON 变量提取：花括号配平 ==========
    def _slice_json(self, text, start):
        if start < 0 or start >= len(text) or text[start] != '{':
            return None
        depth = 0
        in_str = False
        q = ''
        esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == q:
                    in_str = False
                continue
            if c in ('"', "'"):
                in_str = True
                q = c
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    def _find_player_json(self, html):
        """查找 var player_xxx = {...} 的对象，返回 dict 或 None"""
        for m in re.finditer(r'var\s+(player_[A-Za-z0-9_]+)\s*=\s*\{', html):
            brace = html.find('{', m.start())
            if brace < 0:
                continue
            raw = self._slice_json(html, brace)
            if not raw:
                continue
            try:
                return json.loads(raw)
            except Exception:
                continue
        return None

    # ========== 详情 ==========
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.site_url}/index.php/vod/detail/id/{vid}.html"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # ---- 标题 ----
        name = vid
        year = ""
        tm = _RE_DETAIL_TITLE.search(html)
        if tm:
            name = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            ym = re.search(r'(\d{4})', name)
            if ym:
                year = ym.group(1)

        # ---- 封面 ----
        pic = self.default_pic
        pm = _RE_DETAIL_PIC.search(html)
        if pm:
            pic = self._fix_url(pm.group(1))

        # ---- 简介（重点：多层兜底）----
        content = self._extract_content(html)

        # ---- 元信息 ----
        director = ""
        actor = ""
        type_name = ""
        area = ""
        lang = ""

        dm = _RE_DETAIL_DIRECTOR.search(html)
        if dm:
            director = self._clean(dm.group(1))
            # 该正则抓的是整段（可能包含多个 <a>），清理链接标签后取纯文本
            director = re.sub(r'\s+', ' ', director).strip(' ，,、/')

        am = _RE_DETAIL_ACTOR.search(html)
        if am:
            actor = self._clean(am.group(1))
            actor = re.sub(r'\s+', ' ', actor).strip(' ，,、/')

        tpm = _RE_DETAIL_TYPE.search(html)
        if tpm:
            type_name = self._clean(tpm.group(1)).strip(' ，,、/')

        arm = _RE_DETAIL_AREA.search(html)
        if arm:
            area = self._clean(arm.group(1)).strip(' ，,、/')

        lam = _RE_DETAIL_LANG.search(html)
        if lam:
            lang = self._clean(lam.group(1)).strip(' ，,、/')

        # ---- 播放列表：按 sid 分组 ----
        # 结构: <a href="/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html">剧集名</a>
        play_from = []
        play_url = []
        lines = {}   # sid -> list[(nid, ep_name, play_id)]
        line_order = []  # 记录 sid 在 HTML 中的出现顺序

        for m in _RE_PLAY_LINK.finditer(html):
            play_href, play_vid, sid, nid, ep_raw = m.groups()
            sid = int(sid)
            nid = int(nid)
            ep_name = self._clean(ep_raw)
            if not ep_name:
                ep_name = f"第{nid}集"
            if sid not in lines:
                lines[sid] = []
                line_order.append(sid)
            existing = {e[0] for e in lines[sid]}
            if nid not in existing:
                lines[sid].append((nid, ep_name, play_href))

        # 排序各线路内的剧集
        for sid in lines:
            lines[sid].sort(key=lambda x: x[0])

        # 线路名：从 HTML 尝试抓（"由XXX提供"）
        line_names = {}
        for m in re.finditer(
                r'(?:player_infotip|play_list_box|play_source|tab)[^>]*>'
                r'([\s\S]{0,200}?)(?:由|来源)[：:]?\s*([^<\n，,]{2,20})',
                html, re.S):
            # 简化：记录“由XXX提供”式的名字
            pass
        for m in re.finditer(r'由([^<\n，,]{2,20})提供', html):
            # 用出现顺序绑定到 line_order
            pass

        # 更实用：用“播放列表 N”或“线路 N”
        # 苹果CMS海螺模板通常在 tab 里显示“量子资源”“非凡资源”等，抓不出来时用线路N
        source_tip_re = re.compile(
            r'<a[^>]*href="#playlist(\d+)"[^>]*>([^<]+)</a>', re.I)
        for m in source_tip_re.finditer(html):
            sid = int(m.group(1))
            nm = self._clean(m.group(2))
            if nm:
                line_names[sid] = nm

        for sid in line_order:
            eps = lines[sid]
            if not eps:
                continue
            play_from.append(line_names.get(sid, f"线路{sid}"))
            play_url.append("#".join(
                f"{ep_name}${play_href}" for _, ep_name, play_href in eps))

        if not play_url:
            play_from = ["默认线路"]
            play_url = [f"播放${vid}"]

        result = [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_type": type_name,
            "vod_play_from": '$$$'.join(play_from),
            "vod_play_url": '$$$'.join(play_url),
        }]
        return {"list": result}

    # ========== 播放 ==========
    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if "$" in id:
            play_url = id.split("$")[-1]

        now = int(time.time())
        cache_key = str(play_url)
        if cache_key in self._play_cache:
            ts, cached = self._play_cache[cache_key]
            if now - ts < 900:
                return cached

        if play_url.startswith("http") and self._is_media(play_url):
            res = {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self._extract_referer(play_url),
                },
            }
            self._play_cache[cache_key] = (now, res)
            return res

        if not play_url.startswith("/index.php/vod/play/"):
            if play_url.startswith("http"):
                res = {"parse": 0, "url": play_url, "header": self.headers}
            else:
                res = {
                    "parse": 1,
                    "url": f"{self.site_url}/index.php/vod/detail/id/{play_url}.html",
                    "header": self.headers,
                }
            self._play_cache[cache_key] = (now, res)
            return res

        url = f"{self.site_url}{play_url}"
        html = self._fetch(url)
        if html:
            obj = self._find_player_json(html)
            if obj:
                m3u8 = (obj.get("url", "") or "").strip()
                # 处理加密
                try:
                    encrypt = int(obj.get("encrypt", 0) or 0)
                except Exception:
                    encrypt = 0
                if m3u8 and encrypt == 1:
                    m3u8 = urllib.parse.unquote(m3u8)
                elif m3u8 and encrypt == 2:
                    try:
                        m3u8 = base64.b64decode(m3u8).decode('utf-8', 'ignore')
                    except Exception:
                        pass
                m3u8 = m3u8.replace("\\/", "/")
                if m3u8.startswith("//"):
                    m3u8 = "https:" + m3u8
                if m3u8.startswith("http"):
                    res = {
                        "parse": 0,
                        "url": m3u8,
                        "header": {
                            "User-Agent": UA,
                            "Referer": self._extract_referer(m3u8),
                        },
                    }
                    self._play_cache[cache_key] = (now, res)
                    return res

            # 兜底：HTML 里直接搜 m3u8/mp4
            mm = _RE_M3U8.search(html)
            if mm:
                u = mm.group(0).replace("\\/", "/")
                res = {
                    "parse": 0,
                    "url": u,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self._extract_referer(u),
                    },
                }
                self._play_cache[cache_key] = (now, res)
                return res
            mm = _RE_MP4.search(html)
            if mm:
                u = mm.group(0).replace("\\/", "/")
                res = {
                    "parse": 0,
                    "url": u,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self._extract_referer(u),
                    },
                }
                self._play_cache[cache_key] = (now, res)
                return res

        res = {
            "parse": 1,
            "url": url,
            "header": self.headers,
        }
        self._play_cache[cache_key] = (now, res)
        return res

    def _is_media(self, url):
        u = (url or "").lower()
        return ('.m3u8' in u or '.mp4' in u
                or '.flv' in u or '.mkv' in u)

    # ========== 代理 ==========
    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                params = {}
                if isinstance(param, str):
                    for pair in param.split("&"):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            params[k] = v
                url = params.get("url", "")

            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if '%' in url else url

            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/") and not url.startswith("//"):
                url = self.site_url + url

            referer = self._extract_referer(url)

            try:
                rsp = self.fetch(url, headers={
                    "User-Agent": UA,
                    "Referer": referer,
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                }, timeout=15)
                content = rsp.content
                ctype = rsp.headers.get("Content-Type", "image/jpeg")
            except Exception:
                content = b""
                ctype = "image/jpeg"

            if not content:
                return [200, "image/jpeg", b"", ""]
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

    # ========== 辅助 ==========
    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or url.startswith('http')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
