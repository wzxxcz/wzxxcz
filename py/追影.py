# -*- coding: utf-8 -*-
# 追影(zhuiying3.cc) · 极速版爬虫源（补全版）
# 特性：二级分类筛选、精准搜索、直连播放源、缓存加速、简介多级兜底
# TVBox 标准入口：get_spider()

import sys
sys.path.append('..')
from base.spider import Spider as BaseSpider
import re
import json
import hashlib
import time
import base64
from urllib.parse import quote

# ==================== 基础配置 ====================
BASE_URL = "https://zhuiying3.cc"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CATEGORY_MAP = {
    "电影": "dianying",
    "电视剧": "dianshiju",
    "动漫": "dongman",
    "综艺": "zongyi",
    "短剧": "duanju",
}

FILTER_CONFIG = {
    "dianying": {
        "类型": ["全部", "科幻", "剧情", "惊悚", "爱情", "古装", "动作", "悬疑", "犯罪",
                 "谍战", "历史", "喜剧", "奇幻", "家庭", "青春", "冒险", "纪录", "动画",
                 "人物", "文化", "其他"],
        "地区": ["全部", "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国",
                 "泰国", "英国", "法国", "德国", "意大利", "印度", "马来西亚"],
        "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
                 "2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012",
                 "2011", "2010", "2009", "2008"],
        "排序": ["综合排序", "热度最高", "最新上线", "最好评"],
    },
    "dianshiju": {
        "类型": ["全部", "国产", "欧美", "日本", "韩国", "港台", "其他", "剧情", "爱情",
                 "古装", "喜剧", "动作", "悬疑", "犯罪", "奇幻", "科幻", "家庭"],
        "地区": ["全部", "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国",
                 "泰国", "英国"],
        "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020",
                 "2019", "2018", "2017", "2016", "2015"],
        "排序": ["综合排序", "热度最高", "最新上线", "最好评"],
    },
    "dongman": {
        "类型": ["全部", "日本动漫", "国产动漫", "欧美动漫", "其他动漫"],
        "地区": ["全部", "日本", "中国大陆", "美国", "韩国"],
        "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020"],
        "排序": ["综合排序", "热度最高", "最新上线", "最好评"],
    },
    "zongyi": {
        "类型": ["全部", "国产综艺", "日韩综艺", "欧美综艺", "港台综艺"],
        "地区": ["全部", "中国大陆", "韩国", "日本", "中国台湾", "中国香港", "美国"],
        "年份": ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020"],
        "排序": ["综合排序", "热度最高", "最新上线", "最好评"],
    },
    "duanju": {
        "类型": ["全部", "甜宠", "古装", "都市", "悬疑", "逆袭", "穿越", "其他"],
        "地区": ["全部", "中国大陆"],
        "年份": ["全部", "2026", "2025", "2024", "2023"],
        "排序": ["综合排序", "热度最高", "最新上线", "最好评"],
    },
}

SORT_MAP = {
    "综合排序": "",
    "热度最高": "hits_week",
    "最新上线": "id",
    "最好评": "douban_score",
}

VIDEO_EXTS = ('.m3u8', '.mp4', '.flv', '.mkv', '.avi', '.ts', '.mpg', '.m3u')

_HTML_ENTITIES = [
    ('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
    ('&quot;', '"'), ('&#39;', "'"), ('&apos;', "'"), ('&middot;', '·'),
    ('&hellip;', '…'), ('&mdash;', '—'), ('&ndash;', '–'),
]


# ==================== 缓存机制 ====================
class SimpleCache:
    def __init__(self, max_size=50, ttl=300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['time'] < self.ttl:
                return entry['data']
            del self.cache[key]
        return None

    def set(self, key, data):
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['time'])
            del self.cache[oldest_key]
        self.cache[key] = {'data': data, 'time': time.time()}


# ==================== 工具函数 ====================
def _strip_html(text):
    if not text:
        return ""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    for k, v in _HTML_ENTITIES:
        text = text.replace(k, v)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _abs_url(url):
    if not url:
        return ""
    url = url.strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http'):
        return url
    if url.startswith('/'):
        return BASE_URL + url
    return BASE_URL + '/' + url


def _is_rank_img(tag_html):
    """判断是否为排名数字图（Top 1 / Top 2 ... 这类干扰图）"""
    if not tag_html:
        return False
    # class 里带 rang / rank / top-num 这类关键词
    if re.search(r'class\s*=\s*["\'][^"\']*(?:rang_img|rank_img|top_num|top-img|topnum)[^"\']*["\']',
                 tag_html, re.IGNORECASE):
        return True
    # 图片 alt="Top N"
    if re.search(r'alt\s*=\s*["\']Top\s*\d+["\']', tag_html, re.IGNORECASE):
        return True
    return False


def _is_placeholder_img(tag_html):
    """判断是否为纯数字占位图 (1.jpg / 06.png)"""
    if not tag_html:
        return False
    m = re.search(r'(?:data-src|data-original|src)\s*=\s*["\']([^"\']+)["\']',
                  tag_html, re.IGNORECASE)
    if not m:
        return False
    u = m.group(1).strip()
    if re.match(r'^https?://[^\s"\']*/\d+\.(?:jpg|jpeg|png|webp|gif)$', u, re.IGNORECASE):
        return True
    if re.match(r'^/?\d+\.(?:jpg|jpeg|png|webp|gif)$', u, re.IGNORECASE):
        return True
    return False


def _pick_img(tag_html):
    """
    从 <img> 标签中挑选真实图片地址：
    1. 优先选 class 带 hotsearch_item_img / card-cover / poster / cover 的图
    2. 跳过 hotsearch_rang_img (Top N 排名图)
    3. 兼容 data-src / data-original / data-echo / data-lazy-src / src
    4. 过滤 base64 与纯数字占位图
    """
    if not tag_html:
        return ""

    # 优先数据源属性顺序
    lazy_attrs = ('data-original', 'data-src', 'data-lazy-src', 'data-echo',
                  'data-url', 'data-img', 'data-original-src')

    def _clean(u):
        u = (u or '').strip()
        if not u or u.startswith('data:image'):
            return ""
        if re.match(r'^https?://[^\s"\']*/\d+\.(?:jpg|jpeg|png|webp|gif)$', u, re.IGNORECASE):
            return ""
        if re.match(r'^/?\d+\.(?:jpg|jpeg|png|webp|gif)$', u, re.IGNORECASE):
            return ""
        return _abs_url(u)

    def _extract(html):
        for attr in lazy_attrs:
            m = re.search(rf'{attr}\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m:
                got = _clean(m.group(1))
                if got:
                    return got
        m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            got = _clean(m.group(1))
            if got:
                return got
        m = re.search(r'style\s*=\s*["\'][^"\']*url\(([^)]+)\)', html, re.IGNORECASE)
        if m:
            got = _clean(m.group(1).strip('\'"'))
            if got:
                return got
        return ""

    # 1) 先在整个块里找 class 带 hotsearch_item_img 的图（热门搜索的真实海报）
    m = re.search(
        r'<img\b[^>]*class\s*=\s*["\'][^"\']*hotsearch_item_img[^"\']*["\'][^>]*>',
        tag_html, re.IGNORECASE
    )
    if m:
        got = _extract(m.group(0))
        if got:
            return got

    # 2) 在块里找 class 带 card-cover / poster / cover 的图
    for kw in ('card-cover', 'poster', 'cover'):
        m = re.search(
            rf'<img\b[^>]*class\s*=\s*["\'][^"\']*{kw}[^"\']*["\'][^>]*>',
            tag_html, re.IGNORECASE
        )
        if m:
            got = _extract(m.group(0))
            if got:
                return got

    # 3) 逐个 <img> 处理，跳过排名图和占位图
    for m in re.finditer(r'<img\b[^>]*>', tag_html, re.IGNORECASE):
        tag = m.group(0)
        if _is_rank_img(tag):
            continue
        if _is_placeholder_img(tag):
            continue
        got = _extract(tag)
        if got:
            return got

    return ""


# ==================== 爬虫类 ====================
class Spider(BaseSpider):
    _play_cache = SimpleCache(max_size=50, ttl=600)

    # ==================== 初始化 ====================
    def init(self, extend=""):
        global BASE_URL, USER_AGENT
        ext = {}
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
            except Exception:
                ext = {}
        if ext.get('base_url'):
            BASE_URL = str(ext['base_url']).rstrip('/')
        if ext.get('user_agent'):
            USER_AGENT = str(ext['user_agent'])

        self.name = "追影_极速版"
        self.header = {
            "User-Agent": USER_AGENT,
            "Referer": BASE_URL + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def getName(self):
        return "追影_极速版"

    def isVideoFormat(self, url):
        return any(ext in (url or '').lower() for ext in VIDEO_EXTS)

    # ==================== TVBox action 接口 ====================
    def action(self, action_str):
        try:
            return json.dumps({
                "name": self.getName(),
                "base_url": BASE_URL,
                "version": "1.6",
                "filter": self._build_filters(),
            }, ensure_ascii=False)
        except Exception:
            return ""

    # ==================== 安全的 POST 请求 ====================
    def _post(self, url, data, headers=None):
        merged_headers = dict(self.header)
        if headers:
            merged_headers.update(headers)
        merged_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

        body = data.encode('utf-8') if isinstance(data, str) else data

        post_meth = getattr(self, 'post', None)
        if callable(post_meth):
            for call in (
                lambda: post_meth(url, data=body, headers=merged_headers),
                lambda: post_meth(url, body, merged_headers),
                lambda: post_meth(url, data=data, headers=merged_headers),
            ):
                try:
                    rsp = call()
                    if rsp is None:
                        continue
                    return rsp.text if hasattr(rsp, 'text') else str(rsp)
                except Exception:
                    continue

        for kw in ("post_data", "data", "body", "postData"):
            try:
                rsp = self.fetch(url, headers=merged_headers, **{kw: body})
                if rsp is None:
                    continue
                txt = rsp.text if hasattr(rsp, 'text') else str(rsp)
                if txt:
                    return txt
            except Exception:
                continue

        try:
            rsp = self.fetch(url + "?" + data, headers=merged_headers)
            return rsp.text if hasattr(rsp, 'text') else str(rsp)
        except Exception as e:
            raise Exception("无法发送POST请求: %s" % e)

    # ==================== 构建筛选 URL ====================
    def _build_filter_url(self, category, type_name="", region="", year="", sort="", pg=1):
        try:
            p = int(pg)
        except Exception:
            p = 1

        has_filter = (
            (type_name and type_name != "全部") or
            (region and region != "全部") or
            (year and year != "全部") or
            (sort and sort != "综合排序")
        )

        if not has_filter:
            if p > 1:
                return "%s/vodtype/%s/page/%d.html" % (BASE_URL, category, p)
            return "%s/vodtype/%s.html" % (BASE_URL, category)

        params = [""] * 11
        if region and region != "全部":
            params[0] = quote(region, safe='')
        if sort and sort != "综合排序":
            params[1] = SORT_MAP.get(sort, "")
        if type_name and type_name != "全部":
            params[2] = quote(type_name, safe='')
        if year and year != "全部":
            params[10] = quote(year, safe='')

        path = "/vodshow/" + category + "-" + "-".join(params)
        if p > 1:
            path += "-" + str(p)
        return BASE_URL + path + ".html"

    # ==================== 解析视频列表 ====================
    def _parse_video_cards(self, html):
        videos = []
        seen = set()

        pattern = re.compile(
            r'<a\b([^>]*?)href="(?:https?://[^"]*?)?/video/([^"/]+)\.html"([^>]*)>([\s\S]*?)</a>',
            re.DOTALL | re.IGNORECASE
        )

        for m in pattern.finditer(html):
            attrs = (m.group(1) or '') + (m.group(3) or '')
            vid = m.group(2).strip()
            inner = m.group(4) or ''

            if not vid or vid in seen:
                continue
            img_m = re.search(r'<img\b[^>]*>', inner, re.IGNORECASE)
            if not img_m:
                continue

            # 跳过明显的排名干扰卡片（整个 a 标签 class 里带 hotsearch）
            if re.search(r'class\s*=\s*["\'][^"\']*hotsearch[^"\']*["\']', attrs, re.IGNORECASE):
                # 这种多半是热门搜索卡片，跳过
                continue

            seen.add(vid)

            # 封面（新增：跳过排名图）
            pic = _pick_img(inner)
            alt = ""
            alt_m = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', img_m.group(0), re.IGNORECASE)
            if alt_m:
                alt = alt_m.group(1).strip()

            title = ""
            t_m = re.search(
                r'class="[^"]*(?:card-title|title|name)[^"]*"[^>]*>([\s\S]*?)</',
                inner, re.IGNORECASE
            )
            if t_m:
                title = _strip_html(t_m.group(1))
            if not title:
                t_m = re.search(r'title\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
                if t_m:
                    title = t_m.group(1).strip()
            if not title:
                title = alt
            if not title:
                title = _strip_html(inner)[:40]
            if not title:
                continue

            remark = ""
            r_m = re.search(
                r'class="[^"]*(?:card-status|list-thumb-remark|remark|status|note)[^"]*"[^>]*>([\s\S]*?)</',
                inner, re.IGNORECASE
            )
            if r_m:
                remark = _strip_html(r_m.group(1))
            if remark and ('更新' not in remark and '集' not in remark
                           and '完结' not in remark and len(remark) > 12):
                remark = remark[:12]

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        return videos

    # ==================== 解析搜索结果列表 ====================
    def _parse_search_results(self, html):
        videos = []
        seen = set()

        pattern = re.compile(
            r'<div[^>]*class="[^"]*search-list-card[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>',
            re.DOTALL | re.IGNORECASE
        )

        for m in pattern.finditer(html):
            block = m.group(1)
            link_m = re.search(
                r'<a\b[^>]*href="(?:https?://[^"]*?)?/video/([^"/]+)\.html"[^>]*>',
                block, re.IGNORECASE
            )
            if not link_m:
                continue
            vid = link_m.group(1).strip()
            if vid in seen:
                continue
            seen.add(vid)

            title = ""
            t_m = re.search(r'<a\b[^>]*title\s*=\s*["\']([^"\']*)["\']', block, re.IGNORECASE)
            if t_m:
                title = t_m.group(1).strip()
            if not title:
                t_m = re.search(
                    r'class="[^"]*(?:title|name)[^"]*"[^>]*>([\s\S]*?)</',
                    block, re.IGNORECASE
                )
                if t_m:
                    title = _strip_html(t_m.group(1))
            if not title:
                continue

            pic = _pick_img(block)

            remark = ""
            r_m = re.search(
                r'class="[^"]*(?:remark|status|note)[^"]*"[^>]*>([\s\S]*?)</',
                block, re.IGNORECASE
            )
            if r_m:
                remark = _strip_html(r_m.group(1))

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        return videos

    # ==================== 首页分类 ====================
    def homeContent(self, filter):
        result = {}
        classes = [{'type_name': name, 'type_id': key} for name, key in CATEGORY_MAP.items()]
        result['class'] = classes
        if filter:
            result['filters'] = self._build_filters()
        return result

    # ==================== 构建筛选配置 ====================
    def _build_filters(self):
        filters = {}
        key_map = {"类型": "type", "地区": "area", "年份": "year", "排序": "sort"}
        for cat_key, cat_filters in FILTER_CONFIG.items():
            filter_list = []
            for filter_name, filter_values in cat_filters.items():
                key = key_map.get(filter_name, filter_name)
                values = [{"n": v, "v": v} for v in filter_values]
                filter_list.append({"key": key, "name": filter_name, "value": values})
            filters[cat_key] = filter_list
        return filters

    # ==================== 首页推荐 ====================
    def homeVideoContent(self):
        try:
            rsp = self.fetch(BASE_URL + "/", headers=self.header)
            vlist = self._parse_video_cards(rsp.text)
            return {'list': vlist[:30]}
        except Exception as e:
            print("首页获取出错:", e)
            return {'list': []}

    # ==================== 分类列表 ====================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            extend = extend or {}
            url = self._build_filter_url(
                tid,
                extend.get('type', ''),
                extend.get('area', ''),
                extend.get('year', ''),
                extend.get('sort', ''),
                pg
            )
            rsp = self.fetch(url, headers=self.header)
            vlist = self._parse_video_cards(rsp.text)

            try:
                pg_int = int(pg)
            except Exception:
                pg_int = 1

            pagecount = pg_int + 1 if vlist else pg_int

            return {
                'list': vlist,
                'page': pg_int,
                'pagecount': pagecount,
                'limit': len(vlist),
                'total': 9999 if vlist else 0,
            }
        except Exception as e:
            print("分类获取出错:", e)
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ==================== 简介提取 ====================
    def _extract_desc(self, html):
        patterns = [
            r'<div[^>]*class="[^"]*detail-desc[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<div[^>]*class="[^"]*detail-intro[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<div[^>]*class="[^"]*video-desc[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>([\s\S]*?)</div>',
            r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</p>',
            r'<span[^>]*class="[^"]*detail-content-text[^"]*"[^>]*>([\s\S]*?)</span>',
            r'<span[^>]*class="[^"]*detail-intro-text[^"]*"[^>]*>([\s\S]*?)</span>',
        ]
        for p in patterns:
            m = re.search(p, html, re.DOTALL | re.IGNORECASE)
            if m:
                text = _strip_html(m.group(1))
                text = re.sub(r'^(剧情简介|内容简介|影片简介|简介|剧情)\s*[：:]\s*', '', text)
                if len(text) >= 10:
                    return text

        for kw in ('剧情简介', '内容简介', '影片简介', '剧情介绍', '简介'):
            idx = html.find(kw)
            if idx < 0:
                continue
            seg = html[idx: idx + 5000]
            end_m = re.search(r'</(?:div|p|section|article)>', seg)
            if end_m:
                seg = seg[:end_m.start()]
            text = _strip_html(seg)
            text = re.sub(r'^(剧情简介|内容简介|影片简介|剧情介绍|简介)\s*[：:]*\s*', '', text)
            if len(text) >= 10:
                return text

        for pat in (
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
            r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']',
        ):
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                text = _strip_html(m.group(1))
                if len(text) >= 10:
                    return text

        plain = _strip_html(html)
        m = re.search(r'(?:剧情简介|简介|剧情介绍)\s*[：:]\s*(.{20,500})', plain)
        if m:
            return m.group(1).strip()

        return ""

    # ==================== 字段提取 ====================
    def _extract_field(self, html, *labels):
        for label in labels:
            m = re.search(
                rf'{label}\s*[：:]\s*(?:</?[^>]+>\s*)*((?:<a[^>]*>[^<]*</a>\s*[/、,，]?\s*)+)',
                html, re.IGNORECASE
            )
            if m:
                names = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
                if names:
                    return ' / '.join(n.strip() for n in names if n.strip())
            m = re.search(rf'{label}\s*[：:]\s*(?:</?[^>]+>\s*)*([^<\n]{{1,80}})', html)
            if m:
                v = _strip_html(m.group(1))
                if v:
                    return v
        return ""

    # ==================== 详情页 ====================
    def detailContent(self, array):
        try:
            vid = array[0] if isinstance(array, (list, tuple)) else array
            url = BASE_URL + '/video/' + str(vid) + '.html'
            rsp = self.fetch(url, headers=self.header)
            html = rsp.text

            # 标题
            title = ""
            t_m = re.search(
                r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>([\s\S]*?)</h1>',
                html, re.DOTALL | re.IGNORECASE
            )
            if not t_m:
                t_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.DOTALL)
            if t_m:
                title = _strip_html(t_m.group(1))
            if not title:
                t_m = re.search(r'<title>([^<]+)</title>', html)
                if t_m:
                    title = t_m.group(1).strip().split('-')[0].split('_')[0].strip()

            # 封面
            pic = ""
            cover_img_m = re.search(
                r'<img[^>]*class="[^"]*detail-(?:poster|cover)[^"]*"[^>]*>',
                html, re.IGNORECASE
            )
            if cover_img_m:
                pic = _pick_img(cover_img_m.group(0))
            if not pic:
                p_m = re.search(
                    r'class="[^"]*detail-hero-bg[^"]*"[^>]*style="[^"]*url\(([^)]+)\)',
                    html, re.IGNORECASE
                )
                if p_m:
                    pic = _abs_url(p_m.group(1).strip().strip('\'"'))
            if not pic:
                p_m = re.search(
                    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']',
                    html, re.IGNORECASE
                )
                if p_m:
                    pic = _abs_url(p_m.group(1).strip().strip('\'"'))

            # 年份
            year = ""
            y_m = re.search(
                r'class="[^"]*(?:detail-year|year)[^"]*"[^>]*>([^<]+)<',
                html, re.IGNORECASE
            )
            if y_m:
                year = _strip_html(y_m.group(1)).strip('()（）')
            if not year:
                y_m = re.search(r'(\d{4})\s*年', html)
                if y_m:
                    year = y_m.group(1)

            # 地区 / 类型
            area = self._extract_field(html, '地区', '国家', '制片国家')
            if not area:
                a_m = re.search(r'class="[^"]*detail-area[^"]*"[^>]*>([^<]+)<', html)
                if a_m:
                    area = _strip_html(a_m.group(1))

            vod_type = self._extract_field(html, '类型', '分类', '影片类型')
            if not vod_type:
                for cat in CATEGORY_MAP.keys():
                    if cat in html:
                        vod_type = cat
                        break

            # 导演 / 主演
            director = self._extract_field(html, '导演', '導演')
            actor = self._extract_field(html, '主演', '演员', '演員')

            # 简介
            desc = self._extract_desc(html)

            # 状态
            remark = self._extract_field(html, '状态', '备注', '更新')
            if not remark:
                r_m = re.search(
                    r'class="[^"]*(?:card-status|detail-status|remarks)[^"]*"[^>]*>([^<]+)<',
                    html
                )
                if r_m:
                    remark = _strip_html(r_m.group(1))

            # 评分
            score = ""
            s_m = re.search(
                r'class="[^"]*(?:score|rating)[^"]*"[^>]*>([\d.]+)',
                html, re.IGNORECASE
            )
            if s_m:
                score = s_m.group(1).strip()

            # 播放列表
            play_from, play_url = self._parse_playlist(html)

            if not remark and play_url and play_url[0]:
                first_ep = play_url[0].split('#')[0].split('$')[0]
                if first_ep and len(first_ep) <= 20:
                    remark = first_ep

            if not play_from:
                play_from = ["默认线路"]
                play_url = [""]

            vod = {
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_year": year,
                "vod_area": area,
                "vod_type": vod_type,
                "vod_actor": actor,
                "vod_director": director,
                "vod_remarks": remark,
                "vod_score": score,
                "vod_content": desc,
                "vod_play_from": '$$$'.join(play_from),
                "vod_play_url": '$$$'.join(play_url),
            }
            return {'list': [vod]}
        except Exception as e:
            print("详情解析出错:", e)
            return {'list': []}

    # ==================== 播放列表解析 ====================
    def _parse_playlist(self, html):
        play_from, play_url = [], []

        tabs = []
        for m in re.finditer(
            r'<div[^>]*class="[^"]*source-tab[^"]*"[^>]*>([\s\S]*?)</div>',
            html, re.DOTALL | re.IGNORECASE
        ):
            tag = m.group(0)
            name = ""
            n_m = re.search(r'class="[^"]*tab-name[^"]*"[^>]*>([\s\S]*?)</', tag)
            if n_m:
                name = _strip_html(n_m.group(1))
            if not name:
                name = _strip_html(m.group(1))
            target = ""
            for attr in ('data-target', 'data-id', 'data-tab', 'id'):
                a_m = re.search(rf'{attr}\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if a_m:
                    target = a_m.group(1)
                    break
            if target or name:
                tabs.append((target, name))

        blocks = {}
        for m in re.finditer(
            r'<div[^>]*class="[^"]*ep-square-list[^"]*"[^>]*id\s*=\s*["\']([^"\']+)["\'][^>]*>([\s\S]*?)'
            r'(?=<div[^>]*class="[^"]*ep-square-list|<div[^>]*class="[^"]*source-tab|</body>|$)',
            html, re.DOTALL | re.IGNORECASE
        ):
            blocks[m.group(1)] = m.group(2)

        used_names = set()
        for target, name in tabs:
            block = blocks.get(target, "")
            if not block:
                m = re.search(
                    rf'id\s*=\s*["\']{re.escape(target)}["\'][^>]*>([\s\S]*?)</div>',
                    html, re.DOTALL
                )
                block = m.group(1) if m else ""
            if not block:
                continue

            eps = self._extract_episodes(block)
            if not eps:
                continue

            line_name = name or ("线路%d" % (len(play_from) + 1))
            if line_name in used_names:
                idx = 2
                while ("%s-%d" % (line_name, idx)) in used_names:
                    idx += 1
                line_name = "%s-%d" % (line_name, idx)
            used_names.add(line_name)

            play_from.append(line_name)
            play_url.append('#'.join(eps))

        if not play_from:
            eps = self._extract_episodes(html)
            if eps:
                play_from.append("默认线路")
                play_url.append('#'.join(eps))

        return play_from, play_url

    def _extract_episodes(self, block):
        eps = []
        seen = set()

        for m in re.finditer(
            r'<a\b([^>]*?)href\s*=\s*["\']([^"\']*?/play/[^"\']+\.html)["\']([^>]*)>([\s\S]*?)</a>',
            block, re.DOTALL | re.IGNORECASE
        ):
            attrs = (m.group(1) or '') + (m.group(3) or '')
            href = m.group(2).strip()
            inner = m.group(4) or ''

            if href in seen:
                continue
            seen.add(href)

            name = ""
            d_m = re.search(r'data-name\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
            if d_m:
                name = d_m.group(1).strip()
            if not name:
                name = _strip_html(inner)
            if not name or name in ('全集', '播放', '立即播放', '详情'):
                continue

            if href.startswith('http'):
                href = href.replace(BASE_URL, '')
            if not href.startswith('/'):
                href = '/' + href

            eps.append(name + '$' + href)

        return eps

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        try:
            try:
                p = int(pg)
            except Exception:
                p = 1

            if p > 1:
                url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (BASE_URL, p, quote(key))
            else:
                url = "%s/index.php/vod/search/wd/%s.html" % (BASE_URL, quote(key))

            rsp = self.fetch(url, headers=self.header)
            html = rsp.text

            videos = self._parse_search_results(html)
            if not videos:
                videos = self._parse_video_cards(html)
            if not videos:
                seen = set()
                for m in re.finditer(
                    r'<a\b[^>]*href\s*=\s*["\']/video/([^"\']+)\.html["\'][^>]*title\s*=\s*["\']([^"\']*)["\'][^>]*>',
                    html, re.IGNORECASE
                ):
                    vid, title = m.group(1), m.group(2).strip()
                    if vid in seen or not title:
                        continue
                    seen.add(vid)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": "",
                        "vod_remarks": ""
                    })

            return {'list': videos}
        except Exception as e:
            print("搜索出错:", e)
            return {'list': []}

    # ==================== 播放解析 ====================
    def playerContent(self, flag, id, vipFlags):
        play_url = ""
        try:
            if id.startswith('http') and any(ext in id.lower() for ext in VIDEO_EXTS):
                return {
                    "parse": 0,
                    "url": id,
                    "header": {"User-Agent": USER_AGENT, "Referer": BASE_URL + "/"},
                }

            if id.startswith('/'):
                play_url = BASE_URL + id
            elif id.startswith('http'):
                play_url = id
            else:
                play_url = BASE_URL + '/play/' + id + '.html'

            cached = self._play_cache.get(play_url)
            if cached:
                return {
                    "parse": 0,
                    "url": cached,
                    "header": {"User-Agent": USER_AGENT, "Referer": play_url},
                }

            rsp = self.fetch(play_url, headers=self.header)
            html = rsp.text

            config_match = re.search(
                r'MAC_PLAY_CONFIG\s*=\s*(\{[\s\S]*?\})\s*;', html
            )
            if not config_match:
                return {"parse": 1, "url": play_url}

            config_str = config_match.group(1)
            baseKey = self._extract_js_str(config_str, 'baseKey')
            requestUrl = self._extract_js_str(config_str, 'requestUrl')

            if not baseKey or not requestUrl:
                return {"parse": 1, "url": play_url}

            video_url = self._decrypt_player_api(baseKey, requestUrl, play_url)
            if video_url and video_url.startswith('http'):
                self._play_cache.set(play_url, video_url)
                return {
                    "parse": 0,
                    "url": video_url,
                    "header": {"User-Agent": USER_AGENT, "Referer": play_url},
                }

            return {"parse": 1, "url": play_url}

        except Exception as e:
            print("播放解析出错:", e)
            if play_url:
                return {"parse": 1, "url": play_url}
            return {"parse": 1, "url": id}

    def _extract_js_str(self, js_obj, key):
        pattern = rf'{key}\s*:\s*["\']([^"\']+)["\']'
        match = re.search(pattern, js_obj)
        return match.group(1) if match else ""

    def _decrypt_player_api(self, baseKey, requestUrl, referer):
        try:
            timestamp = str(int(time.time()))
            token = hashlib.md5(
                (baseKey + timestamp + USER_AGENT).encode()
            ).hexdigest()

            api_url = BASE_URL + '/player_api.php'
            post_data = "url=%s&timestamp=%s&token=%s" % (
                quote(requestUrl, safe=''), timestamp, token
            )

            headers = {
                "User-Agent": USER_AGENT,
                "Referer": referer,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            }

            resp_text = self._post(api_url, post_data, headers)
            if not resp_text:
                return None

            resp_text = resp_text.strip()
            if not resp_text.startswith('{'):
                j_m = re.search(r'(\{[\s\S]*\})', resp_text)
                if j_m:
                    resp_text = j_m.group(1)

            result = json.loads(resp_text)
            if 'error' in result or 'data' not in result:
                return None

            encrypted = result['data']
            reversed_str = encrypted[::-1]
            pad = len(reversed_str) % 4
            if pad:
                reversed_str += '=' * (4 - pad)

            decoded_bytes = base64.b64decode(reversed_str)
            try:
                decoded_str = decoded_bytes.decode('utf-8')
            except Exception:
                decoded_str = decoded_bytes.decode('latin1')
                try:
                    decoded_str = decoded_str.encode('latin1').decode('utf-8', errors='replace')
                except Exception:
                    pass

            video_data = json.loads(decoded_str)
            jmurl = video_data.get('jmurl', '') or video_data.get('url', '')
            return jmurl if jmurl and jmurl.startswith('http') else None

        except Exception as e:
            print("播放API解密出错:", e)
            return None

    # ==================== 配置 ====================
    config = {"player": {}, "filter": {}}

    def _init_config_filters(self):
        if not self.config.get('filter'):
            self.config['filter'] = self._build_filters()


# ==================== TVBox 标准入口 ====================
def get_spider():
    spider = Spider()
    try:
        spider._init_config_filters()
    except Exception:
        pass
    return spider
