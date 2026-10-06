# -*- coding: utf-8 -*-
"""
4K影仓 Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
站点: https://www.4kcabin.com/
"""
import sys
import json
import re
import time
import base64

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

        def post(self, url, data=None, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.post(url, data=data, headers=headers,
                                timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

    Spider = _BaseSpider

from urllib.parse import quote, unquote


# ============================================================
# 常量
# ============================================================
HOST = "https://www.4kcabin.com"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

CLASSES = [
    {"type_name": "电影", "type_id": "dianying"},
    {"type_name": "电视剧", "type_id": "dianshiju"},
    {"type_name": "动漫", "type_id": "dongman"},
    {"type_name": "综艺", "type_id": "zongyi"},
    {"type_name": "体育赛事", "type_id": "tiyusaishi"},
]

_AREA_VALUES = [
    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "印度", "v": "印度"}, {"n": "泰国", "v": "泰国"},
    {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
]
_YEAR_VALUES = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2013, -1)]
_BY_VALUES = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]
_LANG_VALUES = [
    {"n": "全部", "v": ""}, {"n": "普通话", "v": "普通话"}, {"n": "粤语", "v": "粤语"},
    {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"},
    {"n": "泰语", "v": "泰语"}, {"n": "法语", "v": "法语"},
]

_CLASS_FILTERS = {
    "dianying": [
        {"n": "全部", "v": ""}, {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
        {"n": "爱情", "v": "爱情"}, {"n": "剧情", "v": "剧情"}, {"n": "科幻", "v": "科幻"},
        {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"}, {"n": "恐怖", "v": "恐怖"},
        {"n": "犯罪", "v": "犯罪"}, {"n": "动画", "v": "动画"}, {"n": "冒险", "v": "冒险"},
        {"n": "战争", "v": "战争"}, {"n": "奇幻", "v": "奇幻"}, {"n": "历史", "v": "历史"},
        {"n": "伦理", "v": "伦理"}, {"n": "同性", "v": "同性"}, {"n": "纪录片", "v": "纪录片"},
    ],
    "dianshiju": [
        {"n": "全部", "v": ""}, {"n": "都市", "v": "都市"}, {"n": "爱情", "v": "爱情"},
        {"n": "古装", "v": "古装"}, {"n": "悬疑", "v": "悬疑"}, {"n": "犯罪", "v": "犯罪"},
        {"n": "家庭", "v": "家庭"}, {"n": "青春", "v": "青春"}, {"n": "校园", "v": "校园"},
        {"n": "喜剧", "v": "喜剧"}, {"n": "剧情", "v": "剧情"}, {"n": "历史", "v": "历史"},
        {"n": "战争", "v": "战争"}, {"n": "武侠", "v": "武侠"}, {"n": "仙侠", "v": "仙侠"},
        {"n": "奇幻", "v": "奇幻"}, {"n": "同性", "v": "同性"}, {"n": "短剧", "v": "短剧"},
    ],
    "dongman": [
        {"n": "全部", "v": ""}, {"n": "热血", "v": "热血"}, {"n": "冒险", "v": "冒险"},
        {"n": "奇幻", "v": "奇幻"}, {"n": "科幻", "v": "科幻"}, {"n": "校园", "v": "校园"},
        {"n": "恋爱", "v": "恋爱"}, {"n": "搞笑", "v": "搞笑"}, {"n": "悬疑", "v": "悬疑"},
        {"n": "推理", "v": "推理"}, {"n": "治愈", "v": "治愈"}, {"n": "运动", "v": "运动"},
        {"n": "机战", "v": "机战"}, {"n": "魔法", "v": "魔法"}, {"n": "异世界", "v": "异世界"},
        {"n": "战斗", "v": "战斗"}, {"n": "日常", "v": "日常"}, {"n": "剧情", "v": "剧情"},
    ],
    "zongyi": [
        {"n": "全部", "v": ""}, {"n": "真人秀", "v": "真人秀"}, {"n": "脱口秀", "v": "脱口秀"},
        {"n": "访谈", "v": "访谈"}, {"n": "选秀", "v": "选秀"}, {"n": "音乐", "v": "音乐"},
        {"n": "舞蹈", "v": "舞蹈"}, {"n": "竞技", "v": "竞技"}, {"n": "美食", "v": "美食"},
        {"n": "旅游", "v": "旅游"}, {"n": "游戏", "v": "游戏"}, {"n": "喜剧", "v": "喜剧"},
        {"n": "情感", "v": "情感"}, {"n": "亲子", "v": "亲子"}, {"n": "职场", "v": "职场"},
        {"n": "文化", "v": "文化"}, {"n": "益智", "v": "益智"}, {"n": "生活", "v": "生活"},
    ],
    "tiyusaishi": [
        {"n": "全部", "v": ""}, {"n": "足球", "v": "足球"}, {"n": "篮球", "v": "篮球"},
        {"n": "网球", "v": "网球"}, {"n": "斯诺克", "v": "斯诺克"},
    ],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": _CLASS_FILTERS.get(tid, [{"n": "全部", "v": ""}])},
        {"key": "area", "name": "地区", "value": _AREA_VALUES},
        {"key": "year", "name": "年份", "value": _YEAR_VALUES},
        {"key": "lang", "name": "语言", "value": _LANG_VALUES},
        {"key": "by", "name": "排序", "value": _BY_VALUES},
    ]


# ============================================================
# 预编译正则
# ============================================================
_RE_VODDAIL_ID = re.compile(r'/voddetail/(\d+)\.html')
_RE_TITLE_ATTR = re.compile(r'title="([^"]{2,100})"')
_RE_ALT_ATTR = re.compile(r'alt="([^"]{2,100})"')
_RE_IMG_LAZY = re.compile(
    r'(?:data-original|data-src|data-lazy-src|data-lazy|data-bg|data-echo|'
    r'lay-src|data-lazyurl|data-real|data-thumb|data-img|data-poster|'
    r'data-image|data-cover|data-avatar|data-photo|data-src2|ks-lazyload|'
    r'data-lazyload|data-url|data-srcset|data-thumbnail)\s*=\s*"([^"]+)"',
    re.I)
_RE_IMG_SRC = re.compile(r'src\s*=\s*"([^"]+)"', re.I)
_RE_IMG_SRCSET = re.compile(r'srcset\s*=\s*"([^"]+)"', re.I)
_RE_SOURCE_SRCSET = re.compile(r'<source[^>]*\ssrcset\s*=\s*"([^"]+)"', re.I)
_RE_BG_IMG = re.compile(
    r'background(?:-image)?\s*:\s*url\(["\']?([^"\')]+)["\']?\)', re.I)
_RE_IMG_URL_GENERIC = re.compile(
    r'((?:https?:)?//[^"\s<>]+\.(?:jpg|jpeg|png|webp|gif|bmp))', re.I)
_RE_M3U8_URL = re.compile(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', re.I)
_RE_MP4_URL = re.compile(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', re.I)
_RE_VODPLAY_LINK = re.compile(
    r'href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]+)</a>')
_RE_PAGE_TEXT = re.compile(
    r'共\s*\d+\s*条[^,]*[,，]\s*当前\s*\d+\s*/\s*(\d+)\s*页')
_RE_PAGE_LINK = re.compile(
    r'class="[^"]*page[_-]?link[^"]*"[^>]*href="[^"]*?(\d+)[^"]*?"', re.I)
_RE_H2 = re.compile(r'<h2[^>]*>(.*?)</h2>', re.S)
_RE_H3 = re.compile(r'<h3[^>]*>(.*?)</h3>', re.S)
_RE_TITLE_TAG = re.compile(r'<title>([^<|]+)')

_IMG_SKIP = ('loading', 'placeholder', 'lazyload',
             'logo', 'search', 'icon', 'default', 'blank',
             'nopic', 'no-pic', 'noflag', 'norule')

_SKIP_TEXTS = {
    'HD', '高清', '超清', '4K', '蓝光', '抢先版', '正片', '预告', '完结',
    '查看更多', '加载更多', '首页', '上一页', '下一页', '尾页', 'GO',
    '全部', '类型', '地区', '年份', '语言', '排序', '最新', '最热', '评分',
    '确定', '重置', '筛选', '收起', '展开',
}
_SKIP_NAV = {
    '首页', '上一页', '下一页', '尾页', 'GO',
    '查看更多', '加载更多', '确定', '重置', '筛选',
    '全部', '类型', '地区', '年份', '语言', '排序',
}
_REMARK_PATTERNS = [
    r'class="[^"]*(?:pic-text|pic-tag|module-item-text|tag|remarks|state|label|badge)[^"]*"[^>]*>([^<]{1,20})<',
    r'<span[^>]*class="[^"]*(?:text-right|remarks|state|pic-tag)[^"]*"[^>]*>([^<]{1,20})<',
    r'<i[^>]*>([^<]{1,20})</i>',
    r'<em[^>]*>([^<]{1,20})</em>',
]

# ============================================================
# 简介提取正则（多层兜底，覆盖绝大多数苹果CMS v10 模板）
# ============================================================
_INTRO_PATTERNS = [
    # 八度 / 天启等模板
    r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</div>',
    # 4K影仓 / 常见 custom 模板
    r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<span[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<p[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</p>',
    r'<div[^>]*class="[^"]*vod-detail-content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<p[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)</p>',
    r'<span[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)</span>',
    # id 选择
    r'<div[^>]*id="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*intro[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*id="[^"]*detail[^"]*"[^>]*>([\s\S]*?)</div>',
    # 描述类
    r'<p[^>]*class="[^"]*\bdesc\b[^"]*"[^>]*>([\s\S]*?)</p>',
    r'<div[^>]*class="[^"]*\bdesc\b[^"]*"[^>]*>([\s\S]*?)</div>',
    # 直接“剧情介绍:” “简介:” 段落
    r'(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*</[^>]+>\s*<[^>]*>([\s\S]{10,2000}?)</',
    r'(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*([\s\S]{10,2000}?)(?:<br|\n\n|</p>|</div>|$)',
]


# ============================================================
# Spider 主类
# ============================================================
class Spider(Spider):

    def getName(self):
        return "4K影仓"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""

        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate",
        }

        self._home_cache = []
        self._home_cache_time = 0
        self._cat_cache = {}
        self._search_cache = {}
        self._play_cache = {}

    # ===== 网络工具 =====
    def _rsp_text(self, rsp):
        try:
            return rsp.text
        except Exception:
            try:
                return rsp.content.decode('utf-8', 'ignore')
            except Exception:
                return ""

    def _fetch_html(self, url, timeout=1.5, retries=2):
        for attempt in range(retries):
            try:
                rsp = self.fetch(url, headers=self.header, timeout=timeout)
                text = self._rsp_text(rsp)
                if text and len(text) > 500:
                    head = text[:300].lower()
                    if 'error code: 520' in head or ('cloudflare' in head and '520' in head):
                        if attempt < retries - 1:
                            time.sleep(0.05 * (1.2 ** attempt))
                            continue
                    if ('/voddetail/' in text or '/vodplay/' in text
                            or 'player_aaaa' in text):
                        return text
                    if len(text) > 2000 and 'error code' not in head:
                        return text
                if attempt < retries - 1:
                    time.sleep(0.05 * (1.2 ** attempt))
            except Exception:
                if attempt < retries - 1:
                    time.sleep(0.05 * (1.2 ** attempt))
        return ""

    def _fetch_html_fast(self, url, timeout=1.2, retries=1):
        return self._fetch_html(url, timeout=timeout, retries=retries)

    def _match(self, pattern, text, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1) if m else ""

    def _strip_tags(self, s):
        return re.sub(r'<[^>]+>', '', s or '').strip()

    def _clean_text(self, s):
        """去标签 + 解码实体 + 压缩空白"""
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

    def _is_direct_media(self, url):
        url = (url or "").lower()
        return (".m3u8" in url or ".mp4" in url
                or ".flv" in url or ".mkv" in url)

    def _extract_referer(self, url):
        try:
            if "://" in url:
                scheme = url.split("://")[0]
                host = url.split("://")[1].split("/")[0]
                return scheme + "://" + host + "/"
        except Exception:
            pass
        return HOST + "/"

    def _fix_img_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.lower().startswith('data:'):
            return ""
        url = re.sub(r'^url\(["\']?(.*?)["\']?\)$', r'\1', url)
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/") and not url.startswith("//"):
            url = HOST + url
        elif (not url.startswith("http") and "." in url.split("/")[0]
              and not url.startswith("/")):
            url = "https://" + url
        elif (not url.startswith("http") and not url.startswith("/")
              and not url.startswith("//")):
            if "/" in url or "." in url:
                url = HOST + "/" + url
        url_lower = url.lower()
        filename = url_lower.rsplit('/', 1)[-1] if '/' in url_lower else url_lower
        name_no_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
        if name_no_ext in _IMG_SKIP:
            return ""
        return url

    def _extract_img_from_text(self, text):
        if not text:
            return ""

        def _is_skip(url_lower):
            filename = url_lower.rsplit('/', 1)[-1] if '/' in url_lower else url_lower
            name_no_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
            return name_no_ext in _IMG_SKIP

        for m in _RE_IMG_LAZY.finditer(text):
            url = m.group(1).strip()
            url_lower = url.lower()
            if url_lower.startswith('data:') or _is_skip(url_lower):
                continue
            if len(url) > 5 and ('.' in url or '/' in url):
                url = re.sub(r'^url\(["\']?(.*?)["\']?\)$', r'\1', url)
                return url
        for m in _RE_SOURCE_SRCSET.finditer(text):
            srcset_val = m.group(1).strip()
            first_url = srcset_val.split(',')[0].strip().split(' ')[0].strip()
            if first_url:
                url_lower = first_url.lower()
                if not url_lower.startswith('data:') and not _is_skip(url_lower):
                    if len(first_url) > 5 and ('.' in first_url or '/' in first_url):
                        return first_url
        for m in _RE_IMG_SRCSET.finditer(text):
            srcset_val = m.group(1).strip()
            first_url = srcset_val.split(',')[0].strip().split(' ')[0].strip()
            if first_url:
                url_lower = first_url.lower()
                if not url_lower.startswith('data:') and not _is_skip(url_lower):
                    if len(first_url) > 5 and ('.' in first_url or '/' in first_url):
                        return first_url
        for m in _RE_BG_IMG.finditer(text):
            url = m.group(1).strip()
            url_lower = url.lower()
            if url_lower.startswith('data:') or _is_skip(url_lower):
                continue
            if len(url) > 5 and ('.' in url or '/' in url):
                return url
        for m in _RE_IMG_SRC.finditer(text):
            url = m.group(1).strip()
            url_lower = url.lower()
            if url_lower.startswith('data:') or _is_skip(url_lower):
                continue
            if len(url) > 5 and ('.' in url or '/' in url):
                url = re.sub(r'^url\(["\']?(.*?)["\']?\)$', r'\1', url)
                return url
        for m in _RE_IMG_URL_GENERIC.finditer(text):
            url = m.group(1).strip()
            url_lower = url.lower()
            if not _is_skip(url_lower):
                return url
        return ""

    # ===== URL 构建 =====
    def _build_show_url(self, type_id, ext, page):
        page_str = str(page) if page >= 1 else "1"
        parts = [
            type_id,
            ext.get("area", ""),
            ext.get("by", ""),
            ext.get("class", ""),
            ext.get("lang", ""),
            "", "", "",
            page_str,
            "", "",
            ext.get("year", ""),
        ]
        encoded = [quote(p, safe="") if p else "" for p in parts]
        return HOST + "/vodshow/" + "-".join(encoded) + ".html"

    def _build_search_urls(self, wd, page):
        page_str = str(page) if page >= 1 else "1"
        wd_encoded = quote(wd, safe="")
        urls = [
            HOST + "/vodsearch.html?wd=" + wd_encoded + "&page=" + page_str,
            HOST + "/vodsearch/" + wd_encoded + "-------" + page_str + "---.html",
            HOST + "/vodsearch/" + wd_encoded + "--------" + page_str + "---.html",
            HOST + "/vodsearch/" + wd_encoded + "------" + page_str + "---.html",
            HOST + "/vodsearch/" + wd_encoded + "----------" + page_str + "---.html",
            HOST + "/index.php/vodsearch.html?wd=" + wd_encoded + "&page=" + page_str,
            HOST + "/index.php/vodsearch/" + wd_encoded + "-------" + page_str + "---.html",
            HOST + "/vodsearch/" + wd_encoded + ".html" if page == 1 else None,
        ]
        return [u for u in urls if u]

    # ===== HTML 解析：视频卡片列表 =====
    def _parse_video_cards(self, html):
        results = []
        seen_ids = set()
        unique_ids = []
        for m in _RE_VODDAIL_ID.finditer(html):
            vid = m.group(1)
            if vid not in seen_ids:
                seen_ids.add(vid)
                unique_ids.append(vid)

        for vid in unique_ids:
            a_tags = re.findall(
                r'<a\s+([^>]*?href="/voddetail/%s\.html"[^>]*?)>(.*?)</a>' % vid,
                html, re.S | re.I)

            title = ""
            pic = ""
            remarks = ""

            for attrs, inner in a_tags:
                if not title:
                    m = _RE_TITLE_ATTR.search(attrs)
                    if m:
                        t = m.group(1).strip()
                        if t and t not in _SKIP_TEXTS and not t.startswith('http'):
                            title = t
                if not title:
                    m = _RE_ALT_ATTR.search(inner)
                    if m:
                        t = m.group(1).strip()
                        if t and t not in _SKIP_TEXTS and not t.startswith('http'):
                            title = t
                if not title:
                    text = re.sub(r'<[^>]+>', '', inner).strip()
                    if text and len(text) > 1 and text not in _SKIP_TEXTS:
                        title = text[:100]

                if not pic:
                    for source in (attrs, inner):
                        pic = self._extract_img_from_text(source)
                        if pic:
                            break

                if not remarks:
                    for rp in _REMARK_PATTERNS:
                        rm = re.search(rp, inner, re.I)
                        if rm:
                            val = rm.group(1).strip()
                            if val and val not in _SKIP_NAV:
                                remarks = val
                                break

            if not title or not pic:
                first_pos = html.find('/voddetail/%s.html' % vid)
                if first_pos >= 0:
                    context = html[first_pos:first_pos + 500]
                    if not title:
                        for tag_re in (_RE_H2, _RE_H3):
                            for tm in tag_re.finditer(context):
                                t = self._strip_tags(tm.group(1))
                                if t and t not in _SKIP_TEXTS and not t.startswith('http'):
                                    title = t
                                    break
                            if title:
                                break
                    if not title:
                        texts = re.findall(r'>([^<]{3,100})<', context)
                        for t in texts:
                            t = t.strip()
                            if (t and len(t) > 2 and not t.startswith('http')
                                    and not t.isdigit() and t not in _SKIP_TEXTS):
                                title = t
                                break
                    if not pic:
                        ctx_start = max(0, first_pos - 300)
                        ctx = html[ctx_start:first_pos + 500]
                        pic = self._extract_img_from_text(ctx)

            if not title:
                continue

            pic = self._fix_img_url(pic)
            if not remarks:
                remarks = "HD"

            results.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return results

    # ===== HTML 解析：分页信息 =====
    def _parse_pagination(self, html, base_path="vodshow"):
        max_page = 1
        text_m = _RE_PAGE_TEXT.search(html)
        if text_m:
            max_page = max(max_page, int(text_m.group(1)))
        page_links = _RE_PAGE_LINK.findall(html)
        if page_links:
            nums = [int(x) for x in page_links if x.isdigit()]
            if nums:
                max_page = max(max_page, max(nums))
        url_pages = re.findall(
            r'/%s/[^"]*?-{8}(\d+)-{3}[^"]*?\.html' % base_path, html)
        if url_pages:
            nums = [int(x) for x in url_pages if x.isdigit()]
            if nums:
                max_page = max(max_page, max(nums))
        url_pages2 = re.findall(
            r'href="[^"]*/%s/[^"]*?-{4,}(\d+)-{2,}[^"]*?\.html"' % base_path,
            html, re.I)
        if url_pages2:
            nums = [int(x) for x in url_pages2 if x.isdigit()]
            if nums:
                max_page = max(max_page, max(nums))
        dp_matches = re.findall(r'data-page="(\d+)"', html)
        if dp_matches:
            nums = [int(x) for x in dp_matches if x.isdigit()]
            if nums:
                max_page = max(max_page, max(nums))
        js_m = re.search(r'page_total\s*[=:]\s*[\'"]?(\d+)', html)
        if js_m:
            max_page = max(max_page, int(js_m.group(1)))
        js_m2 = re.search(r'pagecount\s*[=:]\s*[\'"]?(\d+)', html, re.I)
        if js_m2:
            max_page = max(max_page, int(js_m2.group(1)))
        total_m = re.search(r'共\s*(\d+)\s*页', html)
        if total_m:
            max_page = max(max_page, int(total_m.group(1)))
        return max_page

    # ============================================================
    # 简介专用提取（多层兜底）
    # ============================================================
    def _extract_content(self, html):
        """
        多层兜底提取简介：
        1. 各类 content 容器（detail-sketch / vod_content / desc / #desc ...）
        2. "剧情介绍：" / "简介：" 段落
        3. meta description 兜底（并剥掉站点前缀）
        返回去标签、压缩空白后的文本（最多 1200 字）。
        """
        if not html:
            return ""

        def _clean_text(s):
            t = self._clean_text(s)
            # 去掉常见前缀词
            t = re.sub(r'^(?:剧情介绍|内容介绍|故事简介|简介|详情)\s*[:：]?\s*', '', t)
            # 去掉站点后缀噪音
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
            # 至少 15 字且不像一堆标签残留
            if txt and len(txt) >= 15 and not txt.startswith('{'):
                return txt[:1200]

        # 2) meta description 兜底
        mm = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            html, re.I)
        if mm:
            raw = self._clean_text(mm.group(1))
            # 剥离站点前缀：“XXX影视为您提供《YYY》…剧情介绍：”
            raw = re.sub(r'^.*?为你提供[^，,。]*[，,。]\s*', '', raw)
            raw = re.sub(r'^.*?(?:剧情介绍|内容介绍|故事简介|简介)\s*[:：]\s*',
                         '', raw)
            raw = re.sub(r'^[^，,。]{0,20}剧情介绍\s*[:：]\s*', '', raw)
            if raw and len(raw) >= 15:
                return raw[:1200]

        return ""

    # ============================================================
    # 首页
    # ============================================================
    def homeContent(self, filter=False):
        return {
            "class": CLASSES,
            "filters": FILTERS,
        }

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 600:
            return {"list": self._home_cache}

        videos = []
        html = self._fetch_html_fast(HOST + "/")
        if html:
            videos = self._parse_video_cards(html)

        if len(videos) < 12:
            for c in CLASSES[:2]:
                if len(videos) >= 20:
                    break
                cat_html = self._fetch_html_fast(
                    HOST + "/vodshow/" + c["type_id"] + "--------1---.html",
                    timeout=1.5, retries=1)
                if cat_html:
                    cat_videos = self._parse_video_cards(cat_html)
                    existing_ids = {v["vod_id"] for v in videos}
                    for v in cat_videos:
                        if v["vod_id"] not in existing_ids:
                            videos.append(v)
                            existing_ids.add(v["vod_id"])

        self._home_cache = videos
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
                        try:
                            from urllib.parse import parse_qs
                            params = parse_qs(extend)
                            ext = {k: v[0] for k, v in params.items()}
                        except Exception:
                            ext = {}

            cache_key = f"{tid}_{json.dumps(ext, sort_keys=True)}_{page}"
            now = int(time.time())
            if page == 1 and cache_key in self._cat_cache:
                cache_time, cached = self._cat_cache[cache_key]
                if now - cache_time < 300:
                    return cached

            url = self._build_show_url(tid, ext, page)
            html = self._fetch_html(url, timeout=1.5, retries=2)

            if not html:
                return {"page": page, "pagecount": 1, "limit": 20,
                        "total": 0, "list": []}

            videos = self._parse_video_cards(html)
            pagecount = self._parse_pagination(html, "vodshow")
            if pagecount < page:
                pagecount = page

            total = pagecount * len(videos) if videos else 0

            result = {
                "list": videos,
                "page": page,
                "pagecount": pagecount,
                "limit": len(videos),
                "total": total,
            }

            if page == 1:
                self._cat_cache[cache_key] = (now, result)
            return result
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 20,
                    "total": 0, "list": []}

    # ============================================================
    # 详情页
    # ============================================================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vod_id = str(ids[0])

        url = HOST + "/voddetail/" + vod_id + ".html"

        html = ""
        for attempt in range(2):
            html = self._fetch_html(url, timeout=1.5, retries=1)
            if html and len(html) > 500:
                break
            time.sleep(0.1)

        if not html:
            return {"list": []}

        # ---------- 标题 ----------
        title = self._match(r'<h1[^>]*>([^<]+)</h1>', html)
        if not title:
            title = self._match(r'class="[^"]*title[^"]*"[^>]*>([^<]+)<', html)
        if not title:
            title = _RE_TITLE_TAG.match(html).group(1) if _RE_TITLE_TAG.search(html) else ""
        if not title:
            title = "未知"
        title = title.strip()

        # ---------- 封面 ----------
        pic = self._extract_img_from_text(html)
        pic = self._fix_img_url(pic)

        # ---------- 分类 ----------
        type_name = self._match(
            r'<a[^>]*href="/vodshow/[^"]+"[^>]*>([^<]+)</a>', html)

        # ---------- 年份 ----------
        year = ""
        year_match = re.search(r'>\s*(\d{4})\s*<', html)
        if year_match:
            y = int(year_match.group(1))
            if 1900 < y <= 2027:
                year = str(y)

        # ---------- 地区 ----------
        area = ""
        for ap in [
            r'地区.*?<a[^>]*>([^<]+)</a>',
            r'地区[:：]\s*</[^>]+>\s*<[^>]*>([^<]+)',
            r'地区.*?>([^<]{2,10})<',
        ]:
            am = re.search(ap, html, re.S)
            if am:
                area = am.group(1).strip()
                break

        # ---------- 导演 ----------
        director = ""
        for dp in [
            r'导演.*?<a[^>]*>([^<]+)</a>',
            r'导演[:：]\s*</[^>]+>\s*<a[^>]*>([^<]+)</a>',
            r'class="[^"]*director[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
            r'导演[:：]\s*<span[^>]*>([^<]+)</span>',
        ]:
            dm = re.search(dp, html, re.S)
            if dm:
                dv = dm.group(1).strip()
                if dv and '资源' not in dv and '线路' not in dv:
                    director = dv
                    break

        # ---------- 演员 ----------
        actor = ""
        actor_section = re.search(
            r'主演.*?</(?:div|p|section|ul|dl)>', html, re.S)
        if actor_section:
            section_html = actor_section.group(0)
            actor_matches = re.findall(r'<a[^>]*>([^<]+)</a>', section_html)
            if actor_matches:
                actors = [a.strip() for a in actor_matches[:10]
                          if '资源' not in a and '线路' not in a]
                if actors:
                    actor = ",".join(actors)
        if not actor:
            for ap in [
                r'主演[:：]\s*</[^>]+>\s*<a[^>]*>([^<]+)</a>',
                r'class="[^"]*actor[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
                r'主演[:：]\s*<span[^>]*>([^<]+)</span>',
            ]:
                am = re.search(ap, html, re.S)
                if am:
                    a = am.group(1).strip()
                    if a and '资源' not in a and '线路' not in a:
                        actor = a
                        break

        # ---------- 简介（重点：多层兜底）----------
        content = self._extract_content(html)

        # ---------- 备注 ----------
        remarks = self._match(
            r'class="[^"]*(?:remarks|state|pic-text|tag)[^"]*"[^>]*>([^<]{1,20})<',
            html)
        if not remarks:
            remarks = "HD"

        # ---------- 播放源 ----------
        play_links = _RE_VODPLAY_LINK.findall(html)

        lines = {}
        for vid, line_num, ep_num, ep_name in play_links:
            lk = int(line_num)
            ep_id = f"{vid}-{line_num}-{ep_num}"
            ep_name = ep_name.strip()
            if not ep_name:
                ep_name = f"第{ep_num}集"
            if lk not in lines:
                lines[lk] = []
            existing_eps = {e[0] for e in lines[lk]}
            if int(ep_num) not in existing_eps:
                lines[lk].append((int(ep_num), ep_name, ep_id))

        for lk in lines:
            lines[lk].sort()

        sids = sorted(lines.keys())
        line_order = self._extract_line_order(html, sids, title)

        play_from = []
        play_url = []
        for sid, name in line_order:
            if sid in lines:
                play_from.append(name)
                ep_list = [f"{ep_name}${ep_id}"
                           for _, ep_name, ep_id in lines[sid]]
                play_url.append("#".join(ep_list))

        if not play_url:
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic or "",
            "type_name": type_name or "",
            "vod_year": year or "",
            "vod_area": area or "",
            "vod_remarks": remarks or "HD",
            "vod_actor": actor or "",
            "vod_director": director or "",
            "vod_content": content or "",
            "vod_play_from": "$$$".join(play_from) if play_from else "4K影仓",
            "vod_play_url": "$$$".join(play_url) if play_url else "",
        }
        return {"list": [vod]}

    def _extract_line_order(self, html, sids, video_title=""):
        sid_set = set(sids)
        result = []
        used_sids = set()

        title_lower = (video_title or "").strip().lower()
        _BAD_NAMES = {'简介', '剧情', '推荐', '评论', '相关', '下载', '播放',
                      '选集', '详情', '资讯', '首页', '更多', '展开', '收起'}

        def is_valid(text):
            if not text or len(text) >= 30:
                return False
            tl = text.lower().strip()
            if title_lower and (tl == title_lower
                                or (title_lower in tl
                                    and len(tl) < len(title_lower) + 10)):
                return False
            if (text in _SKIP_TEXTS or text in _SKIP_NAV
                    or text in _BAD_NAMES or text.isdigit()):
                return False
            return True

        def clean_name(text):
            text = self._strip_tags(text).strip()
            text = re.sub(r'[-—]\s*在线播放\s*$', '', text)
            text = re.sub(r'[-—]\s*播放\s*$', '', text)
            bracket_m = re.search(r'[\[(（]([^)\]）]+)[\])）]\s*$', text)
            if bracket_m:
                text = bracket_m.group(1).strip()
            return text

        def try_add_sid(sid, name):
            if sid in sid_set and sid not in used_sids and is_valid(name):
                result.append((sid, name))
                used_sids.add(sid)
                return True
            return False

        # 1. JS变量 vod_play_from
        js_from = self._match(
            r'(?:vod_play_from|play_from)\s*[=:]\s*["\']([^"\']+)["\']', html)
        if js_from and '$$$' in js_from:
            js_names = [n.strip() for n in js_from.split('$$$') if n.strip()]
            sorted_sids = sorted(sid_set)
            for i, sid in enumerate(sorted_sids):
                if i < len(js_names) and is_valid(js_names[i]):
                    result.append((sid, js_names[i]))
                    used_sids.add(sid)
            if len(result) == len(sids):
                return result

        # 2. data-tab="playlistN"
        if len(result) < len(sids):
            tabs = re.findall(
                r'data-tab="\.?playlist(\d+)"[^>]*>(.*?)</(?:div|a|li|span|button)>',
                html, re.S | re.I)
            for sid_str, content in tabs:
                sid = int(sid_str)
                name = clean_name(content)
                if try_add_sid(sid, name):
                    continue
                if try_add_sid(sid + 1, name):
                    continue
                try_add_sid(sid - 1, name)

        # 3. href="#playlistN"
        if len(result) < len(sids):
            tabs = re.findall(
                r'href="#playlist(\d+)"[^>]*>(.*?)</a>', html, re.S | re.I)
            for sid_str, content in tabs:
                sid = int(sid_str)
                name = clean_name(content)
                try_add_sid(sid, name)

        # 4. data-target="#playlistN"
        if len(result) < len(sids):
            tabs = re.findall(
                r'data-target="#playlist(\d+)"[^>]*>(.*?)</(?:div|a|li|span|button)>',
                html, re.S | re.I)
            for sid_str, content in tabs:
                sid = int(sid_str)
                name = clean_name(content)
                try_add_sid(sid, name)

        # 5. option value="playlistN"
        if len(result) < len(sids):
            tabs = re.findall(
                r'<option[^>]*value="playlist(\d+)"[^>]*>([^<]+)</option>',
                html, re.I)
            for sid_str, content in tabs:
                sid = int(sid_str)
                name = clean_name(content)
                try_add_sid(sid, name)

        # 6. #playlistN 内的 h2/h3
        for sid in sorted(sid_set - used_sids):
            for h_pat in [
                r'id="playlist%d"[^>]*>.*?<h[23][^>]*>(.*?)</h[23]>' % sid,
                r'id="playlist%d"[^>]*>.*?<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>' % sid,
            ]:
                m = re.search(h_pat, html, re.S | re.I)
                if m:
                    name = clean_name(m.group(1))
                    if is_valid(name):
                        result.append((sid, name))
                        used_sids.add(sid)
                        break

        # 7. 位置映射
        if len(result) < len(sids):
            all_tab_contents = re.findall(
                r'class="[^"]*(?:module-tab-item|tab-item|play-tab|tab-link|nav-link|play-tab-item)[^"]*"[^>]*>(.*?)</(?:div|a|li|span|button)>',
                html, re.S | re.I)
            remaining_sids = sorted(sid_set - used_sids)
            for i, content in enumerate(all_tab_contents):
                if i >= len(remaining_sids):
                    break
                sid = remaining_sids[i]
                name = clean_name(content)
                if is_valid(name):
                    result.append((sid, name))
                    used_sids.add(sid)

        # 8. JS单名
        if js_from and '$$$' not in js_from and is_valid(js_from):
            for sid in sorted(sid_set - used_sids):
                result.append((sid, js_from))
                used_sids.add(sid)
                break

        # 9. 兜底
        for sid in sorted(sid_set - used_sids):
            result.append((sid, f"线路{sid}"))

        return result

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1

            if not key or not key.strip():
                return {"list": []}

            wd = key.strip()
            cache_key = f"{wd}_{page}"
            now = int(time.time())
            if cache_key in self._search_cache:
                cache_time, cached = self._search_cache[cache_key]
                if now - cache_time < 120:
                    return cached

            search_urls = self._build_search_urls(wd, page)
            html = ""
            for url in search_urls:
                if not url:
                    continue
                html = self._fetch_html(url, timeout=1.5, retries=1)
                if html and '/voddetail/' in html:
                    break
                html = ""

            if not html:
                ajax_url = (HOST + "/index.php/ajax/suggest?mid=1&wd="
                            + quote(wd, safe="") + "&limit=20")
                try:
                    rsp = self.fetch(ajax_url, headers=self.header, timeout=1.5)
                    data = json.loads(self._rsp_text(rsp))
                    if data.get("code") == 1 and data.get("list"):
                        videos = []
                        for item in data["list"]:
                            pic = item.get("pic", "")
                            if pic:
                                pic = self._fix_img_url(pic)
                            videos.append({
                                "vod_id": str(item.get("id", "")),
                                "vod_name": item.get("name", ""),
                                "vod_pic": pic,
                                "vod_remarks": "HD",
                            })
                        if videos:
                            result = {"list": videos}
                            self._search_cache[cache_key] = (now, result)
                            return result
                except Exception:
                    pass
                return {"list": []}

            videos = self._parse_video_cards(html)
            if not videos:
                return {"list": []}

            result = {"list": videos}
            self._search_cache[cache_key] = (now, result)
            if len(self._search_cache) > 50:
                expired = [k for k, (t, _) in self._search_cache.items()
                           if now - t > 300]
                for k in expired:
                    del self._search_cache[k]
            return result
        except Exception:
            return {"list": []}

    # ============================================================
    # 播放解析
    # ============================================================
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}

        play_id = str(id).replace("\\/", "/").strip()

        now = int(time.time())
        if play_id in self._play_cache:
            cache_time, cached = self._play_cache[play_id]
            if now - cache_time < 900:
                return cached

        if self._is_direct_media(play_id):
            is_m3u8 = ".m3u8" in play_id.lower()
            media_referer = self._extract_referer(play_id)
            result = {
                "parse": 0,
                "playUrl": "",
                "url": play_id,
                "header": {"User-Agent": UA, "Referer": media_referer},
                "format": "application/x-mpegURL" if is_m3u8 else "",
                "contentType": "application/x-mpegURL" if is_m3u8 else "",
            }
            self._play_cache[play_id] = (now, result)
            return result

        play_url = HOST + "/vodplay/" + play_id + ".html"
        html = self._fetch_html_fast(play_url, timeout=1.5, retries=1)

        if not html:
            result = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
            }
            self._play_cache[play_id] = (now, result)
            return result

        video_url = self._extract_player_url(html)

        if not video_url:
            result = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
            }
            self._play_cache[play_id] = (now, result)
            return result

        if self._is_direct_media(video_url):
            is_m3u8 = ".m3u8" in video_url.lower()
            media_referer = self._extract_referer(video_url)
            result = {
                "parse": 0,
                "playUrl": "",
                "url": video_url,
                "header": {"User-Agent": UA, "Referer": media_referer},
                "format": "application/x-mpegURL" if is_m3u8 else "",
                "contentType": "application/x-mpegURL" if is_m3u8 else "",
            }
            self._play_cache[play_id] = (now, result)
            return result

        result = {
            "parse": 1,
            "playUrl": "",
            "url": video_url,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
        }
        self._play_cache[play_id] = (now, result)
        return result

    # ---------- JSON 变量提取：花括号配平 ----------
    def _slice_json(self, text, start):
        """从 text[start] == '{' 起做花括号配平，返回 JSON 子串或 None"""
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

    def _find_var_json(self, html, varnames):
        """按顺序查找 var NAME = {...} 的 JSON 对象"""
        for name in varnames:
            # 用 word-boundary 避免误匹配 player_aaaa_xxx
            for m in re.finditer(
                    r'(?<![A-Za-z0-9_])' + re.escape(name)
                    + r'\s*[=:]\s*\{', html):
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

    def _extract_player_url(self, html):
        """从播放页 HTML 中解析 player_aaaa / player_data / MacPlayerConfig，
        用花括号配平精确提取 JSON，兼容嵌套转义和 URL 中的引号。"""
        obj = self._find_var_json(
            html, ('player_aaaa', 'player_data', 'MacPlayerConfig'))
        if obj is not None:
            video_url = obj.get("url", "") or ""
            # 兼容极少数把真正地址放其它字段的情况
            if not video_url:
                for k in ('url_next', 'link', 'url3', 'url2'):
                    video_url = obj.get(k, "") or ""
                    if video_url:
                        break
            if video_url:
                encrypt = obj.get("encrypt", 0)
                try:
                    encrypt = int(encrypt)
                except Exception:
                    encrypt = 0
                if encrypt == 1:
                    video_url = unquote(video_url)
                elif encrypt == 2:
                    try:
                        video_url = base64.b64decode(video_url).decode(
                            'utf-8', 'ignore')
                    except Exception:
                        pass
                video_url = video_url.replace("\\/", "/")
                return video_url

        # 兜底 1：直接在 HTML 里搜 m3u8/mp4
        m = _RE_M3U8_URL.search(html)
        if m:
            return m.group(0).replace("\\/", "/")
        m = _RE_MP4_URL.search(html)
        if m:
            return m.group(0).replace("\\/", "/")

        # 兜底 2：var now/url/main
        m = re.search(r'var\s*(?:now|url|main)\s*=\s*["\']([^"\']+)["\']', html)
        if m and self._is_direct_media(m.group(1)):
            return m.group(1).replace("\\/", "/")

        # 兜底 3：iframe 递归
        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.I)
        if iframe:
            iu = iframe.group(1).strip()
            if iu.startswith('//'):
                iu = 'https:' + iu
            if iu.startswith('http'):
                h2 = self._fetch_html_fast(iu, timeout=1.5, retries=1)
                if h2:
                    return self._extract_player_url(h2)
        return ""

    # ===== 本地代理 =====
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
            url = unquote(url) if '%' in url else url

            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/") and not url.startswith("//"):
                url = HOST + url

            referer = self._extract_referer(url)

            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            }, timeout=1.5)

            content = rsp.content
            if not content:
                return [200, "image/jpeg", b"", ""]

            content_type = rsp.headers.get("Content-Type", "image/jpeg")
            if not content_type.startswith("image/"):
                url_lower = url.lower()
                if ".png" in url_lower:
                    content_type = "image/png"
                elif ".webp" in url_lower:
                    content_type = "image/webp"
                elif ".gif" in url_lower:
                    content_type = "image/gif"
                else:
                    content_type = "image/jpeg"
            return [200, content_type, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def destroy(self):
        pass

    def close(self):
        self.destroy()
