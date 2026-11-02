# coding=utf-8
"""
开心影院 kxyy*.cc | TVBox Python 爬虫
由 drpy JS 版等价改写，逻辑与网站结构完全一致：
  - 多站点容灾（kxyy1~kxyy9，可自动探测可用站点）
  - 分类 /vodshow/{tid}--{by}-{type}-----{page}---.html
  - 列表: .row.row-cards > div (a.cover2 / img / .card-title / .badge / .text-muted)
  - 详情页: 基本信息(.col.mb-2 p) + 标签页多线路(.nav.nav-tabs) + 兜底 ul.playlist
  - 播放页: player_data "url" 字段 -> nby.php get_signed_url -> jmurl 解密
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
            method = kw.pop('method', 'get').lower()
            if method == 'post':
                r = self._sess.post(url, headers=headers, timeout=timeout, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[kxyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

SITES = [
    "https://www.kxyy1.cc",
    "https://www.kxyy2.cc",
    "https://www.kxyy3.cc",
    "https://www.kxyy4.cc",
    "https://www.kxyy5.cc",
    "https://www.kxyy6.cc",
    "https://www.kxyy7.cc",
    "https://www.kxyy8.cc",
    "https://www.kxyy9.cc",
]
DEFAULT_SITE_INDEX = 5  # 对应 JS: const baseUrl = sites[5]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "剧集"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "26", "type_name": "短剧"},
    {"type_id": "24", "type_name": "纪录片"},
]

_ORDER_BY = [
    {"n": "默认排序", "v": ""},
    {"n": "更新时间", "v": "time"},
    {"n": "近期热门", "v": "hits_week"},
    {"n": "豆瓣评分", "v": "douban_score"},
]


def _type_filter(values):
    return {"key": "type", "name": "类型",
            "value": [{"n": v or "默认类别", "v": v} for v in values]}


FILTERS = {
    "1": [_type_filter(["", "科幻", "剧情", "惊悚", "爱情", "古装", "动作", "悬疑",
                        "犯罪", "谍战", "历史", "喜剧", "奇幻", "家庭", "青春",
                        "冒险", "纪录", "动画", "人物", "文化", "其他"]),
          {"key": "orderby", "name": "排序", "value": _ORDER_BY}],
    "2": [_type_filter(["", "爱情", "古装", "悬疑", "都市", "喜剧", "战争", "剧情",
                        "青春", "历史", "网剧", "奇幻", "冒险", "励志", "犯罪",
                        "商战", "恐怖", "穿越", "农村", "人物", "商业", "生活", "其他"]),
          {"key": "orderby", "name": "排序", "value": _ORDER_BY}],
    "4": [_type_filter(["", "少年", "热血", "科幻", "冒险", "动画", "爱情", "奇幻",
                        "武侠", "悬疑", "惊悚", "剧情", "音乐", "恐怖", "喜剧", "儿童"]),
          {"key": "orderby", "name": "排序", "value": _ORDER_BY}],
    "3": [_type_filter(["", "真人秀", "脱口秀", "喜剧", "音乐", "爱情", "家庭", "歌舞"]),
          {"key": "orderby", "name": "排序", "value": _ORDER_BY}],
    "26": [{"key": "orderby", "name": "排序", "value": _ORDER_BY}],
    "24": [{"key": "orderby", "name": "排序", "value": _ORDER_BY}],
}


# ===================== 正则（与 cheerio 选择器等价） =====================
# .row.row-cards > div 卡片
_RE_CARD_BLOCK = re.compile(
    r'<div[^>]*class="[^"]*"[\s\S]{0,2000}?</div>\s*(?=<div|</section|</main|$)', re.I)
_RE_COVER_HREF = re.compile(r'<a[^>]*class="[^"]*cover2[^"]*"[^>]*href="([^"]+)"', re.I)
_RE_IMG_SRC = re.compile(r'<img[^>]*?(?:data-src|src)="([^"]+)"', re.I)
_RE_CARD_TITLE = re.compile(r'class="card-title"[^>]*>([\s\S]*?)<', re.I)
_RE_BADGE = re.compile(r'class="badge[^"]*"[^>]*>([^<]*)<', re.I)
_RE_TEXT_MUTED = re.compile(r'class="text-muted"[^>]*>([^<]*)<', re.I)

# 详情基本信息: .col.mb-2 p 内 strong + a
_RE_META_P = re.compile(r'<p[^>]*>([\s\S]*?)</p>', re.I)
_RE_STRONG = re.compile(r'<strong[^>]*>([\s\S]*?)</strong>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)

# 标题/封面/简介
_RE_H1_DESKTOP = re.compile(r'<h1[^>]*class="[^"]*d-none[^"]*d-md-block[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_H1_MOBILE = re.compile(r'<h2[^>]*class="[^"]*d-sm-block[^"]*d-md-none[^"]*"[^>]*>([\s\S]*?)</h2>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC = re.compile(
    r'<div[^>]*class="[^"]*cover-lg-max-25[^"]*"[^>]*>[\s\S]{0,500}?<img[^>]*?(?:data-src|src)="([^"]+)"', re.I)
_RE_PIC_FALLBACK = re.compile(r'<img[^>]*?(?:data-src|src)="([^"]+)"')
_RE_TEXT_ORANGE = re.compile(r'class="text-orange"[^>]*>([^<]*)<', re.I)
_RE_SYNOPSIS = re.compile(r'<div[^>]*id="synopsis"[^>]*>([\s\S]*?)</div>', re.I)

# 标签页多线路: .nav.nav-tabs li.nav-item -> a[href="#tabs-home-3"]
_RE_TAB_LI = re.compile(
    r'<li[^>]*class="[^"]*nav-item[^"]*"[^>]*>\s*<a[^>]*href="#([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)
# 面板内 a.btn
_RE_PANEL_BTN = re.compile(r'<a[^>]*class="[^"]*btn[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PANEL_BLOCK = re.compile(
    r'<div[^>]*id="([^"]+)"[^>]*>([\s\S]*?)(?=<div[^>]*id="|</div>\s*</div>\s*$)', re.I)

# 兜底 ul.playlist (input value "名称$链接")
_RE_PLAYLIST_UL = re.compile(r'<ul[^>]*class="[^"]*playlist[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_PLAYLIST_INPUT = re.compile(r'<input[^>]*value="([^"]*\$[^"]*)"', re.I)

# 通用兜底
_RE_PLAY_A = re.compile(
    r'<a[^>]*(?:class="[^"]*play-list[^"]*"|class="[^"]*anthology-list-play[^"]*")[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页 player_data 中的 "url": "..."
_RE_PLAYER_URL = re.compile(r'"url"\s*:\s*"([^"]+)"')


def _strip_tags(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    return (s.replace('&nbsp;', ' ').replace('\xa0', ' ')
             .replace('&amp;', '&').replace('&quot;', '"')
             .replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')).strip()


class Spider(Spider):

    def getName(self):
        return "开心影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        site = self.extend.get("site") or SITES[DEFAULT_SITE_INDEX]
        self.site_url = site.rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=30):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
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

    def _fix_js_url(self, url):
        """等价 JS fixUrl: 处理 \\/ 与 \\uXXXX 转义"""
        if not isinstance(url, str):
            return ""
        try:
            return json.loads('"%s"' % url)
        except Exception:
            return url

    def _is_direct_video_url(self, url):
        return url.startswith("http") and (".mp4" in url or ".m3u8" in url)

    # ---------- 站点容灾 ----------
    def _probe_site(self):
        """探测首个可用站点；默认站可用则直接用"""
        if self._fetch(self.site_url + "/vodshow/1--hits_week-------1---.html", timeout=12):
            return True
        for s in SITES:
            if s.rstrip("/") == self.site_url:
                continue
            if self._fetch(s + "/", timeout=10):
                self.log("切换站点: %s" % s)
                self.site_url = s.rstrip("/")
                self.headers["Referer"] = self.site_url + "/"
                return True
        return False

    # ---------- 列表解析 (等价 _parseVodList) ----------
    def _parse_vod_list(self, url):
        try:
            html = self._fetch(url)
            if not html:
                # 站点容灾：切到可用站点后按相对路径重建 URL 重试
                if self._probe_site():
                    path = re.sub(r'^https?://[^/]+', '', url) if url.startswith("http") else url
                    html = self._fetch(self.site_url + path)
            videos = []
            seen = set()

            # 按 .row.row-cards 容器逐卡解析（模拟 $el.find 语义）
            row_m = re.search(
                r'<div[^>]*class="[^"]*row[^"]*row-cards[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*row[^"]*"|</main|$)',
                html, re.I)
            scope = row_m.group(1) if row_m else html

            # 每张卡片：a.cover2 的 href + 卡片内 img/title/badge/muted
            card_iter = re.finditer(
                r'<a[^>]*class="[^"]*cover2[^"]*"[^>]*href="([^"]+)"([\s\S]{0,3000}?)(?=<a[^>]*class="[^"]*cover2|$)',
                scope, re.I)
            matched = False
            for m in card_iter:
                matched = True
                href = m.group(1).replace("&amp;", "&")
                block = m.group(2)
                pic = ""
                mp = _RE_IMG_SRC.search(block)
                if mp:
                    pic = mp.group(1)
                name = ""
                mt = _RE_CARD_TITLE.search(block) or _RE_CARD_TITLE.search(
                    block[:block.find("card-title") + 400] if "card-title" in block else "")
                if not mt:
                    mt = re.search(r'card-title[^>]*>([\s\S]*?)<', block, re.I)
                if mt:
                    name = _strip_tags(mt.group(1))
                remarks = ""
                mr = _RE_BADGE.search(block)
                if mr:
                    remarks = _strip_tags(mr.group(1))
                year = ""
                my = _RE_TEXT_MUTED.search(block)
                if my:
                    year = _strip_tags(my.group(1))

                if name and href not in seen:
                    seen.add(href)
                    videos.append({
                        "vod_id": href,
                        "vod_pic": self._fix_url(pic),
                        "vod_name": name,
                        "vod_remarks": remarks,
                        "vod_year": year,
                    })

            # 兜底：整体匹配（与 JS 的 each 遍历结果对齐）
            if not matched:
                for href, block in re.findall(
                        r'href="([^"]+)"[^>]*class="[^"]*cover2[^"]*"([\s\S]{0,2000}?)</a>', scope, re.I):
                    href = href.replace("&amp;", "&")
                    mp = _RE_IMG_SRC.search(block)
                    name = _strip_tags(re.search(r'card-title[^>]*>([\s\S]*?)<', block, re.I).group(1)) \
                        if re.search(r'card-title', block) else ""
                    mr = _RE_BADGE.search(block)
                    if name and href not in seen:
                        seen.add(href)
                        videos.append({
                            "vod_id": href,
                            "vod_pic": self._fix_url(mp.group(1)) if mp else "",
                            "vod_name": name,
                            "vod_remarks": _strip_tags(mr.group(1)) if mr else "",
                            "vod_year": "",
                        })

            self.log("列表 %s -> %d 条" % (url, len(videos)))
            return {"list": videos}
        except Exception as e:
            self.log("list parse error: %s" % e)
            return {"msg": str(e)}

    # ---------- 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = "%s/vodshow/1--hits_week-------1---.html" % self.site_url
        return self._parse_vod_list(url)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        by = extend.get("orderby") or "hits_week"
        ttype = extend.get("type") or ""
        url = "%s/vodshow/%s--%s-%s-----%s---.html" % (
            self.site_url, tid, by, ttype, page)
        self.log("category url: %s" % url)

        res = self._parse_vod_list(url)
        if "list" in res:
            res.update({"page": page, "pagecount": 9999,
                        "limit": 24, "total": 999999})
        return res

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/vodsearch/%s----------%s---.html" % (
            self.site_url, urllib.parse.quote(key), page)
        self.log("search url: %s" % url)
        res = self._parse_vod_list(url)
        if "list" in res:
            res.update({"page": page, "pagecount": 9999,
                        "limit": 24, "total": 999999})
        return res

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 (等价 _parseDetailVod) ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail url: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": "", "vod_pic": "", "vod_remarks": "",
            "type_name": "", "vod_director": "", "vod_actor": "",
            "vod_year": "", "vod_area": "", "vod_content": "",
            "vod_play_from": "", "vod_play_url": "",
        }

        self._parse_detail_base_info(html, vod)
        self._parse_detail_play_list(html, vod)

        if vod["vod_content"]:
            vod["vod_content"] = INTRO_PREFIX + "\n" + vod["vod_content"]
        else:
            vod["vod_content"] = INTRO_PREFIX

        self.log("detail: %s lines=%d" % (vod["vod_name"],
                                          len(vod["vod_play_from"].split("$$$"))))
        return {"list": [vod]}

    def _parse_detail_base_info(self, html, vod):
        # 标题: h1.d-none.d-md-block 优先, h2.d-sm-block.d-md-none 兜底
        m = _RE_H1_DESKTOP.search(html) or _RE_H1_MOBILE.search(html) or _RE_H1_ANY.search(html)
        if m:
            vod["vod_name"] = _strip_tags(m.group(1))

        # 封面: .col-md-auto.col-5.cover-lg-max-25 img
        m = _RE_PIC.search(html) or _RE_PIC_FALLBACK.search(html)
        if m:
            vod["vod_pic"] = self._fix_url(m.group(1))

        # 备注: .text-orange
        m = _RE_TEXT_ORANGE.search(html)
        if m:
            vod["vod_remarks"] = _strip_tags(m.group(1))

        # 字段: .col.mb-2 p 中 strong 标签判定
        for pm in _RE_META_P.finditer(html):
            p = pm.group(1)
            if 'class="col mb-2"' not in html[:pm.start()][-300:]:
                pass  # 宽松处理，直接按 strong 文本判断
            sm = _RE_STRONG.search(p)
            if not sm:
                continue
            strong_text = _strip_tags(sm.group(1)).replace("：", "").strip()

            if strong_text == "导演":
                names = [_strip_tags(x) for x in _RE_A_TEXT.findall(p)]
                vod["vod_director"] = ",".join(x for x in names if x)
            elif strong_text == "主演":
                names = [_strip_tags(x) for x in _RE_A_TEXT.findall(p)]
                vod["vod_actor"] = ",".join(x for x in names if x)
            elif strong_text == "类型":
                am = _RE_A_TEXT.search(p)
                if am:
                    vod["type_name"] = _strip_tags(am.group(1))
            elif strong_text == "制片国家/地区":
                area = _strip_tags(re.sub(r'<strong[\s\S]*?</strong>', '', p))
                vod["vod_area"] = re.sub(r'[\[\]]', '', area)
            elif strong_text in ("首播", "上映时间"):
                release = _strip_tags(re.sub(r'<strong[\s\S]*?</strong>', '', p))
                ym = re.search(r'\d{4}', release)
                if ym:
                    vod["vod_year"] = ym.group(0)

        # 简介: #synopsis
        m = _RE_SYNOPSIS.search(html)
        if m:
            vod["vod_content"] = re.sub(r'\s+', ' ', _strip_tags(m.group(1)))

    def _parse_detail_play_list(self, html, vod):
        play_from = []
        play_url = []

        # 1. 标签页多线路: .nav.nav-tabs li.nav-item
        tab_items = _RE_TAB_LI.findall(html)
        if tab_items:
            for idx, (href_id, inner) in enumerate(tab_items):
                # 等价 JS clone().children().remove(): 去掉子标签及其内容（badge 数量）
                from_name = re.sub(r'<[a-zA-Z][\s\S]*?</[a-zA-Z]+>', '', inner)
                from_name = _strip_tags(from_name) or "线路%d" % (idx + 1)
                play_from.append(from_name)

                episodes = []
                # 找到 href_id 对应的面板内容
                panel = self._find_panel(html, href_id)
                if panel:
                    for href, btn_text in _RE_PANEL_BTN.findall(panel):
                        name = _strip_tags(btn_text)
                        if name and href:
                            episodes.append("%s$%s" % (name, href.replace("&amp;", "&")))
                play_url.append("#".join(episodes))

        # 2. 兼容旧版 ul.playlist
        if not play_from:
            for idx, ul in enumerate(_RE_PLAYLIST_UL.findall(html)):
                play_from.append("线路%d" % (idx + 1))
                episodes = [v for v in _RE_PLAYLIST_INPUT.findall(ul) if "$" in v]
                play_url.append("#".join(episodes))

        # 3. 兜底通用解析
        if not play_from:
            play_from.append("默认线路")
            episodes = []
            for href, text in _RE_PLAY_A.findall(html):
                name = _strip_tags(text)
                if name and href:
                    episodes.append("%s$%s" % (name, href.replace("&amp;", "&")))
            play_url.append("#".join(episodes))

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url)

    def _find_panel(self, html, panel_id):
        # 定位 id=panel_id 的 div 内容块（到下一个同级 id div 或结尾）
        m = re.search(
            r'<div[^>]*id=["\']%s["\'][^>]*>' % re.escape(panel_id), html, re.I)
        if not m:
            return ""
        start = m.end()
        depth = 1
        i = start
        tag_re = re.compile(r'<(/?)div\b[^>]*>', re.I)
        for tm in tag_re.finditer(html, start):
            if tm.group(1):
                depth -= 1
                if depth == 0:
                    i = tm.start()
                    break
            else:
                depth += 1
        return html[start:i]

    # ---------- 播放 (等价 _parsePlay) ----------
    def playerContent(self, flag, id, vipFlags):
        return self._parse_play(id)

    def _parse_play(self, id):
        play_page_url = self._fix_url(id)
        self.log("playPageUrl: %s" % play_page_url)
        try:
            now = int(time.time())
            if play_page_url in self._play_cache:
                ts, res = self._play_cache[play_page_url]
                if now - ts < 600:
                    return res

            html = self._fetch(play_page_url)
            m = _RE_PLAYER_URL.search(html)
            if not m:
                raise Exception("未能匹配到player_data的url字段")

            video_url = self._fix_js_url(m.group(1))
            self.log("videoUrl after fix: %s" % video_url)

            if self._is_direct_video_url(video_url):
                res = {"parse": 0, "playUrl": "", "url": video_url,
                       "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
                self._play_cache[play_page_url] = (now, res)
                return res

            # 签名流程 nby.php
            get_signed_url = ("%s/static/player/nby.php?get_signed_url=1&url=%s"
                              % (self.site_url, video_url))
            signed_res = self._fetch(get_signed_url)
            signed_url = ""
            try:
                signed_url = (json.loads(signed_res) or {}).get("signed_url", "")
            except Exception:
                ms = re.search(r'"signed_url"\s*:\s*"([^"]+)"', signed_res)
                if ms:
                    signed_url = ms.group(1)
            if not signed_url:
                raise Exception("未能获取到签名播放地址")

            getjmurl = "%s/static/player/nby.php%s" % (self.site_url, signed_url)
            jm_res = self._fetch(getjmurl)
            jmurl = ""
            try:
                jmurl = (json.loads(jm_res) or {}).get("jmurl", "")
            except Exception:
                mm = re.search(r'"jmurl"\s*:\s*"([^"]+)"', jm_res)
                if mm:
                    jmurl = mm.group(1)
            if not jmurl:
                raise Exception("未能获取到解密后的播放地址")
            jmurl = self._fix_js_url(jmurl)
            self.log("jmurl: %s" % jmurl)

            res = {"parse": 0, "playUrl": "", "url": jmurl,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page_url] = (now, res)
            return res
        except Exception as e:
            self.log("play parse error: %s" % e)
            return {"parse": 0, "playUrl": "", "url": "", "msg": str(e)}

    # ---------- 其它 ----------
    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
