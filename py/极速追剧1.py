# coding=utf-8
"""
极速追剧 jisuzhuiju.com TVBox Python 爬虫
遵循 TVBox base.spider.Spider 规范
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
    # 如果 TVBox 环境没有 base.spider，提供 fallback
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
            pass

    Spider = _BaseSpider

HOST = "https://jisuzhuiju.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://jisuzhuiju.com/img/favicon.png"

# 一级分类（从网站导航提取）
CLASSES = [
    {"type_id": "1", "type_name": "电视剧"},
    {"type_id": "2", "type_name": "电影"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
    {"type_id": "5", "type_name": "短剧"},
]

# 通用筛选数据
_AREAS = [
    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "美国", "v": "美国"}, {"n": "泰国", "v": "泰国"},
    {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
    {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"},
    {"n": "其他", "v": "其他"}
]

_YEARS = [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
    {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"},
    {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
    {"n": "2018", "v": "2018"}, {"n": "其他", "v": "-1"}
]

_SORTS = [
    {"n": "热度排序", "v": "hot"},
    {"n": "上映时间", "v": "time"},
    {"n": "评分排序", "v": "score"}
]

# 各频道类型筛选
_FILTER_TYPES = {
    "1": [  # 电视剧
        {"n": "全部", "v": ""},
        {"n": "剧情", "v": "7"}, {"n": "古装", "v": "9"},
        {"n": "爱情", "v": "12"}, {"n": "悬疑", "v": "14"},
        {"n": "都市", "v": "18"}, {"n": "犯罪", "v": "34"}
    ],
    "2": [  # 电影
        {"n": "全部", "v": ""},
        {"n": "动作", "v": "43"}, {"n": "喜剧", "v": "44"},
        {"n": "爱情", "v": "45"}, {"n": "科幻", "v": "46"},
        {"n": "恐怖", "v": "47"}, {"n": "剧情", "v": "48"},
        {"n": "战争", "v": "49"}, {"n": "犯罪", "v": "50"},
        {"n": "惊悚", "v": "51"}, {"n": "冒险", "v": "52"},
        {"n": "悬疑", "v": "53"}, {"n": "动画", "v": "54"},
        {"n": "武侠", "v": "55"}, {"n": "古装", "v": "56"},
        {"n": "历史", "v": "57"}, {"n": "传记", "v": "58"},
        {"n": "纪录片", "v": "59"}
    ],
    "3": [  # 动漫
        {"n": "全部", "v": ""},
        {"n": "热血", "v": "60"}, {"n": "恋爱", "v": "61"},
        {"n": "校园", "v": "62"}, {"n": "搞笑", "v": "63"},
        {"n": "机甲", "v": "64"}, {"n": "神魔", "v": "65"},
        {"n": "竞技", "v": "66"}, {"n": "冒险", "v": "67"},
        {"n": "治愈", "v": "68"}, {"n": "百合", "v": "69"},
        {"n": "萝莉", "v": "70"}, {"n": "后宫", "v": "71"},
        {"n": "励志", "v": "72"}, {"n": "泡面番", "v": "73"},
        {"n": "国产动漫", "v": "74"}, {"n": "日本动漫", "v": "75"},
        {"n": "欧美动漫", "v": "76"}
    ],
    "4": [  # 综艺
        {"n": "全部", "v": ""},
        {"n": "选秀", "v": "77"}, {"n": "情感", "v": "78"},
        {"n": "访谈", "v": "79"}, {"n": "播报", "v": "80"},
        {"n": "旅游", "v": "81"}, {"n": "音乐", "v": "82"},
        {"n": "美食", "v": "83"}, {"n": "纪实", "v": "84"},
        {"n": "曲艺", "v": "85"}, {"n": "游戏", "v": "86"},
        {"n": "亲子", "v": "87"}, {"n": "职场", "v": "88"},
        {"n": "脱口秀", "v": "89"}, {"n": "真人秀", "v": "90"},
        {"n": "晚会", "v": "91"}
    ],
    "5": [  # 短剧
        {"n": "全部", "v": ""}
    ]
}

# 最终拼装 FILTERS
FILTERS = {}
for channel_id in ["1", "2", "3", "4", "5"]:
    FILTERS[channel_id] = [
        {"key": "type", "name": "类型", "value": _FILTER_TYPES.get(channel_id, [{"n": "全部", "v": ""}])},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS}
    ]

# ======================== 正则预编译 ========================
# 首页/分类/搜索 卡片列表：匹配 <a href="/detail/xxx.html" ...> 块
_RE_CARD = re.compile(
    r'<a[^>]*href="(/detail/\d+\.html)"[^>]*>(.*?)</a>',
    re.S | re.I)

# 卡片内提取标题、图片、备注
_RE_TITLE = re.compile(r'<p[^>]*class="[^"]*vod-title[^"]*"[^>]*>(.*?)</p>', re.S | re.I)
_RE_PIC = re.compile(r'<img[^>]*src="([^"]+)"', re.I)
_RE_BADGE = re.compile(r'<span[^>]*class="[^"]*vod-badge[^"]*"[^>]*>(.*?)</span>', re.S | re.I)
_RE_SUB = re.compile(r'<p[^>]*class="[^"]*vod-subtitle[^"]*"[^>]*>(.*?)</p>', re.S | re.I)

# 详情页
_RE_DETAIL_TITLE = re.compile(r'<h1[^>]*class="detail-title"[^>]*>(.*?)</h1>', re.S | re.I)
_RE_DETAIL_PIC = re.compile(r'<div[^>]*class="detail-poster-wrapper"[^>]*>.*?<img[^>]*src="([^"]+)"', re.S | re.I)
_RE_SYNOPSIS = re.compile(r'<div[^>]*class="synopsis-content"[^>]*>(.*?)</div>', re.S | re.I)
_RE_META_ITEM = re.compile(r'<div[^>]*class="meta-item"[^>]*>.*?<span[^>]*class="meta-label"[^>]*>(.*?)</span>.*?<span[^>]*class="meta-value"[^>]*>(.*?)</span>', re.S | re.I)

# 播放线路面板
_RE_SOURCE_TAB = re.compile(r'<button[^>]*class="source-tab[^"]*"[^>]*data-target="([^"]+)"[^>]*>(.*?)</button>', re.S | re.I)
_RE_SOURCE_PANEL = re.compile(r'<div[^>]*class="source-panel"[^>]*id="([^"]+)"[^>]*>(.*?)</div>\s*</div>\s*</div>', re.S | re.I)  # 注意可能不精确，需调整
# 更简单的面板抓取：直接找所有 source-panel 块，然后按 id 匹配
_RE_PANEL_BLOCK = re.compile(r'<div[^>]*class="source-panel"[^>]*id="([^"]+)"[^>]*>(.*?)(?=<div[^>]*class="source-panel"|</div>\s*</div>\s*</div>\s*</div>|\Z)', re.S | re.I)
_RE_EPISODE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*episode-btn[^"]*"[^>]*>(.*?)</a>', re.S | re.I)

# 搜索页分页
_RE_PAGECOUNT = re.compile(r'data-totalpages="(\d+)"', re.I)

# 播放解析 API
PLAY_API = HOST + "/api/play-url"

class Spider(Spider):

    def getName(self):
        return "极速追剧"

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
    def _fetch(self, url, timeout=15):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(rsp, 'text'):
                return rsp.text
            if hasattr(rsp, 'content'):
                return rsp.content.decode('utf-8', 'ignore')
            return str(rsp)
        except Exception as e:
            self.log("fetch fail: %s - %s" % (url, e))
            return ""

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

        for m in _RE_CARD.finditer(html):
            href = m.group(1)
            content = m.group(2)
            vid_m = re.search(r'/detail/(\d+)\.html', href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue

            tm = _RE_TITLE.search(content)
            title = self._clean(tm.group(1)) if tm else ""
            if not title:
                continue

            pm = _RE_PIC.search(content)
            pic = self._fix_url(pm.group(1)) if pm else self.default_pic

            bm = _RE_BADGE.search(content)
            remark = self._clean(bm.group(1)) if bm else ""
            if not remark:
                sm = _RE_SUB.search(content)
                remark = self._clean(sm.group(1)) if sm else "HD"

            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remark[:20],
            })
        return videos

    def _get_pagecount(self, html):
        if not html:
            return 1
        m = _RE_PAGECOUNT.search(html)
        if m:
            return int(m.group(1))
        # 兜底：从分页链接找最大页码
        pages = re.findall(r'page=(\d+)', html)
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
        html = self._fetch(self.site_url + "/")
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

        params = {
            "channel": tid,
            "type": extend.get("type", ""),
            "area": extend.get("area", ""),
            "year": extend.get("year", ""),
            "sort": extend.get("sort", "hot"),
            "page": page,
        }
        url = self.site_url + "/filter?" + urllib.parse.urlencode(params)
        html = self._fetch(url)
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
        # 注意：实际搜索 URL 需根据网站确认，这里先用 /search?keyword=
        url = f"{self.site_url}/search?keyword={keyword}&page={page}"
        html = self._fetch(url)
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
        url = f"{self.site_url}/detail/{vid}.html"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = vid
        tm = _RE_DETAIL_TITLE.search(html)
        if tm:
            name = self._clean(tm.group(1))

        # 封面
        pic = self.default_pic
        pm = _RE_DETAIL_PIC.search(html)
        if pm:
            pic = self._fix_url(pm.group(1))

        # 简介（已加上前缀）
        content = ""
        cm = _RE_SYNOPSIS.search(html)
        if cm:
            content = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！" + self._clean(cm.group(1))

        # 元信息
        meta = {}
        for label, val in _RE_META_ITEM.findall(html):
            label = self._clean(label).rstrip("：")
            val = self._clean(val)
            if label and val:
                meta[label] = val

        # 播放线路
        play_from = []
        play_url = []

        # 提取所有线路 tab 名称和对应面板
        tabs = _RE_SOURCE_TAB.findall(html)
        panels = _RE_PANEL_BLOCK.findall(html)
        panel_dict = {pid: pcontent for pid, pcontent in panels}

        for target, tab_name in tabs:
            tab_name = self._clean(tab_name)
            panel_content = panel_dict.get(target, "")
            if not panel_content:
                continue

            eps = []
            for ep_href, ep_name in _RE_EPISODE.findall(panel_content):
                ep_name = self._clean(ep_name)
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append(f"{ep_name}${ep_href}")

            if eps:
                play_from.append(tab_name)
                play_url.append("#".join(eps))

        # 如果解析不到线路，返回空
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
            "vod_remarks": meta.get("备注", ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        # id 格式：/vodplay/6807-bfzym3u8-1.html
        m = re.search(r'/vodplay/(\d+)-([^/]+?)-(\d+)\.html', id)
        if not m:
            return {"parse": 1, "url": self._fix_url(id), "header": self.headers}

        vod_id, play_from, index = m.groups()
        params = {
            "vodId": vod_id,
            "playFrom": play_from,
            "index": index,
        }
        try:
            api_url = PLAY_API + "?" + urllib.parse.urlencode(params)
            headers = self.headers.copy()
            headers["X-Requested-With"] = "XMLHttpRequest"
            rsp = self.fetch(api_url, headers=headers, timeout=12)
            data = rsp.json()
            if data.get("code") == 200 and data.get("url"):
                real_url = data["url"]
                play_headers = data.get("headers", {})
                if not play_headers:
                    play_headers = {"User-Agent": UA, "Referer": self.site_url + "/"}
                # 返回字典，不要 JSON 字符串
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_url,
                    "header": play_headers,
                }
        except Exception as e:
            self.log("playerContent error: %s" % e)

        # 解析失败，返回播放页地址交给 TVBox 嗅探
        return {
            "parse": 1,
            "url": self._fix_url(id),
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
