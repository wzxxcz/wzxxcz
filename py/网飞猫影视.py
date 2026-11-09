# coding=utf-8
"""
网飞猫影视 allurespabeauty.com | TVBox Python 爬虫
全部基于实抓页面源码校对（2026-11 校验）：

  分类/筛选：/search.php?searchtype=5&tid={tid}&area=&year=&order=&page=N
            每页 36 条；尾页数字取 <span class="num">1/1669</span>
  静态分类：/all/{tid}.html、/all/{tid}-{page}.html（不支持筛选，仅备用）
  详情：    /uty/{id}.html
            - 标题 <h3 class="title">，简介 <div class="stui-content__desc">
            - 剧集在 <mip-vd-tabs> 内：先一个线路名 <ul><li>名称</li>，
              随后若干个 <ul class="stui-content__playlist"> 按线路顺序排列
  播放：    /play/{id}-{sid}-{ep}.html
            - <mip-iframe src="/js/player/dmplayer/player/index.php?url=<m3u8>">
            - 部分剧集该 url 为空（站方坏链），此时交回 TVBox 嗅探

注意：search.php 有 JS Cookie 校验（idc_search_browser），
      不带 Cookie 直接请求只会返回 733 字节的“正在验证浏览器”页。
      本爬虫会自动取 Cookie 并附 _idc_pass 重试，因此分类/搜索必须走 search.php。
"""
import re
import sys
import json
import time
import random
import string
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
                print("[wangfeimao]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.allurespabeauty.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/pic/nopic.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_SIZE = 36          # 站点列表每页固定 36 条（实测）
IDC_TTL = 1500          # Cookie 有效期 30 分钟，留 60 秒余量

# ===================== 分类 =====================
CLASSES = [
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

# 顶层分类下的子分类 tid -> 名称（首页“更多”里的小类链接，已逐个实抓确认有数据）
_SUB_CLASS = {
    "2": [("13", "国产剧"), ("14", "香港剧"), ("15", "台湾剧"), ("16", "欧美剧"),
          ("25", "韩国剧"), ("26", "日本剧"), ("27", "泰国剧"), ("28", "海外剧"),
          ("29", "短剧")],
    "1": [("5", "动作片"), ("6", "喜剧片"), ("7", "爱情片"), ("8", "科幻片"),
          ("9", "恐怖片"), ("10", "剧情片"), ("11", "战争片"), ("12", "纪录片")],
    "3": [("30", "大陆综艺"), ("31", "港台综艺"), ("32", "日韩综艺"), ("33", "欧美综艺")],
    "4": [("34", "大陆动漫"), ("35", "日本动漫"), ("36", "欧美动漫"), ("37", "海外动漫"),
          ("38", "动画片")],
}

# 地区筛选：站方筛选栏只给了“大陆/香港/台湾/日本/韩国/欧美/泰国/其他”，
# 但实测 area=欧美 恒返回 0 条（数据里存的是具体国家），故按实际有数据的值给选项。
_AREAS_BASE = ["大陆", "香港", "台湾", "日本", "韩国", "美国", "英国", "法国",
               "德国", "加拿大", "澳大利亚", "西班牙", "意大利", "印度",
               "俄罗斯", "泰国"]
_AREAS_EXTRA = {
    "2": ["新加坡", "马来西亚", "其他"],
    "1": ["新加坡", "马来西亚", "其他"],
    "3": [],                      # 综艺 area=其他 实测 0 条
    "4": ["欧美"],                 # 动漫才有“欧美”这个聚合值
}


def _areas_for(tid):
    return ([{"n": "全部", "v": ""}] +
            [{"n": a, "v": a} for a in _AREAS_BASE + _AREAS_EXTRA.get(tid, [])])
# 站点年份筛选实测为 2026 起向下，给到 2010
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
_SORTS = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hit"}, {"n": "推荐", "v": "commend"}]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _subs = [{"n": "全部", "v": ""}] + [{"n": n, "v": t} for t, n in _SUB_CLASS.get(_tid, [])]
    FILTERS[_tid] = [
        {"key": "tid", "name": "分类", "value": _subs},
        {"key": "area", "name": "地区", "value": _areas_for(_tid)},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "order", "name": "排序", "value": _SORTS},
    ]

# ===================== 正则 =====================
# 列表项切块：<li class="stui-vodlist__item"> ... </li>
_RE_ITEM = re.compile(r'<li[^>]*class="stui-vodlist__item[^"]*"[^>]*>([\s\S]*?)</li>', re.I)
_RE_ITEM_A = re.compile(
    r'<a[^>]*class="stui-vodlist__thumb[^"]*"[^>]*>', re.I)
_RE_HREF_TITLE = re.compile(r'href="(/uty/\d+\.html)"[^>]*title="([^"]*)"', re.I)
_RE_HREF_TITLE_R = re.compile(r'title="([^"]*)"[^>]*href="(/uty/\d+\.html)"', re.I)
_RE_IMG = re.compile(r'<mip-img[^>]*?(?:src|data-original)="([^"]+)"', re.I)
_RE_IMG_ANY = re.compile(r'(?:data-original|data-src|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', re.I)
_RE_PICTEXT = re.compile(r'<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)

# 首页顶部轮播（结构与普通卡片不同，用 mip-carousle-subtitle）
_RE_BANNER = re.compile(
    r'<a[^>]*href="(/uty/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
    r'[\s\S]{0,600}?<mip-img[^>]*?src="([^"]*)"'
    r'[\s\S]{0,300}?class="mip-carousle-subtitle"[^>]*>([^<]*)<', re.I)

# 分页：<span class="num">1/1669</span> 最准；尾页 <a href="?page=1669...">尾页</a>
_RE_PAGE_NUM = re.compile(r'<span[^>]*class="num"[^>]*>\s*\d+\s*/\s*(\d+)\s*</span>', re.I)
_RE_PAGE_TAIL = re.compile(r'href="[^"]*[?&]page=(\d+)[^"]*"[^>]*>\s*尾页', re.I)
_RE_PAGE_ANY = re.compile(r'[?&]page=(\d+)', re.I)

# 详情页
_RE_OG = re.compile(r'<meta\s+(?:property|name)="(og:[^"]+|description|keywords)"\s+content="([^"]*)"', re.I)
_RE_TITLE_TAG = re.compile(r'<(?:h1|h3)[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>([\s\S]*?)</(?:h1|h3)>', re.I)
_RE_DESC_DIV = re.compile(r'<div[^>]*class="stui-content__desc"[^>]*>([\s\S]*?)</div>', re.I)
_RE_DESC_P = re.compile(r'<p[^>]*class="desc[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', re.I)
_RE_DATA_YEAR = re.compile(r'年份：\s*</span>\s*(\d{4})', re.I)
_RE_DATA_AREA = re.compile(r'地区：\s*</span>\s*([^<\s]+)', re.I)
_RE_DATA_CLASS = re.compile(r'类型：\s*</span>\s*([^<\s]+)', re.I)

# 剧集区
_RE_TABS_BLOCK = re.compile(r'<mip-vd-tabs[^>]*>([\s\S]*?)</mip-vd-tabs>', re.I)
_RE_TAB_UL = re.compile(r'<ul>([\s\S]*?)</ul>', re.I)
_RE_TAB_LI = re.compile(r'<li>([^<]+)</li>', re.I)
_RE_PLAYLIST_UL = re.compile(
    r'<ul[^>]*class="stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*title="([^"]*)"[^>]*href="(/play/[^"]+?\.html)"', re.I)
_RE_EP_A_R = re.compile(
    r'<a[^>]*href="(/play/[^"]+?\.html)"[^>]*title="([^"]*)"', re.I)

# 播放页
_RE_IFRAME = re.compile(r'<mip-iframe[^>]*?src="([^"]+)"', re.I)
_RE_PLAY_SRC = re.compile(r'<div[^>]*class="stui-player__video[^"]*"[^>]*>([\s\S]{0,1200}?)</div>', re.I)

# 校验页 / 限流页
_RE_IDC = re.compile(r'document\.cookie="(idc_search_browser)=([0-9a-fA-F]+)', re.I)
_RE_IDC_PAGE = re.compile(r'idc_search_browser|正在验证浏览器', re.I)
_RE_LIMIT = re.compile(r'搜索限制为\s*\d+\s*秒|搜索太频繁|请稍后再试', re.I)


class Spider(Spider):

    def getName(self):
        return "网飞猫影视"

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
        self._idc = ""          # "idc_search_browser=xxx"
        self._idc_ts = 0.0
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础请求 ----------------
    def _raw(self, url, timeout=20, headers=None, allow_redirects=True):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            rsp = self.fetch(url, headers=h, timeout=timeout,
                             allow_redirects=allow_redirects)
        except TypeError:
            # 某些 TVBox 版本的 fetch 不认 allow_redirects
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout)
            except Exception as e:
                self.log("fetch FAIL %s -> %s" % (url, e))
                return ""
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

        if hasattr(rsp, "text"):
            text = rsp.text or ""
        elif hasattr(rsp, "content"):
            text = rsp.content.decode("utf-8", "ignore")
        else:
            text = str(rsp)

        # 部分站点返回 gbk 乱码，按中文特征纠一次
        if text and "\ufffd" not in text and "锟" in text[:3000]:
            try:
                text = text.encode("latin-1", "ignore").decode("gbk", "ignore")
            except Exception:
                pass
        return text

    def _is_idc_page(self, text):
        return bool(text) and len(text) < 2000 and _RE_IDC_PAGE.search(text)

    def _refresh_idc(self):
        """向 search.php 取一次校验 Cookie（校验页本身带 cookie 值）。"""
        html = self._raw(self.site_url + "/search.php?searchtype=5&tid=1&page=1")
        m = _RE_IDC.search(html or "")
        if m:
            self._idc = "%s=%s" % (m.group(1), m.group(2))
            self._idc_ts = time.time()
            self.log("idc cookie 已获取: %s" % self._idc[:32])
        else:
            self._idc = ""
        return self._idc

    def _idc_cookie(self):
        if self._idc and (time.time() - self._idc_ts) < IDC_TTL:
            return self._idc
        return self._refresh_idc()

    @staticmethod
    def _pass_token():
        # 站点只校验 cookie，_idc_pass 任意值即可（实测随机值同样通过）
        n = int(time.time() * 1000)
        d = "0123456789abcdefghijklmnopqrstuvwxyz"
        s = ""
        while n:
            s = d[n % 36] + s
            n //= 36
        return (s or "0") + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))

    def _fetch(self, url, timeout=20, headers=None, allow_redirects=True):
        text = self._raw(url, timeout=timeout, headers=headers, allow_redirects=allow_redirects)
        if not self._is_idc_page(text):
            return text

        # 命中 JS Cookie 校验页 -> 取 cookie 后带 _idc_pass 重试
        for _ in range(2):
            ck = self._idc_cookie()
            if not ck:
                break
            h = dict(headers or {})
            h["Cookie"] = ck
            sep = "&" if "?" in url else "?"
            retry_url = url + sep + "_idc_pass=" + self._pass_token()
            text2 = self._raw(retry_url, timeout=timeout, headers=h,
                              allow_redirects=allow_redirects)
            if not self._is_idc_page(text2):
                return text2
            self._idc = ""      # cookie 失效，下一轮重新取
            self._idc_ts = 0.0
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
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[\u200b-\u200f\u2028-\u202f\ufeff]", "", s)
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _clean_intro(self, s):
        """简介专用：额外清掉站方插入的 @广告@ 词。"""
        s = self._clean(s)
        s = re.sub(r"@[^@\n]{0,40}@", "", s)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip(" ，,。.、|/-")

    # ---------------- 列表解析 ----------------
    def _card_from_block(self, block):
        m = _RE_ITEM_A.search(block)
        if not m:
            return None
        a_tag = m.group(0)
        h = _RE_HREF_TITLE.search(a_tag)
        if h:
            href, title = h.group(1), h.group(2)
        else:
            h = _RE_HREF_TITLE_R.search(a_tag)
            if not h:
                return None
            title, href = h.group(1), h.group(2)

        pic = ""
        mi = _RE_IMG.search(block)
        if mi:
            pic = mi.group(1)
        if not pic or pic.endswith("nopic.gif"):
            mi = _RE_IMG_ANY.search(block)
            pic = mi.group(1) if mi else ""

        remark = ""
        mr = _RE_PICTEXT.search(block)
        if mr:
            remark = mr.group(1)

        return {
            "vod_id": href,
            "vod_name": self._clean(title)[:100],
            "vod_pic": self._fix_url(pic) or self.default_pic,
            "vod_remarks": self._clean(remark),
        }

    def _extract_videos(self, html, with_banner=False):
        videos = []
        seen = set()
        if not html:
            return videos

        def push(v):
            if not v or v["vod_id"] in seen:
                return
            seen.add(v["vod_id"])
            videos.append(v)

        if with_banner:
            for m in _RE_BANNER.finditer(html):
                push({
                    "vod_id": m.group(1),
                    "vod_name": self._clean(m.group(2) or m.group(4))[:100],
                    "vod_pic": self._fix_url(m.group(3)) or self.default_pic,
                    "vod_remarks": "推荐",
                })

        blocks = _RE_ITEM.findall(html)
        if not blocks:
            # 兜底：页面结构变了，只取 href + title
            for m in re.finditer(r'<a[^>]*href="(/uty/\d+\.html)"[^>]*title="([^"]*)"', html, re.I):
                push({
                    "vod_id": m.group(1),
                    "vod_name": self._clean(m.group(2))[:100],
                    "vod_pic": self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        for b in blocks:
            push(self._card_from_block(b))
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        m = _RE_PAGE_TAIL.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        nums = [int(x) for x in _RE_PAGE_ANY.findall(html)]
        return max(nums) if nums else 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML len=%d" % len(html))
        return {"list": self._extract_videos(html, with_banner=True)}

    def _list_url(self, tid, page, extend):
        params = {
            "searchtype": "5",
            "tid": str(tid),
            "page": str(page),
        }
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("order"):
            params["order"] = extend["order"]
        return "%s/search.php?%s" % (self.site_url, urllib.parse.urlencode(params))

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        # 子分类通过筛选的 tid 传入
        real_tid = extend.get("tid") or tid
        url = self._list_url(real_tid, page, extend)
        self.log("category: %s" % url)
        html = self._fetch(url)

        if not html or _RE_LIMIT.search(html):
            self.log("  空页或命中限流")
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": PAGE_SIZE, "total": 0}

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  videos=%d pagecount=%d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_SIZE, "total": pagecount * PAGE_SIZE,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)

        if html and _RE_LIMIT.search(html):
            self.log("  命中搜索限流，稍后重试一次")
            time.sleep(2)
            html = self._fetch(url)

        if not html:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": PAGE_SIZE, "total": 0}

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_SIZE, "total": pagecount * PAGE_SIZE,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML len=%d" % len(html))
        if not html or self._is_idc_page(html):
            return {"list": []}

        og = {}
        for m in _RE_OG.finditer(html):
            og[m.group(1).lower()] = self._clean(m.group(2))

        # 标题：og:title -> h3.title / h1.title
        name = og.get("og:title") or ""
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1))
        name = re.sub(r"\s*[\(（]\d{4}[\)）]\s*$", "", name).strip() or vod_id

        pic = og.get("og:image") or ""
        if not pic:
            m = _RE_IMG.search(html)
            pic = m.group(1) if m else ""
        pic = self._fix_url(pic) or self.default_pic

        director = og.get("og:video:director", "")
        actor = og.get("og:video:actor", "")
        vclass = og.get("og:video:class", "")
        varea = og.get("og:video:area", "")
        lang = og.get("og:video:language", "")

        m = _RE_DATA_YEAR.search(html)
        year = m.group(1) if m else ""
        if not year:
            m = re.search(r"于(\d{4})年(?:上映|播出|发行)", og.get("og:description", "") or "")
            year = m.group(1) if m else ""
        if not varea:
            m = _RE_DATA_AREA.search(html)
            varea = m.group(1) if m else ""
        if not vclass:
            m = _RE_DATA_CLASS.search(html)
            vclass = m.group(1) if m else ""

        # 简介：完整剧情区 -> 短简介 -> meta description -> og:description -> 基础信息兜底
        content = self._pick_intro(html, og, name, director, actor, varea, year, vclass)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        play_from, play_url = self._parse_playlists(html)
        self.log("  lines=%s" % play_from)

        # 更新状态：详情页首个 pic-text（如“更新至第16集”“全9集”）
        remarks = ""
        mr = _RE_PICTEXT.search(html)
        if mr:
            remarks = self._clean(mr.group(1))
        if not remarks:
            ep_total = 0
            for p in play_url:
                ep_total = max(ep_total, len(p.split("#")))
            remarks = ("共%d集" % ep_total) if ep_total > 1 else "HD"

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": varea,
            "vod_year": year,
            "vod_lang": lang,
            "vod_type": vclass,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    @staticmethod
    def _intro_ok(text, name):
        """判断简介是否有效：不能为空、不能只是片名/“片名在线观看”这类占位。"""
        if not text:
            return False
        t = text.strip()
        if len(t) < 15:
            return False
        if "详细" in t and len(t) < 22:
            return False
        n = (name or "").strip()
        if n:
            strip_rx = r"[\s\-—:：·、,，。.!！?？《》]"
            base = re.sub(strip_rx, "", t)
            nb = re.sub(strip_rx, "", n)
            if nb and (base == nb or base in (nb + "在线观看", nb + "在线看", nb + "剧情介绍", nb + "简介")):
                return False
        return True

    def _pick_intro(self, html, og, name, director, actor, area, year, vclass):
        # 1) 完整剧情区 <div class="stui-content__desc">
        m = _RE_DESC_DIV.search(html)
        if m:
            t = self._clean_intro(m.group(1))
            if self._intro_ok(t, name):
                return t
        # 2) 短简介 <p class="desc">（去掉“简介：”与“详细 >”）
        m = _RE_DESC_P.search(html)
        if m:
            t = self._clean_intro(m.group(1))
            t = re.sub(r"^\s*简介[：:]\s*", "", t)
            t = re.sub(r"\s*详细\s*>?\s*$", "", t).strip()
            if self._intro_ok(t, name):
                return t
        # 3) meta description（去掉“网飞猫影视_片名剧情介绍：”模板前缀）
        md = og.get("description", "")
        if not md:
            m = _RE_META_DESC.search(html)
            md = m.group(1) if m else ""
        md = self._clean_intro(md)
        md = re.sub(r"^[^_]{0,12}_[^：]{0,60}剧情介绍[：:]\s*", "", md)
        md = re.sub(r"^网飞猫[^_]{0,8}_?", "", md)
        if name:
            md = re.sub(r"(讲述的是)\s*" + re.escape(name), r"\1", md)
        md = re.sub(r"[，,、]?\s*讲述的是\s*[：:]?\s*$", "", md).strip()
        if self._intro_ok(md, name):
            return md
        # 4) og:description
        t = self._clean_intro(og.get("og:description", ""))
        if self._intro_ok(t, name):
            return t
        # 5) 站方根本没写简介时，用基础信息拼一句
        bits = []
        if director and director not in ("未知", "内详"):
            bits.append("%s执导" % director)
        if actor and actor not in ("未知", "内详"):
            al = [x for x in actor.split(",")[:3] if x]
            if al:
                bits.append("%s等主演" % "、".join(al))
        tail = "，".join([x for x in [area, (year + "年") if year else "", vclass] if x])
        s = "《%s》" % name
        if bits:
            s += "由" + "，".join(bits)
        s += ("，%s。" % tail) if tail else "。"
        return s

    def _parse_playlists(self, html):
        play_from, play_url = [], []
        if not html:
            return play_from, play_url

        block_m = _RE_TABS_BLOCK.search(html)
        block = block_m.group(1) if block_m else html

        # 线路名：剧集区里第一个 <ul>（tab 栏），其 li 文本即线路名
        names = []
        tab_m = _RE_TAB_UL.search(block)
        if tab_m:
            names = [self._clean(x) for x in _RE_TAB_LI.findall(tab_m.group(1))]
            names = [n for n in names if n]
        # 去重但保序
        seen_n, tmp = set(), []
        for n in names:
            if n not in seen_n:
                seen_n.add(n)
                tmp.append(n)
        names = tmp

        uls = _RE_PLAYLIST_UL.findall(block)
        for idx, ul_html in enumerate(uls):
            eps = []
            for m in _RE_EP_A.finditer(ul_html):
                ep_name = self._clean(m.group(1))
                href = m.group(2)
                if href.startswith("/"):
                    href = self.site_url + href
                if not ep_name:
                    ep_name = "第%02d集" % (len(eps) + 1)
                eps.append((ep_name, href))
            if not eps:
                continue
            line_name = names[idx] if idx < len(names) else ("线路%d" % (idx + 1))
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))
        return play_from, play_url

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags=None):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        cached = self._play_cache.get(play_page)
        if cached and now - cached[0] < 300:
            return cached[1]

        html = self._fetch(play_page, headers={"Referer": self.site_url + "/"})
        m3u8 = self._extract_m3u8(html)
        self.log("  m3u8=%s" % (m3u8[:160] if m3u8 else "EMPTY"))

        if m3u8:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            # 站方该集 url 为空（坏链）：把播放页交回 TVBox 嗅探
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        self._play_cache[play_page] = (now, res)
        return res

    def _extract_m3u8(self, html):
        if not html:
            return ""
        # 优先播放器容器内的 iframe
        src = ""
        box = _RE_PLAY_SRC.search(html)
        m = _RE_IFRAME.search(box.group(1) if box else html)
        if m:
            src = m.group(1).replace("&amp;", "&")
        if not src:
            return ""

        real = ""
        if "url=" in src:
            # 本站 url 是 iframe 的最后一个参数，直接取到末尾，避免 m3u8 自带 & 参数被截断
            real = src.split("url=", 1)[1]
        elif ".m3u8" in src.lower():
            real = src

        real = urllib.parse.unquote(real or "").strip()
        if not real:
            return ""
        if real.startswith("//"):
            real = "https:" + real
        if not real.startswith("http"):
            real = self._fix_url(real)
        return real if real.startswith("http") else ""

    # ---------------- 杂项 ----------------
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
        if not url:
            return False
        u = url.lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
