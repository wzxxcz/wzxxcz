# -*- coding: utf-8 -*-
"""
宝园影视 Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
站点: https://www.cnbaoyuan.com/

修复/补全:
  - 简介提取增强（多层回退 + 平衡标签扫描）
  - 剧集列表属性顺序兼容
  - 播放源 tab 定位兼容
  - 搜索 URL 编码
  - 首集预缓存状态追踪
  - iframe 单引号 / 相对协议兼容
"""

import sys
import json
import re
import time
import hashlib

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

    class Spider:
        _session = None

        def _get_session(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                try:
                    adapter = _rq.adapters.HTTPAdapter(
                        pool_connections=20,
                        pool_maxsize=30,
                        max_retries=0,
                        pool_block=False,
                    )
                    self._session.mount('http://', adapter)
                    self._session.mount('https://', adapter)
                except Exception:
                    pass
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            s = self._get_session()
            r = s.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r


from urllib.parse import quote, urlparse, parse_qs


# ============================================================
# 常量
# ============================================================

HOST = "https://www.cnbaoyuan.com"
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# ---- 卡片提取 ----
# 用前瞻兼容属性顺序，避免 A/B 两种模板差异导致漏抓
_RE_CARD_ITEM = re.compile(
    r'<a\b'
    r'(?=[^>]*\bhref="/cnbvod/(?P<vid>\d+)\.html")'
    r'(?=[^>]*\btitle="(?P<name>[^"]*)")'
    r'(?=[^>]*\b(?:data-original|data-src)="(?P<pic>[^"]+)")'
    r'[^>]*>',
    re.I
)
_RE_REMARK = re.compile(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]+)</span>')

# ---- 详情页 ----
_RE_H1 = re.compile(r'<h1[^>]*>([^<]+)</h1>')
_RE_TITLE_TAG = re.compile(r'<title>.*?《([^》]+)》')
_RE_PIC = re.compile(r'(?:data-original|data-src)="([^"]+)"')
_RE_INFO = re.compile(
    r'分类：</b></span><a[^>]*>([^<]+)</a>.*?'
    r'地区：</b></span>([^<]+).*?'
    r'年份：</b></span>(\d+)',
    re.S
)
_RE_ACTOR = re.compile(r'主演：</b></span>(.*?)</p>', re.S)
_RE_DIRECTOR = re.compile(r'导演：</b></span>(.*?)</p>', re.S)
_RE_META_DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]+)"')
_RE_UPDATE = re.compile(r'更新[:：]\s*(?:</b>)?\s*(?:</span>)?\s*([^<\r\n]+)', re.I)
_RE_TABS = re.compile(r'<a\b[^>]*href="#(playlist\d+)"[^>]*>(.*?)</a>', re.S)
_RE_PAGES = re.compile(r'page=(\d+)')
_RE_TOTAL = re.compile(r'共\s*(\d+)\s*页')
_RE_TAG = re.compile(r'<[^>]+>')
_RE_SPACE = re.compile(r'\s+')
_RE_IFRAME = re.compile(r'<iframe[^>]*\bsrc=["\']([^"\']+)["\']', re.I)
_RE_EP_NUM = re.compile(r'(\d+)')

# 简介回退模式（按优先级）
_RE_CONTENT_DIV = re.compile(r'<div[^>]*class="[^"]*(?:\bcontent\b|detail-content|vod-detail-content)[^"]*"[^>]*>', re.I)
_RE_CONTENT_SPAN = re.compile(
    r'简介[:：]\s*(?:</b>)?\s*(?:</span>)?\s*(?:<[^>]+>)*\s*(.*?)</(?:div|p|span)>',
    re.S
)
_RE_CONTENT_PREFIX = re.compile(
    r'(?:剧情|简介)[:：]\s*</[^>]+>\s*(.*?)</(?:div|p)>',
    re.S
)

# ---- m3u8/mp4 提取（按命中率从高到低）----
_RE_M3U8_PATTERNS = [
    re.compile(r'var\s+now\s*=\s*"([^"]+)"'),                    # 本站最常见
    re.compile(r'"url"\s*:\s*"(https?://[^"]+)"', re.I),          # JSON 格式（player_aaaa / player 等）
    re.compile(r'var\s+url\s*=\s*"([^"]+)"'),
    re.compile(r'file\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', re.I),
    re.compile(r'src\s*=\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', re.I),
    re.compile(r'video_url\s*=\s*"([^"]+)"', re.I),
    re.compile(r'"link"\s*:\s*"(https?://[^"]+)"', re.I),
]
_RE_M3U8_BARE = re.compile(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', re.I)
_RE_MP4_BARE = re.compile(r'(https?://[^\s"\'<>\\]+\.mp4[^\s"\'<>\\]*)', re.I)


# 主分类（6个大类）
CLASSES = [
    {"type_name": "精选", "type_id": "0"},
    {"type_name": "电影", "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "动漫", "type_id": "4"},
    {"type_name": "综艺", "type_id": "3"},
    {"type_name": "短剧", "type_id": "5"},
]

# 各分类的类型筛选
_TYPE_FILTERS = {
    "0": [{"n": "全部", "v": ""},
          {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
          {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
          {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"}, {"n": "悬疑", "v": "悬疑"},
          {"n": "犯罪", "v": "犯罪"}, {"n": "奇幻", "v": "奇幻"}, {"n": "家庭", "v": "家庭"},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}, {"n": "甜宠", "v": "甜宠"}],
    "1": [{"n": "全部", "v": ""},
          {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
          {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
          {"n": "战争", "v": "战争"}, {"n": "悬疑", "v": "悬疑"}, {"n": "犯罪", "v": "犯罪"},
          {"n": "纪录片", "v": "纪录片"}, {"n": "灾难", "v": "灾难"}, {"n": "冒险", "v": "冒险"},
          {"n": "惊悚", "v": "惊悚"}, {"n": "传记", "v": "传记"}, {"n": "历史", "v": "历史"},
          {"n": "家庭", "v": "家庭"}],
    "2": [{"n": "全部", "v": ""},
          {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"}, {"n": "言情", "v": "言情"},
          {"n": "悬疑", "v": "悬疑"}, {"n": "战争", "v": "战争"}, {"n": "犯罪", "v": "犯罪"},
          {"n": "民国", "v": "民国"}, {"n": "穿越", "v": "穿越"}, {"n": "奇幻", "v": "奇幻"},
          {"n": "家庭", "v": "家庭"}, {"n": "网剧", "v": "网剧"}, {"n": "剧情", "v": "剧情"},
          {"n": "甜宠", "v": "甜宠"}, {"n": "逆袭", "v": "逆袭"}, {"n": "反转", "v": "反转"},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}],
    "3": [{"n": "全部", "v": ""},
          {"n": "真人秀", "v": "真人秀"}, {"n": "脱口秀", "v": "脱口秀"},
          {"n": "竞技", "v": "竞技"}, {"n": "访谈", "v": "访谈"},
          {"n": "选秀", "v": "选秀"}, {"n": "美食", "v": "美食"},
          {"n": "旅游", "v": "旅游"}, {"n": "音乐", "v": "音乐"},
          {"n": "搞笑", "v": "搞笑"}, {"n": "生活", "v": "生活"}],
    "4": [{"n": "全部", "v": ""},
          {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}, {"n": "恋爱", "v": "恋爱"},
          {"n": "奇幻", "v": "奇幻"}, {"n": "冒险", "v": "冒险"}, {"n": "古装", "v": "古装"},
          {"n": "都市", "v": "都市"}, {"n": "玄幻", "v": "玄幻"}, {"n": "治愈", "v": "治愈"},
          {"n": "日常", "v": "日常"}, {"n": "励志", "v": "励志"}, {"n": "美食", "v": "美食"},
          {"n": "系统", "v": "系统"}, {"n": "脑洞", "v": "脑洞"}, {"n": "逆袭", "v": "逆袭"},
          {"n": "反转", "v": "反转"}, {"n": "异能", "v": "异能"}],
    "5": [{"n": "全部", "v": ""},
          {"n": "都市", "v": "都市"}, {"n": "古装", "v": "古装"}, {"n": "言情", "v": "言情"},
          {"n": "穿越", "v": "穿越"}, {"n": "逆袭", "v": "逆袭"}, {"n": "反转", "v": "反转"},
          {"n": "甜宠", "v": "甜宠"}, {"n": "霸总", "v": "霸总"}, {"n": "战神", "v": "战神"},
          {"n": "神医", "v": "神医"}, {"n": "赘婿", "v": "赘婿"}, {"n": "复仇", "v": "复仇"},
          {"n": "重生", "v": "重生"}, {"n": "玄幻", "v": "玄幻"}, {"n": "搞笑", "v": "搞笑"},
          {"n": "热血", "v": "热血"}, {"n": "家庭", "v": "家庭"}],
}

_AREA_FILTER = {"key": "area", "name": "地区", "value": [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "欧美", "v": "欧美"},
    {"n": "泰国", "v": "泰国"}, {"n": "其他", "v": "其他"},
]}

_YEAR_FILTER = {"key": "year", "name": "年份", "value": [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
    {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"},
    {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"},
    {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
]}

_LANG_FILTER = {"key": "lang", "name": "语言", "value": [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
    {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}, {"n": "法语", "v": "法语"},
    {"n": "德语", "v": "德语"}, {"n": "其他", "v": "其他"},
]}

_BY_FILTER = {"key": "by", "name": "排序", "value": [
    {"n": "最新", "v": "time"},
    {"n": "最热", "v": "hit"},
    {"n": "评分", "v": "score"},
]}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    tf = {"key": "class", "name": "类型", "value": _TYPE_FILTERS.get(tid, [{"n": "全部", "v": ""}])}
    FILTERS[tid] = [tf, _AREA_FILTER, _YEAR_FILTER, _LANG_FILTER, _BY_FILTER]


# ============================================================
# 工具函数
# ============================================================

def _strip(s):
    """去 HTML 标签 + 空白压缩"""
    return _RE_SPACE.sub(' ', _RE_TAG.sub('', s or '').strip())


def _fix_pic(url):
    """修复图片 URL"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http"):
        url = HOST + url if url.startswith("/") else HOST + "/" + url
    return url


def _proxy_img(url):
    """图片直链 + @Referer 防盗链（兼容 FongMi/T3 与 T4）"""
    if not url:
        return ""
    url = _fix_pic(url)
    return url + "@Referer=" + HOST + "/"


def _cache_key(*parts):
    raw = "|".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "宝园影视"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""

        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # 首页缓存（5 分钟）
        self._home_cache = []
        self._home_cache_time = 0

        # 分类/搜索页缓存（2 分钟）
        self._list_cache = {}
        self._list_cache_time = {}
        self._LIST_CACHE_TTL = 120

        # 详情页缓存（10 分钟）
        self._detail_cache = {}
        self._detail_cache_time = {}

        # 播放结果缓存（5 分钟）
        self._player_cache = {}
        self._player_cache_time = {}

        # 首集预缓存标记（修复：原逻辑永真）
        self._precached = set()

        self._MAX_LIST_CACHE = 50
        self._MAX_DETAIL_CACHE = 30
        self._MAX_PLAYER_CACHE = 50

    def _trim_cache(self, cache_dict, time_dict, max_size):
        if len(cache_dict) > max_size:
            sorted_keys = sorted(cache_dict.keys(), key=lambda k: time_dict.get(k, 0))
            remove_count = max_size // 2
            for k in sorted_keys[:remove_count]:
                cache_dict.pop(k, None)
                time_dict.pop(k, None)

    # ===== 网络工具 =====
    def _txt(self, url, timeout=3):
        try:
            rsp = self.fetch(url, headers=self.header, timeout=timeout)
            try:
                return rsp.text
            except Exception:
                return rsp.content.decode('utf-8', 'ignore')
        except Exception:
            return ""

    def _match(self, pattern, text, flags=0):
        if isinstance(pattern, str):
            m = re.search(pattern, text, flags)
        else:
            m = pattern.search(text)
        return m.group(1) if m else ""

    def _findall(self, pattern, text, flags=0):
        if isinstance(pattern, str):
            return re.findall(pattern, text, flags)
        return pattern.findall(text)

    def _origin(self, url):
        try:
            parsed = urlparse(url)
            return parsed.scheme + "://" + parsed.hostname + "/"
        except Exception:
            return HOST + "/"

    def _ep_num(self, ep_name):
        if not ep_name:
            return 99999
        m = _RE_EP_NUM.search(ep_name)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 99999

    def _extract_m3u8(self, html):
        """从 HTML 提取 m3u8/mp4 直链（按命中率排序）"""
        for pat in _RE_M3U8_PATTERNS:
            m = pat.search(html)
            if m:
                url = m.group(1)
                # 处理 JSON / JS 转义
                url = (url.replace("\\u002F", "/")
                          .replace("\\u002f", "/")
                          .replace("\\/", "/")
                          .replace("\\", ""))
                if url.startswith("//"):
                    url = "https:" + url
                low = url.lower()
                if ".m3u8" in low or ".mp4" in low:
                    return url
        for pat in (_RE_M3U8_BARE, _RE_MP4_BARE):
            m = pat.search(html)
            if m:
                return m.group(1)
        return ""

    # ===== 卡片提取 =====
    def _parse_cards(self, html):
        cards = []
        remarks = _RE_REMARK.findall(html)

        for i, m in enumerate(_RE_CARD_ITEM.finditer(html)):
            vid = m.group("vid")
            name = (m.group("name") or "").strip()
            pic = m.group("pic")
            if not name or not pic:
                continue
            remark = "HD"
            if i < len(remarks):
                r = remarks[i].strip()
                if r:
                    remark = r
            cards.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": _proxy_img(pic),
                "vod_remarks": remark,
            })
        return cards

    # ===== 简介提取（修复重点）=====
    def _extract_content(self, html):
        """
        多层回退提取简介：
          1. div.content（用平衡 div 扫描，避免嵌套截断）
          2. 简介：标签后内容
          3. meta description
        """
        # --- 方法 1：div.content 平衡扫描 ---
        for m in _RE_CONTENT_DIV.finditer(html):
            start = m.end()
            depth = 1
            pos = start
            limit = min(len(html), start + 20000)  # 限长防卡
            while pos < limit and depth > 0:
                open_idx = html.find('<div', pos)
                close_idx = html.find('</div>', pos)
                if close_idx == -1:
                    break
                if open_idx != -1 and open_idx < close_idx:
                    depth += 1
                    pos = open_idx + 4
                else:
                    depth -= 1
                    pos = close_idx + 6
            if depth == 0:
                raw = html[start:pos - 6]
                text = _strip(raw)
                if len(text) > 15:
                    return text[:500]

        # --- 方法 2：简介：标签 ---
        for pat in (_RE_CONTENT_SPAN, _RE_CONTENT_PREFIX):
            m = pat.search(html)
            if m:
                text = _strip(m.group(1))
                if len(text) > 15:
                    return text[:500]

        # --- 方法 3：meta description ---
        m = _RE_META_DESC.search(html)
        if m:
            text = m.group(1).strip()
            if len(text) > 15:
                return text[:500]

        return ""

    # ============================================================
    # 首页
    # ============================================================

    def homeContent(self, filter):
        return {
            "class": CLASSES,
            "filters": FILTERS,
        }

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {"list": self._home_cache[:72]}

        html = self._txt(HOST + "/", timeout=3)
        videos = self._parse_cards(html) if html else []

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {"list": self._home_cache}

    # ============================================================
    # 分类列表
    # ============================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    try:
                        ext = json.loads(extend)
                    except Exception:
                        ext = {}

            tid_str = str(tid)

            # 精选（tid=0）无筛选 + 第1页 → 直接用首页缓存
            if tid_str == "0":
                has_filter = any(ext.get(k, "") for k in ("class", "area", "year", "lang", "by"))
                if not has_filter and page <= 1:
                    vods = self.homeVideoContent().get("list", [])
                    return {
                        "list": vods,
                        "page": 1,
                        "pagecount": 1,
                        "limit": len(vods) or 36,
                        "total": len(vods) or 0,
                    }

            ck = _cache_key(tid_str, page,
                            ext.get("class", ""), ext.get("area", ""),
                            ext.get("year", ""), ext.get("lang", ""),
                            ext.get("by", ""))
            now = int(time.time())
            cached = self._list_cache.get(ck)
            if cached and now - self._list_cache_time.get(ck, 0) < self._LIST_CACHE_TTL:
                vods, pagecount = cached
                return {
                    "list": vods,
                    "page": page,
                    "pagecount": pagecount,
                    "limit": 36,
                    "total": pagecount * 36,
                }

            if tid_str == "0":
                params = ["searchtype=5", "page=" + str(page)]
            else:
                params = ["searchtype=5", "tid=" + tid_str, "page=" + str(page)]

            jq = ext.get("class", "")
            if jq:
                params.append("jq=" + quote(jq))
            area = ext.get("area", "")
            if area:
                params.append("area=" + quote(area))
            year = ext.get("year", "")
            if year:
                params.append("year=" + quote(year))
            lang = ext.get("lang", "")
            if lang:
                params.append("lang=" + quote(lang))
            order = ext.get("by", "")
            if order:
                params.append("order=" + quote(order))

            url = HOST + "/search.php?" + "&".join(params)
            html = self._txt(url, timeout=3)

            if not html:
                return {"page": page, "pagecount": 1, "limit": 36, "total": 0, "list": []}

            vods = self._parse_cards(html)

            pagecount = self._match(_RE_TOTAL, html)
            if pagecount:
                pagecount = int(pagecount)
            else:
                max_page = self._findall(_RE_PAGES, html)
                pagecount = max(int(p) for p in max_page) if max_page else 1

            self._list_cache[ck] = (vods, pagecount)
            self._list_cache_time[ck] = now
            self._trim_cache(self._list_cache, self._list_cache_time, self._MAX_LIST_CACHE)

            return {
                "list": vods,
                "page": page,
                "pagecount": pagecount,
                "limit": 36,
                "total": pagecount * 36,
            }
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 36, "total": 0, "list": []}

    # ============================================================
    # 详情页
    # ============================================================

    def _get_detail_html(self, vod_id):
        now = int(time.time())
        cached = self._detail_cache.get(vod_id)
        cached_time = self._detail_cache_time.get(vod_id, 0)
        if cached and now - cached_time < 600:
            return cached

        url = HOST + "/cnbvod/" + vod_id + ".html"
        html = self._txt(url, timeout=3)
        if not html or len(html) < 1000:
            time.sleep(0.1)
            html = self._txt(url, timeout=3)

        if html and len(html) > 1000:
            self._detail_cache[vod_id] = html
            self._detail_cache_time[vod_id] = now
            self._trim_cache(self._detail_cache, self._detail_cache_time, self._MAX_DETAIL_CACHE)

        return html

    def _precache_first_episode(self, vod_id, html):
        """预解析首集播放地址"""
        try:
            tabs = _RE_TABS.findall(html)
            if not tabs:
                return
            first_tab_id = tabs[0][0]

            # 定位首个 tab 容器范围
            m = re.search(r'id="' + re.escape(first_tab_id) + r'"', html)
            if not m:
                return
            start = m.start()
            # 找下一个 tab 起始
            end = len(html)
            for tab_id, _ in tabs[1:]:
                n = re.search(r'id="' + re.escape(tab_id) + r'"', html[start:])
                if n:
                    end = min(end, start + n.start())
                    break
            tab_html = html[start:end]

            ep_m = re.search(
                r'href="(/cnbplayer/' + re.escape(vod_id) + r'-(\d+)-(\d+)\.html)"',
                tab_html
            )
            if not ep_m:
                return
            first_play_url = HOST + ep_m.group(1)

            now = int(time.time())
            if first_play_url in self._player_cache:
                if now - self._player_cache_time.get(first_play_url, 0) < 300:
                    return

            play_html = self._txt(first_play_url, timeout=3)
            if not play_html:
                return

            direct_url = self._extract_m3u8(play_html)
            result = None
            if direct_url:
                result = self._build_play_result(direct_url)
            else:
                iframe_url = self._match(_RE_IFRAME, play_html)
                if iframe_url:
                    if iframe_url.startswith("//"):
                        iframe_url = "https:" + iframe_url
                    elif not iframe_url.startswith("http"):
                        iframe_url = HOST + iframe_url
                    resolved = self._resolve_iframe(iframe_url)
                    if resolved:
                        result = self._build_play_result(resolved)

            if result:
                self._player_cache[first_play_url] = result
                self._player_cache_time[first_play_url] = now
        except Exception:
            pass

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0])

        html = self._get_detail_html(vod_id)
        if not html:
            return {"list": []}

        # 基本信息
        name = self._match(_RE_H1, html)
        if not name:
            name = self._match(_RE_TITLE_TAG, html)

        pic = _proxy_img(self._match(_RE_PIC, html))

        type_name = area = year = ""
        m = _RE_INFO.search(html)
        if m:
            type_name = m.group(1).strip()
            area = m.group(2).strip()
            year = m.group(3).strip()

        m = _RE_ACTOR.search(html)
        actor = _strip(m.group(1)) if m else ""

        m = _RE_DIRECTOR.search(html)
        director = _strip(m.group(1)) if m else ""

        # ---- 简介（修复重点）----
        content = self._extract_content(html)

        # 更新状态
        remark = self._match(_RE_UPDATE, html).strip()
        if not remark:
            m = _RE_REMARK.search(html)
            remark = m.group(1).strip() if m else ""
        if not remark:
            remark = "HD"

        # ---- 播放列表 ----
        play_from_list = []
        play_url_list = []

        tabs = _RE_TABS.findall(html)
        if not tabs:
            tabs = [("playlist1", "秒播")]

        # 计算每个 tab 的位置范围
        tab_ranges = []
        for idx, (tab_id, tab_name) in enumerate(tabs):
            m = re.search(r'id="' + re.escape(tab_id) + r'"', html)
            if m:
                tab_ranges.append((m.start(), idx, tab_id, _strip(tab_name)))
        tab_ranges.sort()

        for i, (start, idx, tab_id, tab_name) in enumerate(tab_ranges):
            end = tab_ranges[i + 1][0] if i + 1 < len(tab_ranges) else len(html)
            tab_html = html[start:end]

            # 修复：不依赖属性顺序，先抓 <a> 标签再解析属性
            episodes = []
            for am in re.finditer(r'<a\b([^>]*)>([^<]*)</a>', tab_html):
                attrs, text = am.group(1), am.group(2)
                href_m = re.search(
                    r'href="(/cnbplayer/' + re.escape(vod_id) + r'-(\d+)-(\d+)\.html)"',
                    attrs
                )
                if not href_m:
                    continue
                title_m = re.search(r'\btitle="([^"]*)"', attrs)
                ep_name = (title_m.group(1) if title_m else text).strip()
                if not ep_name or "APP秒播" in ep_name:
                    continue
                link = href_m.group(1)
                try:
                    pidx = int(href_m.group(3))
                except Exception:
                    pidx = 99999
                episodes.append({
                    "name": ep_name,
                    "link": HOST + link,
                    "part_idx": pidx,
                })

            if episodes:
                episodes.sort(key=lambda x: (x["part_idx"], self._ep_num(x["name"])))
                ep_strs = ["%s$%s" % (ep["name"], ep["link"]) for ep in episodes]
                play_from_list.append(tab_name or ("线路%d" % (idx + 1)))
                play_url_list.append("#".join(ep_strs))

        if not play_url_list:
            return {"list": []}

        # 首集预缓存（仅首次）
        if vod_id not in self._precached:
            self._precache_first_episode(vod_id, html)
            self._precached.add(vod_id)
            if len(self._precached) > 100:
                self._precached.clear()

        vod = {
            "vod_id": vod_id,
            "vod_name": name or "",
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remark,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content or "",
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        return {"list": [vod]}

    # ============================================================
    # 搜索
    # ============================================================

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            ck = _cache_key("search", key, page)
            now = int(time.time())
            cached = self._list_cache.get(ck)
            if cached and now - self._list_cache_time.get(ck, 0) < self._LIST_CACHE_TTL:
                vods, _ = cached
                return {"list": vods}

            # 修复：URL 编码
            url = HOST + "/search.php?searchword=" + quote(key)
            if page > 1:
                url += "&page=" + str(page)

            html = self._txt(url, timeout=3)
            if not html:
                return {"list": []}

            vods = self._parse_cards(html)

            self._list_cache[ck] = (vods, 1)
            self._list_cache_time[ck] = now
            self._trim_cache(self._list_cache, self._list_cache_time, self._MAX_LIST_CACHE)

            return {"list": vods}
        except Exception:
            return {"list": []}

    # ============================================================
    # 播放解析
    # ============================================================

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}

        play_url = str(id)

        now = int(time.time())
        cached = self._player_cache.get(play_url)
        if cached and now - self._player_cache_time.get(play_url, 0) < 300:
            return cached

        result = None

        if "/cnbplayer/" in play_url:
            html = self._txt(play_url, timeout=3)
            if html:
                direct_url = self._extract_m3u8(html)
                if direct_url:
                    result = self._build_play_result(direct_url)

                if not result:
                    iframe_url = self._match(_RE_IFRAME, html)
                    if iframe_url:
                        if iframe_url.startswith("//"):
                            iframe_url = "https:" + iframe_url
                        elif not iframe_url.startswith("http"):
                            iframe_url = HOST + iframe_url
                        resolved = self._resolve_iframe(iframe_url)
                        if resolved:
                            result = self._build_play_result(resolved)

            if not result:
                result = {
                    "parse": 1,
                    "playUrl": "",
                    "url": play_url,
                    "header": {"User-Agent": UA, "Referer": HOST + "/"},
                }

        elif ".m3u8" in play_url.lower() or ".mp4" in play_url.lower():
            result = self._build_play_result(play_url)

        else:
            result = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
            }

        self._player_cache[play_url] = result
        self._player_cache_time[play_url] = now
        self._trim_cache(self._player_cache, self._player_cache_time, self._MAX_PLAYER_CACHE)
        return result

    def _build_play_result(self, url):
        is_m3u8 = ".m3u8" in url.lower()
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self._origin(url),
            },
            "format": "application/x-mpegURL" if is_m3u8 else "",
            "contentType": "application/x-mpegURL" if is_m3u8 else "",
        }

    def _resolve_iframe(self, iframe_url, _depth=0):
        if _depth > 1:
            return ""
        try:
            referer = self._origin(iframe_url)
            headers = dict(self.header)
            headers["Referer"] = referer
            rsp = self.fetch(iframe_url, headers=headers, timeout=3)
            try:
                html = rsp.text
            except Exception:
                html = rsp.content.decode('utf-8', 'ignore')
            if not html:
                return ""

            url = self._extract_m3u8(html)
            if url:
                return url

            nested = self._match(_RE_IFRAME, html)
            if nested and nested != iframe_url:
                if nested.startswith("//"):
                    nested = "https:" + nested
                elif not nested.startswith("http"):
                    parsed = urlparse(iframe_url)
                    nested = parsed.scheme + "://" + parsed.netloc + nested
                return self._resolve_iframe(nested, _depth + 1)

        except Exception:
            pass
        return ""

    # ===== 本地代理（图片回退用）=====
    def localProxy(self, param):
        if not param:
            return [200, "text/plain", b"", ""]

        if isinstance(param, str):
            try:
                qs = parse_qs(param)
                ptype = qs.get("type", [""])[0]
                img_url = qs.get("url", [""])[0]
            except Exception:
                return [200, "text/plain", b"", ""]
        elif isinstance(param, dict):
            ptype = param.get("type", "")
            img_url = param.get("url", "")
        else:
            return [200, "text/plain", b"", ""]

        if ptype == "img" and img_url:
            try:
                headers = {
                    "User-Agent": UA,
                    "Referer": HOST + "/",  # 修复：用站点 Referer
                }
                rsp = self.fetch(img_url, headers=headers, timeout=5)
                data = rsp.content
                content_type = "image/jpeg"
                if data[:3] == b'\xff\xd8\xff':
                    content_type = "image/jpeg"
                elif data[:8] == b'\x89PNG\r\n\x1a\n':
                    content_type = "image/png"
                elif data[:4] == b'GIF8':
                    content_type = "image/gif"
                elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                    content_type = "image/webp"
                else:
                    try:
                        ct = rsp.headers.get("Content-Type", "")
                        if ct:
                            content_type = ct.split(";")[0].strip()
                    except Exception:
                        pass
                return [200, content_type, data, ""]
            except Exception:
                return [404, "text/plain", b"", ""]

        return [200, "text/plain", b"", ""]

    # ===== 清理 =====
    def destroy(self):
        self._detail_cache.clear()
        self._detail_cache_time.clear()
        self._player_cache.clear()
        self._player_cache_time.clear()
        self._list_cache.clear()
        self._list_cache_time.clear()
        self._home_cache = []
        self._home_cache_time = 0
        self._precached.clear()

    def close(self):
        self.destroy()
