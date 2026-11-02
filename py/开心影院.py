# coding=utf-8
"""
开心影院 kxyy1.cc ( Tabler V4 模板) | TVBox Python 爬虫
依据真实页面 HTML（首页/分类筛选/搜索/详情/播放）逐字段精确实现：
  - 分类: /vodshow/{id}-...  id: 1电影 2电视剧 3综艺 4动漫 26短剧 24纪录片
  - 筛选 URL 11 参数制: {id}-{地区p1}-{排序p2}-{类型p3}-{p4..p7}-{页码p8}-{p9,p10}-{年份p11}.html
    实测: /vodshow/1-中国大陆--科幻--------2026.html
          /vodshow/1-中国大陆-time---------2026.html
          /vodshow/1-中国大陆-------2---2026.html (第2页)
  - 搜索: /vodsearch/{kw}----------{page}---.html
  - 卡片: div.card.card-sm.card-link (a[href=/voddetail/xx.html] + img + span.badge + ribbon评分)
  - 详情: h1 标题, og:image 封面, .col.mb-2 p strong 字段, #synopsis 简介, nav-tabs 多线路(TT源/IK源)
  - 播放: player_data.url 直链 m3u8 (如 bfikuncdn.com/.../index.m3u8)
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
                print("[kxyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

SITES = [
    "https://www.kxyy1.cc", "https://www.kxyy2.cc", "https://www.kxyy3.cc",
    "https://www.kxyy4.cc", "https://www.kxyy5.cc", "https://www.kxyy6.cc",
    "https://www.kxyy7.cc", "https://www.kxyy8.cc", "https://www.kxyy9.cc",
]
DEFAULT_SITE = SITES[0]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 资源分类（与真实筛选面板 "资源分类" 完全一致）
CLASSES = [
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "26", "type_name": "短剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "纪录片"},
]

# 影视类型（真实 "影视类型" 面板，电影页实测）
_TYPES = ["科幻", "剧情", "惊悚", "爱情", "古装", "动作", "悬疑", "犯罪",
          "谍战", "历史", "喜剧", "奇幻", "家庭", "青春", "冒险", "纪录",
          "动画", "人物", "文化", "其他"]
# 制片地区（真实 "制片地区" 面板）
_AREAS = ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国",
          "英国", "法国", "德国", "意大利", "印度", "马来西亚"]
# 排序（真实 "影视排序" 面板: 更新时间/近期热门/豆瓣评分，默认为空=默认排序）
_SORTS = [{"n": "默认排序", "v": ""},
          {"n": "更新时间", "v": "time"},
          {"n": "近期热门", "v": "hits_week"},
          {"n": "豆瓣评分", "v": "douban_score"}]

_YEAR_VALUES = [str(y) for y in range(2026, 1999, -1)] + \
               ["90年代", "80年代", "70年代", "其他"]

FILTERS = {}
for _c in CLASSES:
    FILTERS[_c["type_id"]] = [
        {"key": "cls", "name": "类型",
         "value": [{"n": "不限", "v": ""}] + [{"n": t, "v": t} for t in _TYPES]},
        {"key": "area", "name": "地区",
         "value": [{"n": "不限", "v": ""}] + [{"n": a, "v": a} for a in _AREAS]},
        {"key": "year", "name": "年份",
         "value": [{"n": "不限", "v": ""}] + [{"n": y, "v": y} for y in _YEAR_VALUES]},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 卡片块: div.card.card-sm.card-link ... （首页/分类页/猜你喜欢通用）
_RE_CARD_BLOCK = re.compile(r'<div class="card card-sm card-link">([\s\S]*?)</div>\s*</div>', re.I)
_RE_CARD_WINDOW = re.compile(r'<div class="card card-sm card-link">', re.I)
_RE_HREF_DETAIL = re.compile(r'href="(/voddetail/[^"]+?\.html)"', re.I)
_RE_IMG = re.compile(r'<img[^>]*?(?:data-src|src)="([^"]+)"', re.I)
_RE_BADGE = re.compile(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>([^<]*)</span>', re.I)
_RE_RIBBON = re.compile(r'<(?:div|strong)[^>]*class="ribbon[^"]*"[^>]*>([^<]*)</(?:div|strong)>', re.I)
_RE_CARD_TITLE = re.compile(r'<h[34][^>]*class="[^"]*card-title[^"]*"[^>]*>([\s\S]*?)</h[34]>', re.I)
_RE_TEXT_MUTED = re.compile(r'<p[^>]*class="[^"]*text-muted[^"]*"[^>]*>([^<]*)</p>', re.I)

# 分类页分页: 尾页/页码
_RE_LAST_PAGE = re.compile(
    r'<a[^>]*href="(/(?:vodshow|vodsearch)/[^"]*?\.html)"[^>]*>\s*尾页\s*<', re.I)
_RE_NEXT_PAGE = re.compile(
    r'<a[^>]*href="(/vodshow/[^"]+?\.html)"[^>]*>\s*(?:下一页|<svg)', re.I)

# 详情
_RE_OG_IMAGE = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_BADGE_ANY = re.compile(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>([^<]*)</span>', re.I)
_RE_META_P = re.compile(r'<p[^>]*>([\s\S]*?)</p>', re.I)
_RE_STRONG = re.compile(r'<strong[^>]*>([\s\S]*?)</strong>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_SYNOPSIS = re.compile(
    r'id="synopsis"[\s\S]*?<div class="card-body">([\s\S]*?)</div>', re.I)
_RE_TEXT_ORANGE = re.compile(r'<span class="text-orange">([^<]*)</span>', re.I)

# 线路标签页
_RE_TAB_LI = re.compile(
    r'<li class="nav-item"><a href="#([^"]+)"[^>]*>([\s\S]*?)</a></li>', re.I)
_RE_PANEL_BTN = re.compile(r'<a[^>]*class="[^"]*btn[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', re.I)
_RE_PANEL_BLOCK = re.compile(r'<div class="tab-pane[^"]*" id="([^"]+)">([\s\S]*?)</div>\s*</div>', re.I)

# 播放页 player_data
_RE_PLAYER_DATA = re.compile(r'var\s+player_data\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)


def _strip_tags(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    return (s.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
             .replace('&amp;', '&').replace('&quot;', '"')
             .replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')).strip()


def _fix_js_url(url):
    """等价 JS fixUrl: 处理 \\/ 与 \\uXXXX 转义"""
    if not isinstance(url, str):
        return ""
    try:
        return json.loads('"%s"' % url)
    except Exception:
        return url


class Spider(Spider):

    def getName(self):
        return "开心影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        site = self.extend.get("site") or DEFAULT_SITE
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

    # ---------- 列表解析（首页/分类页卡片） ----------
    def _parse_vod_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 以 card-sm card-link 标记切块（自闭合嵌套，用窗口法）
        marks = [m.start() for m in _RE_CARD_WINDOW.finditer(html)]
        marks.append(len(html))
        for i in range(len(marks) - 1):
            block = html[marks[i]:marks[i + 1]]
            mh = _RE_HREF_DETAIL.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            mt = _RE_CARD_TITLE.search(block)
            name = _strip_tags(mt.group(1)) if mt else ""
            if not name:
                continue
            mi = _RE_IMG.search(block)
            pic = self._fix_url(mi.group(1)) if mi else ""
            remarks = ""
            mr = _RE_RIBBON.search(block)
            if mr:
                score = _strip_tags(mr.group(1))
                if score:
                    remarks = score
            mb = _RE_BADGE.search(block)
            if mb:
                remark_text = _strip_tags(mb.group(1))
                remarks = ("%s·%s" % (remarks, remark_text)) if remarks else remark_text
            my = _RE_TEXT_MUTED.search(block)
            date = _strip_tags(my.group(1)) if my else ""
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks or date,
                "vod_year": date[:4] if re.match(r'\d{4}', date) else "",
            })
        return videos

    # ---------- 分类 URL 构造（11 参数制，与真实 URL 逐字符一致） ----------
    def _build_vodshow_url(self, tid, page, extend):
        params = [
            extend.get("area") or "",                          # p1 地区
            extend.get("sort") or "",                          # p2 排序
            extend.get("cls") or "",                           # p3 类型
            "", "", "",                                        # p4-p6
            "",                                                # p7
            str(page) if page > 1 else "",                     # p8 页码
            "", "",                                            # p9-p10
            extend.get("year") or "",                          # p11 年份
        ]
        path = "/vodshow/%s-%s.html" % (tid, "-".join(params))
        # 中文/特殊字符需 URL 编码（与站内链接 %E4%B8%AD 一致）
        return urllib.parse.quote(path, safe="/:.%")

    def _page_count(self, html):
        m = _RE_LAST_PAGE.search(html)
        if m:
            # /vodshow/{tid}-{11参数}.html，页码在第8个参数（索引7）
            try:
                seg = urllib.parse.unquote(m.group(1))
                parts = re.match(r'/(?:vodshow|vodsearch)/[^-]+-(.*)\.html',
                                 seg, re.I)
                if parts:
                    params = parts.group(1).split('-')
                    if len(params) >= 8 and params[7].isdigit():
                        return int(params[7])
                    # 搜索页格式: /vodsearch/{kw}----------N---.html
                    nums = re.findall(r'\d+', parts.group(1))
                    if nums:
                        return int(nums[-1])
            except Exception:
                pass
        return 9999

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_vod_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        url = self._fix_url(self._build_vodshow_url(tid, page, extend))
        self.log("category url: %s" % url)
        html = self._fetch(url)

        # 容灾：失败尝试其它线路域名
        if not html:
            for s in SITES:
                if s.rstrip("/") == self.site_url:
                    continue
                self.site_url = s.rstrip("/")
                self.headers["Referer"] = self.site_url + "/"
                url = self._fix_url(self._build_vodshow_url(tid, page, extend))
                self.log("尝试备用站点: %s" % url)
                html = self._fetch(url)
                if html:
                    break
        if not html:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 24, "total": 0}

        videos = self._parse_vod_list(html)
        pagecount = self._page_count(html)
        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": 24, "total": pagecount * 24}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        # 真实格式: /vodsearch/关键词----------1---.html
        path = "/vodsearch/%s----------%d---.html" % (
            urllib.parse.quote(key), page)
        url = self._fix_url(path)
        self.log("search url: %s" % url)
        html = self._fetch(url)
        videos = self._parse_search_list(html)
        pagecount = self._page_count(html) if html else 1
        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": 20, "total": pagecount * 20}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 搜索结果解析（专用布局: search-movie-title） ----------
    def _parse_search_list(self, html):
        videos = []
        if not html:
            return videos
        items = re.findall(
            r'(<a class="d-inline-block[\s\S]*?search-movie-title[\s\S]*?</a>[\s\S]{0,2000}?)</div>\s*</div>\s*</div>',
            html, re.I)
        # 整块按 col-12 行切
        rows = re.split(r'<div class="col-12">', html)
        for row in rows[1:]:
            mh = _RE_HREF_DETAIL.search(row)
            if not mh:
                continue
            href = mh.group(1)
            mt = re.search(r'search-movie-title[^>]*title="([^"]*)"', row, re.I)
            if not mt:
                mt = re.search(r'search-movie-title[\s\S]*?>([\s\S]*?)</a>', row, re.I)
            name = _strip_tags(mt.group(1)) if mt else ""
            if not name:
                continue
            # 标题文本形如: 2026短剧《东北老舅》完结 → 提取状态
            full = ""
            mt2 = re.search(r'search-movie-title[\s\S]*?>([\s\S]*?)</a>', row, re.I)
            if mt2:
                full = _strip_tags(mt2.group(1))
            remark = ""
            mstate = re.search(r'》\s*(\S+)\s*$', full)
            if mstate:
                remark = mstate.group(1)
            mi = _RE_IMG.search(row)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._fix_url(mi.group(1)) if mi else "",
                "vod_remarks": remark,
                "vod_year": full[:4] if re.match(r'\d{4}', full) else "",
            })
        return videos

    # ---------- 详情 ----------
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

        # 标题: h1 "老舅 (2025)"
        m = _RE_H1.search(html)
        if m:
            name = _strip_tags(m.group(1))
            ym = re.search(r'^(.*?)\s*\((\d{4})\)\s*$', name)
            if ym:
                vod["vod_name"] = ym.group(1).strip()
                vod["vod_year"] = ym.group(2)
            else:
                vod["vod_name"] = name

        # 封面: og:image（真实详情页元数据，最可靠）
        mi = _RE_OG_IMAGE.search(html)
        if mi:
            vod["vod_pic"] = mi.group(1)

        # 备注: 摘要 span.text-orange（如 "全27集"）+ 豆瓣评分 badge
        mo = _RE_TEXT_ORANGE.search(html)
        if mo:
            vod["vod_remarks"] = _strip_tags(mo.group(1))
        for mb in _RE_BADGE_ANY.finditer(html):
            t = _strip_tags(mb.group(1))
            if t.startswith("豆瓣评分：") and not t.endswith("暂无"):
                vod["vod_score"] = t.replace("豆瓣评分：", "")
                break

        # 元信息: <div class="col mb-2"><p><strong>导演：</strong>...</p>
        for pm in _RE_META_P.finditer(html):
            p = pm.group(1)
            sm = _RE_STRONG.search(p)
            if not sm:
                continue
            label = _strip_tags(sm.group(1)).replace("：", "").strip()
            rest = _strip_tags(re.sub(r'<strong[\s\S]*?</strong>', '', p))
            if label == "导演":
                names = [_strip_tags(x) for x in _RE_A_TEXT.findall(p)]
                vod["vod_director"] = ",".join(x for x in names if x) or rest
            elif label == "主演":
                names = [_strip_tags(x) for x in _RE_A_TEXT.findall(p)]
                vod["vod_actor"] = ",".join(x for x in names if x) or rest
            elif label == "类型":
                names = [_strip_tags(x) for x in _RE_A_TEXT.findall(p)]
                vod["type_name"] = ",".join(x for x in names if x) or rest
            elif label in ("制片国家/地区", "地区"):
                vod["vod_area"] = re.sub(r'[\[\]]', '', rest)
            elif label in ("首播", "上映时间", "上映"):
                ym2 = re.search(r'\d{4}', rest)
                if ym2 and not vod["vod_year"]:
                    vod["vod_year"] = ym2.group(0)

        # 简介: #synopsis 折叠面板内 .card-body
        ms = _RE_SYNOPSIS.search(html)
        if ms:
            vod["vod_content"] = re.sub(r'\s+', ' ', _strip_tags(ms.group(1)))
        vod["vod_content"] = (INTRO_PREFIX + "\n" + vod["vod_content"]) \
            if vod["vod_content"] else INTRO_PREFIX

        # 线路与剧集（nav-tabs: TT源/IK源，顺序=网站显示顺序）
        self._parse_detail_play_list(html, vod)
        return {"list": [vod]}

    def _parse_detail_play_list(self, html, vod):
        play_from = []
        play_url = []

        # 1. 标签页多线路: li.nav-item > a[href="#tabs-home-N"]（名称去掉 svg 图标与 badge 数量）
        panels = {pid: body for pid, body in _RE_PANEL_BLOCK.findall(html)}
        for pid, inner in _RE_TAB_LI.findall(html):
            from_name = re.sub(r'<(svg|span)[\s\S]*?</\1>', '', inner)
            from_name = _strip_tags(from_name) or "线路%d" % (len(play_from) + 1)
            episodes = []
            body = panels.get(pid)
            if body:
                for href, btn_text in _RE_PANEL_BTN.findall(body):
                    name = _strip_tags(btn_text)
                    if name and href:
                        episodes.append("%s$%s" % (name, href.replace("&amp;", "&")))
            if episodes:
                play_from.append(from_name)
                play_url.append("#".join(episodes))

        # 2. 兜底: 全页 /vodplay/ 链接（按出现顺序）
        if not play_from:
            episodes = []
            for href, text in re.findall(
                    r'<a[^>]*href="(/vodplay/[^"]+?\.html)"[^>]*>([^<]*)</a>', html, re.I):
                name = _strip_tags(text)
                if name and href and (href, name) not in episodes:
                    episodes.append((href, name))
            if episodes:
                play_from.append("默认线路")
                play_url.append("#".join("%s$%s" % (n, h) for h, n in episodes))

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url)

    # ---------- 播放（player_data.url 直链 m3u8） ----------
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
            md = _RE_PLAYER_DATA.search(html)
            if not md:
                raise Exception("未能匹配到player_data")

            try:
                pd = json.loads(md.group(1))
                video_url = pd.get("url", "")
            except Exception:
                mu = re.search(r'"url"\s*:\s*"([^"]+)"', md.group(1))
                video_url = mu.group(1) if mu else ""

            video_url = _fix_js_url(video_url)
            self.log("videoUrl: %s" % video_url)
            if not video_url:
                raise Exception("player_data中无url")

            if not (video_url.startswith("http") and
                    (".m3u8" in video_url or ".mp4" in video_url)):
                # 非直链时走 nby.php 签名解密（兜底，同站系旧逻辑）
                video_url = self._resolve_signed(video_url)

            res = {"parse": 0, "playUrl": "", "url": video_url,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page_url] = (now, res)
            return res
        except Exception as e:
            self.log("play parse error: %s" % e)
            return {"parse": 0, "playUrl": "", "url": "", "msg": str(e)}

    def _resolve_signed(self, video_url):
        get_signed_url = ("%s/static/player/nby.php?get_signed_url=1&url=%s"
                          % (self.site_url, video_url))
        signed_res = self._fetch(get_signed_url)
        signed_url = ""
        try:
            signed_url = (json.loads(signed_res) or {}).get("signed_url", "")
        except Exception:
            ms = re.search(r'"signed_url"\s*:\s*"([^"]+)"', signed_res or "")
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
            mm = re.search(r'"jmurl"\s*:\s*"([^"]+)"', jm_res or "")
            if mm:
                jmurl = mm.group(1)
        if not jmurl:
            raise Exception("未能获取到解密后的播放地址")
        return _fix_js_url(jmurl)

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
