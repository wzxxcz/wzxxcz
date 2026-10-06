# coding=utf-8
"""
开心影院 kxyy1.cc TVBox Python 爬虫
苹果CMS v10 模板 + 自建 nby.php 两段式解析
"""
import re
import sys
import json
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
                print("[kxyy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

HOST = "https://www.kxyy1.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/images/img-bj-k.png"

# ============ 分类 ============
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "26", "type_name": "短剧"},
    {"type_id": "24", "type_name": "纪录片"},
]

_AREAS = ["", "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "泰国", "英国", "法国", "德国", "意大利", "印度", "马来西亚"]
_YEARS = ["", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
          "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010",
          "2009", "2008", "2007", "2006", "2005", "2004", "2003", "2002",
          "2001", "2000", "90年代", "80年代", "70年代", "其他"]
_SORTS = [
    {"n": "更新时间", "v": "time"},
    {"n": "近期热门", "v": "hits_week"},
    {"n": "豆瓣评分", "v": "douban_score"},
]

FILTERS = {}
for cid in ["1", "2", "3", "4", "26", "24"]:
    FILTERS[cid] = [
        {"key": "area", "name": "地区", "value": [{"n": a or "不限", "v": a} for a in _AREAS]},
        {"key": "year", "name": "年份", "value": [{"n": y or "不限", "v": y} for y in _YEARS]},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]

# ============ 正则 ============
_RE_DETAIL_LINK = re.compile(
    r'<a[^>]*?href="(/voddetail/(\d+)\.html)"[^>]*?>(.*?)</a>',
    re.S | re.I)

_RE_DETAIL_TITLE = re.compile(r'<h1[^>]*class="[^"]*d-none d-md-block[^"]*"[^>]*>([^<]+)</h1>', re.I)
_RE_DETAIL_TITLE_M = re.compile(r'<h2[^>]*class="[^"]*d-sm-block d-md-none[^"]*"[^>]*>([^<]+)</h2>', re.I)
_RE_DETAIL_PIC = re.compile(r'<div class="col-md-auto[^"]*"><img[^>]*src="([^"]+)"', re.I)
_RE_DETAIL_CONTENT = re.compile(r'<div class="card-body"><p>(.*?)</p></div>', re.S | re.I)
_RE_DETAIL_META = re.compile(r'<p class="[^"]*mb-0 mb-md-2[^"]*"><strong>([^：<]+)：</strong>(.*?)</p>', re.S | re.I)

_RE_TABS = re.compile(
    r'<li class="nav-item"><a href="#tabs-home-(\d+)"[^>]*>([^<]+)&nbsp;<span class="badge">(\d+)</span></a></li>',
    re.I)
_RE_PANE = re.compile(r'<div class="tab-pane[^"]*" id="tabs-home-(\d+)">(.*?)</div>\s*</div>', re.S | re.I)
_RE_EP_BTN = re.compile(r'<a class="btn btn-square[^"]*"\s+href="([^"]+)"[^>]*>([^<]+)</a>', re.I)

_RE_PLAYER_DATA = re.compile(r'var player_data=(\{.*?\});', re.S | re.I)
_RE_TAIL_PAGE = re.compile(r'href="[^"]*?(\d+)\.html"[^>]*>尾页</a>', re.I)


class Spider(Spider):

    def getName(self):
        return "开心影院"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC

    # ---------- 网络 ----------
    def _fetch(self, url, timeout=15, headers=None):
        try:
            req_h = dict(self.headers)
            if headers:
                req_h.update(headers)
            rsp = self.fetch(url, headers=req_h, timeout=timeout)
            if hasattr(rsp, 'text'):
                return rsp.text
            if hasattr(rsp, 'content'):
                return rsp.content.decode('utf-8', 'ignore')
            return str(rsp)
        except Exception as e:
            self.log("fetch fail: %s - %s" % (url, e))
            return ""

    def _fetch_json(self, url, timeout=12, headers=None):
        text = self._fetch(url, timeout=timeout, headers=headers)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

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

    # ---------- 列表解析（更稳健）----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_DETAIL_LINK.finditer(html):
            href, vid, inner = m.groups()
            if vid in seen:
                continue

            a_start = m.start()
            a_end = m.end()
            a_tag = html[a_start:a_end]

            # 标题：优先 a 的 title 属性，其次 a 后面 card-body 的 h3
            title = ""
            tm = re.search(r'title="([^"]+)"', a_tag, re.I)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                tail = html[a_end:a_end + 800]
                tm = re.search(r'<h3[^>]*class="[^"]*card-title[^"]*"[^>]*>([^<]+)</h3>', tail, re.I)
                if tm:
                    title = self._clean(tm.group(1))
            if not title:
                title = self._clean(inner)
            if not title:
                continue

            # 图片
            pic = self.default_pic
            pm = re.search(r'<img[^>]*?(?:data-src|src)="([^"]+)"', inner, re.I)
            if pm:
                pic = self._fix_url(pm.group(1))

            # 备注
            remark = ""
            tail = html[a_end:a_end + 800]
            bm = re.search(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>([^<]+)</span>', tail, re.I)
            if bm:
                remark = self._clean(bm.group(1))
            if not remark:
                rm = re.search(r'<strong[^>]*class="[^"]*ribbon[^"]*"[^>]*>([^<]+)</strong>', a_tag, re.I)
                if rm:
                    remark = self._clean(rm.group(1))
            if not remark:
                rm = re.search(r'<div class="ribbon[^"]*">([^<]+)</div>', a_tag, re.I)
                if rm:
                    remark = self._clean(rm.group(1))

            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remark[:30],
            })
        return videos

    def _get_pagecount(self, html):
        if not html:
            return 1
        tm = _RE_TAIL_PAGE.search(html)
        if tm:
            return int(tm.group(1))
        # 从分页链接里找最大数字段
        pages = re.findall(r'vodshow/[^"]*?-(\d+)-[^"]*?\.html', html)
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

        area = extend.get("area", "")
        year = extend.get("year", "")
        by = extend.get("by", "time")

        # macCMS v10 12 段路径：
        # {id}-{area}-{by}-{class}-{lang}-{letter}-{?}-{?}-{page}-{?}-{?}-{year}
        parts = [
            str(tid),                                 # f1 频道 id
            urllib.parse.quote(area) if area else "", # f2 地区
            by or "",                                 # f3 排序
            "",                                       # f4 类型（暂未支持）
            "",                                       # f5 语言
            "",                                       # f6 字母
            "",                                       # f7
            "",                                       # f8
            str(page) if page > 1 else "",            # f9 页码
            "",                                       # f10
            "",                                       # f11
            year or "",                               # f12 年份
        ]
        path = "-".join(parts)
        url = f"{self.site_url}/vodshow/{path}.html"

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
        url = f"{self.site_url}/vodsearch/-------------.html?wd={keyword}"
        if page > 1:
            url += f"&page={page}"
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
        url = f"{self.site_url}/voddetail/{vid}.html"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = vid
        tm = _RE_DETAIL_TITLE.search(html) or _RE_DETAIL_TITLE_M.search(html)
        if tm:
            name = self._clean(tm.group(1))
            name = re.sub(r'\s*\(\d{4}\)\s*$', '', name)

        pic = self.default_pic
        pm = _RE_DETAIL_PIC.search(html)
        if pm:
            pic = self._fix_url(pm.group(1))

        content = ""
        cm = _RE_DETAIL_CONTENT.search(html)
        if cm:
            content = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！" + self._clean(cm.group(1))

        meta = {}
        for m in _RE_DETAIL_META.finditer(html):
            label = self._clean(m.group(1)).strip()
            val = self._clean(m.group(2)).strip()
            if label and val:
                meta[label] = val

        play_from = []
        play_url = []

        tabs = _RE_TABS.findall(html)
        panes = _RE_PANE.findall(html)
        pane_dict = {pid: pcontent for pid, pcontent in panes}

        for sid, tab_name, ep_count in tabs:
            tab_name = self._clean(tab_name)
            pane_content = pane_dict.get(sid, "")
            if not pane_content:
                continue
            eps = []
            for ep_href, ep_name in _RE_EP_BTN.findall(pane_content):
                ep_name = self._clean(ep_name)
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
            "vod_year": meta.get("首播", meta.get("年份", "")),
            "vod_area": meta.get("制片国家/地区", ""),
            "vod_lang": meta.get("语言", ""),
            "vod_type": meta.get("类型", ""),
            "vod_remarks": (meta.get("集数", "") and ("全" + meta["集数"] + "集")) or "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放解析 ----------
    def _resolve_nby(self, from_key, raw_url):
        """
        nby.php 两段式：
        1. GET {site}/static/player/{from}.php?get_signed_url=1&url=<encode(raw_url)>
           → {"signed_url": "..."}
        2. GET signed_url
           → {"urltype": "hls", "jmurl": "真实m3u8"}
        """
        iframe_base = f"{self.site_url}/static/player/{from_key.lower()}.php"

        step1_url = (
            iframe_base
            + "?get_signed_url=1&url="
            + urllib.parse.quote(raw_url, safe='')
        )
        step1_headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        data1 = self._fetch_json(step1_url, timeout=12, headers=step1_headers)
        if not data1:
            self.log("step1 no json: %s" % step1_url)
            return ""

        signed_url = data1.get("signed_url", "")
        if not signed_url:
            self.log("step1 no signed_url: %s" % data1)
            return ""

        if signed_url.startswith("//"):
            signed_url = "https:" + signed_url
        elif signed_url.startswith("/"):
            signed_url = self.site_url + signed_url

        step2_headers = {
            "User-Agent": UA,
            "Referer": step1_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        data2 = self._fetch_json(signed_url, timeout=12, headers=step2_headers)
        if not data2:
            self.log("step2 no json: %s" % signed_url)
            return ""

        jmurl = data2.get("jmurl") or data2.get("url") or ""
        if jmurl:
            jmurl = jmurl.replace('\\/', '/')
            return jmurl
        self.log("step2 no jmurl: %s" % data2)
        return ""

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            play_url = id
        else:
            play_url = self._fix_url(id)

        html = self._fetch(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}

        m = _RE_PLAYER_DATA.search(html)
        if not m:
            return {"parse": 1, "url": play_url, "header": self.headers}

        try:
            data = json.loads(m.group(1))
        except Exception:
            return {"parse": 1, "url": play_url, "header": self.headers}

        encrypt = str(data.get("encrypt", "0"))
        raw_url = data.get("url", "")
        from_key = data.get("from", "")

        if encrypt == "1":
            raw_url = urllib.parse.unquote(raw_url)
        elif encrypt == "2":
            try:
                raw_url = base64.b64decode(raw_url).decode('utf-8', 'ignore')
            except Exception:
                pass

        if not raw_url:
            return {"parse": 1, "url": play_url, "header": self.headers}

        # A. 已是 m3u8/mp4 直链
        if any(ext in raw_url.lower() for ext in ['.m3u8', '.mp4']):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        # B. nby.php 两段式解析
        if from_key and from_key.lower() not in ("", "parse"):
            try:
                real = self._resolve_nby(from_key, raw_url)
                if real:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": real,
                        "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                    }
            except Exception as e:
                self.log("nby resolve fail: %s" % e)

        # C. 兜底交给 TVBox 嗅探
        if from_key:
            iframe_url = (
                f"{self.site_url}/static/player/{from_key.lower()}.php?url="
                + urllib.parse.quote(raw_url, safe='')
            )
            return {
                "parse": 1,
                "playUrl": "",
                "url": iframe_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        return {"parse": 1, "url": play_url, "header": self.headers}

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
