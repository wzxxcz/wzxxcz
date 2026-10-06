# coding=utf-8
"""
豆花电影网 dhvideo.cc | TVBox Python 爬虫 (完整增强版)
结构: 自研播放器 + /api/m3u8 二次跳转 box.dyrs.com.de/api/super
策略: 列表/详情/搜索直抓，播放交给 TVBox 嗅探 (parse=1)

功能:
  ✅ 5 大频道分类 (电影/电视剧/综艺/动漫/短剧)
  ✅ 类型 + 地区 + 排序 + 年份 四维筛选
  ✅ 详情页提取 导演/演员/评分/热度排名/简介
  ✅ 10 条线路自动分组 + 优先级排序
  ✅ 播放页解析 window.xg_video_player_doc.aa.url
  ✅ /api/m3u8 302 跳转与 JSON 双向兼容
  ✅ 搜索分页 (page 从 0 开始)
  ✅ 列表页备注 (1080p/正片/更新至第X集)
  ✅ 首页返回数量动态化
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
                print("[douhua]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ============================================================
#  常量配置
# ============================================================
HOST = "https://dhvideo.cc"
SION_ID = "6ac4b6643b9fea31774d1157"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/douhua/douhua.me.png"

# 一级分类
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

# 排序方式
_SORTS = [
    {"n": "热度最高", "v": "play_hot"},
    {"n": "豆瓣评分", "v": "group_douban"},
]

# 年份
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 地区（从分类页提取完整列表）
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
    {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "泰国", "v": "泰国"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "澳大利亚", "v": "澳大利亚"},
    {"n": "比利时", "v": "比利时"}, {"n": "菲律宾", "v": "菲律宾"},
    {"n": "墨西哥", "v": "墨西哥"}, {"n": "丹麦", "v": "丹麦"},
    {"n": "波兰", "v": "波兰"}, {"n": "印度尼西亚", "v": "印度尼西亚"},
    {"n": "土耳其", "v": "土耳其"}, {"n": "巴西", "v": "巴西"},
]

# 各频道二级类型
_FILTERS_MOVIE = [
    "全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
    "悬疑", "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争",
    "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片",
]
_FILTERS_TV = [
    "全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
    "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
    "武侠", "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装",
]
_FILTERS_VARIETY = [
    "全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
    "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
    "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技",
    "爱情", "犯罪", "家庭", "历史",
]
_FILTERS_ANIME = [
    "全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
    "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
    "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园",
]
_FILTERS_SHORT = [
    "全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
    "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
    "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史",
    "动画", "战争",
]

_FILTER_MAP = {
    "dianying":  _FILTERS_MOVIE,
    "dianshiju": _FILTERS_TV,
    "zongyi":    _FILTERS_VARIETY,
    "dongman":   _FILTERS_ANIME,
    "duanju":    _FILTERS_SHORT,
}

# 组装 FILTERS
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTER_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ============================================================
#  正则
# ============================================================
# 列表卡片
_RE_CARD = re.compile(
    r'<a\s+href="(/(?:movie|tv)/[^"]+?)"[^>]*?>\s*'
    r'<img\s+[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)

# 列表备注（1080p / 正片 / 更新至第X集等）
_RE_REMARK = re.compile(
    r'<span class="bg-black/60[^>]*>\s*([^<]+?)\s*</span>', re.I)

# 详情页剧集按钮
_RE_EPISODE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*?data-origin="([^"]+)"[^>]*?data-title="([^"]+)"',
    re.S | re.I)

# 播放页 window.xg_video_player_doc.aa
_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)

# 详情页标题
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)

# 详情页封面
_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)

# 简介
_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)

# 详情页元信息
_RE_DIRECTOR = re.compile(
    r'<span class="text-\[#2e2e2e\] font-bold">导演</span>\s*'
    r'<span[^>]*>([^<]+)</span>', re.S)
_RE_ACTOR = re.compile(
    r'<span class="text-\[#2e2e2e\] font-bold">主演</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.S)
_RE_SCORE = re.compile(r'vk-badge">\s*([\d.]+)\s*</div>')
_RE_HOT = re.compile(r'([\d,]+)\s*\(电视剧排名:\s*(\d+),\s*总排名:\s*(\d+)\)')

# meta description 兜底
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)


# ============================================================
#  线路优先级
# ============================================================
_LINE_PRIORITY = [
    "vip", "1080zyk", "wztv", "bfzym3u8", "dyttm3u8",
    "ffm3u8", "lzm3u8", "modum3u8", "jsm3u8", "mtm3u8",
]

_LINE_ALIAS = {
    "vip": "VIP线路", "modum3u8": "魔都M3U8", "jsm3u8": "极速M3U8",
    "mtm3u8": "茅台M3U8", "1080zyk": "1080资源", "lzm3u8": "量子M3U8",
    "bfzym3u8": "暴风资源", "dyttm3u8": "电影天堂", "ffm3u8": "非凡M3U8",
    "wztv": "王者TV",
}


# ============================================================
#  Spider
# ============================================================
class Spider(Spider):

    def getName(self):
        return "豆花电影"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.sion_id  = self.extend.get("sion_id") or SION_ID
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init done: site=%s sid=%s" % (self.site_url, self.sion_id))

    # ---------------- 网络 ----------------
    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html):
        """从列表/搜索/首页 HTML 中提取影片卡片"""
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href, name, pic = m.group(1), m.group(2), m.group(3)
            href = href.replace("&amp;", "&")
            if not href or href in seen:
                continue

            name = self._clean(name)
            if not name:
                continue

            # 提取备注：在 <a ...> 标签之后的 300 字符内找
            tail = html[m.end():m.end() + 400]
            rm = _RE_REMARK.search(tail)
            remark = self._clean(rm.group(1)) if rm else ""

            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark[:30],
            })
        return videos

    def _page_count(self, html):
        """从分页链接中取最大页码 (page 从 0 开始)"""
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        """首页取所有卡片（动态返回，不截断）"""
        url = "%s/?sion_id=%s" % (self.site_url, self.sion_id)
        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        self.log("home videos: %d" % len(videos))
        # 去重后全部返回，TVBox 会自动分页展示
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

        # 参数清洗
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        # 该站 page 从 0 开始，所以 page-1
        params = {
            "page": page - 1,
            "sort_field": extend.get("sort_field") or "play_hot",
            "sion_id": self.sion_id,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]

        query = urllib.parse.urlencode(params)
        url = "%s/%s.html?%s" % (self.site_url, tid, query)

        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._page_count(html)
        self.log("category %s p%d -> %d videos url=%s" %
                 (tid, page, len(videos), url))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/s?name=%s&sion_id=%s&page=%d" % (
            self.site_url, keyword, self.sion_id, page - 1)
        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._page_count(html)
        self.log("search '%s' p%d -> %d videos" % (key, page, len(videos)))
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)

        html = self._fetch(url)
        if not html:
            self.log("detail empty: %s" % url)
            return {"list": []}

        # ---- 标题 ----
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # ---- 封面 ----
        pic = self.default_pic
        m = _RE_PIC_ID.search(html)
        if m:
            pic = self.site_url + m.group(0)

        # ---- 简介 ----
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = ("🍊小提示：本站资源抓取自豆花电影网，"
                       "请勿相信视频中的广告。\n" + content)

        # ---- 元信息 ----
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))
            actor = re.sub(r"\s*,\s*", ", ", actor)

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        hot_info = ""
        m = _RE_HOT.search(html)
        if m:
            hot_info = "热度 %s (剧集排名 %s, 总排名 %s)" % (
                m.group(1), m.group(2), m.group(3))

        # ---- 剧集 ----
        groups = {}  # origin -> [(name, href), ...]
        for m in _RE_EPISODE.finditer(html):
            href, origin, ep_name = m.group(1), m.group(2), m.group(3)
            href = href.replace("&amp;", "&")
            if href.startswith("/"):
                href = self.site_url + href
            groups.setdefault(origin, []).append((ep_name.strip(), href))

        if not groups:
            self.log("detail: no episodes")
            return {"list": []}

        # ---- 线路优先级排序 ----
        sorted_origins = sorted(
            groups.keys(),
            key=lambda x: (_LINE_PRIORITY.index(x)
                           if x in _LINE_PRIORITY else 999)
        )

        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            alias = _LINE_ALIAS.get(origin, origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        self.log("detail lines: %s  eps: %s" %
                 (play_from, [len(x.split("#")) for x in play_url]))

        # ---- 备注 ----
        remarks = ""
        if hot_info:
            remarks = hot_info
        elif len(groups) > 1:
            remarks = "%d条线路" % len(groups)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        """
        播放流程:
          1) 打开播放页, 从 window.xg_video_player_doc.aa 里抽 /api/m3u8?...
          2) 请求 /api/m3u8 -> 302 到 box.dyrs.com.de/api/super (第三方播放器)
          3) 该播放器有强反爬（ts 分片 302 到百度图片）Python 拿不到 m3u8
          4) 所以最终交给 TVBox 嗅探 (parse=1)
        """
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("playerContent: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        # 1) 播放页 → aa.url
        html = self._fetch(play_page)
        api_url = self._extract_api_m3u8(html) if html else ""
        self.log("api_url = %s" % (api_url[:160] if api_url else "EMPTY"))

        # 2) 跟随 /api/m3u8 302 → box 播放页
        if api_url:
            if api_url.startswith("/"):
                api_url = self.site_url + api_url
            box_page = self._resolve_to_box_page(api_url, referer=play_page)
            if box_page:
                # 若 box_page 是 m3u8 直链, 直接播放
                if box_page.endswith(".m3u8") or ".m3u8?" in box_page:
                    res = {
                        "parse": 0,
                        "playUrl": "",
                        "url": box_page,
                        "header": {"User-Agent": UA, "Referer": play_page},
                    }
                    self._play_cache[play_page] = (now, res)
                    self.log("=> direct m3u8")
                    return res

                # 否则让 TVBox 嗅探 box 播放页
                res = {
                    "parse": 1,
                    "playUrl": "",
                    "url": box_page,
                    "header": {"User-Agent": UA, "Referer": play_page},
                }
                self._play_cache[play_page] = (now, res)
                self.log("=> sniff box page")
                return res

        # 3) 兜底: 把播放页交给 TVBox 嗅探
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_api_m3u8(self, html):
        """从播放页中抽 aa.url (形如 /api/m3u8?origin=...&url=...)"""
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            m2 = re.search(r'(/api/m3u8\?[^"\'\\\s]+)', html)
            if m2:
                return m2.group(1).replace("&amp;", "&")
            return ""

        raw = m.group(1)
        # JS 转义还原
        raw = (raw.replace("\\\\u0026", "&")
                  .replace("\\u0026", "&")
                  .replace("\\\\u0022", '"')
                  .replace("\\u0022", '"')
                  .replace("\\/", "/"))
        try:
            aa = json.loads(raw)
            return aa.get("url", "")
        except Exception as e:
            self.log("aa parse fail: %s" % e)
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""

    def _resolve_to_box_page(self, api_url, referer=None):
        """
        请求 /api/m3u8?origin=xxx&url=xxx
        处理 3 种情况:
          A. 302 → Location 是 box.dyrs.com.de 播放页
          B. 200 → body 是 #EXTM3U (直接 m3u8)
          C. 200 → body 是 JSON (含 url/playUrl 字段)
        """
        try:
            rsp = self.fetch(api_url, headers={
                "User-Agent": UA,
                "Referer": referer or (self.site_url + "/"),
                "Accept": "text/html,application/json,*/*",
            }, timeout=12, allow_redirects=False)
        except Exception as e:
            self.log("resolve m3u8 fail: %s" % e)
            return ""

        # A. 302
        loc = ""
        if hasattr(rsp, "headers"):
            loc = (rsp.headers.get("Location", "") or
                   rsp.headers.get("location", ""))
        if loc:
            loc = loc.replace("&amp;", "&")
            if loc.startswith("//"):
                loc = "https:" + loc
            self.log("302 -> %s" % loc[:160])
            return loc

        # B/C. 200
        text = ""
        try:
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
        except Exception:
            pass

        if "#EXTM3U" in text:
            self.log("body is m3u8")
            return api_url  # 让 TVBox 直连这个 api_url

        # C. JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                u = (data.get("url") or data.get("playUrl") or
                     data.get("play_url") or "")
                if u:
                    if u.startswith("//"):
                        u = "https:" + u
                    elif u.startswith("/"):
                        u = self.site_url + u
                    self.log("json url -> %s" % u[:160])
                    return u
        except Exception:
            pass

        return ""

    # ---------------- 图片代理 ----------------
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
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }, timeout=15)
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
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
