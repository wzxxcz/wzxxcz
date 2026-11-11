# coding=utf-8
"""
4K电影网 zzhczj.com | TVBox Python 爬虫 
关键:
  - 全站伪静态路由:
      频道      /unit/{type_id}.html         分页 /unit/{type_id}-{page}.html
      筛选      /pack/[by/{排序}/][area/{地区}/][class/{类型}/]id/1[/page/{页}][/year/{年}][/lang/{语言}].html
      详情      /pagevid/{vod_id}.html
      播放      /slotplay/{vod_id}/{sid}/{nid}.html
  - 筛选项（类型/地区/年份/语言/排序）启动时直接从站点筛选区实时抓取，与网页端 100% 同步；
    筛选 URL 按站点真实规则拼接，拼接未命中会自动降级为「逐项跟随页面真实链接」
  - 线路顺序严格按详情页「切换来源」下拉的显示顺序（页面里线路名与 sid 并不对应）
  - 列表「副标题」取缩略图角标 pic-text（正片 / 已完结 / 更新至xxxx期）
  - 源站偶发 Cloudflare 520，内置多次重试 + 分级降级
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

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

_AREAS = [{"n": "全部", "v": ""}] + \
         [{"n": x, "v": x} for x in
          ("大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
           "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他")]

_LANGS = [{"n": "全部", "v": ""}] + \
         [{"n": x, "v": x} for x in
          ("国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它")]

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]

# 静态兜底（homeContent 会优先从站点实时解析真实筛选项，解析失败才用这份）
_CLASS_MAP = {
    "1": ["动作", "喜剧", "爱情", "恐怖", "科幻", "剧情", "战争", "警匪",
          "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
          "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
          "儿童", "网络电影"],
    "2": ["国产剧", "港台剧", "日韩剧", "欧美剧", "海外剧", "动作", "喜剧",
          "爱情", "悬疑", "古装", "都市", "家庭", "犯罪", "战争", "历史",
          "青春", "科幻", "恐怖", "剧情", "武侠", "谍战", "年代", "农村", "儿童"],
    "3": ["综艺", "真人秀", "脱口秀", "选秀", "访谈", "晚会", "搞笑", "情感",
          "生活", "音乐", "游戏", "美食", "旅游", "亲子", "体育", "纪实"],
    "4": ["国漫", "日漫", "欧美", "动画", "热血", "搞笑", "恋爱", "冒险",
          "奇幻", "科幻", "治愈", "校园", "悬疑", "运动", "亲子"],
    "24": ["短剧", "古装", "现代", "言情", "逆袭", "战神", "穿越", "重生",
           "悬疑", "喜剧", "豪门", "都市", "甜宠", "虐恋"],
}

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": x, "v": x} for x in _CLASS_MAP.get(_tid, [])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


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
            return "cate"
        return ""

    def _key_from_label(self, label):
        label = label or ""
        if "分类" in label:
            return "cate"
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
            for _name, href in items:
                k = self._key_from_href(href)
                if k:
                    key = k
                    break
            if not key:
                key = self._key_from_label(label)
            if not key or key in out:
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
        """直接从站点筛选区抓真实选项，保证与网页一致；任何异常返回 None"""
        filters = {}
        for c in CLASSES:
            tid = c["type_id"]
            html = self._fetch("%s/unit/%s.html" % (self.site_url, tid),
                               timeout=8, retry=1)
            screen = self._parse_screen(html)
            data = []
            if screen.get("class"):
                data.append({"key": "class", "name": "类型",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["class"]]})
            if screen.get("area"):
                data.append({"key": "area", "name": "地区",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["area"]]})
            if screen.get("year"):
                data.append({"key": "year", "name": "年份",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["year"]]})
            if screen.get("lang"):
                data.append({"key": "lang", "name": "语言",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["lang"]]})
            if screen.get("sort"):
                data.append({"key": "sort", "name": "排序",
                             "value": [{"n": n, "v": v} for n, v in screen["sort"]]})
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
        """按站点真实伪静态规则拼装（已实测）：
        /pack/[by/{排序}/][area/{地区}/][class/{类型}/]id/{频道}[/page/{页}][/year/{年}][/lang/{语言}].html
        """
        def q(v):
            return urllib.parse.quote(str(v))

        parts = []
        if ext.get("sort"):
            parts.append("by/" + q(ext["sort"]))
        if ext.get("area"):
            parts.append("area/" + q(ext["area"]))
        if ext.get("class"):
            parts.append("class/" + q(ext["class"]))
        parts.append("id/" + str(tid))
        try:
            if int(page) > 1:
                parts.append("page/%d" % int(page))
        except Exception:
            pass
        if ext.get("year"):
            parts.append("year/" + q(ext["year"]))
        if ext.get("lang"):
            parts.append("lang/" + q(ext["lang"]))
        return "%s/pack/%s.html" % (self.site_url, "/".join(parts))

    def _follow_filter(self, tid, ext, page=1):
        """兜底：像人一样逐个点筛选项，全程只使用页面里真实存在的链接"""
        cur_url = "%s/unit/%s.html" % (self.site_url, tid)
        html = self._fetch(cur_url, timeout=15, retry=2)
        if not html:
            cur_url = "%s/pack/id/%s.html" % (self.site_url, tid)
            html = self._fetch(cur_url, timeout=15, retry=2)

        for key in ("class", "area", "year", "lang"):
            val = ext.get(key)
            if not val:
                continue
            href = self._match_screen(html, key, val)
            if not href or href == cur_url:
                continue
            nxt = self._fetch(href, timeout=12, retry=3)
            if not nxt or not self._extract_videos(nxt):
                self.log("筛选项无结果: %s=%s" % (key, val))
                continue
            cur_url, html = href, nxt

        if ext.get("sort"):
            for name, code in (self._parse_screen(html).get("sort") or []):
                if code == ext["sort"] or str(ext["sort"]) in name:
                    href = "%s/pack/by/%s/id/%s.html" % (self.site_url, code, tid)
                    nxt = self._fetch(href, timeout=12, retry=2)
                    if nxt and self._extract_videos(nxt):
                        cur_url, html = href, nxt
                    break

        if page > 1:
            purl = self._page_url(html, cur_url, page)
            if purl and purl != cur_url:
                nxt = self._fetch(purl, timeout=15, retry=2)
                if nxt:
                    cur_url, html = purl, nxt
        return html, cur_url

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        ext = self._norm_extend(extend)
        tid = str(tid).strip()

        has_filter = any(ext.get(k) for k in ("class", "area", "year", "lang", "sort"))

        html, cur_url = "", ""
        if has_filter:
            cur_url = self._build_filter_url(tid, ext, page)
            html = self._fetch(cur_url, timeout=15, retry=3)
            if html:
                if not self._extract_videos(html) and page > 1:
                    # 筛选页翻页失败时退回「同条件第 1 页」，别给未筛选的错误内容
                    u1 = self._build_filter_url(tid, ext, 1)
                    h1 = self._fetch(u1, timeout=15, retry=2)
                    if self._extract_videos(h1):
                        html, cur_url = h1, u1
                if not self._extract_videos(html):
                    self.log("模板筛选未命中，改走链接跟随: %s" % cur_url)
                    html, cur_url = self._follow_filter(tid, ext, page)
            else:
                self.log("筛选页请求失败: %s" % cur_url)

        if not self._extract_videos(html):
            # 无筛选 / 兜底：直接走频道页（/unit/{tid}.html、/unit/{tid}-{page}.html）
            if page > 1:
                cur_url = "%s/unit/%s-%d.html" % (self.site_url, tid, page)
            else:
                cur_url = "%s/unit/%s.html" % (self.site_url, tid)
            h2 = self._fetch(cur_url, timeout=15, retry=2)
            if not h2 and page == 1:
                h2 = self._fetch("%s/unit/%s-1.html" % (self.site_url, tid),
                                 timeout=12, retry=2)
                if h2:
                    cur_url = "%s/unit/%s-1.html" % (self.site_url, tid)
            if not h2:
                cur_url = "%s/pack/id/%s.html" % (self.site_url, tid)
                h2 = self._fetch(cur_url, timeout=15, retry=2)
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
            if now - ts < 600:
                return res

        html = self._fetch(play_page, headers={"Referer": self.site_url + "/"})
        direct = self._parse_play_html(html, play_page)
        self.log("  direct: %s" % (direct[:180] if direct else "EMPTY"))

        if direct:
            low = direct.lower()
            if ".m3u8" in low or ".mp4" in low:
                res = {
                    "parse": 0, "playUrl": "", "url": direct,
                    "header": {"User-Agent": UA, "Referer": play_page},
                }
            else:
                res = {
                    "parse": 1, "playUrl": "", "url": play_page,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

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
