# coding=utf-8
"""
两个BT影视 www.bttwo.life | TVBox Python 爬虫 (豆花 dhvideo 契约)
站点结构（线上快照 + 浏览器实证 ，SSR + Alpine.js，ArtPlayer/hls.js）:
  - 首页:   / （首屏 swiper 轮播 + 网格 movie-card）
  - 分类/筛选/列表: /filter?classify=<1电影2电视剧3动漫4综艺>&areas=<地区id>
            &types=<题材id>&years=<年份id>&tags=<标签id>&sort_by=<update_time|hits|score>
            &order=desc&page=<n> （每页 24，分页参数 page）
  - 详情/播放: /play/<slug>
  - 搜索:   /search?q=<关键词> （GET，单页结果）
  - 卡片:   网格 div.movie-card[data-vod-id="<slug>"]；主 <a href="/play/<slug>">，
            封面 img[data-src]（src 为 placeholder），标题 h3，备注角标封面内
            span.absolute...text-right（全X集/更新至X集），悬浮层简介 p.line-clamp-2；
            搜索卡片为 div.group.relative，无 data-vod-id，slug 取自 href。
  - 详情:   .movie-poster h1 片名；海报 img 封面；栅格 label(col-span-1 gray-500) /
            value(col-span-2 gray-300)：又名/导演/编剧/主演/类型/地区/语言/上映；
            简介 剧情简介 p.text-gray-300；meta description 兜底。
  - 线路:   episodeManager(line, ep, [{lineName:'alists', episodeCount:N}])，
            线路名取 lineName，顺序按数组；选集 <a href="/play/<slug>" data-line
            data-episode dataid>，每集独立 slug + dataid。
  - 播放签名（Rust WASM 已纯 Python 还原）:
            s = HMAC_SHA256(key=slug, msg="<dataid>:<毫秒时间戳>:<slug>").hexdigest()[:32]
            k = base64url( play_key XOR 循环密钥 "nbmovie2024secretkey" )；
            play_key 为详情页内联 userlink，空/0 时 k="0"
            GET /video/play?p=<dataid>&v=<slug>&q=1080&s=<s>&t=<毫秒>&k=<k>
            响应 data.quality_urls[]：url 直链（mp4/m3u8），subtitle_url 字幕。
"""
import re
import sys
import json
import time
import hmac
import hashlib
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
            try:
                print("[bttwo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.bttwo.life"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# k 编码循环密钥（WASM 内常量，实证还原）
_SECRET = b"nbmovie2024secretkey"

# ===================== 分类（对齐站点顶部导航）=====================
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "动漫"},
    {"type_id": "4", "type_name": "综艺"},
]

# 筛选维度值（站点内部数字 id，filter.html 实证提取）
_AREAS = {
    "5": "美国", "6": "法国", "7": "中国", "9": "未知", "11": "日本",
    "12": "韩国", "14": "中国香港", "16": "俄罗斯", "17": "波兰", "18": "德国",
    "19": "意大利", "21": "中国台湾", "22": "澳大利亚", "24": "西班牙", "30": "英国",
    "32": "加拿大", "33": "泰国", "34": "印度", "41": "丹麦", "52": "中国大陆",
    "65": "马来西亚", "74": "菲律宾", "78": "其他", "79": "瑞典", "80": "挪威",
    "81": "阿根廷", "82": "冰岛", "83": "保加利亚", "84": "爱尔兰", "85": "墨西哥",
    "86": "比利时", "87": "匈牙利", "88": "哥伦比亚", "89": "西德", "90": "新西兰",
    "91": "巴西", "92": "南非", "93": "印度尼西亚", "94": "奥地利", "95": "瑞士",
    "96": "捷克", "97": "巴哈马",
}
_TYPES = {
    "1": "剧情", "2": "悬疑", "3": "恐怖", "4": "惊悚", "5": "喜剧", "6": "爱情",
    "9": "犯罪", "10": "动作", "11": "动画", "12": "奇幻", "13": "音乐", "14": "科幻",
    "15": "历史", "16": "战争", "18": "冒险", "19": "家庭", "20": "纪录", "23": "西部",
    "24": "电视电影", "25": "情色", "26": "真人秀", "27": "古装", "28": "传记",
    "29": "同性", "30": "运动", "31": "武侠", "32": "歌舞", "33": "纪录片", "34": "灾难",
    "35": "短片",
}
_YEARS = {
    "1": "2026", "3": "2025", "4": "2024", "56": "2023", "13": "2022", "2": "2021",
    "6": "2020", "8": "2019", "9": "2018", "12": "2017", "11": "2016", "14": "2015",
    "15": "2014", "22": "2013", "10": "2012", "17": "2011", "25": "2010", "20": "2009",
    "23": "2008", "30": "2007", "31": "2006", "7": "2005", "24": "2004", "28": "2003",
    "19": "2002", "29": "2001", "43": "2000", "45": "1999", "33": "1998", "34": "1997",
    "37": "1996", "21": "1995", "27": "1994", "26": "1993", "35": "1992", "18": "1991",
    "42": "1990", "44": "1989", "60": "1988", "73": "1987", "32": "1986", "40": "1985",
    "63": "1984", "59": "1983", "36": "1982", "5": "1981", "39": "1980", "61": "1979",
    "66": "1978", "48": "1977", "38": "1976", "57": "1975", "62": "1974", "53": "1973",
    "54": "1972", "51": "1971", "41": "1969", "77": "1968", "76": "1966", "58": "1965",
    "46": "1963", "65": "1962", "71": "1961", "75": "1960", "16": "1959", "67": "1958",
    "50": "1957", "49": "1956", "47": "1955", "68": "1954", "72": "1952", "70": "1949",
    "64": "1948", "52": "1938", "55": "1931", "69": "1925", "74": "1921",
}
_TAGS = {"1": "4k", "36": "院线", "37": "HD", "38": "TC"}
_SORTS = [("最新上映", "update_time"), ("最受欢迎", "hits"), ("评分最高", "score")]


def _opts(d):
    return [{"n": "全部", "v": ""}] + [
        {"n": name, "v": vid} for vid, name in d.items()]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "areas", "name": "地区", "value": _opts(_AREAS)},
        {"key": "types", "name": "题材", "value": _opts(_TYPES)},
        {"key": "years", "name": "年份", "value": _opts(_YEARS)},
        {"key": "tags", "name": "标签", "value": _opts(_TAGS)},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]

# ===================== 正则 =====================
_RE_PLAY = re.compile(r'/play/([a-z0-9]+)', re.I)
_RE_H3 = re.compile(r'<h3[^>]*>([\s\S]*?)</h3>', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]*)"', re.I)
_RE_PIC_SRC = re.compile(r'data-src="([^"]*)"', re.I)
_RE_IMG_SRC = re.compile(r'\bsrc="([^"]*)"', re.I)
_RE_REMARK = re.compile(
    r'<span class="absolute[^"]*text-right[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
# 搜索卡片：右上标签角标（4k/HD/院线）与左上年份，均为 div
_RE_REMARK_TAG = re.compile(
    r'<div class="absolute top-2 right-2[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_SEARCH_YEAR = re.compile(
    r'<div class="absolute top-2 left-2[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_RATING = re.compile(
    r'<span class="text-green-500[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_BLURB = re.compile(
    r'<p class="[^"]*line-clamp-2[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_DATA_SUB = re.compile(r'data-subtitle="([^"]*)"', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_POSTER_IMG = re.compile(
    r'<div class="flex gap-3 movie-poster">[\s\S]*?<img[^>]*src="([^"]*)"', re.I)
_RE_FIELD = re.compile(
    r'<div class="col-span-1 text-gray-500">([^<]+)</div>\s*'
    r'<div class="col-span-2 text-gray-300">([\s\S]*?)</div>', re.I)
_RE_INTRO = re.compile(
    r'<p class="text-xs text-gray-300 leading-relaxed">([\s\S]*?)</p>', re.I)
_RE_YEAR = re.compile(r'text-gray-400">(\d{4})<', re.I)
_RE_EPCOUNT = re.compile(r'共\s*(\d+)\s*集')
_RE_USERLINK = re.compile(r"userlink:'([^']*)'")
_RE_LINES = re.compile(r"lineName:\s*'([^']+)',\s*episodeCount:\s*\d+")
_RE_EP_BLOCK = re.compile(r'<a\b[\s\S]*?</a>', re.I)
_RE_EP_HREF = re.compile(r'href="/play/([a-z0-9]+)"', re.I)
_RE_EP_LINE = re.compile(r'data-line="(\d+)"', re.I)
_RE_EP_NO = re.compile(r'data-episode="(\d+)"', re.I)
_RE_EP_ID = re.compile(r'dataid="(\d+)"', re.I)
_RE_EP_SPAN = re.compile(r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)


class Spider(Spider):

    # ---------- 基础 ----------
    def getName(self):
        return "两个BT影视"

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
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    def _fetch(self, url, timeout=15, headers=None, retries=3):
        last = ""
        for attempt in range(retries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self.fetch(url, headers=h, timeout=timeout)
                if hasattr(rsp, "text"):
                    last = rsp.text or ""
                elif hasattr(rsp, "content"):
                    last = rsp.content.decode("utf-8", "ignore")
                else:
                    last = str(rsp)
                if last and "upstream connect error" not in last:
                    return last
            except Exception as e:
                self.log("fetch FAIL", url, e)
            if attempt < retries - 1:
                time.sleep(0.6 * (attempt + 1))
        return last

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
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
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        return any(k in pic for k in ("placeholder", "loading", "blank", "default.svg"))

    # ---------- 列表卡片 ----------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        # 按 slug 有序去重；同一 slug 在主卡/悬浮层/轮播重复出现，只取一次
        order = []
        for m in _RE_PLAY.finditer(html):
            slug = m.group(1)
            if slug not in seen:
                seen.add(slug)
                order.append((slug, m.start()))

        for slug, pos in order:
            block = html[max(0, pos - 200):pos + 4000]

            mt = _RE_H3.search(block)
            name = self._clean(mt.group(1)) if mt else ""
            if not name:
                mt = _RE_ALT.search(block)
                name = self._clean(mt.group(1)) if mt else ""
            if not name:
                mt = _RE_DATA_TITLE.search(block)
                name = self._clean(mt.group(1)) if mt else ""
            if not name:
                continue

            mp = _RE_PIC_SRC.search(block)
            if not mp:
                mp = _RE_IMG_SRC.search(block)
            pic = self._fix_url(mp.group(1).replace("&amp;", "&")) if mp else self.default_pic
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

            mr = _RE_REMARK.search(block)
            remarks = self._clean(mr.group(1)) if mr else ""
            if not remarks:
                mr = _RE_REMARK_TAG.search(block)
                remarks = self._clean(mr.group(1)) if mr else ""
            if not remarks:
                mr = _RE_RATING.search(block)
                remarks = self._clean(mr.group(1)) if mr else ""

            mb = _RE_BLURB.search(block)
            subtitle = self._clean(mb.group(1)) if mb else ""
            if not subtitle:
                mb = _RE_DATA_SUB.search(block)
                subtitle = self._clean(mb.group(1)) if mb else ""
            if not subtitle:
                my = _RE_SEARCH_YEAR.search(block)
                subtitle = self._clean(my.group(1)) if my else ""

            videos.append({
                "vod_id": slug,
                "vod_name": name[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": subtitle,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in re.findall(r'page=(\d+)', html)]
        if pages:
            return max(pages)
        return 9999

    # ---------- 筛选 URL ----------
    def _filter_url(self, tid, extend, page):
        q = {"classify": tid}
        if extend.get("areas"):
            q["areas"] = extend["areas"]
        if extend.get("types"):
            q["types"] = extend["types"]
        if extend.get("years"):
            q["years"] = extend["years"]
        if extend.get("tags"):
            q["tags"] = extend["tags"]
        if extend.get("sort"):
            q["sort_by"] = extend["sort"]
            q["order"] = "desc"
        if page and page > 1:
            q["page"] = page
        return self.site_url + "/filter?" + urllib.parse.urlencode(q)

    # ---------- 首页 / 分类 / 搜索 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._filter_url(tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        url = "%s/search?q=%s" % (self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        return {
            "list": videos, "page": page,
            "pagecount": 1, "limit": 20, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        slug = vod_id.split("@")[-1]
        if vod_id.startswith("http"):
            url = vod_id
            slug = _RE_PLAY.search(vod_id)
            slug = slug.group(1) if slug else slug
        else:
            url = self.site_url + "/play/" + slug
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 片名
        name = ""
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("-")[0].split("两个BT")[0])
        name = name.strip() or slug

        # 封面
        pic = self.default_pic
        mp = _RE_POSTER_IMG.search(html)
        if mp:
            pic = self._fix_url(mp.group(1)) or self.default_pic
        if self._is_placeholder_pic(pic):
            mo = _RE_OG_IMG.search(html)
            if mo:
                pic = self._fix_url(mo.group(1))
        if self._is_placeholder_pic(pic):
            pic = self.default_pic

        # 元信息栅格
        fields = {}
        for mf in _RE_FIELD.finditer(html):
            label = self._clean(mf.group(1))
            value = self._clean(mf.group(2))
            if label and value:
                fields[label] = value

        director = fields.get("导演", "")
        actor = fields.get("主演", "")
        area = fields.get("地区", "")
        classify = fields.get("类型", "")
        year = ""
        my = re.search(r"(\d{4})", fields.get("上映", ""))
        if my:
            year = my.group(1)
        if not year:
            # 海报区段内的纯年份 span（避开封面 URL 里的上传年份）
            ps = re.search(r'movie-poster[\s\S]*?(?=剧情简介|</div>\s*</div>)', html)
            seg = ps.group(0) if ps else html
            my = _RE_YEAR.search(seg)
            if my:
                year = my.group(1)
        if not year:
            my = _RE_YEAR.search(html)
            if my:
                year = my.group(1)

        # 简介
        content = ""
        mi = _RE_INTRO.search(html)
        if mi:
            content = self._clean(mi.group(1))
        if not content:
            md = _RE_META_DESC.search(html)
            if md:
                content = self._clean(md.group(1))
        content = re.sub(r"^(剧情简介|简介)[：:]\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 线路与选集 =====
        line_names = _RE_LINES.findall(html)
        if not line_names:
            line_names = ["alists"]

        # line(1-based) -> [(ep_no, name, dataid, slug)]
        lines = {}
        for mo in _RE_EP_BLOCK.finditer(html):
            block = mo.group(0)
            if "dataid=" not in block:
                continue
            mh = _RE_EP_HREF.search(block)
            md2 = _RE_EP_ID.search(block)
            if not mh or not md2:
                continue
            ep_slug = mh.group(1)
            ml = _RE_EP_LINE.search(block)
            me = _RE_EP_NO.search(block)
            line_no = int(ml.group(1)) if ml else 1
            ep_no = int(me.group(1)) if me else len(lines.get(line_no, [])) + 1
            ms = _RE_EP_SPAN.search(block)
            ep_text = self._clean(ms.group(1)) if ms else ""
            if not ep_text:
                head = re.match(r'<a\b[\s\S]*?>', block)
                ep_text = self._clean(block[head.end():]) if head else ""
            ep_name = ep_text or ("第%d集" % ep_no)
            lines.setdefault(line_no, []).append(
                (ep_no, ep_name, md2.group(1), ep_slug))

        play_from, play_url = [], []
        for idx, eps in sorted(lines.items()):
            eps.sort(key=lambda x: x[0])
            base = line_names[idx - 1] if idx - 1 < len(line_names) else ("线路%d" % idx)
            line_name = base
            i = 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join(
                "%s$%s@%s" % (n, dataid, ep_slug)
                for _, n, dataid, ep_slug in eps))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        ep_count = sum(len(v) for v in lines.values())
        remarks = ""
        mc = _RE_EPCOUNT.search(html)
        if mc:
            remarks = "共%s集" % mc.group(1)
        if not remarks:
            remarks = "%d集" % ep_count

        return {"list": [{
            "vod_id": slug,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks,
            "vod_area": area,
            "vod_year": year,
            "vod_classify": classify,
            "type_name": classify,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放签名 ----------
    @staticmethod
    def _enc_k(play_key):
        if not play_key or play_key == "0":
            return "0"
        pb = play_key.encode("utf-8")
        x = bytes(b ^ _SECRET[i % len(_SECRET)] for i, b in enumerate(pb))
        return base64.urlsafe_b64encode(x).decode()

    def _sign_url(self, dataid, slug, play_key, quality="1080"):
        t = str(int(time.time() * 1000))
        msg = "%s:%s:%s" % (dataid, t, slug)
        s = hmac.new(slug.encode("utf-8"), msg.encode("utf-8"),
                     hashlib.sha256).hexdigest()[:32]
        k = self._enc_k(play_key)
        qs = urllib.parse.urlencode({
            "p": dataid, "v": slug, "q": quality,
            "s": s, "t": t, "k": k,
        })
        return self.site_url + "/video/play?" + qs

    @staticmethod
    def _pick_quality(quality_urls):
        """按站点顺序选第一条有效直链；优先 1080/超清，跳过锁定/空 url。"""
        if not quality_urls:
            return ""
        valid = [q for q in quality_urls
                 if q.get("url") and str(q.get("url")) not in ("1", "")]
        if not valid:
            return ""
        for q in valid:
            br = str(q.get("bitrate") or "")
            title = str(q.get("title") or "")
            if br == "1080" or "1080" in title or "超清" in str(q.get("description") or ""):
                return str(q["url"])
        return str(valid[0]["url"])

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        now = int(time.time())
        if raw in self._play_cache:
            ts, res = self._play_cache[raw]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # id 形态：<dataid>@<slug>；兜底 http 播放页
        if "@" in raw:
            dataid, slug = raw.split("@", 1)
            detail_url = self.site_url + "/play/" + slug
        elif raw.startswith("http"):
            detail_url = raw
            mp = _RE_PLAY.search(raw)
            slug = mp.group(1) if mp else ""
            dataid = ""
        else:
            detail_url = self.site_url + "/play/" + raw
            slug = raw
            dataid = ""

        # 取本集页面内联 userlink（每次刷新随机，须实时抓取）
        play_key = "0"
        html = self._fetch(detail_url, headers=header)
        mu = _RE_USERLINK.search(html)
        if mu and mu.group(1):
            play_key = mu.group(1)

        # 未带 dataid 时，从页面选集里按当前 slug 反查 dataid
        if not dataid and slug:
            for mo in _RE_EP_BLOCK.finditer(html):
                block = mo.group(0)
                mh = _RE_EP_HREF.search(block)
                if mh and mh.group(1) == slug:
                    md2 = _RE_EP_ID.search(block)
                    if md2:
                        dataid = md2.group(1)
                        break

        stream = ""
        if dataid and slug:
            try:
                play_url = self._sign_url(dataid, slug, play_key)
                self.log("play: %s" % play_url[:160])
                rsp = self.fetch(play_url, headers=header, timeout=15)
                body = rsp.text if hasattr(rsp, "text") else \
                    rsp.content.decode("utf-8", "ignore")
                j = json.loads(body)
                if j.get("code") == 200 and j.get("data"):
                    stream = self._pick_quality(
                        j["data"].get("quality_urls"))
            except Exception as e:
                self.log("签名播放失败: %s" % e)

        if stream:
            stream = self._fix_url(stream)
            stream = self._resolve_sub_stream(stream, header)
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[raw] = (now, res)
            self.log("  => 直链: %s" % stream[:160])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": detail_url, "header": header}
        self._play_cache[raw] = (now, res)
        return res

    def _resolve_sub_stream(self, url, header):
        """master 多码率→第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
        if not url or ".mp4" in url.lower():
            return url

        def _get(target):
            last = None
            for _ in range(2):
                try:
                    rs = self.fetch(target, headers=header, timeout=10)
                    if getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?"))
                except Exception as e:
                    last = e
            return None, last

        try:
            rm, err = _get(url)
            if err is not None:
                return url
            text = rm.text if hasattr(rm, "text") else ""
            if "#EXT-X-STREAM-INF" not in text:
                return url
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _get(sub)
                    if rs is not None:
                        return sub
                    break
        except Exception as e:
            self.log("子流解析回退:", e)
        return url

    # ---------- 其余契约 ----------
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
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"})
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, rsp.content, ""]
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
