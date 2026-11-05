# coding=utf-8
"""
爱壹帆影视 dongganchaoren.com | TVBox Python 爬虫 
站点特征:
  - MacCMS V10 + template/nine (奈飞风格)
  - 分类页   : /genre/2x{tid}.html
  - 筛选列表 : /show/{tid}-{area}-{class}-{year}-{order}-{letter}-{page}.html
  - 详情页   : /show/2x{vod_id}.html
  - 播放页   : /viewing/2x{vod_id}/{sid}/{nid}.html
  - 播放器   : var player_aaaa={...,"url":"https://xxx/index.m3u8","from":"wjm3u8"}
说明:
  - 站点前置 Cloudflare, 偶发 520/403, 内置重试 + UA 轮换
"""
import re
import sys
import json
import time
import random
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

    class _BaseSpider(object):
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
            timeout = kw.pop('timeout', 20)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[donggan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站点常量 =====================
HOST = "https://dongganchaoren.com"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
UA_MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
UA_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
             "Mobile/15E148 Safari/604.1")
UA_LIST = [UA_PC, UA_MAC, UA_IPHONE]

DEFAULT_PIC = HOST + "/template/nine/statics/img/load.gif"

# 一级分类 (与站点 /genre/2x{id}.html 完全一致)
CLASSES = [
    {"type_id": "1x1",  "type_name": "电影"},
    {"type_id": "1x2",  "type_name": "电视剧"},
    {"type_id": "1x3",  "type_name": "综艺片"},
    {"type_id": "1x4",  "type_name": "动漫"},
    {"type_id": "1x24", "type_name": "短剧"},
]

# 站点真实子分类 (来自详情页面包屑 / 侧栏, 形如 /genre/2x44.html)
CLASS_MAP = {
    "1x1":  ["电影", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片",
             "战争片", "纪录片", "动画片", "伦理片", "预告片"],
    "1x2":  ["电视剧", "国产剧", "香港剧", "韩国剧", "欧美剧", "台湾剧", "日本剧",
             "海外剧", "泰剧"],
    "1x3":  ["综艺片", "大陆综艺", "港台综艺", "日韩综艺", "欧美综艺"],
    "1x4":  ["动漫", "国产动漫", "日韩动漫", "欧美动漫", "海外动漫"],
    "1x24": ["短剧", "AI漫剧"],
}

# 排序 (MacCMS 兼容: time/hits/score)
_SORTS = [
    {"n": "最新更新", "v": "time"},
    {"n": "最多播放", "v": "hits"},
    {"n": "评分最高", "v": "score"},
]

# 年份
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 地区
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"},
    {"n": "中国香港", "v": "中国香港"},
    {"n": "中国台湾", "v": "中国台湾"},
    {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"},
    {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"},
    {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"},
    {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"},
    {"n": "泰国", "v": "泰国"},
    {"n": "其他", "v": "其他"},
]

# 类型 (详情页 vod_class, 如 "漫剧")
_CLASSES_TYPE = {
    "1x1":  ["全部", "剧情", "喜剧", "动作", "爱情", "科幻", "恐怖", "悬疑",
             "犯罪", "冒险", "奇幻", "战争", "历史", "传记", "灾难", "武侠",
             "动画", "纪录片", "音乐", "歌舞", "家庭", "儿童", "运动", "西部"],
    "1x2":  ["全部", "剧情", "喜剧", "爱情", "悬疑", "犯罪", "动作", "古装",
             "都市", "家庭", "历史", "战争", "奇幻", "科幻", "青春", "武侠",
             "谍战", "军旅", "情感", "时装", "伦理", "搞笑", "热血"],
    "1x3":  ["全部", "真人秀", "脱口秀", "选秀", "访谈", "晚会", "综艺",
             "音乐", "游戏", "生活", "美食", "竞技", "文化", "喜剧"],
    "1x4":  ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
             "儿童", "悬疑", "国漫", "日漫", "玄幻", "治愈", "校园", "热血"],
    "1x24": ["全部", "短剧", "AI漫剧", "爱情", "剧情", "古装", "爽文", "穿越",
             "悬疑", "都市", "家庭", "喜剧", "奇幻", "玄幻", "犯罪", "复仇"],
}

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "class", "name": "分类",
         "value": list(CLASS_MAP.get(_tid, ["全部"]))},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "type", "name": "类型",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _CLASSES_TYPE.get(_tid, ["全部"])]},
        {"key": "order", "name": "排序", "value": _SORTS},
    ]

# 线路名 -> 展示名 (站点 player_aaaa.from)
_LINE_ALIAS = {
    "wjm3u8":  "无尽4K",
    "wjm3u8_2": "无尽4K备用",
    "lzm3u8":  "量子M3U8",
    "bfzym3u8": "暴风资源",
    "ffm3u8":  "非凡M3U8",
    "dyttm3u8": "电影天堂",
    "1080zyk": "1080资源",
    "modum3u8": "魔都M3U8",
    "jsm3u8":  "极速M3U8",
    "wolong":  "卧龙资源",
    "hnm3u8":  "红牛资源",
    "kuaikan": "快看资源",
}
# 线路优先级 (数字越小越靠前)
_LINE_PRIORITY = ["wjm3u8", "wjm3u8_2", "lzm3u8", "bfzym3u8", "ffm3u8",
                  "dyttm3u8", "1080zyk", "modum3u8", "jsm3u8", "wolong",
                  "hnm3u8", "kuaikan"]

# ===================== 正则 =====================
# 列表卡片: <a class="netflix-vodlist__thumb lazyload" href="/show/2x962740.html"
#              title="..." data-original="封面">
#              <span ...>0.0分</span><span class="pic-text text-right">全集</span>
_RE_CARD = re.compile(
    r'<a\s+class="netflix-vodlist__thumb[^"]*"\s+'
    r'href="(/show/[^"]+)"\s+title="([^"]*)"\s+'
    r'data-original="([^"]*)"'
    r'(.*?)</a>',
    re.S | re.I)

_RE_CARD_FALLBACK = re.compile(
    r'<h4\s+class="title[^"]*">\s*'
    r'<a\s+href="([^"]+)"\s+title="([^"]*)"',
    re.S | re.I)

_RE_PIC_TEXT = re.compile(
    r'<span\s+class="pic-text[^"]*">\s*([^<]*?)\s*</span>', re.I)
_RE_PIC_TAG = re.compile(
    r'<span\s+class="pic-tag[^"]*"[^>]*>\s*([^<]*?)\s*</span>', re.I)
_RE_ACTOR_TXT = re.compile(
    r'<p\s+class="text[^"]*">\s*主演[:：]\s*([^<]*)</p>', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>\s*([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_SCORE = re.compile(r'<span\s+class="branch">\s*([\d.]+)\s*</span>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<div\s+class="netflix-content__thumb">[\s\S]{0,400}?'
    r'<img[^>]*?(?:data-original|src)="([^"]+)"', re.I)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)', re.I)
_RE_OG_DESC = re.compile(
    r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)', re.I)

# 副标题: 详情页 <p class="data"><span class="text-muted">更新：</span>
#          <span class="text-red">全集/2026-11-03</span></p>
_RE_SUBTITLE = re.compile(
    r'<span\s+class="text-muted[^"]*">\s*更新\s*[:：]\s*</span>\s*'
    r'<span\s+class="text-red[^"]*">\s*([^<]*?)\s*</span>', re.I)

# 面包屑分类
_RE_BREAD = re.compile(
    r'<span\s+class="text-muted">当前位置：</span>(.*?)</div>', re.S | re.I)

# 元信息容器: 每条 <p class="data">...</p>
_RE_META_P = re.compile(r'<p\s+class="data[^"]*">([\s\S]*?)</p>', re.I)

# 元信息单行: <span class="text-muted">地区：</span><a ...>中国大陆</a>
# 注意: 站点的 span 没有闭合换行, 不能按 </p> 截断, 按整 p 处理后再切分
_RE_META_ROW = re.compile(
    r'<span\s+class="text-muted[^"]*">\s*(分类|地区|年份|主演|导演|更新|'
    r'语言|别名|人气|状态)\s*[:：]\s*</span>', re.I)

# 剧情简介
_RE_DESC_SKETCH = re.compile(
    r'<span\s+class="sketch content">([\s\S]*?)</span>', re.I)
_RE_DESC_FULL = re.compile(
    r'<span\s+class="data"\s+style="display:\s*none;">([\s\S]*?)</span>',
    re.I)
_RE_DESC_BOX = re.compile(
    r'id="desc"([\s\S]*?)<!--\s*剧情简介', re.I)

# 播放地址块
_RE_PLAY_BLOCK = re.compile(
    r'<h3\s+class="title">\s*播放地址\s*</h3>([\s\S]*?)'
    r'<div\s+class="netflix-vod-detail__extras">', re.I)
_RE_TAB = re.compile(
    r'<li[^>]*>\s*<a\s+href="#playlist(\d+)"[^>]*>\s*([^<]*?)\s*</a>', re.I)
_RE_PANE_START = re.compile(
    r'<div\s+id="playlist(\d+)"[^>]*>', re.I)
_RE_EP_LINK = re.compile(
    r'<a[^>]*class="btn[^"]*"[^>]*href="([^"]+)"[^>]*>\s*([^<]*?)\s*</a>', re.I)

# 播放页 player_aaaa:  JSON 含 \" 转义与嵌套对象, 不能用非贪婪匹配,
# 先定位起始位置再靠括号配对截取
_RE_PLAYER_START = re.compile(
    r'var\s+player_aaaa\s*=\s*\{', re.I)

_RE_IFRAME_URL = re.compile(
    r'<iframe[^>]+src="[^"]*?[?&]url=(https?://[^"&]+)', re.I)
_RE_M3U8_ANY = re.compile(r'(https?://[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*)', re.I)

# 分页
_RE_PAGER = re.compile(
    r'<a[^>]*href="[^"]*?/show/[^"]*?(\d+)\.html"[^>]*>\s*(?:末页|尾页)', re.I)
_RE_PAGER_NUM = re.compile(r'/show/[^"/]*?-(\d+)\.html', re.I)

# Cloudflare 错误页
_RE_CF_ERR = re.compile(
    r'Error code (?:520|521|522|523|524|525|526)|cf-error-details|'
    r'Web server is returning an unknown error', re.I)


class Spider(Spider):

    def getName(self):
        return "爱壹帆影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA_PC,
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._detail_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _warm_up(self):
        """先访首页拿 cookie / 过 CF 预热, 失败也不影响后续"""
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15, retry=1)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=20, headers=None, retry=3, allow_redirects=True):
        """带重试与 UA 轮换的 fetch; 站点偶发 520/403, 但 body 常有效"""
        h = dict(self.headers)
        if headers:
            h.update(headers)

        last_text = ""
        for attempt in range(max(1, retry)):
            try:
                if attempt > 0:
                    h["User-Agent"] = random.choice(UA_LIST)
                try:
                    rsp = self.fetch(url, headers=h, timeout=timeout,
                                     allow_redirects=allow_redirects)
                except TypeError:
                    rsp = self.fetch(url, headers=h, timeout=timeout)

                text = ""
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)

                if not text:
                    continue

                # CF 错误页 -> 重试
                if _RE_CF_ERR.search(text[:4000]):
                    last_text = ""
                    self.log("  CF 错误页 (try %d): %s" % (attempt + 1, url[:80]))
                    if attempt + 1 < retry:
                        time.sleep(1 + attempt)
                    continue

                # 短内容视为失败
                if len(text) < 2000:
                    last_text = text
                    if attempt + 1 < retry:
                        time.sleep(1)
                    continue

                return text
            except Exception as e:
                self.log("  fetch FAIL (try %d) %s -> %s"
                         % (attempt + 1, url[:80], e))
                if attempt + 1 < retry:
                    time.sleep(1)
        return last_text

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
              .replace("&#39;", "'").replace("&lt;", "<")
              .replace("&gt;", ">").replace("&ldquo;", "“")
              .replace("&rdquo;", "”"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _norm_id(self, vod_id):
        """统一成 /show/2x{id}.html 形式"""
        vod_id = str(vod_id or "").strip()
        if not vod_id:
            return ""
        if vod_id.startswith("http"):
            return vod_id
        if vod_id.startswith("/"):
            return self.site_url + vod_id
        if re.match(r"^\d+$", vod_id):
            return "%s/show/2x%s.html" % (self.site_url, vod_id)
        if vod_id.startswith("2x"):
            return "%s/show/%s.html" % (self.site_url, vod_id)
        return "%s/show/%s.html" % (self.site_url, vod_id)

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html, limit=0):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href = m.group(1)
            name = self._clean(m.group(2))
            pic = m.group(3)
            inner = m.group(4) or ""

            if href in seen:
                continue
            seen.add(href)

            remarks = ""
            mt = _RE_PIC_TEXT.search(inner)
            if mt:
                remarks = self._clean(mt.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    name or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        # 兜底: 只拿到 h4 标题的情况
        if not videos:
            for m in _RE_CARD_FALLBACK.finditer(html):
                href = m.group(1)
                if href in seen or "/show/" not in href:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(m.group(2)) or href,
                    "vod_pic":     self.default_pic,
                    "vod_remarks": "",
                })

        if limit and len(videos) > limit:
            videos = videos[:limit]
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        nums = [int(x) for x in _RE_PAGER_NUM.findall(html) if x.isdigit()]
        nums = [n for n in nums if n < 999999]
        if nums:
            return max(max(nums), 1)
        m = _RE_PAGER.search(html)
        if m:
            try:
                return max(int(m.group(1)), 1)
            except Exception:
                pass
        return 9999

    def _build_list_url(self, tid, page, extend):
        """构造筛选列表 URL
        /show/{tid}-{area}-{class}-{year}-{order}-{letter}-{page}.html
        """
        tid_num = tid.split("x")[-1] if "x" in tid else tid
        area = (extend.get("area") or "").strip()
        cls = (extend.get("class") or "").strip()
        year = (extend.get("year") or "").strip()
        order = (extend.get("order") or "").strip()
        letter = (extend.get("letter") or "").strip()

        # 类型(vod_class) 站点筛选位: 放到 class 位, 用 type 兜底
        if cls and cls not in ("全部", tid):
            pass
        elif extend.get("type"):
            cls = (extend.get("type") or "").strip()

        segs = [tid_num, area, cls, year, order, letter]
        if page and int(page) > 1:
            segs.append(str(int(page)))

        body = "-".join(urllib.parse.quote(s, safe="") for s in segs)
        return "%s/show/%s.html" % (self.site_url, body)

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            self._warm_up()
            html = self._fetch(self.site_url + "/", retry=3)
            self.log("home HTML 长度: %d" % len(html))
            videos = self._extract_videos(html)
            self.log("home 视频数: %d" % len(videos))
            return {"list": videos}
        except Exception as e:
            self.log("homeVideoContent err: %s" % e)
            return {"list": []}

    # ---------------- 分类 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        extend = {k: v for k, v in extend.items()
                  if v not in ("", None, "全部")}

        # 无筛选时直接走分类页, 性能更好
        url = self._build_list_url(tid, page, extend)
        self.log("category: %s" % url)

        html = self._fetch(url, retry=3)

        # 分类页 / 筛选页都拿不到卡片 -> 退回 /genre/2xN.html
        videos = self._extract_videos(html)
        used_genre = False
        if not videos:
            tid_num = tid.split("x")[-1] if "x" in tid else tid
            alt = "%s/genre/2x%s.html" % (self.site_url, tid_num)
            if page > 1:
                alt += "?page=%d" % page
            self.log("  回退分类页: %s" % alt)
            html2 = self._fetch(alt, retry=2)
            v2 = self._extract_videos(html2)
            if v2:
                videos, html = v2, html2
                used_genre = True

        pagecount = self._page_count(html)
        if used_genre and pagecount >= 9999:
            # 该站 /genre 页为推荐聚合页, 无分页器; 筛选页才有真实分页
            pagecount = page if videos else 1

        self.log("  结果: %d 条, 页数: %s" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) or 24,
            "total": pagecount * (len(videos) or 24),
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick=False, pg="1"):
        self._warm_up()
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        kw = urllib.parse.quote(key, safe="")
        url = "%s/search/wd/%s.html" % (self.site_url, kw)
        if page > 1:
            url += "?page=%d" % page
        self.log("search: %s" % url)

        html = self._fetch(url, retry=3)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("  结果: %d" % len(videos))

        return {
            "list": videos,
            "page": page,
            "pagecount": self._page_count(html),
            "limit": len(videos) or 24,
            "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def _parse_meta(self, html):
        """解析 分类/地区/年份/主演/导演/更新/语言 等行
        站点结构: <p class="data"><span class="text-muted">分类：</span>
                  <a href="...">短剧</a><span class="split-line"></span>...
                  </p>
        同一 p 内可能有多组 标签:值, 按 split-line 切分
        """
        meta = {}

        for pm in _RE_META_P.finditer(html):
            body = pm.group(1)
            heads = list(_RE_META_ROW.finditer(body))
            if not heads:
                continue

            for i, hm in enumerate(heads):
                key = hm.group(1)
                start = hm.end()
                end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
                seg = body[start:end]

                # 去掉 split-line 标记
                seg = re.sub(r'<span\s+class="split-line"></span>', "|", seg)

                links = re.findall(r'>\s*([^<>]+?)\s*</a>', seg)
                if links:
                    vals = [x.strip() for x in links if x.strip()]
                else:
                    vals = [self._clean(x) for x in seg.split("|")]

                vals = [re.sub(r"^[：:\s]+", "", v).strip() for v in vals]
                vals = [v for v in vals
                        if v and v not in ("详情", "|", "&nbsp;")]
                val = " / ".join(vals)
                val = re.sub(r"\s*/\s*$", "", val).strip()
                if val and key not in meta:
                    meta[key] = val

        return meta

    def _parse_episodes(self, html):
        """解析播放地址: 返回 [(线路名, [(集名, 播放页url), ...]), ...]
        保持站点 tab 原始顺序
        """
        block = _RE_PLAY_BLOCK.search(html)
        if not block:
            m = re.search(r'播放地址([\s\S]*)$', html)
            block_html = m.group(1) if m else ""
        else:
            block_html = block.group(1)

        if not block_html:
            return []

        # tab 顺序
        tabs = []
        for m in _RE_TAB.finditer(block_html):
            idx = int(m.group(1))
            name = self._clean(m.group(2)) or ("线路%d" % idx)
            if idx not in [t[0] for t in tabs]:
                tabs.append((idx, name))

        # 每个 pane 的剧集: 按 <div id="playlistN"> 起始位置切片,
        # 避免非贪婪 </div> 把多个 pane 并到一起
        starts = list(_RE_PANE_START.finditer(block_html))
        panes = {}
        for i, sm in enumerate(starts):
            idx = int(sm.group(1))
            end = starts[i + 1].start() if i + 1 < len(starts) else len(block_html)
            body = block_html[sm.end():end]
            if idx in panes:      # 同一线路多次出现, 合并
                continue
            eps = []
            for mm in _RE_EP_LINK.finditer(body):
                href = mm.group(1)
                name = self._clean(mm.group(2))
                if not href or "/viewing/" not in href:
                    continue
                eps.append((name or ("第%d集" % (len(eps) + 1)),
                            self._fix_url(href.replace("&amp;", "&"))))
            if eps:
                panes[idx] = eps

        if not tabs:
            tabs = [(k, "线路%d" % k) for k in sorted(panes.keys())]

        groups = []
        for idx, name in tabs:
            eps = panes.get(idx) or []
            if eps:
                groups.append((name, eps))
        return groups

    def _extract_player_json(self, html):
        """提取 var player_aaaa={...} 的 JSON 对象 (括号配对, 支持转义)"""
        if not html:
            return {}
        m = _RE_PLAYER_START.search(html)
        if not m:
            return {}

        start = m.end() - 1          # 指向 '{'
        depth = 0
        in_str = False
        esc = False

        for i in range(start, min(len(html), start + 20000)):
            ch = html[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = html[start:i + 1]
                    try:
                        obj = json.loads(raw)
                        return obj if isinstance(obj, dict) else {}
                    except Exception:
                        # 站内常见 \/ 转义, 个别字段可能非法, 用宽松兜底
                        try:
                            obj = json.loads(raw.replace("\\/", "/"))
                            return obj if isinstance(obj, dict) else {}
                        except Exception:
                            return {}
        return {}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = str(ids[0])
        url = self._norm_id(vod_id)
        self.log("detail: %s" % url)

        # 缓存 5 分钟
        now = int(time.time())
        if url in self._detail_cache:
            ts, res = self._detail_cache[url]
            if now - ts < 300:
                return res

        html = self._fetch(url, retry=3)
        self.log("  HTML 长度: %d" % len(html))
        if not html or _RE_CF_ERR.search(html[:4000]):
            return {"list": []}

        # ---- 标题 / 副标题 ----
        name = ""
        m = _RE_H1.search(html) or _RE_H1_ANY.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1))
                name = re.split(r"[《》\-_|]", name)
                name = max(name, key=len).strip() if name else ""
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        sub_title = ""
        # 站点副标题: "全集/2026-11-03" 或 "106分钟/2026-07-27"
        m = _RE_SUBTITLE.search(html)
        if m:
            sub_title = self._clean(m.group(1))
        # 兜底: 详情页封面角标 <span class="pic-text text-right">高清</span>
        if not sub_title:
            m = _RE_PIC_TEXT.search(html)
            if m:
                sub_title = self._clean(m.group(1))

        # ---- 封面 ----
        pic = ""
        m = _RE_DETAIL_PIC.search(html) or _RE_OG_IMG.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic:
            pic = self.default_pic

        # ---- 元信息 ----
        meta = self._parse_meta(html)
        area = meta.get("地区", "")
        year = meta.get("年份", "")
        category = meta.get("分类", "")
        actor = meta.get("主演", "")
        director = meta.get("导演", "")
        updated = meta.get("更新", "")
        lang = meta.get("语言", "")
        alias = meta.get("别名", "")

        # 备注(副标题): 优先站点 text-red 副标题, 其次状态, 再其次别名/更新
        remarks = sub_title or meta.get("状态", "") or alias or updated

        # ---- 评分 ----
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # ---- 简介 ----
        content = ""
        box = _RE_DESC_BOX.search(html)
        scope = box.group(1) if box else html

        m = _RE_DESC_FULL.search(scope)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC_SKETCH.search(scope)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = _RE_OG_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            # 详情页顶部 p.desc
            m = re.search(r'<p\s+class="desc[^"]*">([\s\S]*?)</p>', html, re.I)
            if m:
                content = self._clean(m.group(1))

        content = content.strip()
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ---- 剧集 ----
        groups = self._parse_episodes(html)
        self.log("  线路: %s" % {k: len(v) for k, v in groups})

        if not groups:
            # 无播放源: 仍返回详情, 便于用户看到信息
            return {"list": [{
                "vod_id":       vod_id,
                "vod_name":     name,
                "vod_pic":      pic,
                "vod_content":  content,
                "vod_actor":    actor or "未知",
                "vod_director": director or "未知",
                "vod_area":     area,
                "vod_year":     year,
                "vod_lang":     lang,
                "vod_score":    score,
                "vod_remarks":  remarks,
                "vod_class":    category,
                "vod_play_from": "",
                "vod_play_url":  "",
                "vod_pubdate":  updated,
            }]}

        # 线路排序: 已知线路按优先级, 其余保持站点原顺序
        def _key(item):
            n = item[0]
            if n in _LINE_PRIORITY:
                return _LINE_PRIORITY.index(n)
            return 500 + len(_LINE_PRIORITY)

        # 先保持原顺序, 再按优先级稳定排序(站点 tab 顺序为主)
        order_origin = {n: i for i, (n, _) in enumerate(groups)}
        groups_sorted = sorted(
            groups, key=lambda x: (_key(x), order_origin.get(x[0], 999)))

        play_from = []
        play_url = []
        for gname, eps in groups_sorted:
            play_from.append(gname)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        res = {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor or "未知",
            "vod_director": director or "未知",
            "vod_area":     area,
            "vod_year":     year,
            "vod_lang":     lang,
            "vod_score":    score,
            "vod_remarks":  remarks,
            "vod_class":    category,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
            "vod_pubdate":  updated,
        }]}

        self._detail_cache[url] = (now, res)
        return res

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = self._norm_id(id) if "/viewing/" not in str(id) \
            else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page, retry=3,
                           headers={"Referer": self.site_url + "/"})

        m3u8 = ""
        from_ = ""
        if html:
            cfg = self._extract_player_json(html)
            if cfg:
                m3u8 = cfg.get("url", "") or ""
                from_ = cfg.get("from", "") or ""
                enc = cfg.get("encrypt", 0)
                if enc and m3u8:
                    self.log("  检测到 encrypt=%s, 尝试直接使用" % enc)
                # url_next 兜底
                if not m3u8:
                    m3u8 = cfg.get("url_next", "") or ""

            if not m3u8:
                m2 = _RE_IFRAME_URL.search(html)
                if m2:
                    m3u8 = urllib.parse.unquote(m2.group(1))

            if not m3u8:
                m3 = _RE_M3U8_ANY.search(html)
                if m3:
                    m3u8 = m3.group(1).replace("\\/", "/")

        if m3u8:
            m3u8 = m3u8.replace("\\/", "/").replace("&amp;", "&").strip()
            self.log("  from=%s => m3u8: %s" % (from_, m3u8[:160]))

            # 站点直链 m3u8 一般无防盗链, 但带上 Referer 更稳
            header = {
                "User-Agent": UA_PC,
                "Referer": self.site_url + "/",
            }
            if "ppqrrs" in m3u8 or "wjv1" in m3u8:
                header["Referer"] = self.site_url + "/"

            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": header,
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 交 TVBox 嗅探
        self.log("  未取到 m3u8, 交给解析")
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {
                "User-Agent": UA_PC,
                "Referer": self.site_url + "/",
            },
        }
        self._play_cache[play_page] = (now, res)
        return res

    # ---------------- 其他 ----------------
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
            if "%" in url:
                url = urllib.parse.unquote(url)
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA_PC,
                "Referer": self.site_url + "/",
            }, timeout=20)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return ".m3u8" in u or ".mp4" in u or ".flv" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
