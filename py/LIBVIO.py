# coding=utf-8
"""
LIBVIO libvio.cam | TVBox Python 爬虫
关键:
  - 站点是 MacCMS10 + libvio 模板，带 UA + Referer 直取即可
  - 列表/筛选入口 /show/{12 槽位}.html
    槽位顺序: 分类-地区-排序-类型-语言-空-空-空-页码-空-空-年份
  - 分类沿用站点 5 大类，站内“分类”子类(动作/喜剧... = /show/6..)走筛选首行
  - 详情页按 h3 线路标题 + 其下选集 ul 的顺序输出线路与剧集
  - 副标题取卡片 .pic-text text-right
  - 播放页 player_aaaa 的 encrypt=3 是站点第三方 smartplay 加密 token，
    走 parse=1 交回 App 用站点播放器原样解析
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
                print("[libvio]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.libvio.cam"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/libvio/statics/img/load.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "纪录片"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "综艺"},
]

_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

# 站点筛选面板原始数据（名称与顺序与站点一致）
_F_T1 = {
    "class": [("动作", "6"), ("喜剧", "7"), ("爱情", "8"), ("科幻", "9"),
              ("恐怖", "10"), ("剧情", "11"), ("战争", "12")],
    "type": ["爱情", "奇幻", "喜剧", "动作", "科幻", "武侠", "冒险", "惊悚",
             "恐怖", "犯罪", "动画", "剧情", "悬疑", "战争", "家庭", "运动",
             "灾难", "传记", "历史", "短片", "西部", "纪录片", "歌舞", "古装",
             "音乐", "剧情片", "儿童", "真人秀"],
    "area": ["大陆", "香港", "台湾", "日本", "美国", "英国", "韩国", "西班牙",
             "泰国", "法国", "丹麦", "智利", "土耳其", "德国", "瑞典", "印度",
             "新西兰", "爱尔兰", "比利时", "希腊", "澳大利亚", "芬兰", "巴西",
             "俄罗斯", "加拿大", "意大利", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["国语", "粤语", "日语", "英语", "韩语", "夏威夷语", "法语", "德语",
             "丹麦语", "西班牙语", "耳其语", "印地语", "芬兰语", "四川乐山话",
             "俄语", "意大利语", "汉语普通话", "闽南语", "其它"],
}

_F_T2 = {
    "class": [("国产剧", "13"), ("港台剧", "14"), ("日韩剧", "15"), ("海外剧", "16")],
    "type": ["喜剧", "科幻", "悬疑", "欧美", "剧情", "奇幻", "古装", "动作",
             "犯罪", "冒险", "惊悚", "恐怖", "历史", "爱情", "音乐", "家庭",
             "国产", "运动", "动画", "西部", "战争", "传记", "灾难", "纪录片",
             "短片", "海外", "真人秀"],
    "area": ["美国", "韩国", "英国", "日本", "大陆", "台湾", "德国", "哥伦比亚",
             "意大利", "西班牙", "丹麦", "挪威", "法国", "香港", "泰国", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["英语", "韩语", "日语", "国语", "德语", "西班牙语", "意大利语",
             "那不勒", "挪威语", "其它"],
}

_F_T3 = {
    "class": [],
    "type": ["科幻", "纪录片", "欧美", "犯罪", "记录", "喜剧", "真人秀", "音乐",
             "歌舞", "动画", "历史", "传记", "悬疑", "运动", "短片", "剧情",
             "家庭", "冒险", "灾难"],
    "area": ["大陆", "英国", "日本", "韩国", "美国", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
}

_F_T4 = {
    "class": [("国产动漫", "24"), ("日韩动漫", "25"), ("港台动漫", "26"), ("欧美动漫", "27")],
    "type": ["动画", "日韩动漫", "喜剧", "剧情", "科幻", "家庭", "奇幻", "冒险",
             "欧美动漫", "动作", "悬疑", "犯罪", "爱情", "惊悚", "灾难", "音乐",
             "恐怖", "战争", "运动", "歌舞", "古装", "历史", "短片", "国产动漫",
             "战斗"],
    "area": ["大陆", "日本", "美国", "韩国", "西班牙", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["日语", "英语", "国语", "韩语", "其它"],
}

_F_T5 = {
    "class": [("大陆综艺", "17"), ("港台综艺", "18"), ("日韩综艺", "20"), ("欧美综艺", "21")],
    "type": [],
    "area": [],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": [],
}

_F_MAP = {"1": _F_T1, "2": _F_T2, "3": _F_T3, "4": _F_T4, "5": _F_T5}


def _opts(names):
    out = [{"n": "全部", "v": ""}]
    for x in names:
        out.append({"n": x, "v": x})
    return out


def _build_filters():
    filters = {}
    for c in CLASSES:
        tid = c["type_id"]
        f = _F_MAP[tid]
        rows = []
        cls = f["class"]
        if cls:
            rows.append({"key": "class", "name": "分类",
                         "value": [{"n": "全部", "v": ""}] +
                                  [{"n": n, "v": v} for n, v in cls]})
        else:
            rows.append({"key": "class", "name": "分类",
                         "value": [{"n": "全部", "v": ""}]})
        rows.append({"key": "type", "name": "类型", "value": _opts(f["type"])})
        rows.append({"key": "area", "name": "地区", "value": _opts(f["area"])})
        rows.append({"key": "year", "name": "年份", "value": _opts(f["year"])})
        rows.append({"key": "lang", "name": "语言", "value": _opts(f["lang"])})
        rows.append({"key": "sort", "name": "排序", "value": list(_SORTS)})
        filters[tid] = rows
    return filters


FILTERS = _build_filters()

# ===================== 正则 =====================
_RE_COMMENT = re.compile(r"<!--[\s\S]*?-->", re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_PAGECOUNT = re.compile(r'class="active num"><a>(\d+)/(\d+)</a>')
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.S)
_RE_DETAIL_PIC = re.compile(
    r'<a class="pic" href="[^"]*" title="[^"]*">\s*'
    r'<img[^>]*?data-original="([^"]*)"', re.S)
_RE_DATA_TYPE = re.compile(
    r'类型：([\s\S]*?) / 地区：([\s\S]*?) / 年份：([\s\S]*?) / 上映：([^<]*)')
_RE_ACTOR_DIR = re.compile(r'主演：([\s\S]*?) / 导演：([\s\S]*?)</p>')
_RE_SCORE = re.compile(r'<span class="douban"[^>]*>([\d.]+)</span>')
_RE_INTRO_FULL = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>')
_RE_INTRO_SKETCH = re.compile(r'<span class="detail-sketch"[^>]*>([\s\S]*?)</span>')
_RE_LINE = re.compile(
    r'<h3[^>]*>([\s\S]*?)</h3>[\s\S]{0,300}?'
    r'<ul class="stui-content__playlist[\s\S]*?</ul>', re.S)
_RE_LINE_A = re.compile(r'<a href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.S)
_RE_PLAYER_AA = re.compile(r"var player_aaaa=(\{[\s\S]*?\});\s*</script>")


class Spider(Spider):

    def getName(self):
        return "LIBVIO"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=20):
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
        s = _RE_TAG.sub("", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------- 列表 ----------
    def _build_show_url(self, tid, page, ext):
        seg = [
            str(tid),
            ext.get("area") or "",
            ext.get("sort") or "time",
            ext.get("type") or "",
            ext.get("lang") or "",
            "", "", "",
            str(page) if page > 1 else "",
            "", "",
            ext.get("year") or "",
        ]
        return "%s/show/%s.html" % (self.site_url, "-".join(seg))

    def _page_count(self, html):
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                return 1
        return 1

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        html = _RE_COMMENT.sub("", html)
        for ch in html.split('class="stui-vodlist__box"')[1:]:
            m = re.search(
                r'href="/detail/(\d+)\.html" title="([^"]*)"[\s\S]{0,400}?'
                r'data-original="([^"]*)"', ch, re.S)
            if not m:
                continue
            vid, name, pic = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            remarks = ""
            rm = re.search(r'<span class="pic-text text-right">([\s\S]*?)</span>', ch)
            if rm:
                remarks = self._clean(rm.group(1))
            videos.append({
                "vod_id": "/detail/%s.html" % vid,
                "vod_name": self._clean(name),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

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
            if extend[k] in ("", None, "全部"):
                del extend[k]

        # 站点“分类”=子分类 id，直接替换 type_id；“类型”走 URL 槽位4
        sub_type = extend.get("class") or ""
        if sub_type:
            tid = sub_type

        url = self._build_show_url(tid, page, extend)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 12, "total": pagecount * 12,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page <= 1:
            url = "%s/search/%s-------------.html" % (self.site_url, kw)
        else:
            url = "%s/search/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        return {
            "list": self._extract_videos(html), "page": page,
            "pagecount": self._page_count(html),
            "limit": 12, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}
        html = _RE_COMMENT.sub("", html)

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0])
        name = re.sub(r"\s*(高清|HD|BD)\s*$", "", name).strip() or vod_id

        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic

        vod_type = area = year = release = ""
        m = _RE_DATA_TYPE.search(html)
        if m:
            vod_type = self._clean(m.group(1))
            area = self._clean(m.group(2))
            year = self._clean(m.group(3))
            release = self._clean(m.group(4))

        director = ""
        actor = ""
        m = _RE_ACTOR_DIR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))
            director = self._clean(m.group(2))

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 简介（优先全量 detail-content）
        content = ""
        m = _RE_INTRO_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_SKETCH.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 线路 + 选集（完全按站点 h3 顺序）
        play_from = []
        play_url = []
        for m in _RE_LINE.finditer(html):
            line_name = self._clean(m.group(1))
            eps = []
            for a in _RE_LINE_A.finditer(m.group(0)):
                href = self._fix_url(a.group(1))
                ep = self._clean(a.group(2)) or str(len(eps) + 1)
                eps.append("%s$%s" % (ep, href))
            if not eps:
                continue
            play_from.append(line_name or ("线路%d" % (len(play_from) + 1)))
            play_url.append("#".join(eps))

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_area": area,
            "vod_year": year,
            "vod_remarks": "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        # 少数线路若是 encrypt=1/2 的明文直链，能解就直接直链
        direct = self._direct_url(self._fetch(play_page))
        if direct:
            res = {
                "parse": 0, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % direct[:160])
            return res

        # 站点 encrypt=3：加密 token 由站点播放器向 smartplay 接口换取，
        # 交回 App 按站点原样解析
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _direct_url(self, html):
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            return ""
        try:
            data = json.loads(m.group(1).replace("\\/", "/"))
        except Exception:
            return ""
        raw = data.get("url") or ""
        enc = str(data.get("encrypt") or "0")
        if not raw:
            return ""
        try:
            if enc == "1":
                raw = urllib.parse.unquote(raw)
            elif enc == "2":
                import base64
                raw = urllib.parse.unquote(base64.b64decode(
                    raw + "=" * ((4 - len(raw) % 4) % 4)).decode("utf-8", "ignore"))
            elif enc != "0":
                return ""
        except Exception:
            return ""
        if raw.startswith("http") and (".m3u8" in raw or ".mp4" in raw):
            return raw
        return ""

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
