# coding=utf-8
"""
片库 pianku.online TVBox Python 爬虫（多路解析兜底版）
站点：4k01.pianku.online
苹果CMS v10 模板 + 第三方 m3u8 解析
"""
import re
import sys
import json
import time
import base64
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
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
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
                print("[pianku]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

HOST = "https://4k01.pianku.online"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/load.gif"

CLASSES = [
    {"type_id": "20", "type_name": "电影"},
    {"type_id": "37", "type_name": "剧集"},
    {"type_id": "43", "type_name": "动漫"},
    {"type_id": "45", "type_name": "综艺"},
]

_FILTER_TYPES = {
    "20": [
        {"n": "全部", "v": ""},
        {"n": "动作片", "v": "21"}, {"n": "喜剧片", "v": "22"},
        {"n": "爱情片", "v": "23"}, {"n": "科幻片", "v": "24"},
        {"n": "恐怖片", "v": "25"}, {"n": "剧情片", "v": "26"},
        {"n": "战争片", "v": "27"}, {"n": "惊悚片", "v": "28"},
        {"n": "犯罪片", "v": "29"}, {"n": "冒险篇", "v": "30"},
        {"n": "动画片", "v": "31"}, {"n": "悬疑片", "v": "32"},
        {"n": "武侠片", "v": "33"}, {"n": "奇幻片", "v": "34"},
        {"n": "纪录片", "v": "35"}, {"n": "其他片", "v": "36"},
    ],
    "37": [
        {"n": "全部", "v": ""},
        {"n": "国产剧", "v": "38"}, {"n": "港台剧", "v": "39"},
        {"n": "欧美剧", "v": "40"}, {"n": "日韩剧", "v": "41"},
        {"n": "其他剧", "v": "42"},
    ],
    "43": [
        {"n": "全部", "v": ""},
        {"n": "动漫", "v": "44"},
    ],
    "45": [
        {"n": "全部", "v": ""},
    ]
}

_YEARS = [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
    {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
    {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
    {"n": "2018", "v": "2018"},
]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"}, {"n": "中国", "v": "中国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
    {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
]

_SORTS = [
    {"n": "最新", "v": "time"},
    {"n": "最热", "v": "hits"},
    {"n": "评分", "v": "score"},
]

FILTERS = {}
for tid in ["20", "37", "43", "45"]:
    FILTERS[tid] = [
        {"key": "class", "name": "分类", "value": _FILTER_TYPES.get(tid, [{"n": "全部", "v": ""}])},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]

# ==================== 正则预编译 ====================
_RE_LIST_ITEM = re.compile(
    r'<div class="vod-item">\s*<a[^>]*href="(/voddetail/(\d+)\.html)"[^>]*>(.*?)</a>\s*</div>',
    re.S | re.I)

_RE_PIC = re.compile(r'<img[^>]*src="([^"]+)"', re.I)
_RE_REMARKS = re.compile(r'<span class="remarks">([^<]*)</span>', re.I)
_RE_TITLE = re.compile(r'<h4 class="title">([^<]*)</h4>', re.I)
_RE_SUBTITLE = re.compile(r'<p class="subtitle">([^<]*)</p>', re.I)

_RE_DETAIL_TITLE = re.compile(r'<h1 class="detail-title">([^<]*)<span', re.S | re.I)
_RE_DETAIL_PIC = re.compile(r'<div class="detail-poster">\s*<img[^>]*src="([^"]+)"', re.S | re.I)
_RE_DETAIL_DESC = re.compile(r'<div class="detail-desc">.*?<p>(.*?)</p>', re.S | re.I)
_RE_DETAIL_META = re.compile(r'<div class="detail-meta">(.*?)</div>', re.S | re.I)
_RE_META_ITEM = re.compile(r'<span>([^：]+)：([^<]*)</span>', re.I)

_RE_SOURCE_TAB = re.compile(r'<span class="source-tab-item[^"]*"[^>]*data-target="([^"]+)"[^>]*>([^<]+)</span>', re.I)
_RE_SOURCE_PANE = re.compile(r'<div class="source-pane[^"]*" id="([^"]+)">(.*?)</div>\s*</div>', re.S | re.I)
_RE_PLAY_BTN = re.compile(r'<a href="([^"]+)" class="play-btn-item[^"]*"[^>]*>([^<]+)</a>', re.I)

_RE_PLAYER_AAAA = re.compile(r'var player_aaaa=(\{.*?\});', re.S | re.I)

# ==================== 多重 m3u8 提取正则 ====================
# 1. 直接抓 URL
_RE_M3U8_URL = re.compile(r'https?://[^\s"\'<>\\\u4e00-\u9fff]+\.m3u8[^\s"\'<>\\\u4e00-\u9fff]*', re.I)
# 2. JSON 里的 "url":"..."
_RE_JSON_URL = re.compile(r'"url"\s*:\s*"([^"]+)"', re.I)
# 3. JSON 里的 "data":"..." 或 "video":"..."
_RE_JSON_DATA = re.compile(r'"(?:data|video|play_url|playUrl|source|src)"\s*:\s*"([^"]+)"', re.I)
# 4. video/source 标签
_RE_VIDEO_TAG = re.compile(r'<(?:video|source)[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I)
# 5. script 里的 src = "xxx.m3u8"
_RE_JS_SRC = re.compile(r'\b(?:url|src|source|video)\s*[:=]\s*["\']([^"\']*?\.(?:m3u8|mp4)[^"\']*)["\']', re.I)

# ==================== 第三方解析接口（按优先级） ====================
# 每个 from_key 对应一个列表，依次尝试
_PARSE_PREFIXES = {
    "qq": [
        "https://wsyzy.top/m3u8/?url=",        # 备用线路：直接 m3u8
        "https://mujizybf.com/m3u8/?url=",     # 自营 4K
        "https://jimaoys99.com/parse?url=",    # 自营
        "https://tv.time1080.xyz/player/?url=",  # 腾讯官方
        "https://free.maccms.xyz/?url=",       # 无广告线路
    ],
    "qiyi": [
        "https://wsyzy.top/m3u8/?url=",
        "https://mujizybf.com/m3u8/?url=",
        "https://tv.time1080.xyz/player/?url=",
    ],
    "youku": [
        "https://wsyzy.top/m3u8/?url=",
        "https://mujizybf.com/m3u8/?url=",
        "https://tv.time1080.xyz/player/?url=",
    ],
    "mgtv": [
        "https://wsyzy.top/m3u8/?url=",
        "https://mujizybf.com/m3u8/?url=",
        "https://tv.time1080.xyz/player/?url=",
    ],
    "bilibili": [
        "https://wsyzy.top/m3u8/?url=",
        "https://tv.time1080.xyz/player/?url=",
    ],
}

# 通用兜底（未匹配到 from 时）
_FALLBACK_PREFIXES = [
    "https://wsyzy.top/m3u8/?url=",
    "https://mujizybf.com/m3u8/?url=",
    "https://jimaoys99.com/parse?url=",
    "https://tv.time1080.xyz/player/?url=",
    "https://free.maccms.xyz/?url=",
]

# 模拟浏览器 UA 池（部分接口对 UA 敏感）
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

class Spider(Spider):

    def getName(self):
        return "片库"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ---------- 网络请求 ----------
    def _fetch(self, url, timeout=15, headers=None, follow_redirects=True):
        try:
            req_headers = dict(self.headers)
            if headers:
                req_headers.update(headers)
            rsp = self.fetch(url, headers=req_headers, timeout=timeout)
            text = ""
            if hasattr(rsp, 'text'):
                text = rsp.text
            elif hasattr(rsp, 'content'):
                text = rsp.content.decode('utf-8', 'ignore')
            else:
                text = str(rsp)
            # 记录最终 URL（有些接口会 302 到真实 m3u8）
            final_url = ""
            try:
                final_url = rsp.url if hasattr(rsp, 'url') else url
            except Exception:
                final_url = url
            return text, final_url
        except Exception as e:
            self.log("fetch fail: %s - %s" % (url, e))
            return "", url

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

    # ---------- 列表解析 ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_LIST_ITEM.finditer(html):
            href, vid, content = m.groups()
            if vid in seen:
                continue

            tm = _RE_TITLE.search(content)
            title = self._clean(tm.group(1)) if tm else ""
            if not title:
                continue

            pm = _RE_PIC.search(content)
            pic = self._fix_url(pm.group(1)) if pm else self.default_pic

            rm = _RE_REMARKS.search(content)
            remarks = self._clean(rm.group(1)) if rm else ""

            sm = _RE_SUBTITLE.search(content)
            sub = self._clean(sm.group(1)) if sm else ""

            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks or sub[:20],
            })
        return videos

    def _get_pagecount(self, html):
        if not html:
            return 1
        m = re.search(r'href="[^"]*-(\d+)\.html"[^>]*>尾页</a>', html, re.I)
        if m:
            return int(m.group(1))
        pages = re.findall(r'/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html, _ = self._fetch(self.site_url + "/")
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

        class_tid = extend.get("class") or tid

        if page == 1:
            url = f"{self.site_url}/vodtype/{class_tid}.html"
        else:
            url = f"{self.site_url}/vodtype/{class_tid}-{page}.html"

        html, _ = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = f"{self.site_url}/vodsearch/-------------.html?wd={keyword}"
        if page > 1:
            url += f"&page={page}"
        html, _ = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = f"{self.site_url}/voddetail/{vid}.html"
        html, _ = self._fetch(url)
        if not html:
            return {"list": []}

        name = vid
        tm = _RE_DETAIL_TITLE.search(html)
        if tm:
            name = self._clean(tm.group(1))

        pic = self.default_pic
        pm = _RE_DETAIL_PIC.search(html)
        if pm:
            pic = self._fix_url(pm.group(1))

        content = ""
        cm = _RE_DETAIL_DESC.search(html)
        if cm:
            content = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！" + self._clean(cm.group(1))

        meta = {}
        for block in _RE_DETAIL_META.findall(html):
            for label, val in _RE_META_ITEM.findall(block):
                label = self._clean(label).strip()
                val = self._clean(val).strip()
                if label and val:
                    meta[label] = val

        play_from = []
        play_url = []

        tabs = _RE_SOURCE_TAB.findall(html)
        panes = _RE_SOURCE_PANE.findall(html)
        pane_dict = {pid: pcontent for pid, pcontent in panes}

        for target, tab_name in tabs:
            tab_name = self._clean(tab_name)
            pane_content = pane_dict.get(target, "")
            if not pane_content:
                continue

            eps = []
            for ep_href, ep_name in _RE_PLAY_BTN.findall(pane_content):
                ep_name = self._clean(ep_name)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append(f"{ep_name}${ep_href}")

            if eps:
                play_from.append(tab_name)
                play_url.append("#".join(eps))

        if not play_url:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": meta.get("主演", ""),
            "vod_director": meta.get("导演", ""),
            "vod_year": meta.get("年份", ""),
            "vod_area": meta.get("地区", ""),
            "vod_lang": meta.get("语言", ""),
            "vod_type": "",
            "vod_remarks": meta.get("状态", ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 核心：多路解析 m3u8 ----------
    def _extract_m3u8_from_response(self, html, final_url):
        """
        从响应中多重提取 m3u8/mp4 直链。
        返回找到的第一个可用地址，找不到返回空字符串。
        """
        if not html and not final_url:
            return ""

        # 如果响应本身就是 m3u8（Content-Type 为 mpegurl）
        if html and html.lstrip().startswith("#EXTM3U"):
            # 本身是 m3u8 内容，返回 final_url
            if final_url and ('.m3u8' in final_url.lower() or 'm3u8' in final_url.lower()):
                return final_url
            # 有些接口把 url 也放在响应里
            mm = _RE_M3U8_URL.search(html)
            if mm:
                return mm.group(0)
            # 无法从内容推断 URL，只能返回 final_url
            return final_url if final_url else ""

        # 依次尝试 5 种提取方式
        candidates = []

        # 1) 直接的 m3u8 URL
        candidates += _RE_M3U8_URL.findall(html or "")

        # 2) JSON url 字段
        for u in _RE_JSON_URL.findall(html or ""):
            if u and ('.m3u8' in u.lower() or '.mp4' in u.lower()):
                candidates.append(u)

        # 3) JSON data/video/source 字段
        for u in _RE_JSON_DATA.findall(html or ""):
            if u and ('.m3u8' in u.lower() or '.mp4' in u.lower()):
                candidates.append(u)

        # 4) video/source 标签
        for u in _RE_VIDEO_TAG.findall(html or ""):
            if u and ('.m3u8' in u.lower() or '.mp4' in u.lower() or u.startswith('http')):
                candidates.append(u)

        # 5) JS 里的 url/src/source
        for u in _RE_JS_SRC.findall(html or ""):
            if u:
                candidates.append(u)

        # 清洗并去重
        cleaned = []
        seen = set()
        for u in candidates:
            if not u:
                continue
            # unescape / unicode 转义处理
            u = u.replace('\\/', '/').replace('\\u002F', '/').replace('\\u0026', '&')
            u = u.rstrip('\\').rstrip('"').rstrip("'").strip()
            if not u:
                continue
            # 相对路径转绝对
            if u.startswith('//'):
                u = 'https:' + u
            if u.startswith('/'):
                u = self.site_url + u
            if not u.startswith('http'):
                continue
            if u in seen:
                continue
            seen.add(u)
            cleaned.append(u)

        # 优先返回 m3u8
        for u in cleaned:
            if '.m3u8' in u.lower():
                return u
        # 其次 mp4
        for u in cleaned:
            if '.mp4' in u.lower():
                return u
        # 最后任意
        return cleaned[0] if cleaned else ""

    def _try_parse_prefix(self, prefix, raw_url):
        """尝试一个解析接口，成功返回 m3u8 URL，失败返回空字符串"""
        encoded = urllib.parse.quote(raw_url, safe='')
        test_url = prefix + encoded
        try:
            # 用不同的 UA 试一次
            for ua in _UA_POOL[:2]:
                text, final_url = self._fetch(
                    test_url,
                    timeout=10,
                    headers={
                        "User-Agent": ua,
                        "Referer": self.site_url + "/",
                        "Accept": "*/*",
                    }
                )
                m3u8 = self._extract_m3u8_from_response(text, final_url)
                if m3u8:
                    self.log("resolve OK: %s -> %s" % (prefix, m3u8[:80]))
                    return m3u8
            self.log("resolve NO: %s" % prefix)
        except Exception as e:
            self.log("resolve ERR: %s - %s" % (prefix, e))
        return ""

    def _resolve_m3u8(self, from_key, raw_url):
        """多路尝试解析，返回 m3u8 直链"""
        prefixes = _PARSE_PREFIXES.get(from_key, []) or _FALLBACK_PREFIXES
        # 先去重、去空
        tried = set()
        for prefix in prefixes:
            if not prefix or prefix in tried:
                continue
            tried.add(prefix)
            m3u8 = self._try_parse_prefix(prefix, raw_url)
            if m3u8:
                return m3u8
        return ""

    def playerContent(self, flag, id, vipFlags):
        """
        四级兜底：
        A. url 本身是 m3u8/mp4 直链 → parse:0
        B. 服务端多路解析出 m3u8 → parse:0
        C. 播放页 HTML 里直接藏着 m3u8 → parse:0
        D. 全失败 → parse:1（先给 TVBox 一个解析页 URL 嗅探，再退到播放页 URL 嗅探）
        """
        if id.startswith("http"):
            play_url = id
        else:
            play_url = self._fix_url(id)

        html, _ = self._fetch(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}

        # 先看播放页里有没有直接藏 m3u8
        direct = self._extract_m3u8_from_response(html, "")
        if direct:
            self.log("direct m3u8 from page: %s" % direct[:80])
            return {
                "parse": 0,
                "playUrl": "",
                "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        m = _RE_PLAYER_AAAA.search(html)
        if not m:
            return {"parse": 1, "url": play_url, "header": self.headers}

        try:
            data = json.loads(m.group(1))
        except Exception as e:
            self.log("parse player_aaaa error: %s" % e)
            return {"parse": 1, "url": play_url, "header": self.headers}

        encrypt = str(data.get("encrypt", "0"))
        raw_url = data.get("url", "")
        from_key = data.get("from", "")

        # 解密
        if encrypt == "1":
            raw_url = urllib.parse.unquote(raw_url)
        elif encrypt == "2":
            try:
                raw_url = base64.b64decode(raw_url).decode('utf-8', 'ignore')
            except Exception:
                pass

        if not raw_url:
            return {"parse": 1, "url": play_url, "header": self.headers}

        # A. 已经是直链
        if any(ext in raw_url.lower() for ext in ['.m3u8', '.mp4']):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        # B. 多路服务端解析
        m3u8_url = self._resolve_m3u8(from_key, raw_url)
        if m3u8_url:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        # D. 全失败，让 TVBox 嗅探
        # 先尝试返回解析页 URL（TVBox 的 webview 里有完整的 JS 环境，能跑解析）
        prefixes = _PARSE_PREFIXES.get(from_key, []) or _FALLBACK_PREFIXES
        if prefixes:
            sniff_url = prefixes[0] + urllib.parse.quote(raw_url, safe='')
            return {
                "parse": 1,
                "playUrl": "",
                "url": sniff_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        return {
            "parse": 1,
            "url": play_url,
            "header": self.headers,
        }

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
            elif url.startswith("/"):
                url = self.site_url + url

            rsp = self.fetch(url, headers=self.headers, timeout=15)
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
        return '.m3u8' in url or '.mp4' in url or url.startswith('http')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
