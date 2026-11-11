# coding=utf-8
"""
4K电影网 zzhczj.com | TVBox Python 爬虫 
关键:
  - 全站伪静态路由（2026-11-11 从缓存页真实链接逐字实测）:
      频道      /unit/{type_id}.html         分页 /unit/{type_id}-{page}.html
      筛选      /pack/[by/{排序}/][class/{类型}/][area/{地区}/area/{年份}/area/{语言}/]\
id/{频道或分类ID}[/page/{页}][/letter/{字母}].html
                ★ 该站模板把「年份」「语言」与「地区」共用 area 段:
                  网页真实链接为 /pack/area/2018/id/13.html、/pack/area/国语/id/13.html
                  （旧拼法 /pack/id/13/year/2018.html 会导致 CF 缓存永不命中）
                （「按分类」是独立分类 id：国产剧=/pack/id/13.html 等）
      详情      /pagevid/{vod_id}.html
      播放      /slotplay/{vod_id}/{sid}/{nid}.html
  - 筛选 7 维与网页端 100% 同步: 分类(cat=站点真实分类id)/类型/地区/年份/语言/字母/排序，
    启动时实时抓站点筛选区解析（行级判定年份/语言，与网页逐字一致）；
    筛选翻页优先走页面真实分页链接
  - 线路顺序严格按详情页「切换来源」下拉的显示顺序（页面里线路名与 sid 并不对应）
  - 播放直链从 player_aaaa 提取；当前线路播放页拿不到（源站520）时自动接力其它线路同集，
    成功结果缓存 1 小时；所有 m3u8 已实测可直连（仅需 UA）
  - 列表「副标题」取缩略图角标 pic-text（正片 / 已完结 / 更新至xxxx期）
  - 源站半残: Cloudflare 边缘有缓存的页面 200，回源全部 520 →
    内置重试 + 页面结果缓存(5分钟)/负缓存(1分钟)，成功过一次的内容之后秒开
"""
import re
import sys
import json
import time
import base64
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
            method = kw.pop('method', 'get')
            data = kw.pop('data', None)
            if str(method).lower() == 'post':
                r = self._sess.post(url, headers=headers, timeout=timeout, data=data, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, data=None, headers=None, **kw):
            kw['method'] = 'post'
            kw['data'] = data
            return self.fetch(url, headers=headers, **kw)

        def log(self, *a, **kw):
            try:
                print("[zzhczj]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zzhczj.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/hl034/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# ===== 静态兜底（homeContent 优先从站点实时解析，解析失败才用这份）=====
# 以下全部为 2026-11-11 从 5 个频道页实测抓取的真实值（含各频道真实分类 id）
# 注意：短剧频道网页上就没有类型/地区/年份筛选，兜底也保持为空
# 「按分类」是独立分类 id（/pack/id/{N}.html）
_CAT_MAP = {
    "1": [("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
          ("剧情片", "10"), ("战争片", "11"), ("动画片", "41"), ("记录片", "12"),
          ("恐怖片", "39")],
    "2": [("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"),
          ("欧美剧", "16"), ("台湾剧", "22"), ("日本剧", "21"),
          ("泰国剧", "20"), ("海外剧", "23")],
    "3": [("大陆综艺", "25"), ("日韩综艺", "26"), ("港台综艺", "27"),
          ("欧美综艺", "28")],
    "4": [("国产动漫", "29"), ("日本动漫", "30"), ("港台动漫", "42"),
          ("欧美动漫", "31"), ("海外动漫", "43")],
    "24": [("短剧大全", "40"), ("AI漫剧", "44")],
}

_CLASS_MAP = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
          "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
          "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
          "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
          "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
          "曲艺", "生活", "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
          "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
          "亲子", "益智", "励志", "其他"],
    "24": [],  # 网页上短剧频道无类型筛选
}

_AREA_MAP = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
    "24": [],  # 网页上短剧频道无地区筛选
}

_YEAR_MAP = {
    "1": [str(y) for y in range(2026, 2009, -1)],
    "2": [str(y) for y in range(2026, 2009, -1)],
    "3": [str(y) for y in range(2018, 2003, -1)],
    "4": [str(y) for y in range(2018, 2003, -1)],
    "24": [],  # 网页上短剧频道无年份筛选
}

_LANG_MAP = {
    "1": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    "2": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "3": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "4": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "24": [],
}

_LETTERS = [{"n": "全部", "v": ""}] + \
           [{"n": x, "v": x} for x in
            list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]]

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _data = []
    if _CAT_MAP.get(_tid):
        _data.append({"key": "cat", "name": "分类",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": n, "v": v} for n, v in _CAT_MAP[_tid]]})
    if _CLASS_MAP.get(_tid):
        _data.append({"key": "class", "name": "类型",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _CLASS_MAP[_tid]]})
    if _AREA_MAP.get(_tid):
        _data.append({"key": "area", "name": "地区",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _AREA_MAP[_tid]]})
    if _YEAR_MAP.get(_tid):
        _data.append({"key": "year", "name": "年份",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _YEAR_MAP[_tid]]})
    if _LANG_MAP.get(_tid):
        _data.append({"key": "lang", "name": "语言",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _LANG_MAP[_tid]]})
    _data.append({"key": "letter", "name": "字母", "value": _LETTERS})
    _data.append({"key": "sort", "name": "排序", "value": _SORTS})
    FILTERS[_tid] = _data


# ===================== 正则 =====================
# 列表卡片：<li class="stui-vodlist__item"> ... </li>
_RE_ITEM_BLOCK = re.compile(
    r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>([\s\S]*?)</li>', re.I)

_RE_HREF_PAGEVID = re.compile(r'href="([^"]*?/pagevid/[^"]+?)"', re.I)
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC_ATTR = re.compile(r'(?:data-original|data-src|data-echo|src)="([^"]+)"', re.I)
_RE_PIC_TEXT = re.compile(
    r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)

# 旧式卡片（兜底：整段直配）
_RE_CARD_FALLBACK = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="(/pagevid/[^"]+)"'
    r'[^>]*title="([^"]*)"[^>]*?(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

# 分页
_RE_PAGE_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-page[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_TOTAL_PAGE = re.compile(r'<span[^>]*class="[^"]*num[^"]*"[^>]*>\s*\d+\s*/\s*(\d+)\s*</span>', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>', re.I)

# 筛选区
_RE_SCREEN_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-screen__list[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_SCREEN_LABEL = re.compile(
    r'<span[^>]*class="[^"]*text-muted[^"]*"[^>]*>\s*按([^<]{1,6})</span>', re.I)
_RE_NAV_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-pannel__nav[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_BY_VAL = re.compile(r'/by/([A-Za-z0-9_]+)/', re.I)

# 详情页
_RE_DETAIL_AREA = re.compile(
    r'<div[^>]*class="[^"]*stui-content__detail[^"]*"[^>]*>([\s\S]*?)<div[^>]*class="[^"]*playbtn',
    re.I)
_RE_H3_TITLE = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_SCORE = re.compile(r'<span[^>]*class="[^"]*score[^"]*"[^>]*>\s*([\d.]+)\s*<', re.I)
_RE_TYPE = re.compile(r'类型：</span>\s*([^<]*)<', re.I)
_RE_AREA = re.compile(r'地区：</span>\s*([^<]*)<', re.I)
_RE_YEAR = re.compile(r'年份：</span>\s*([^<]*)<', re.I)
_RE_ACTOR = re.compile(r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*主演：\s*</span>([\s\S]*?)</p>', re.I)
_RE_DIRECTOR = re.compile(r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*导演：\s*</span>([\s\S]*?)</p>', re.I)
_RE_DESC_BLOCK = re.compile(
    r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_DESC_SHORT = re.compile(
    r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_PIC_TEXT_DETAIL = re.compile(
    r'<div[^>]*class="[^"]*stui-content__thumb[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_TAG_TITLE = re.compile(r'<title>([\s\S]*?)</title>', re.I)

# 播放列表
_RE_PLAYLIST_ZONE = re.compile(
    r'id="playlist"([\s\S]*?)(?:<!--\s*end 播放列表|剧情介绍)', re.I)
_RE_TAB_ITEM = re.compile(
    r'<a[^>]*href="#playlist(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_BLOCK = re.compile(
    r'<div[^>]*id="playlist(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页
_RE_PLAYER_OBJ = re.compile(r'player_[A-Za-z0-9_]{0,24}\s*=\s*\{')
_RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
_RE_M3U8 = re.compile(r'(https?:)?//[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*', re.I)
_RE_MP4 = re.compile(r'(https?:)?//[^\s"\'<>\\]+?\.mp4[^\s"\'<>\\]*', re.I)
# MacPlayer / 自定义播放器：url:"..." / Url:"..."
_RE_ANY_URL = re.compile(
    r'["\']?(?:url|Url|link|Link|src)["\']?\s*[:=]\s*["\']((?:https?:)?//[^"\']{10,})["\']')


class Spider(Spider):

    def getName(self):
        return "4K电影网"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        if not isinstance(self.extend, dict):
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._page_cache = {}
        self._filters_cache = None
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    # ---------------------------------------------------------------- 基础
    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=12, retry=1)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _resp_text(self, rsp):
        if rsp is None:
            return ""
        try:
            if hasattr(rsp, "text") and rsp.text:
                return rsp.text
            if hasattr(rsp, "content"):
                return (rsp.content or b"").decode("utf-8", "ignore")
        except Exception:
            pass
        try:
            return str(rsp)
        except Exception:
            return ""

    def _fetch(self, url, timeout=20, headers=None, retry=3, data=None):
        """GET/POST 抓取，自带 520 / 空响应重试"""
        if not url:
            return ""
        for i in range(max(1, retry)):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                if data is not None:
                    try:
                        rsp = self.fetch(url, headers=h, timeout=timeout,
                                         method="post", data=data)
                    except TypeError:
                        rsp = self.fetch(url, headers=h, timeout=timeout, data=data)
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
                text = self._resp_text(rsp)
                code = getattr(rsp, "status_code", 0) or 0
                low = text or ""
                bad = (code in (403, 429, 502, 503, 520, 521, 522, 524)
                       or re.search(r"error\s*code[:\s]*5\d\d", low, re.I)
                       or "Web server is returning an unknown error" in low
                       or "cf-error-details" in low
                       or len(low) < 120)
                if not bad:
                    return text
                if i < retry - 1:
                    time.sleep(0.7 + i * 0.8 + random.random() * 0.4)
            except Exception as e:
                if i >= retry - 1:
                    self.log("fetch FAIL %s -> %s" % (url, e))
                time.sleep(0.6)
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
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
              .replace("&ldquo;", "“").replace("&rdquo;", "”")
              .replace("&hellip;", "…").replace("&mdash;", "—"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _safe_name(self, s):
        s = self._clean(s)
        s = s.replace("$", " ").replace("#", " ").replace("$$$", " ")
        return s.strip() or "正片"

    # ---------------------------------------------------------------- 列表
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for blk in _RE_ITEM_BLOCK.findall(html):
            mh = _RE_HREF_PAGEVID.search(blk)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            if href in seen:
                continue

            mt = _RE_TITLE_ATTR.search(blk)
            name = self._clean(mt.group(1)) if mt else ""

            pic = ""
            for cand in _RE_PIC_ATTR.findall(blk):
                if cand and "load.gif" not in cand and not cand.startswith("data:"):
                    pic = cand
                    break

            remarks = ""
            mp = _RE_PIC_TEXT.search(blk)
            if mp:
                remarks = self._clean(mp.group(1))

            if not name:
                ml = re.findall(r'>([^<>]{1,60})</a>', blk)
                name = self._clean(ml[-1]) if ml else ""

            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name or href.split("/")[-1].replace(".html", ""),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        if videos:
            return videos

        # 兜底：整段直配
        for href, alt, pic in _RE_CARD_FALLBACK.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt) or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_TOTAL_PAGE.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        blk = _RE_PAGE_BLOCK.search(html)
        if blk:
            nums = []
            for href, txt in _RE_A_TAG.findall(blk.group(1)):
                t = self._clean(txt)
                if t.isdigit():
                    nums.append(int(t))
                if "尾页" in t:
                    mm = re.search(r"-(\d+)\.html", href) or re.search(r"/(\d+)\.html", href)
                    if mm:
                        nums.append(int(mm.group(1)))
            if nums:
                return max(nums)
        return 1

    def _page_tpl(self, html):
        """从分页区反推页码模板，如 /unit/1-2.html -> /unit/1-{p}.html"""
        blk = _RE_PAGE_BLOCK.search(html or "")
        if not blk:
            return ""
        block = blk.group(1)
        for href, txt in _RE_A_TAG.findall(block):
            t = self._clean(txt)
            if not t.isdigit() or not href:
                continue
            n = t
            cands = ["-%s.html" % n, "_%s.html" % n, "/page/%s.html" % n,
                     "/page/%s" % n, "page=%s" % n, "/%s.html" % n, "-%s-" % n]
            for pat in cands:
                if pat in href:
                    return href.replace(pat, pat.replace(n, "{p}"), 1)
        return ""

    def _page_url(self, html, cur_url, page):
        """取第 page 页的真实地址"""
        if page <= 1:
            return cur_url
        blk = _RE_PAGE_BLOCK.search(html or "")
        if blk:
            for href, txt in _RE_A_TAG.findall(blk.group(1)):
                if self._clean(txt) == str(page) and href:
                    return self._fix_url(href)
        tpl = self._page_tpl(html)
        if tpl:
            return self._fix_url(tpl.replace("{p}", str(page)))
        return ""

    # ---------------------------------------------------------------- 筛选
    def _key_from_href(self, href):
        h = href or ""
        if "/year/" in h:
            return "year"
        if "/lang/" in h:
            return "lang"
        if "/letter/" in h:
            return "letter"
        if "/area/" in h:
            return "area"
        if "/class/" in h:
            return "class"
        if re.search(r'/pack/id/\d+\.html$', h):
            return "cat"
        return ""

    def _key_from_label(self, label):
        label = label or ""
        if "分类" in label or "频道" in label:
            return "cat"
        if "类型" in label:
            return "class"
        if "地区" in label:
            return "area"
        if "年份" in label:
            return "year"
        if "语言" in label:
            return "lang"
        if "字母" in label:
            return "letter"
        return ""

    def _parse_screen(self, html):
        """解析筛选区，返回 {key: [(名称, 绝对URL)]}
        以链接形态判定维度（站点「按地区」标签有时写成语言列表，不能只信文字）
        """
        out = {}
        if not html:
            return out
        for block in _RE_SCREEN_BLOCK.findall(html):
            ml = _RE_SCREEN_LABEL.search(block)
            label = ml.group(1).strip() if ml else ""

            items = []
            for href, txt in _RE_A_TAG.findall(block):
                name = self._clean(txt)
                if not name or not href or href.startswith("javascript"):
                    continue
                items.append((name, self._fix_url(href)))
            if len(items) < 2:
                continue

            key = ""
            # 先用「非『全部』」链接形态判定维度（「全部」是 /pack/id/N.html，
            # 会被误判成 cat）；area 段再做行级判定：该站模板把年份/语言
            # 也生成为 /pack/area/{值}/（如 area/2018、area/国语）
            for name, href in items:
                if name == "全部":
                    continue
                k = self._key_from_href(href)
                if k:
                    key = k
                    break
            if key == "area":
                key = self._row_area_key(items) or "area"
            if not key:
                key = self._key_from_label(label)
            if not key or key in out:
                continue
            if key == "cat":
                # 「按频道」行（电影/电视剧/…）与「按分类」行同为 /pack/id/N.html，
                # 区别在于频道行没有「全部」项 —— 没有 /pack.html 的视为频道行，跳过
                if not any(h.rstrip("/").endswith("/pack.html") for _n, h in items):
                    continue
                # 频道 id 集合也是频道行特征（个别页面无 /pack.html 时兜底）
                ids = re.findall(r"/pack/id/(\d+)\.html", " ".join(h for _n, h in items))
                if ids and all(i in {c["type_id"] for c in CLASSES} for i in ids):
                    continue
            out[key] = items

        # 排序 nav
        nb = _RE_NAV_BLOCK.search(html)
        if nb:
            items = []
            for href, txt in _RE_A_TAG.findall(nb.group(1)):
                mb = _RE_BY_VAL.search(href)
                if not mb:
                    continue
                items.append((self._clean(txt), mb.group(1)))
            if items:
                out["sort"] = items
        return out

    def _match_screen(self, html, key, val):
        screen = self._parse_screen(html)
        items = screen.get(key) or []
        val = str(val).strip()
        for name, href in items:
            if name == val:
                return href
        for name, href in items:
            if val and (val in name or name in val):
                return href
        return ""

    # ---------------------------------------------------------------- 首页
    def _build_filters_from_site(self):
        """直接从站点筛选区抓真实选项，保证与网页一致；任何异常返回 None
        网页顺序: 按分类(独立id) -> 按类型 -> 按地区 -> 按年份 -> 按语言 -> 按字母 -> 排序
        """
        filters = {}
        for c in CLASSES:
            tid = c["type_id"]
            html = self._fetch("%s/unit/%s.html" % (self.site_url, tid),
                               timeout=8, retry=1)
            screen = self._parse_screen(html)
            data = []
            if screen.get("cat"):
                # 「按分类」是独立的分类 id（如 国产剧 -> /pack/id/13.html）
                items = []
                for n, href in screen["cat"]:
                    mnum = re.search(r"/pack/id/(\d+)\.html", href)
                    if mnum and n != "全部":
                        items.append({"n": n, "v": mnum.group(1)})
                if items:
                    data.append({"key": "cat", "name": "分类",
                                 "value": [{"n": "全部", "v": ""}] + items})
            if screen.get("class"):
                data.append({"key": "class", "name": "类型",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["class"]]})
            if screen.get("area"):
                data.append({"key": "area", "name": "地区",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["area"]]})
            if screen.get("year"):
                # 站点年份行本身有重复乱序项，去重保持原有顺序
                yitems, yseen = [], set()
                for n, _href in screen["year"]:
                    if n not in yseen:
                        yseen.add(n)
                        yitems.append(n)
                data.append({"key": "year", "name": "年份",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n in yitems]})
            if screen.get("lang"):
                data.append({"key": "lang", "name": "语言",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["lang"]]})
            if screen.get("letter"):
                data.append({"key": "letter", "name": "字母",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["letter"]]})
            if screen.get("sort"):
                # 固定按网页默认顺序（时间→人气→评分），不受缓存页 active 状态影响
                sorder = {"time": 0, "hits": 1, "score": 2}
                sitems = [(n, v) for n, v in screen["sort"] if v in sorder]
                sitems.sort(key=lambda x: sorder[x[1]])
                data.append({"key": "sort", "name": "排序",
                             "value": [{"n": n, "v": v} for n, v in sitems]})
            if data:
                filters[tid] = data
        # 解析失败的频道用静态兜底补齐，保证筛选栏不缺项
        for c in CLASSES:
            tid = c["type_id"]
            if tid not in filters:
                filters[tid] = FILTERS.get(tid) or []
        return filters or None

    def _get_filters(self):
        if self._filters_cache is not None:
            return self._filters_cache
        use_dynamic = str(self.extend.get("dynamic_filter", "1")) != "0"
        filters = None
        if use_dynamic:
            try:
                filters = self._build_filters_from_site()
            except Exception as e:
                self.log("动态筛选失败: %s" % e)
        if not filters:
            filters = FILTERS
        self._filters_cache = filters
        return filters

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": self._get_filters()}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("home 视频: %d 条" % len(videos))
        return {"list": videos[:60]}

    # ---------------------------------------------------------------- 分类
    def _fetch_cached(self, url, timeout=15, retry=2, headers=None):
        """分类/筛选页抓取：成功结果缓存 5 分钟，失败负缓存 1 分钟。
        源站间歇 520，缓存能显著减少重复撞墙，并保证翻页/重进秒开。
        """
        now = time.time()
        hit = self._page_cache.get(url)
        if hit:
            ts, text = hit
            if text and now - ts < 300:
                return text
            if not text and now - ts < 60:
                return ""
        html = self._fetch(url, timeout=timeout, retry=retry, headers=headers)
        ok = bool(html) and len(html) > 120
        self._page_cache[url] = (now, html if ok else "")
        # 缓存别无限膨胀
        if len(self._page_cache) > 200:
            for k in sorted(self._page_cache, key=lambda k: self._page_cache[k][0])[:100]:
                del self._page_cache[k]
        return html

    def _norm_extend(self, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        out = {}
        for k, v in extend.items():
            if v in ("", None, "全部", "0"):
                continue
            out[k] = v
        return out

    def _build_filter_url(self, tid, ext, page=1):
        """按站点真实伪静态规则拼装（全部从缓存页内真实链接逐字实测）：
        /pack/[by/{排序}/][class/{类型}/][area/{地区}/area/{年份}/area/{语言}/]\
id/{频道或分类ID}[/page/{页}][/letter/{字母}].html
        注意：该站模板把「年份」「语言」与「地区」共用 area 段 ——
        网页真实链接为 /pack/area/2018/id/13.html、/pack/area/国语/id/13.html
        （2026-11-11 从 /pack/id/13.html 缓存页逐字提取，与旧拼法
        /pack/id/13/year/2018.html 不一致，那会导致访客侧 CF 缓存永不命中）
        """
        def q(v):
            return urllib.parse.quote(str(v))

        parts = []
        if ext.get("sort"):
            parts.append("by/" + q(ext["sort"]))
        if ext.get("class"):
            parts.append("class/" + q(ext["class"]))
        # 地区/年份/语言共用 area 段，按 地区->年份->语言 依次输出（与网页一致）
        for k in ("area", "year", "lang"):
            if ext.get(k):
                parts.append("area/" + q(ext[k]))
        # 「分类」选中时它是独立的分类 id（/pack/id/13.html），替代频道 id
        ident = str(ext.get("cat") or tid)
        parts.append("id/" + str(ident))
        try:
            if int(page) > 1:
                parts.append("page/%d" % int(page))
        except Exception:
            pass
        if ext.get("letter"):
            parts.append("letter/" + q(ext["letter"]))
        return "%s/pack/%s.html" % (self.site_url, "/".join(parts))

    _LANG_WORDS = {"国语", "英语", "粤语", "闽南语", "韩语", "日语",
                   "法语", "德语", "其它", "其他"}

    def _row_area_key(self, items):
        """行级判定 area 段维度：该站模板把年份/语言也生成为 /pack/area/{值}/。
        行内 area 值全为数字 -> 年份；多为语言词 -> 语言；否则 -> 地区
        """
        vals = []
        for _n, h in items:
            m = re.search(r"/pack/area/([^/]+)/", h)
            if m:
                vals.append(urllib.parse.unquote(m.group(1)))
        vals = [v for v in vals if v]
        if not vals:
            return ""
        if all(v.isdigit() for v in vals):
            return "year"
        hits = sum(1 for v in vals
                   if v.endswith("语") or v in self._LANG_WORDS)
        if hits and hits * 2 >= len(vals):
            return "lang"
        return "area"

    def _follow_filter(self, tid, ext, page=1):
        """兜底：像人一样逐个点筛选项，全程只使用页面里真实存在的链接"""
        cur_url = "%s/unit/%s.html" % (self.site_url, tid)
        html = self._fetch_cached(cur_url, timeout=15, retry=2)
        if not html:
            cur_url = "%s/pack/id/%s.html" % (self.site_url, tid)
            html = self._fetch_cached(cur_url, timeout=15, retry=2)

        for key in ("cat", "class", "area", "year", "lang", "letter"):
            val = ext.get(key)
            if not val:
                continue
            href = self._match_screen(html, key, val)
            if not href or href == cur_url:
                continue
            nxt = self._fetch_cached(href, timeout=12, retry=3)
            if not nxt or not self._extract_videos(nxt):
                self.log("筛选项无结果: %s=%s" % (key, val))
                continue
            cur_url, html = href, nxt

        if ext.get("sort"):
            for name, code in (self._parse_screen(html).get("sort") or []):
                if code == ext["sort"] or str(ext["sort"]) in name:
                    href = "%s/pack/by/%s/id/%s.html" % (self.site_url, code, tid)
                    nxt = self._fetch_cached(href, timeout=12, retry=2)
                    if nxt and self._extract_videos(nxt):
                        cur_url, html = href, nxt
                    break

        if page > 1:
            purl = self._page_url(html, cur_url, page)
            if purl and purl != cur_url:
                nxt = self._fetch_cached(purl, timeout=15, retry=2)
                if nxt:
                    cur_url, html = purl, nxt
        return html, cur_url

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        ext = self._norm_extend(extend)
        tid = str(tid).strip()

        has_filter = any(ext.get(k)
                         for k in ("cat", "class", "area", "year", "lang",
                                   "letter", "sort"))

        html, cur_url = "", ""
        if has_filter:
            # 先拿「同条件第 1 页」，再优先使用页面里真实的翻页链接（与网页完全一致）
            u1 = self._build_filter_url(tid, ext, 1)
            h1 = self._fetch_cached(u1, timeout=15, retry=3)
            if page > 1 and self._extract_videos(h1):
                purl = self._page_url(h1, u1, page)
                if purl and purl != u1:
                    html = self._fetch_cached(purl, timeout=15, retry=3)
                    if self._extract_videos(html):
                        cur_url, u1 = purl, purl
            if not self._extract_videos(html):
                cur_url = self._build_filter_url(tid, ext, page)
                html = h1 if (h1 and page == 1) else \
                    self._fetch_cached(cur_url, timeout=15, retry=3)
                if page > 1 and not self._extract_videos(html):
                    # 筛选页翻页失败时退回「同条件第 1 页」，别给未筛选的错误内容
                    if self._extract_videos(h1):
                        html, cur_url = h1, u1
            if not self._extract_videos(html):
                self.log("模板筛选未命中，改走链接跟随: %s" % cur_url)
                html, cur_url = self._follow_filter(tid, ext, page)

        if not self._extract_videos(html):
            # 无筛选 / 兜底：直接走频道页（/unit/{tid}.html、/unit/{tid}-{page}.html）
            if page > 1:
                cur_url = "%s/unit/%s-%d.html" % (self.site_url, tid, page)
            else:
                cur_url = "%s/unit/%s.html" % (self.site_url, tid)
            h2 = self._fetch_cached(cur_url, timeout=15, retry=2)
            if not h2 and page == 1:
                h2 = self._fetch_cached("%s/unit/%s-1.html" % (self.site_url, tid),
                                 timeout=12, retry=2)
                if h2:
                    cur_url = "%s/unit/%s-1.html" % (self.site_url, tid)
            if not h2:
                cur_url = "%s/pack/id/%s.html" % (self.site_url, tid)
                h2 = self._fetch_cached(cur_url, timeout=15, retry=2)
            if h2:
                html = h2

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("category tid=%s pg=%s url=%s => %d 条 / %d 页"
                 % (tid, page, cur_url, len(videos), pagecount))

        if pagecount < page:
            pagecount = page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": min(pagecount, 9999) * 24,
        }

    # ---------------------------------------------------------------- 搜索
    def _search_html(self, key, page=1):
        q = urllib.parse.quote(key)
        # 1) 站点表单是 POST /find3.html
        html = self._fetch(self.site_url + "/find3.html",
                           data={"wd": key}, timeout=20, retry=2)
        if self._extract_videos(html):
            return html
        # 2) GET 形式
        for u in ("%s/find3.html?wd=%s" % (self.site_url, q),
                  "%s/index.php/vod/search/wd/%s.html" % (self.site_url, q),
                  "%s/search/%s-------------.html" % (self.site_url, q)):
            h2 = self._fetch(u, timeout=18, retry=2)
            if self._extract_videos(h2):
                return h2
        # 3) 联想接口
        try:
            h3 = self._fetch("%s/index.php/ajax/suggest?mid=1&wd=%s&limit=30"
                             % (self.site_url, q), timeout=15, retry=1)
            obj = json.loads(h3)
            lst = obj.get("list") or []
            if lst:
                videos = []
                for it in lst:
                    vid = it.get("id") or it.get("vod_id")
                    videos.append({
                        "vod_id": "/pagevid/%s.html" % vid,
                        "vod_name": self._clean(it.get("name") or it.get("vod_name")),
                        "vod_pic": self._fix_url(it.get("pic") or it.get("vod_pic")) or self.default_pic,
                        "vod_remarks": self._clean(it.get("remarks") or ""),
                    })
                self._suggest_cache = videos
                return "__SUGGEST__"
        except Exception:
            pass
        return ""

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        self._suggest_cache = None
        html = self._search_html(key, page)
        if html == "__SUGGEST__":
            videos = self._suggest_cache or []
            return {"list": videos, "page": 1, "pagecount": 1,
                    "limit": len(videos) or 24, "total": len(videos)}
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("search %s => %d 条" % (key, len(videos)))
        return {"list": videos, "page": page, "pagecount": max(1, pagecount),
                "limit": 24, "total": max(1, pagecount) * 24}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------------------------------------------------------- 详情
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]).strip()
        if vod_id.isdigit():
            vod_id = "/pagevid/%s.html" % vod_id
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # ---- 信息区 ----
        zone_m = _RE_DETAIL_AREA.search(html)
        zone = zone_m.group(1) if zone_m else html[:20000]

        name = ""
        m = _RE_H3_TITLE.search(zone)
        if m:
            name = self._clean(re.sub(r'<span[^>]*class="[^"]*score[^"]*"[\s\S]*?</span>', "", m.group(1)))
        if not name:
            m = _RE_TAG_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0].split("《")[-1].replace("》", ""))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        score = ""
        m = _RE_SCORE.search(zone) or _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        type_name = area = year = ""
        m = _RE_TYPE.search(zone)
        if m:
            type_name = self._clean(m.group(1))
        m = _RE_AREA.search(zone)
        if m:
            area = self._clean(m.group(1))
        m = _RE_YEAR.search(zone)
        if m:
            year = self._clean(m.group(1))

        actor = ""
        m = _RE_ACTOR.search(zone)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        director = ""
        m = _RE_DIRECTOR.search(zone)
        if m:
            director = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        # 副标题（缩略图角标） / 封面
        thumb_zone = ""
        m = _RE_PIC_TEXT_DETAIL.search(html)
        if m:
            thumb_zone = m.group(1)

        remarks = ""
        if thumb_zone:
            mp = _RE_PIC_TEXT.search(thumb_zone)
            if mp:
                remarks = self._clean(mp.group(1))
        if not remarks:
            m = re.search(r'更新时间：\s*([\d-]+)', html)
            if m:
                remarks = "更新于" + m.group(1)

        pic = ""
        for cand in _RE_PIC_ATTR.findall(thumb_zone or html):
            if cand and "load.gif" not in cand and not cand.startswith("data:"):
                pic = cand
                break
        pic = self._fix_url(pic) or self.default_pic

        # ---- 简介 ----
        content = ""
        m = _RE_DESC_BLOCK.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC_SHORT.search(zone)
            if m:
                content = self._clean(re.sub(r'<a[^>]*>[\s\S]*?</a>', "", m.group(1)))
                content = content.replace("简介：", "", 1)
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ---- 播放线路（严格按「切换来源」下拉顺序）----
        play_from, play_url = self._parse_playlist(html)
        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
            "type_name": type_name,
        }]}

    def _parse_playlist(self, html):
        """返回 (play_from, play_url)，顺序 = 详情页 tab 顺序"""
        zone_m = _RE_PLAYLIST_ZONE.search(html)
        zone = zone_m.group(1) if zone_m else html

        # tab 顺序
        tabs = []
        for sid, raw in _RE_TAB_ITEM.findall(zone):
            nm = self._clean(raw)
            if not nm:
                continue
            tabs.append((sid, nm))

        # 每个 sid 的剧集
        eps = {}
        for sid, body in _RE_EP_BLOCK.findall(zone):
            items = []
            for href, raw in _RE_EP_A.findall(body):
                href = href.replace("&amp;", "&").strip()
                if not href or href.startswith("javascript") or "#" in href:
                    continue
                items.append((self._safe_name(raw), self._fix_url(href)))
            if items:
                eps[sid] = items

        if not eps:
            return [], []

        order = []
        used = set()
        for sid, nm in tabs:
            if sid in eps and sid not in used:
                order.append((nm, sid))
                used.add(sid)
        for sid in eps.keys():
            if sid not in used:
                order.append(("线路%s" % sid, sid))
                used.add(sid)

        play_from, play_url = [], []
        names = set()
        for nm, sid in order:
            items = eps[sid]
            label = nm or ("线路%s" % sid)
            base = label
            i = 2
            while label in names:
                label = "%s-%d" % (base, i)
                i += 1
            names.add(label)
            play_from.append(label)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in items))
        return play_from, play_url

    # ---------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 3600:
                return res

        # 播放页 Referer 实测：各线路 CDN 对 Referer 不敏感，带站点首页即可
        html = self._fetch(play_page, timeout=20, retry=2,
                           headers={"Referer": self.site_url + "/"})
        direct = self._parse_play_html(html, play_page)
        self.log("  direct: %s" % (direct[:180] if direct else "EMPTY"))

        if direct:
            res = self._make_play_res(direct)
            self._play_cache[play_page] = (now, res)
            return res

        # ===== 关键兜底：源站间歇 520，当前线路拿不到时自动接力其它线路的同集 =====
        # 播放页路由 /slotplay/{vid}/{sid}/{nid}.html，各线路同集数的 nid 一致
        m = re.search(r"/slotplay/(\d+)/(\d+)/(\d+)\.html", play_page)
        if m:
            vid, cur_sid, nid = m.group(1), int(m.group(2)), m.group(3)
            others = [s for s in range(1, 9) if s != cur_sid]
            for sid2 in others:
                alt = "%s/slotplay/%s/%d/%s.html" % (self.site_url, vid, sid2, nid)
                h2 = self._fetch(alt, timeout=12, retry=1,
                                 headers={"Referer": self.site_url + "/"})
                d2 = self._parse_play_html(h2, alt)
                if d2:
                    self.log("  线路%s 失败, 接力线路%s: %s"
                             % (cur_sid, sid2, d2[:120]))
                    res = self._make_play_res(d2)
                    self._play_cache[play_page] = (now, res)
                    return res

        # 最终兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        return res

    def _make_play_res(self, direct):
        low = direct.lower()
        if ".m3u8" in low or ".mp4" in low:
            return {
                "parse": 0, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        # 直链但没有视频扩展名 → 仍交嗅探
        return {"parse": 1, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def _parse_play_html(self, html, page_url=""):
        if not html:
            return ""

        # 1) player_aaaa = {...}
        for m in _RE_PLAYER_OBJ.finditer(html):
            start = m.end() - 1
            try:
                obj, _end = json.JSONDecoder().raw_decode(html[start:])
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            url = self._pick_link(obj)
            if url:
                return url

        # 2) 宽松 "url" / "link"
        for key in ("url", "link"):
            m = re.search(r'"%s"\s*:\s*"([^"]{8,})"' % key, html)
            if m:
                u = self._pick_link({"url": m.group(1)})
                if u:
                    return u

        # 3) iframe 嵌套（再进一层）
        m = _RE_IFRAME.search(html)
        if m:
            src = self._fix_url(m.group(1))
            if src and src != page_url and "zzhczj" not in src:
                inner = self._fetch(src, headers={"Referer": page_url or self.site_url + "/"})
                u = self._parse_play_html(inner, src)
                if u:
                    return u

        # 4) 页面里裸的 m3u8 / mp4
        for reg in (_RE_M3U8, _RE_MP4):
            m = reg.search(html)
            if m:
                u = m.group(0).replace("\\/", "/")
                if u.startswith("//"):
                    u = "https:" + u
                return u

        # 5) 播放器配置里的其它 http 地址（无扩展名 m3u8 也能捞到）
        m = _RE_ANY_URL.search(html.replace("\\/", "/"))
        if m:
            u = m.group(1).strip()
            if u.startswith("//"):
                u = "https:" + u
            if not re.search(r'\.(?:jpg|jpeg|png|webp|gif|css|js|html?)(?:\?|$)', u, re.I):
                return u
        return ""

    def _pick_link(self, obj):
        enc = str(obj.get("encrypt", "0"))
        for key in ("url", "link"):
            raw = obj.get(key) or ""
            if not isinstance(raw, str):
                continue
            raw = raw.strip().replace("\\/", "/")
            if not raw:
                continue
            if raw.startswith("//"):
                raw = "https:" + raw
            # 注意：base64 / urlencode 后的串也可能以 http 开头，必须校验 ://
            if re.match(r'^https?://', raw, re.I):
                return raw

            dec = ""
            if enc == "1":
                dec = self._b64(raw)
            elif enc == "2":
                dec = urllib.parse.unquote(raw).replace("\\/", "/")
                if dec.startswith("//"):
                    dec = "https:" + dec
                if not re.match(r'^https?://', dec, re.I):
                    dec = ""
            else:
                dec = self._b64(raw)
                if not dec:
                    dec = urllib.parse.unquote(raw).replace("\\/", "/")
                    if dec.startswith("//"):
                        dec = "https:" + dec
                    if not re.match(r'^https?://', dec, re.I):
                        dec = ""
            if dec:
                return dec
        return ""

    def _b64(self, s):
        try:
            t = s.strip().replace("-", "+").replace("_", "/")
            pad = len(t) % 4
            if pad:
                t += "=" * (4 - pad)
            dec = base64.b64decode(t).decode("utf-8", "ignore").strip()
            dec = dec.replace("\\/", "/")
            if dec.lower().startswith("http"):
                return dec
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
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = getattr(rsp, "content", b"") or b""
            ctype = ""
            if hasattr(rsp, "headers"):
                ctype = rsp.headers.get("Content-Type", "") or ""
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
