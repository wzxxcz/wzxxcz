# coding=utf-8
"""
西瓜影院 bzzdyy.com | TVBox Python 爬虫 
关键:
  - 苹果CMS v10 架构，分类/筛选/详情/播放全部按站点真实结构解析
  - 筛选真实抓取（类型子栏目ID / 地区 / 年份 / 排序），参数顺序严格 id->by->class->area->year
  - 详情页多线路 Tab（TX/QY/YK/MG/BZ/短剧/人人…），线路与剧集顺序完全按站点原始顺序
  - 播放页 player_aaaa 取 from/url -> 解析接口 hls.xiguadh.com -> apiToken -> m3u8/mp4 直链
  - 兼容「中间跳转页」型解析结果（HTML <a href> / JS / meta refresh 自动跟随）
"""
import re
import sys
import json
import time
import html as _html
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
                print("[bzzdyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.bzzdyy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/jiandan/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "20", "type_name": "电影"},
    {"type_id": "37", "type_name": "连续剧"},
    {"type_id": "43", "type_name": "动漫"},
    {"type_id": "45", "type_name": "综艺"},
    {"type_id": "47", "type_name": "B站"},
    {"type_id": "60", "type_name": "人人专区"},
]

# 站点解析接口（播放器 playerconfig.js 内的 parse 字段）
PARSE_API = "https://hls.xiguadh.com/?url="

# 播放来源中文别名（playerconfig.js 的 player_list.show）
FROM_ALIAS = {
    "qq": "TX", "qiyi": "QY", "youku": "YK", "mgtv": "MG",
    "bilibili": "BZ", "djplayer": "短剧", "rrmj": "人人",
    "dplayer": "DPlayer", "videojs": "VideoJS", "iva": "IVA",
    "iframe": "外链", "link": "外链数据", "swf": "Flash", "flv": "FLV",
}

# 地区筛选（站点按中文地区名传参，乱序参数会 0 结果，这里只用于拼接）
AREAS = [
    "内地", "中国", "中国香港", "中国台湾", "美国", "日本", "韩国",
    "英国", "法国", "德国", "意大利", "加拿大", "印度", "泰国",
    "西班牙", "俄罗斯", "澳大利亚", "其他",
]


# ===================== 正则 =====================
# 列表卡片（分类页 / 搜索页 / 首页通用）
_RE_CARD = re.compile(
    r'<a[^>]+class="stui-vodlist__thumb[^"]*"[^>]*?href="(/[^"]*?vod/detail/id/\d+\.html)"'
    r'[^>]*?title="([^"]*)"[^>]*?data-original="([^"]*)"',
    re.S | re.I)
_RE_CARD_ALT = re.compile(
    r'<a[^>]+class="stui-vodlist__thumb[^"]*"[^>]*?href="(/[^"]*?vod/detail/id/\d+\.html)"'
    r'[^>]*?title="([^"]*)"[^>]*?data-src="([^"]*)"',
    re.S | re.I)
_RE_CARD_SIMPLE = re.compile(
    r'<a[^>]+href="(/[^"]*?vod/detail/id/\d+\.html)"[^>]*?title="([^"]*)"', re.S | re.I)
_RE_REMARKS = re.compile(
    r'<span class="pic-text text-right"><b>([^<]*)</b></span>', re.I)
_RE_PIC_TEXT1 = re.compile(
    r'<span class="pic-text1 text-right"><b>([^<]*)</b></span>', re.I)

# 列表块：用于把「卡片 + 副标题」按 li 对齐
_RE_LI = re.compile(r'<li[^>]*>([\s\S]*?)</li>', re.I)

# 筛选区
_RE_SCREEN = re.compile(r'<div class="stui-screen">([\s\S]*?)<!-- end 筛选 -->', re.I)
_RE_SCREEN_UL = re.compile(r'<ul class="clearfix">([\s\S]*?)</ul>', re.I)
_RE_SCREEN_TITLE = re.compile(r'<span>按([^<]+)：</span>', re.I)
_RE_A = re.compile(r'<a\s+([^>]*)>([\s\S]*?)</a>', re.I)
_RE_HREF_ATTR = re.compile(r'href=["\']([^"\']*)["\']', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*?data-original="([^"]*)"', re.I)
_RE_TYPE = re.compile(r'类型：([^<]*)</p>', re.I)
_RE_AREA = re.compile(r'地区：([^<]*)</p>', re.I)
_RE_YEAR = re.compile(r'年份：([^<]*)</p>', re.I)
# 逐 <p class="data"> 取字段，避免跨标签误匹配
_RE_DATA_P = re.compile(r'<p class="data[^"]*">([\s\S]*?)</p>', re.I)
_RE_MIX = re.compile(
    r'类型：([^/<]*)[/\s]*地区：([^/<]*)[/\s]*年份：([^/<]*)', re.I)
_RE_SKETCH = re.compile(
    r'<span class="detail-sketch">([\s\S]*?)</span>', re.I)
_RE_DETAILCONTENT = re.compile(
    r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路 Tab：<li><a href="#playlist1" data-toggle="tab">TX</a></li>
_RE_TAB = re.compile(
    r'<a\s+href="#playlist(\d+)"[^>]*>([^<]*)</a>', re.I)
# 每个 playlist 容器
_RE_PLAYLIST = re.compile(
    r'<div id="playlist(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="([^"]*vod/play/[^"]*)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_PLAY_NOW = re.compile(r'正在播放：([^<&]*)', re.I)

# 解析页
_RE_TOKEN = re.compile(r'apiToken:\s*"([^"]*)"', re.I)

# 分页
_RE_PAGENUM = re.compile(r'<li[^>]*class="[^"]*active num[^"]*"[^>]*><a>(\d+)/(\d+)</a>', re.I)
_RE_PAGE_LINK = re.compile(r'/page/(\d+)\.html', re.I)


class Spider(Spider):

    def getName(self):
        return "西瓜影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._filter_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=20, headers=None):
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
        s = _html.unescape(s)
        s = s.replace("\xa0", " ").replace("\u3000", " ")
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html):
        """解析列表：卡片 + 副标题（备注）一一对应"""
        videos = []
        if not html:
            return videos

        # 先按 <li> 切块，保证「卡片」和「<b>备注</b>」不串位
        blocks = _RE_LI.findall(html)
        if not blocks:
            blocks = [html]

        seen = set()
        for blk in blocks:
            m = (_RE_CARD.search(blk) or _RE_CARD_ALT.search(blk) or
                 _RE_CARD_SIMPLE.search(blk))
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            name = self._clean(m.group(2))
            pic = m.group(3) if m.lastindex and m.lastindex >= 3 else ""
            if href in seen:
                continue
            seen.add(href)

            remarks = ""
            mr = _RE_REMARKS.search(blk)
            if mr:
                remarks = self._clean(mr.group(1))
            cat = ""
            mc = _RE_PIC_TEXT1.search(blk)
            if mc:
                cat = self._clean(mc.group(1))

            if not name:
                name = href

            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks or cat,
            })
        return videos

    def _page_count(self, html):
        """读取 1/2358 形式的总页数"""
        if not html:
            return 1
        m = _RE_PAGENUM.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        pages = [int(x) for x in _RE_PAGE_LINK.findall(html)]
        return max(pages) if pages else 1

    # ---------------- 筛选 ----------------
    # 站点参数顺序必须为 id -> class -> area -> year，乱序会 0 结果
    def _get_filters(self, tid):
        """筛选：类型(真实子栏目ID) + 剧情 + 地区 + 年份 + 排序"""
        if tid in self._filter_cache:
            return self._filter_cache[tid]

        url = "%s/index.php/vod/type/id/%s.html" % (self.site_url, tid)
        html = self._fetch(url)

        # 类型：抓「按类型」里的全部子栏目（真实 id，链接绝对可用）
        classes = [{"n": "全部", "v": ""}]
        ms = _RE_SCREEN.search(html or "")
        if ms:
            seg = ms.group(1)
            for ul in _RE_SCREEN_UL.findall(seg):
                mt = _RE_SCREEN_TITLE.search(ul)
                if not mt or self._clean(mt.group(1)) != "类型":
                    continue
                for am in _RE_A.finditer(ul):
                    text = self._clean(am.group(2))
                    mh = _RE_HREF_ATTR.search(am.group(1))
                    href = mh.group(1) if mh else ""
                    mid = re.search(r'/id/(\d+)\.html', href)
                    if not text or not mid:
                        continue
                    if text == "全部":
                        continue
                    item = {"n": text, "v": mid.group(1)}
                    if item not in classes:
                        classes.append(item)
                break

        filters = []
        if len(classes) > 1:
            filters.append({"key": "class", "name": "类型", "value": classes})
        filters.append({"key": "area", "name": "地区",
                        "value": [{"n": x, "v": x} for x in ["全部"] + AREAS]})
        filters.append({"key": "year", "name": "年份",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": str(y), "v": str(y)}
                                  for y in range(2026, 1999, -1)]})
        filters.append({"key": "sort", "name": "排序",
                        "value": [{"n": "最新", "v": ""},
                                  {"n": "最热", "v": "hits"},
                                  {"n": "评分", "v": "score"},
                                  {"n": "时间", "v": "time"}]})
        self._filter_cache[tid] = filters
        return filters

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter=False):
        filters = {}
        if filter:
            for c in CLASSES:
                try:
                    filters[c["type_id"]] = self._get_filters(c["type_id"])
                except Exception as e:
                    self.log("filters %s fail: %s" % (c["type_id"], e))
        return {"class": CLASSES, "filters": filters}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html)
        self.log("home: %d" % len(videos))
        return {"list": videos}

    def _build_show_url(self, tid, page, combo):
        """
        拼苹果CMS show 链接（参数顺序固定 id -> by -> class -> area -> year -> page）：
          /index.php/vod/show/id/20/class/21/area/美国/year/2024/page/2.html
        注意：顺序不能乱，站点对乱序参数会返回 0 条。
        """
        combo = combo or {}
        cid = str(combo.get("class") or tid)
        parts = []
        sort = combo.get("sort")
        if sort:
            parts.append("by/%s" % sort)
        parts.append("id/%s" % cid)
        if combo.get("area"):
            parts.append("area/%s" % urllib.parse.quote(str(combo["area"])))
        if combo.get("year"):
            parts.append("year/%s" % urllib.parse.quote(str(combo["year"])))
        if page and page > 1:
            parts.append("page/%d" % page)
        return "%s/index.php/vod/show/%s.html" % (self.site_url, "/".join(parts))

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        combo = {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if isinstance(extend, dict):
            for k, v in extend.items():
                if v in ("", "全部", None):
                    continue
                if isinstance(v, str) and v.strip().startswith("{"):
                    try:
                        combo.update(json.loads(v))
                        continue
                    except Exception:
                        pass
                if k in ("class", "area", "year", "sort"):
                    combo[k] = v

        url = self._build_show_url(tid, page, combo)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        if not videos and combo:
            # 组合无效（脏值）时退回纯分类，避免空列表
            html = self._fetch(self._build_show_url(tid, page, {}))
            videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("category %s p%d %s -> %d条/%d页"
                 % (tid, page, json.dumps(combo, ensure_ascii=False),
                    len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page > 1:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (self.site_url, page, kw)
        else:
            url = "%s/index.php/vod/search/wd/%s.html" % (self.site_url, kw)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("search %s p%d -> %d" % (key, page, len(videos)))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
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
            return {"list": []}

        def pick(*regexes):
            for r in regexes:
                m = r.search(html)
                if m:
                    v = self._clean(m.group(1))
                    if v and v != "未知":
                        return v
            return ""

        # 标题
        name = pick(_RE_H1, _RE_H1_ANY)
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1)).split("_")[0].split("-")[0]
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = ""
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic or pic == DEFAULT_PIC:
            m = _RE_CARD.search(html) or _RE_CARD_ALT.search(html)
            if m:
                pic = self._fix_url(m.group(3))
        if not pic:
            pic = self.default_pic

        # 简介：detail-content 优先，其次 detail-sketch，最后 meta
        content = pick(_RE_DETAILCONTENT, _RE_SKETCH)
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # 元信息：逐个 <p class="data"> 单独解析，杜绝跨行误吃
        info = {"type": "", "area": "", "year": "", "lang": "",
                "state": "", "upd": "", "director": "", "actor": ""}
        for pm in _RE_DATA_P.finditer(html):
            seg = pm.group(1)
            if "状态：" in seg and not info["state"]:
                ms = re.search(r'状态：[\s\S]*?>([^<]*)</span>', seg)
                info["state"] = self._clean(ms.group(1)) if ms else self._clean(seg.split("状态：")[1])
            elif "导演：" in seg and not info["director"]:
                info["director"] = self._clean(seg.split("导演：")[1])
            elif "主演：" in seg and not info["actor"]:
                info["actor"] = self._clean(seg.split("主演：")[1])
            elif "语言：" in seg and not info["lang"]:
                info["lang"] = self._clean(seg.split("语言：")[1])
            elif "更新：" in seg and not info["upd"]:
                info["upd"] = self._clean(seg.split("更新：")[1])

        m = _RE_MIX.search(html)
        if m:
            info["type"] = self._clean(m.group(1))
            info["area"] = self._clean(m.group(2))
            info["year"] = self._clean(m.group(3))
        else:
            # 兼容分开写的页面
            for key, rx in (("type", _RE_TYPE), ("area", _RE_AREA), ("year", _RE_YEAR)):
                mm = rx.search(html)
                if mm:
                    info[key] = self._clean(mm.group(1))

        vod_type = info["type"]
        area = info["area"]
        year = info["year"]
        lang = info["lang"]
        state = info["state"]
        upd = info["upd"]
        director = info["director"]
        actor = info["actor"]
        if actor:
            actor = re.sub(r"[,，\s]+", ",", actor).strip(",")
            actor = ", ".join([a for a in actor.split(",") if a])

        remarks = state or upd or ""

        # 播放线路（按站点 Tab 顺序 + playlist 容器顺序）
        play_from = []
        play_url = []

        tab_order = []
        for tm in _RE_TAB.finditer(html):
            tab_order.append((tm.group(1), self._clean(tm.group(2))))

        plist = {}
        for pm in _RE_PLAYLIST.finditer(html):
            plist[pm.group(1)] = pm.group(2)

        order = [x[0] for x in tab_order if x[0] in plist]
        for k in plist.keys():
            if k not in order:
                order.append(k)

        tabname = dict(tab_order)
        for idx in order:
            eps = []
            seen = set()
            for em in _RE_EP_A.finditer(plist[idx]):
                href = em.group(1).replace("&amp;", "&")
                ep_name = self._clean(em.group(2)) or ("第%d集" % (len(eps) + 1))
                if href.startswith("/"):
                    href = self.site_url + href
                if href in seen:
                    continue
                seen.add(href)
                eps.append("%s$%s" % (ep_name, href))
            if not eps:
                continue
            name_line = tabname.get(idx) or ("线路%s" % idx)
            play_from.append(name_line)
            play_url.append("#".join(eps))

        if not play_from:
            return {"list": []}

        # 主线顺序：完全按站点线路 Tab 的原始顺序（TX → QY → YK → MG → BZ …）
        pairs = list(zip(play_from, play_url))
        vod_content_full = content

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": vod_type or "",
            "vod_year": year or "",
            "vod_area": area or "",
            "vod_lang": lang or "",
            "vod_remarks": remarks or ("%d条线路" % len(pairs)),
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": vod_content_full,
            "vod_play_from": "$$$".join([p[0] for p in pairs]),
            "vod_play_url": "$$$".join([p[1] for p in pairs]),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(str(id))
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 300:
                return res

        html = self._fetch(play_page)
        info = self._parse_player(html)
        src_url = info.get("url", "")
        frm = (info.get("from") or "").strip()
        self.log("player %s from=%s url=%s" % (play_page, frm, src_url[:120]))

        res = None
        # 1) 本身就是 m3u8/mp4 直链
        if re.search(r"\.(m3u8|mp4|flv)(\?|$)", src_url, re.I):
            res = self._direct(src_url, play_page)

        # 2) 走站点解析接口
        if res is None and src_url:
            real = self._resolve(src_url, play_page)
            if real:
                res = self._direct(real, play_page)

        # 3) 兜底：交给 TVBox 嗅探
        if res is None:
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        self._play_cache[play_page] = (now, res)
        return res

    def _direct(self, url, referer):
        """m3u8 统一带上站点 header，TVBox 系播放器可直出"""
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": referer,
                "Origin": self.site_url,
            },
        }

    def _parse_player(self, html):
        """解析 player_aaaa 与 正在播放"""
        out = {}
        if not html:
            return out
        m = _RE_PLAYER.search(html)
        if not m:
            return out
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json.loads(raw.replace("\\/", "/"))
            except Exception:
                data = {}
        if isinstance(data, dict):
            out["url"] = (data.get("url") or "").replace("\\/", "/")
            out["from"] = data.get("from") or ""
            out["link_next"] = data.get("link_next") or ""
        if not out.get("url"):
            mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if mu:
                out["url"] = mu.group(1).replace("\\/", "/").replace("\\u0026", "&")
        mn = _RE_PLAY_NOW.search(html)
        if mn:
            out["now"] = self._clean(mn.group(1))
        return out

    def _follow_link(self, url, depth=0):
        """
        部分解析源返回 HTML 跳转页（<a href="...m3u8">），
        这里递归跟随，直到拿到真正的 m3u8 / mp4 地址。
        """
        if depth > 3 or not url:
            return url
        if re.search(r"\.(m3u8|mp4|flv)(\?|$)", url, re.I):
            return url
        body = self._fetch(url, timeout=18, headers={
            "User-Agent": UA,
            "Referer": "https://hls.xiguadh.com/",
            "Accept": "*/*",
        })
        if not body:
            return url
        if body.lstrip().startswith("#EXTM3U"):
            return url
        # HTML 跳转页
        m = re.search(r'''<a[^>]+href=["']([^"']+)["']''', body, re.I)
        if m:
            nxt = m.group(1).replace("&amp;", "&")
            return self._follow_link(nxt, depth + 1)
        # JS 跳转
        m = re.search(r'''(?:location\.href|window\.location)\s*=\s*["']([^"']+)["']''', body, re.I)
        if m:
            return self._follow_link(m.group(1).replace("&amp;", "&"), depth + 1)
        # meta refresh
        m = re.search(r'''http-equiv=["']refresh["'][^>]*content=["'][^"']*url=([^"';]+)''', body, re.I)
        if m:
            return self._follow_link(m.group(1), depth + 1)
        return url

    def _resolve(self, src_url, referer):
        """调站点解析接口 hls.xiguadh.com -> apiToken -> api/resolve.php -> m3u8"""
        try:
            page = PARSE_API + urllib.parse.quote(src_url, safe="")
            h = self._fetch(page, timeout=20, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
                "Accept": "text/html,*/*",
            })
            if not h:
                self.log("  解析页空")
                return ""
            mt = _RE_TOKEN.search(h)
            if not mt:
                self.log("  未取到 apiToken")
                return ""
            token = mt.group(1)
            api = "https://hls.xiguadh.com/api/resolve.php?token=" + \
                  urllib.parse.quote(token, safe="")
            body = self._fetch(api, timeout=20, headers={
                "User-Agent": UA,
                "Referer": "https://hls.xiguadh.com/",
                "Accept": "application/json, */*",
            })
            if not body:
                return ""
            try:
                data = json.loads(body)
            except Exception:
                return ""
            if str(data.get("code")) != "200":
                self.log("  resolve 失败: %s" % body[:120])
                return ""
            u = (data.get("url") or "").replace("\\/", "/")
            if not u:
                return ""
            # 中间跳转页 -> 追到真正的 m3u8
            final = self._follow_link(u)
            self.log("  resolve -> %s%s" % (final[:140],
                                            "" if final == u else "  (跟跳转)"))
            return final
        except Exception as e:
            self.log("  resolve 异常: %s" % e)
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
