# coding=utf-8
"""
星空影视 yuntuzhijian.com | TVBox Python 爬虫 
站点形态: MacCMS V10 (stui_block mb13 主题), HTML 直出, 无 PoW / 验证码盾, 列表/详情/播放免登录。

分类(对齐站点顶部导航, 共六类):
  1 电影 / 2 电视剧 / 3 综艺 / 4 动漫 / 35 动画片 / 36 短剧。

路由(连字符槽位, 12 段; seg0 tid, seg1 地区, seg2 排序, seg3 题材, seg4 语言,
  seg5 字母, seg6/7/8 空, seg9 页码, seg10 空, seg11 年份[列表] / 关键词[搜索]):
  库页  /vodshow/<tid>-<area>-<by>-<class>-<lang>-<letter>----<page>--<year>.html
  搜索  /vodsearch/<tid>-<area>-<by>-<class>-<lang>-<letter>----<page>--<wd>.html
  详情  /voddetail/<vid>.html
  播放  /vodplay/<vid>-<sid>-<nid>.html

子类(站点分类面板 tid, 选中即 seg0 换 tid; 明细见 _SUBCAT):
  电影 6 动作片/7 喜剧片/8 爱情片/9 科幻片/10 恐怖片/11 剧情片/12 战争片/24 纪录片
  电视剧 13 国产剧/14 香港剧/15 台湾剧/16 日本剧/20 泰国剧/21 韩国剧/22 欧美剧/23 海外剧
  综艺 25 大陆综艺/26 港台综艺/27 日韩综艺/28 欧美综艺
  动漫 29 国产动漫/30 日韩动漫/31 港台动漫/32 欧美动漫/34 海外动漫
  短剧 37 女频恋爱/38 反转爽剧/39 年代穿越/40 脑洞悬疑/41 现代都市/42 古装仙侠/43 热血剧情

筛选 extend key: class(题材 seg3) / area(地区 seg1) / lang(语言 seg4) /
  year(年份 seg11) / by(排序 seg2: time 最新 / hits 人气 / score 评分) / letter(字母 seg5)。
  题材/地区/语言逐分类独立静态表(站点面板实证, 见下方 _FILTER_TABLE)。

详情: h1 片名; 封面 img.lazyload[data-original] 兜底 og:image; 评分 div.score span.branch;
  元信息 p.data 内 span.text-muted 标签 ↔ a 值配对(类型/地区/年份/语言/主演/导演/标签);
  简介 .detail-sketch → .detail-content → meta description 三层兜底; 前缀固定注入, 空简介只回前缀。
线路: div.stui-pannel-box.b.playlist.mb 盒, h3.title 线路名, 盒内 ul.stui-content__playlist li>a 选集;
  选集按末段 /<vid>-<sid>-<nid>.html 第二组 nid 数值正序(站点 DOM 已正序, 脚本仍重排保险)。

播放链:
  1) 播放页内嵌 player_aaaa = {flag, encrypt, from, url, url_next, sid, nid, ...}
  2) encrypt=0 且 url 为 http 直链 → parse:0 直链 m3u8/mp4
  3) 提取不到 / 加密 → parse:1 交壳子嗅探播放页
  直链 header 只带 UA(CDN 防盗链按 no-referrer 惯例, 不带 Referer)。

脚本文件名: spider_yuntuzhijian.py (交付 api 链接须含 .py 后缀, 满足壳子 isPy 判定)。
简介前缀固定注入; 源脚本名 / 远程 URL 结尾含 .py。
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
                print("[ytzj]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.yuntuzhijian.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/mb13/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点顶部导航） =====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "35", "type_name": "动画片"},
    {"type_id": "36", "type_name": "短剧"},
]

# 子类 tid（站点分类面板; extend.sub 传子类 tid 时 seg0 换 tid）
_SUBCAT = {
    "1":  [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
           ("10", "恐怖片"), ("11", "剧情片"), ("12", "战争片"), ("24", "纪录片")],
    "2":  [("13", "国产剧"), ("14", "香港剧"), ("15", "台湾剧"), ("16", "日本剧"),
           ("20", "泰国剧"), ("21", "韩国剧"), ("22", "欧美剧"), ("23", "海外剧")],
    "3":  [("25", "大陆综艺"), ("26", "港台综艺"), ("27", "日韩综艺"), ("28", "欧美综艺")],
    "4":  [("29", "国产动漫"), ("30", "日韩动漫"), ("31", "港台动漫"),
           ("32", "欧美动漫"), ("34", "海外动漫")],
    "36": [("37", "女频恋爱"), ("38", "反转爽剧"), ("39", "年代穿越"), ("40", "脑洞悬疑"),
           ("41", "现代都市"), ("42", "古装仙侠"), ("43", "热血剧情")],
}

# 排序（seg2; 站点面板: 按时间/按人气/按评分）; 选项统一为 {"n": 面板名, "v": 路由值} 对象
_SORTS = [{"n": "全部", "v": ""}, {"n": "最新", "v": "time"},
          {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_LETTERS = [{"n": "全部", "v": ""}] + [{"n": c, "v": c} for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [{"n": "0-9", "v": "0-9"}]

# 逐分类筛选面板（站点 show 页实证; v=路由值, n=面板名）
_FILTER_TABLE = {
    "1": {
        "area": ["其他", "加拿大", "印度", "台湾", "大陆", "德国", "意大利", "日本",
                 "法国", "泰国", "美国", "英国", "西班牙", "韩国", "香港"],
        "class": ["儿童", "冒险", "农村", "剧情", "动作", "动画", "历史", "古装", "喜剧",
                  "奇幻", "微电影", "恐怖", "悬疑", "惊悚", "战争", "文艺", "枪战", "武侠",
                  "爱情", "犯罪", "科幻", "经典", "网络电影", "警匪", "运动", "青春"],
        "lang": ["其它", "国语", "德语", "日语", "法语", "粤语", "英语", "闽南语", "韩语"],
    },
    "2": {
        "area": ["其他", "内地", "台湾", "新加坡", "日本", "泰国", "美国", "英国", "韩国", "香港"],
        "class": ["乡村", "其他", "剧情", "动作", "历史", "古装", "商战", "喜剧", "奇幻",
                  "家庭", "情景", "战争", "犯罪", "经典", "网剧", "青春偶像"],
        "lang": ["其它", "国语", "日语", "粤语", "英语", "闽南语", "韩语"],
    },
    "3": {
        "area": ["其他", "内地", "台湾", "新加坡", "日本", "泰国", "美国", "英国", "韩国", "香港"],
        "class": ["情感", "播报", "旅游", "曲艺", "求职", "游戏互动", "生活", "纪实",
                  "美食", "访谈", "财经", "选秀", "音乐"],
        "lang": ["其它", "国语", "日语", "粤语", "英语", "闽南语", "韩语"],
    },
    "4": {
        "area": ["其他", "内地", "台湾", "新加坡", "日本", "泰国", "美国", "英国", "韩国", "香港"],
        "class": ["亲子", "其他", "冒险", "动作", "励志", "原创", "少女", "少年", "情感",
                  "战争", "推理", "搞笑", "机战", "校园", "热血", "益智", "社会", "科幻",
                  "萝莉", "运动"],
        "lang": ["其它", "国语", "日语", "粤语", "英语", "闽南语", "韩语"],
    },
    "35": {
        "area": ["其他", "内地", "台湾", "新加坡", "日本", "泰国", "美国", "英国", "韩国", "香港"],
        "class": ["乡村", "其他", "剧情", "动作", "历史", "古装", "商战", "喜剧", "奇幻",
                  "家庭", "情景", "战争", "犯罪", "经典", "网剧", "青春偶像"],
        "lang": ["其它", "国语", "日语", "粤语", "英语", "闽南语", "韩语"],
    },
    "36": {
        "area": ["其他", "内地", "台湾", "新加坡", "日本", "泰国", "美国", "英国", "韩国", "香港"],
        "class": ["乡村", "其他", "剧情", "动作", "历史", "古装", "商战", "喜剧", "奇幻",
                  "家庭", "情景", "战争", "犯罪", "经典", "网剧", "青春偶像"],
        "lang": ["其它", "国语", "日语", "粤语", "英语", "闽南语", "韩语"],
    },
}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    tab = _FILTER_TABLE.get(tid, {})
    FILTERS[tid] = [
        {"key": "class", "name": "类型", "value": _opts(tab.get("class", []))},
        {"key": "area",  "name": "地区", "value": _opts(tab.get("area", []))},
        {"key": "lang",  "name": "语言", "value": _opts(tab.get("lang", []))},
        {"key": "year",  "name": "年份", "value": _YEARS},
        {"key": "by",    "name": "排序", "value": _SORTS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
    ]

# ===================== 正则 =====================
# 卡片: <a class="stui-vodlist__thumb lazyload" href="/voddetail/xx.html" title="片名" data-original="封面">
_RE_CARD = re.compile(
    r'<a[^>]*class="stui-vodlist__thumb[^"]*lazyload"[^>]*href="(/voddetail/\d+\.html)"[^>]*'
    r'(?:title="([^"]*)")?[^>]*?(?:data-original|data-src)="([^"]*)"', re.I)
# 兜底: 先取详情链接, 再在其块内找封面/标题
_RE_DETAIL_HREF = re.compile(r'href="(/voddetail/\d+\.html)"', re.I)
_RE_CARD_IMG = re.compile(r'<img[^>]*?(?:data-original|data-src)="([^"]*)"', re.I)
_RE_CARD_TITLE = re.compile(r'<h4[^>]*class="title[^"]*"[^>]*>\s*<a[^>]*title="([^"]*)"', re.I)
_RE_CARD_NOTE = re.compile(r'<span class="pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)
_RE_CARD_ACTOR = re.compile(r'<p class="text[^"]*"[^>]*>([\s\S]*?)</p>', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)', re.I)

# 详情元信息块: <p class="data..."><span class="text-muted">标签：</span><a ...>值</a>...
_RE_DATA_BLOCK = re.compile(r'<p class="data[^"]*">([\s\S]*?)</p>', re.I)
_RE_DATA_LABEL = re.compile(r'<span class="text-muted">([^<]*)</span>', re.I)
_RE_DATA_VAL = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)
_RE_SCORE = re.compile(r'<div class="score"[\s\S]*?<span class="branch">([\d.]+)</span>', re.I)

# 简介: .detail-sketch → .detail-content
_RE_INTRO_SKETCH = re.compile(r'<span class="detail-sketch">([\s\S]*?)</span>', re.I)
_RE_INTRO_FULL = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)

# 线路分组盒: h3.title 线路名 + ul.stui-content__playlist 选集
_RE_PLAYLIST = re.compile(
    r'<div class="stui-pannel-box b playlist mb">([\s\S]*?)(?=<div class="stui-pannel stui-pannel-bg'
    r'|<div class="stui-pannel-box"|剧情介绍|猜你喜欢|</body>)', re.I)
_RE_LINE_NAME = re.compile(r'<h3 class="title">([^<]*)</h3>', re.I)
_RE_EPISODE = re.compile(r'<li[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', re.I)
_RE_EP_NO = re.compile(r'/(\d+)-(\d+)\.html')

# 播放页 player_aaaa（JSON 后接 </script>，无分号结尾）
_RE_PLAYER = re.compile(r'player_aaaa=(\{[\s\S]*?\})', re.I)

_PAGE_LIMIT = 36


class Spider(Spider):

    def getName(self):
        return "星空影视"

    # ---------------- 工具 ----------------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
        except Exception:
            pass

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
             .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&middot;", "·"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 卡片提取 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 优先完整卡片匹配
        for href, title, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100] or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
                "vod_subtitle": "",
            })

        if videos:
            # 备注 / 副标题按详情链接块回填
            self._fill_notes(html, videos, seen)
            return videos

        # 兜底: 详情链接 + 块内封面/标题分离匹配
        hrefs = _RE_DETAIL_HREF.findall(html)
        imgs = _RE_CARD_IMG.findall(html)
        for i, href in enumerate(hrefs):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            pic = imgs[i] if i < len(imgs) else ""
            videos.append({
                "vod_id": href,
                "vod_name": href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
                "vod_subtitle": "",
            })
        return videos

    def _fill_notes(self, html, videos, seen):
        # 按 li 卡片块回填备注(pic-text)
        blocks = re.findall(r'<li class="col-[^"]*">([\s\S]*?)</li>', html, re.I)
        for blk in blocks:
            mh = _RE_DETAIL_HREF.search(blk)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            mn = _RE_CARD_NOTE.search(blk)
            note = self._clean(mn.group(1)) if mn else ""
            for v in videos:
                if v["vod_id"] == href:
                    v["vod_remarks"] = note

    # ---------------- 路由构造 ----------------
    def _build_url(self, kind, tid, extend, page, tail=""):
        area = extend.get("area") or ""
        by = extend.get("by") or ""
        cls = extend.get("class") or ""
        lang = extend.get("lang") or ""
        letter = extend.get("letter") or ""
        year = extend.get("year") or ""
        # 子类 tid 覆盖 seg0; 搜索通道跨分类, seg0 留空
        seg0 = "" if kind == "vodsearch" else (extend.get("sub") or tid)
        seg1 = urllib.parse.quote(area, safe="")
        seg2 = by
        seg3 = urllib.parse.quote(cls, safe="")
        seg4 = urllib.parse.quote(lang, safe="")
        seg5 = letter
        seg8 = str(page)
        seg11 = urllib.parse.quote(tail, safe="") if tail else year
        segs = [seg0, seg1, seg2, seg3, seg4, seg5, "", "", seg8, "", "", seg11]
        return self.site_url + "/%s/%s.html" % (kind, "-".join(segs))

    def homeContent(self, filter=False):
        return {"class": list(CLASSES), "filters": dict(FILTERS)}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        url = self._build_url("vodshow", tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  HTML 长度: %d, 卡片: %d" % (len(html), len(videos)))

        pagecount = page if len(videos) < _PAGE_LIMIT else page + 1
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": _PAGE_LIMIT, "total": pagecount * _PAGE_LIMIT,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip(), safe="")
        # 搜索 vodsearch 为 14 段槽位(实证): seg2 地区 / seg4 题材 / seg10 页码 / seg13 关键词
        segs = ["", "", "", "", "", "", "", "", "", "", str(page), "", "", keyword]
        url = self.site_url + "/vodsearch/" + "-".join(segs) + ".html"
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": page if len(videos) < _PAGE_LIMIT else page + 1,
            "limit": _PAGE_LIMIT, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 片名
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*[（(]\d{4}[)）]\s*$", "", name).strip() or vod_id

        # 封面: 详情封面 data-original 兜底 og:image
        pic = self.default_pic
        mi = re.search(
            r'<div class="stui-content__thumb">[\s\S]*?data-original="([^"]*)"', html)
        if mi:
            pic = self._fix_url(mi.group(1))
        else:
            mi = _RE_OG_IMG.search(html)
            if mi:
                pic = self._fix_url(mi.group(1))

        # 简介: .detail-sketch → .detail-content → meta description
        content = ""
        m = _RE_INTRO_SKETCH.search(html)
        if m:
            content = self._clean(m.group(1))
        if (not content or "暂无简介" in content):
            m = _RE_INTRO_FULL.search(html)
            if m:
                content = self._clean(m.group(1))
        if (not content or "暂无简介" in content):
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content or "暂无简介" in content:
            content = ""
        if content:
            content = re.sub(r"^\s*" + re.escape(name) + r"\s*", "", content).strip()
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # 元信息配对: 块内 span.text-muted 标签 ↔ 紧随 a 值交替扫描
        meta = {}
        for blk in _RE_DATA_BLOCK.findall(html):
            current = None
            for lab, val in re.findall(
                    r'<span class="text-muted">([^<]*)</span>|<a[^>]*>([^<]*)</a>', blk):
                if lab:
                    current = self._clean(lab).rstrip("：:")
                    meta.setdefault(current, [])
                elif val and current:
                    v = self._clean(val)
                    if v:
                        meta[current].append(v)
        meta = {k: ", ".join(v) for k, v in meta.items()}
        director = meta.get("导演", "")
        actor = meta.get("主演", "")
        year = meta.get("年份", "")
        area = meta.get("地区", "")
        vclass = meta.get("类型", "")
        lang = meta.get("语言", "")

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # ===== 线路与选集 =====
        play_from, play_url = [], []
        for box in _RE_PLAYLIST.findall(html):
            mn = _RE_LINE_NAME.search(box)
            line_name = self._clean(mn.group(1)) if mn else ""
            eps = _RE_EPISODE.findall(box)
            if not eps:
                continue

            def _ep_no(ep):
                em = _RE_EP_NO.search(ep[0])
                return int(em.group(2)) if em else 0

            eps = sorted(eps, key=_ep_no)
            # 去重
            seen_ep, uniq = set(), []
            for h, n in eps:
                if h in seen_ep:
                    continue
                seen_ep.add(h)
                uniq.append((h, n))
            alias = line_name or ("线路%d" % (len(play_from) + 1))
            play_from.append(alias)
            play_url.append("#".join(
                "%s$%s" % (self._clean(n) or ("第%d集" % (i + 1)), self._fix_url(h))
                for i, (h, n) in enumerate(uniq)))

        if not play_from:
            return {"list": []}

        remarks_parts = [x for x in (year, area, vclass) if x]
        remarks = " ".join(remarks_parts)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_class": vclass,
            "vod_lang": lang,
            "vod_score": score,
            "vod_subtitle": "",
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real = ""
        encrypt = 0

        m = _RE_PLAYER.search(html)
        if m:
            try:
                conf = json.loads(m.group(1))
                encrypt = int(conf.get("encrypt", 0) or 0)
                real = str(conf.get("url") or "")
            except Exception as e:
                self.log("  player_aaaa 解析失败: %s" % e)

        if real and real.startswith("http") and encrypt == 0:
            res = {
                "parse": 0, "playUrl": "", "url": real,
                "header": {"User-Agent": UA},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % real[:120])
            return res

        # 兜底: 交壳子嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    # ---------------- 壳子兼容方法 ----------------
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
            rsp = self.fetch(url, headers={"User-Agent": UA}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
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
