# coding=utf-8
"""
开心影院 kxyy TVBox Python 爬虫
自动探测主域名 + macCMS v10 + nby.php 两段式解析
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

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CANDIDATE_HOSTS = [
    "https://www.kxyyhd.com",
    "https://www.kxyy1.cc",
    "https://kxyy1.cc",
    "https://www.kxyy.tv",
    "https://www.kxyy.app",
    "https://www.kxyytv.com",
]

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

FILTERS = {}
for cid in ["1", "2", "3", "4", "26", "24"]:
    FILTERS[cid] = [
        {"key": "area", "name": "地区", "value": [{"n": a or "不限", "v": a} for a in _AREAS]},
        {"key": "year", "name": "年份", "value": [{"n": y or "不限", "v": y} for y in _YEARS]},
    ]

_RE_VID = re.compile(r'/voddetail/(\d+)\.html', re.I)

_RE_DETAIL_TITLE = re.compile(r'<h1[^>]*class="[^"]*d-none d-md-block[^"]*"[^>]*>([^<]+)</h1>', re.I)
_RE_DETAIL_TITLE_M = re.compile(r'<h2[^>]*class="[^"]*d-sm-block d-md-none[^"]*"[^>]*>([^<]+)</h2>', re.I)
_RE_DETAIL_PIC = re.compile(r'<div class="col-md-auto[^"]*"><img[^>]*src="([^"]+)"', re.I)
_RE_DETAIL_CONTENT = re.compile(r'<div class="card-body"><p>(.*?)</p></div>', re.S | re.I)
_RE_DETAIL_META = re.compile(r'<p class="[^"]*mb-0 mb-md-2[^"]*"><strong>([^：<]+)：</strong>(.*?)</p>', re.S | re.I)

# ★ 修正后的 TABS 正则：抓整个 <a> 内容
_RE_TABS = re.compile(
    r'<li class="nav-item">\s*<a href="#tabs-home-(\d+)"[^>]*>(.*?)</a>\s*</li>',
    re.S | re.I)
# 从 tab 内容里提取 badge 数字
_RE_TAB_BADGE = re.compile(r'<span class="badge">(\d+)</span>', re.I)

_RE_PANE = re.compile(r'<div class="tab-pane[^"]*" id="tabs-home-(\d+)">(.*?)</div>\s*</div>', re.S | re.I)

# 剧集按钮：详情页是 "btn btn-square"，播放页是 "btn btn-success btn-square"
_RE_EP_BTN = re.compile(
    r'<a class="btn[^"]*btn-square[^"]*"\s+href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I)

_RE_PLAYER_DATA = re.compile(r'var player_data=(\{.*?\});', re.S | re.I)
_RE_TAIL_PAGE = re.compile(r'href="[^"]*?(\d+)\.html"[^>]*>尾页</a>', re.I)


class Spider(Spider):

    def getName(self):
        return "开心影院"

    def init(self, extend=""):
        self.site_url = _CANDIDATE_HOSTS[0]
        self.headers = {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
        }
        for h in _CANDIDATE_HOSTS:
            try:
                rsp = self.fetch(h + "/", headers={'User-Agent': UA}, timeout=8)
                html = ""
                if hasattr(rsp, 'text'):
                    html = rsp.text
                elif hasattr(rsp, 'content'):
                    html = rsp.content.decode('utf-8', 'ignore')
                if html and '/voddetail/' in html:
                    self.site_url = h
                    self.headers['Referer'] = h + "/"
                    self.log("host picked: %s" % h)
                    break
            except Exception as e:
                self.log("host fail %s: %s" % (h, e))
        self.default_pic = self.site_url + "/images/img-bj-k.png"

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

    # ---------- 列表解析 ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_VID.finditer(html):
            vid = m.group(1)
            if vid in seen:
                continue

            start = max(0, m.start() - 400)
            end = min(len(html), m.end() + 500)
            ctx = html[start:end]

            title = ""
            tm = re.search(r'title="([^"]+)"', ctx, re.I)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'<h3[^>]*class="[^"]*card-title[^"]*"[^>]*>([^<]+)</h3>', ctx, re.I)
                if tm:
                    title = self._clean(tm.group(1))
            if not title:
                continue

            pic = self.default_pic
            pm = re.search(r'<img[^>]*?(?:data-src|src)="([^"]+)"', ctx, re.I)
            if pm:
                pic = self._fix_url(pm.group(1))

            remark = ""
            bm = re.search(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>([^<]+)</span>', ctx, re.I)
            if bm:
                remark = self._clean(bm.group(1))
            if not remark:
                rm = re.search(r'<(?:strong|div)[^>]*class="[^"]*ribbon[^"]*"[^>]*>([^<]+)</(?:strong|div)>', ctx, re.I)
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
        self.log("home videos: %d (html_len=%d)" % (len(videos), len(html) if html else 0))
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

        parts = [
            str(tid),
            urllib.parse.quote(area) if area else "",
            "",
            "",
            "",
            "",
            "",
            "",
            str(page) if page > 1 else "",
            "",
            "",
            year or "",
        ]
        path = "-".join(parts)
        url = f"{self.site_url}/vodshow/{path}.html"

        html = self._fetch(url)
        videos = self._extract_videos(html) if html else []
        pagecount = self._get_pagecount(html)
        if not videos:
            self.log("empty category: url=%s html_len=%d" % (url, len(html) if html else 0))

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
            self.log("detail page empty: %s" % url)
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

        # ---------- 播放线路（修正版）----------
        play_from = []
        play_url = []

        # 1) 抓所有 tab：<li ...><a href="#tabs-home-N" ...>内容(含 svg)</a></li>
        tabs = []
        for m in _RE_TABS.finditer(html):
            sid = m.group(1)
            tab_inner = m.group(2)
            bm = _RE_TAB_BADGE.search(tab_inner)
            if not bm:
                continue
            tab_name = self._clean(tab_inner)
            # 去掉名字末尾的 badge 数字（例如 "YX源 47" → "YX源"）
            tab_name = re.sub(r'\s*\d+\s*$', '', tab_name).strip()
            if not tab_name:
                tab_name = "线路%s" % sid
            tabs.append((sid, tab_name))

        self.log("detail tabs found: %d" % len(tabs))

        # 2) 抓所有 pane
        panes = _RE_PANE.findall(html)
        pane_dict = {pid: pcontent for pid, pcontent in panes}
        self.log("detail panes found: %d" % len(panes))

        for sid, tab_name in tabs:
            pane_content = pane_dict.get(sid, "")
            if not pane_content:
                self.log("pane %s empty" % sid)
                continue
            eps = []
            for ep_href, ep_name in _RE_EP_BTN.findall(pane_content):
                ep_name = self._clean(ep_name)
                if not ep_name:
                    continue
                eps.append(f"{ep_name}${ep_href}")
            self.log("pane %s eps: %d" % (sid, len(eps)))
            if eps:
                play_from.append(tab_name)
                play_url.append("#".join(eps))

        if not play_url:
            self.log("no play_url resolved")
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
    def _resolve_nby(self, from_key, raw_url, play_page_url):
        iframe_base = f"{self.site_url}/static/player/{from_key.lower()}.php"
        iframe_page = iframe_base + "?url=" + urllib.parse.quote(raw_url, safe='')

        try:
            self._fetch(iframe_page, timeout=8, headers={
                "User-Agent": UA,
                "Referer": play_page_url,
            })
        except Exception:
            pass

        step1_url = (
            iframe_base
            + "?get_signed_url=1&url="
            + urllib.parse.quote(raw_url, safe='')
        )
        step1_headers = {
            "User-Agent": UA,
            "Referer": play_page_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        text1 = self._fetch(step1_url, timeout=12, headers=step1_headers)
        self.log("step1 body: %s" % (text1[:200] if text1 else "EMPTY"))

        try:
            data1 = json.loads(text1)
        except Exception:
            data1 = None
        if not isinstance(data1, dict):
            self.log("step1 not json")
            return ""

        signed_url = data1.get("signed_url", "")
        if not signed_url:
            self.log("step1 no signed_url")
            return ""

        if signed_url.startswith("http://") or signed_url.startswith("https://"):
            step2_url = signed_url
        elif signed_url.startswith("//"):
            step2_url = "https:" + signed_url
        elif signed_url.startswith("/"):
            step2_url = self.site_url + signed_url
        elif signed_url.startswith("?"):
            step2_url = iframe_base + signed_url
        else:
            step2_url = iframe_base + "?" + signed_url

        step2_headers = {
            "User-Agent": UA,
            "Referer": iframe_page,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        text2 = self._fetch(step2_url, timeout=12, headers=step2_headers)
        self.log("step2 body: %s" % (text2[:200] if text2 else "EMPTY"))

        try:
            data2 = json.loads(text2)
        except Exception:
            data2 = None
        if not isinstance(data2, dict):
            self.log("step2 not json")
            return ""

        jmurl = data2.get("jmurl") or data2.get("url") or ""
        if jmurl:
            jmurl = jmurl.replace('\\/', '/')
            self.log("m3u8 got: %s" % jmurl[:120])
            return jmurl
        self.log("step2 no jmurl")
        return ""

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            play_url = id
        else:
            play_url = self._fix_url(id)

        play_url_main = play_url
        m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', play_url)
        if m:
            play_url_main = f"{self.site_url}/vodplay/{m.group(1)}-{m.group(2)}-{m.group(3)}.html"

        html = self._fetch(play_url_main)
        if not html:
            self.log("play page empty: %s" % play_url_main)
            return {"parse": 1, "url": play_url_main, "header": self.headers}

        m2 = _RE_PLAYER_DATA.search(html)
        if not m2:
            self.log("no player_data in page")
            return {"parse": 1, "url": play_url_main, "header": self.headers}

        try:
            data = json.loads(m2.group(1))
        except Exception as e:
            self.log("player_data parse error: %s" % e)
            return {"parse": 1, "url": play_url_main, "header": self.headers}

        encrypt = str(data.get("encrypt", "0"))
        raw_url = data.get("url", "")
        from_key = data.get("from", "")
        self.log("player_data: from=%s encrypt=%s url=%s" % (from_key, encrypt, raw_url[:60]))

        if encrypt == "1":
            raw_url = urllib.parse.unquote(raw_url)
        elif encrypt == "2":
            try:
                raw_url = base64.b64decode(raw_url).decode('utf-8', 'ignore')
            except Exception:
                pass

        if not raw_url:
            return {"parse": 1, "url": play_url_main, "header": self.headers}

        if any(ext in raw_url.lower() for ext in ['.m3u8', '.mp4']):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        if from_key and from_key.lower() not in ("", "parse"):
            try:
                real = self._resolve_nby(from_key, raw_url, play_url_main)
                if real:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": real,
                        "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                    }
            except Exception as e:
                self.log("nby resolve fail: %s" % e)

            iframe_url = (
                f"{self.site_url}/static/player/{from_key.lower()}.php?url="
                + urllib.parse.quote(raw_url, safe='')
            )
            return {
                "parse": 1,
                "playUrl": "",
                "url": iframe_url,
                "header": {"User-Agent": UA, "Referer": play_url_main},
            }

        return {"parse": 1, "url": play_url_main, "header": self.headers}

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
