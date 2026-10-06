# coding=utf-8
"""
云途影视 gw7.cc | 海螺模板 (conch) | 苹果CMS v10
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

# 简介前缀（片方广告提醒）
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 一级分类（真实确认：从首页导航和详情页筛选链接）
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "连续剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "20", "type_name": "AI漫剧"},
]

# 二级分类（class 参数用中文，海螺模板通用）
_CLASS_FILTERS = {
    "1": [  # 电影
        {"n": "全部", "v": ""},
        {"n": "动作", "v": "动作"}, {"n": "喜剧", "v": "喜剧"},
        {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
        {"n": "恐怖", "v": "恐怖"}, {"n": "剧情", "v": "剧情"},
        {"n": "战争", "v": "战争"}, {"n": "动画", "v": "动画"},
        {"n": "奇幻", "v": "奇幻"}, {"n": "冒险", "v": "冒险"},
        {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"},
        {"n": "犯罪", "v": "犯罪"}, {"n": "古装", "v": "古装"},
        {"n": "历史", "v": "历史"}, {"n": "运动", "v": "运动"},
        {"n": "经典", "v": "经典"}, {"n": "网络电影", "v": "网络电影"},
    ],
    "2": [  # 连续剧
        {"n": "全部", "v": ""},
        {"n": "国产", "v": "国产"}, {"n": "港台", "v": "港台"},
        {"n": "日韩", "v": "日韩"}, {"n": "欧美", "v": "欧美"},
        {"n": "海外", "v": "海外"},
        {"n": "古装", "v": "古装"}, {"n": "战争", "v": "战争"},
        {"n": "青春", "v": "青春"}, {"n": "喜剧", "v": "喜剧"},
        {"n": "家庭", "v": "家庭"}, {"n": "犯罪", "v": "犯罪"},
        {"n": "动作", "v": "动作"}, {"n": "奇幻", "v": "奇幻"},
        {"n": "悬疑", "v": "悬疑"}, {"n": "都市", "v": "都市"},
        {"n": "短剧", "v": "短剧"},
    ],
    "3": [  # 综艺
        {"n": "全部", "v": ""},
        {"n": "真人秀", "v": "真人秀"}, {"n": "脱口秀", "v": "脱口秀"},
        {"n": "音乐", "v": "音乐"}, {"n": "竞技", "v": "竞技"},
        {"n": "访谈", "v": "访谈"}, {"n": "情感", "v": "情感"},
        {"n": "生活", "v": "生活"},
    ],
    "4": [  # 动漫
        {"n": "全部", "v": ""},
        {"n": "热血", "v": "热血"}, {"n": "冒险", "v": "冒险"},
        {"n": "奇幻", "v": "奇幻"}, {"n": "科幻", "v": "科幻"},
        {"n": "校园", "v": "校园"}, {"n": "恋爱", "v": "恋爱"},
        {"n": "搞笑", "v": "搞笑"}, {"n": "战斗", "v": "战斗"},
        {"n": "日常", "v": "日常"},
    ],
    "20": [  # AI漫剧
        {"n": "全部", "v": ""},
        {"n": "短剧", "v": "短剧"},
    ],
}

_AREAS = [
    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "美国", "v": "美国"}, {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"},
]
_LANGS = [
    {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
    {"n": "粤语", "v": "粤语"}, {"n": "英语", "v": "英语"},
    {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"},
    {"n": "泰语", "v": "泰语"},
]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": _CLASS_FILTERS.get(tid, [{"n": "全部", "v": ""}])},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]


# ======================== 预编译正则 ========================
_RE_CARD_LOOSE = re.compile(
    r'<a[^>]*?href="/index\.php/vod/detail/id/(\d+)\.html"[^>]*?>', re.I)
_RE_TITLE_ATTR = re.compile(r'title="([^"]{1,120})"')
_RE_DATA_ORIGINAL = re.compile(r'data-original="([^"]+)"')
_RE_SRC = re.compile(r'src="([^"]+)"')
_RE_PIC_TEXT = re.compile(
    r'<span[^>]*class="[^"]*pic_text[^"]*"[^>]*>\s*([^<]{1,20})\s*</span>')

_RE_TAB_BLOCK = re.compile(
    r'<div[^>]*class="[^"]*play_source_tab[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.I)
_RE_TAB_ITEM = re.compile(r'<a[^>]*alt="([^"]+)"', re.I)

_RE_PLAY_BOX = re.compile(
    r'<div[^>]*class="[^"]*play_list_box[^"]*"[^>]*>(.*?)(?='
    r'<div[^>]*class="[^"]*play_list_box|</div>\s*</div>\s*</div>|\Z)',
    re.DOTALL | re.I)
_RE_PLAY_LINK = re.compile(
    r'<a[^>]*href="(/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"'
    r'[^>]*>([^<]+)</a>', re.I)

_RE_H2_TITLE = re.compile(
    r'<h2[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>([\s\S]*?)</h2>', re.I)
_RE_THUMB_IN_DETAIL = re.compile(
    r'<div[^>]*class="[^"]*content_thumb[^"]*"[^>]*>[\s\S]*?'
    r'<a[^>]*?data-original="([^"]+)"', re.I)

_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)
_RE_M3U8 = re.compile(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', re.I)
_RE_MP4 = re.compile(r'https?://[^\s"\'<>\\]+\.mp4[^\s"\'<>\\]*', re.I)

# 简介：优先完整版 full_text，再简版 context
_INTRO_PATTERNS = [
    r'<div[^>]*class="[^"]*content_desc\s+full_text[^"]*"[^>]*>'
    r'[\s\S]*?<span[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*content_desc\s+context[^"]*"[^>]*>'
    r'[\s\S]*?<span[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*sketch[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([\s\S]*?)</div>',
    r'<div[^>]*class="[^"]*content_desc[^"]*"[^>]*>[\s\S]*?<span[^>]*>([\s\S]*?)</span>',
    r'<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)</div>',
]


class Spider(Spider):

    def getName(self):
        return "云途影视"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._home_cache = []
        self._home_cache_time = 0
        self._play_cache = {}

    # ---------- 网络 ----------
    def _fetch(self, url, timeout=15):
        try:
            try:
                rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            except TypeError:
                rsp = self.fetch(url, headers=self.headers)
            if hasattr(rsp, 'text'):
                return rsp.text
            if hasattr(rsp, 'content'):
                return rsp.content.decode('utf-8', 'ignore')
            return str(rsp)
        except Exception as e:
            try:
                self.log("fetch fail: %s - %s" % (url, e))
            except Exception:
                pass
            return ""

    # ---------- 工具 ----------
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

        for m in _RE_CARD_LOOSE.finditer(html):
            tag = m.group(0)
            vid = m.group(1)
            if vid in seen:
                continue

            tm = _RE_TITLE_ATTR.search(tag)
            if not tm:
                continue
            title = tm.group(1).strip()
            if not title:
                continue

            pic = ""
            dm = _RE_DATA_ORIGINAL.search(tag)
            if dm:
                pic = dm.group(1).strip()
            else:
                sm = _RE_SRC.search(tag)
                if sm:
                    pic = sm.group(1).strip()

            # 备注：紧跟在 <a> 后面的 pic_text
            tail = html[m.end():m.end() + 300]
            rm = _RE_PIC_TEXT.search(tail)
            remark = rm.group(1).strip() if rm else ""

            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark or "HD",
            })
        return videos

    def _get_pagecount(self, html):
        if not html:
            return 1
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            return int(m.group(1))
        return 1

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 600:
            return {"list": self._home_cache}
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html) if html else []
        self._home_cache = videos
        self._home_cache_time = now
        return {"list": videos}

    # ---------- 分类 ----------
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

        paths = ["id/%s" % tid]
        if extend.get("class"):
            paths.append("class/%s" % urllib.parse.quote(extend['class']))
        if extend.get("area"):
            paths.append("area/%s" % urllib.parse.quote(extend['area']))
        if extend.get("lang"):
            paths.append("lang/%s" % urllib.parse.quote(extend['lang']))
        if extend.get("year"):
            paths.append("year/%s" % extend['year'])
        by = extend.get("by", "")
        if by and by != "time":
            paths.append("by/%s" % by)

        has_filter = len(paths) > 1
        path_type = "show" if has_filter else "type"

        if page == 1:
            url = "%s/index.php/vod/%s/%s.html" % (
                self.site_url, path_type, "/".join(paths))
        else:
            url = "%s/index.php/vod/%s/%s/page/%d.html" % (
                self.site_url, path_type, "/".join(paths), page)

        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html) if html else 1
        if pagecount < page:
            pagecount = page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        # 表单 action="/index.php/vod/search.html" 是 GET
        url = "%s/index.php/vod/search.html?wd=%s" % (self.site_url, keyword)
        if page > 1:
            url += "&page=%d" % page
        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html) if html else 1
        if pagecount < page:
            pagecount = page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 48,
            "total": pagecount * 48,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 简介提取 ----------
    def _extract_content(self, html):
        if not html:
            return ""

        def _clean_text(s):
            t = self._clean(s)
            t = re.sub(r'^(?:剧情介绍|内容介绍|故事简介|简介|详情|剧情)\s*[:：]?\s*',
                       '', t)
            t = re.sub(r'\s*(?:详情请|请收藏|本网站|更多精彩).*$', '', t)
            return t.strip()

        for pat in _INTRO_PATTERNS:
            try:
                m = re.search(pat, html, re.S | re.I)
            except Exception:
                continue
            if not m:
                continue
            raw = m.group(1) if m.groups() else m.group(0)
            txt = _clean_text(raw)
            if txt and len(txt) >= 15:
                return txt[:1500]

        # meta description 兜底
        m = _RE_META_DESC.search(html)
        if m:
            raw = self._clean(m.group(1))
            raw = re.sub(r'^.*?剧情\s*[:：]\s*', '', raw)
            raw = re.sub(r'^.*?剧情介绍\s*[:：]\s*', '', raw)
            raw = re.sub(r'^高清资源在线播放\s*', '', raw)
            if raw and len(raw) >= 15:
                return raw[:1500]

        return ""

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        url = "%s/index.php/vod/detail/id/%s.html" % (self.site_url, vid)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题（h2.title）
        name = vid
        tm = _RE_H2_TITLE.search(html)
        if tm:
            t = self._clean(tm.group(1))
            if t:
                name = t

        # 封面
        pic = self.default_pic
        pm = _RE_THUMB_IN_DETAIL.search(html)
        if pm:
            pic = self._fix_url(pm.group(1))

        # 简介（添加前缀）
        content = self._extract_content(html)
        if content:
            content = INTRO_PREFIX + content

        # 元信息：遍历每个 <li class="data">
        director = ""
        actor = ""
        type_name = ""
        area = ""
        lang = ""
        year = ""
        remarks = ""

        for m in re.finditer(
                r'<li[^>]*class="[^"]*\bdata\b[^"]*"[^>]*>([\s\S]*?)</li>',
                html):
            text = self._clean(m.group(1))

            if not year:
                ym = re.search(r'年份\s*[：:]\s*(\d{4})', text)
                if ym:
                    year = ym.group(1)

            if not area:
                am = re.search(r'地区\s*[：:]\s*([^\s]+)', text)
                if am:
                    area = am.group(1)

            if not type_name:
                tpm = re.search(r'类型\s*[：:]\s*([^\s]+)', text)
                if tpm:
                    type_name = tpm.group(1)

            if not lang:
                lm = re.search(r'语言\s*[：:]\s*([^\s]+)', text)
                if lm:
                    lang = lm.group(1)

            if not remarks:
                sm = re.search(r'状态\s*[：:]\s*([^\s/]+)', text)
                if sm:
                    remarks = sm.group(1).strip()

            if not actor:
                am = re.search(r'主演\s*[：:]\s*(.+?)$', text)
                if am:
                    actor = re.sub(r'\s+', ' ', am.group(1)).strip()

            if not director:
                dm = re.search(r'导演\s*[：:]\s*(.+?)$', text)
                if dm:
                    director = re.sub(r'\s+', ' ', dm.group(1)).strip()

        # ===== 播放列表：按 tab 顺序 + play_list_box 一一对应 =====
        # 1) tab 名字（按 HTML 出现顺序）
        tab_names = []
        tb = _RE_TAB_BLOCK.search(html)
        if tb:
            for tm2 in _RE_TAB_ITEM.finditer(tb.group(1)):
                nm = tm2.group(1).strip()
                if nm:
                    tab_names.append(nm)

        # 2) play_list_box（按 HTML 出现顺序，与 tab 一一对应）
        play_from = []
        play_url = []
        boxes = _RE_PLAY_BOX.findall(html)

        for idx, box in enumerate(boxes):
            links = _RE_PLAY_LINK.findall(box)
            if not links:
                continue
            source_name = (tab_names[idx] if idx < len(tab_names)
                           else "线路%d" % (idx + 1))

            seen_eps = set()
            ep_list = []
            for href, pvid, sid, nid, ep_name in links:
                ep_clean = self._clean(ep_name) or ("第%s集" % nid)
                key = "%s$%s" % (ep_clean, href)
                if key in seen_eps:
                    continue
                seen_eps.add(key)
                ep_list.append(key)

            if ep_list:
                play_from.append(source_name)
                play_url.append("#".join(ep_list))

        # 3) 兜底：全局抓一次
        if not play_url:
            all_links = _RE_PLAY_LINK.findall(html)
            if all_links:
                ep_list = []
                seen = set()
                for href, pvid, sid, nid, ep_name in all_links:
                    ep_clean = self._clean(ep_name) or ("第%s集" % nid)
                    key = "%s$%s" % (ep_clean, href)
                    if key in seen:
                        continue
                    seen.add(key)
                    ep_list.append(key)
                if ep_list:
                    play_from = ["默认线路"]
                    play_url = ["#".join(ep_list)]

        if not play_url:
            return {"list": []}

        return {"list": [{
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
            "vod_remarks": remarks or "HD",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_path = str(id)
        if "$" in play_path:
            play_path = play_path.split("$")[-1]

        now = int(time.time())
        cache_key = play_path
        if cache_key in self._play_cache:
            ts, cached = self._play_cache[cache_key]
            if now - ts < 900:
                return cached

        # 已是直链
        if play_path.startswith("http") and (
                '.m3u8' in play_path.lower() or '.mp4' in play_path.lower()):
            res = {
                "parse": 0,
                "url": play_path,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[cache_key] = (now, res)
            return res

        url = (play_path if play_path.startswith("http")
               else (self.site_url + play_path if play_path.startswith("/")
                     else "%s/%s" % (self.site_url, play_path)))

        html = self._fetch(url)
        if html:
            m3u8 = self._extract_player_url(html)
            if m3u8:
                res = {
                    "parse": 0,
                    "url": m3u8,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                }
                self._play_cache[cache_key] = (now, res)
                return res

        res = {"parse": 1, "url": url, "header": self.headers}
        self._play_cache[cache_key] = (now, res)
        return res

    def _extract_player_url(self, html):
        # 找 var player_xxx = {...}
        for m in re.finditer(
                r'(?<![A-Za-z0-9_])player_[A-Za-z0-9_]+\s*=\s*\{', html):
            brace = html.find('{', m.start())
            if brace < 0:
                continue
            raw = self._slice_json(html, brace)
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            u = (obj.get('url') or '').replace('\\/', '/')
            if u.startswith('//'):
                u = 'https:' + u
            if u and ('.m3u8' in u.lower() or '.mp4' in u.lower()):
                enc = obj.get('encrypt', 0)
                try:
                    enc = int(enc)
                except Exception:
                    enc = 0
                if enc == 1:
                    u = urllib.parse.unquote(u)
                elif enc == 2:
                    try:
                        u = base64.b64decode(u).decode('utf-8', 'ignore')
                    except Exception:
                        pass
                return u

        m = _RE_M3U8.search(html)
        if m:
            return m.group(0).replace('\\/', '/')
        m = _RE_MP4.search(html)
        if m:
            return m.group(0).replace('\\/', '/')
        return ""

    def _slice_json(self, text, start):
        """花括号配平，从 text[start]=='{' 起精确截取 JSON"""
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

    # ---------- 代理 ----------
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

            ref = self.site_url + "/"
            if "://" in url:
                try:
                    scheme = url.split("://")[0]
                    host = url.split("://")[1].split("/")[0]
                    ref = scheme + "://" + host + "/"
                except Exception:
                    pass

            try:
                rsp = self.fetch(url, headers={
                    "User-Agent": UA,
                    "Referer": ref,
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

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or url.startswith('http')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
