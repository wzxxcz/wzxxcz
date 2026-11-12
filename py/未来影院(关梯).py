# coding=utf-8
"""
未来影院 gygxpt.com | TVBox Python 爬虫 
站点协议（实测）:
  - 分类: /gyglist/{tid}.html  (第1页) | /gyglist/{tid}-{pg}.html (翻页)
  - 详情: /gygvod/{vid}.html   -> og: 元数据 + #playNumTab 线路 + ul.play_num_list 选集
  - 播放: /gygplayer/{vid}-{sid}-{nid}.html -> var now="...m3u8" 直链
  - 搜索: /search.php?searchword={kw}&page={pn}
线路顺序: #playNumTab a 的 DOM 序，sid = tab 的 a.id - 1
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
                print("[gygxpt]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.gygxpt.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/templets/gygxpt/images/pic/1.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 实测分类表（41 个，已剔除 55 预告 / 60 亚洲剧）
CLASSES = [
    {"type_id": "1",   "type_name": "电影"},
    {"type_id": "2",   "type_name": "电视剧"},
    {"type_id": "3",   "type_name": "综艺"},
    {"type_id": "4",   "type_name": "动漫"},
    {"type_id": "30",  "type_name": "短剧"},
    {"type_id": "5",   "type_name": "动作片"},
    {"type_id": "6",   "type_name": "爱情片"},
    {"type_id": "7",   "type_name": "科幻片"},
    {"type_id": "8",   "type_name": "恐怖片"},
    {"type_id": "9",   "type_name": "战争片"},
    {"type_id": "10",  "type_name": "喜剧片"},
    {"type_id": "11",  "type_name": "纪录片"},
    {"type_id": "12",  "type_name": "剧情片"},
    {"type_id": "28",  "type_name": "悬疑片"},
    {"type_id": "29",  "type_name": "犯罪片"},
    {"type_id": "13",  "type_name": "国产剧"},
    {"type_id": "14",  "type_name": "港剧"},
    {"type_id": "15",  "type_name": "欧美剧"},
    {"type_id": "16",  "type_name": "韩剧"},
    {"type_id": "32",  "type_name": "台湾剧"},
    {"type_id": "33",  "type_name": "日本剧"},
    {"type_id": "34",  "type_name": "海外剧"},
    {"type_id": "42",  "type_name": "泰剧"},
    {"type_id": "45",  "type_name": "国产综艺"},
    {"type_id": "46",  "type_name": "日韩综艺"},
    {"type_id": "47",  "type_name": "港台综艺"},
    {"type_id": "48",  "type_name": "欧美综艺"},
    {"type_id": "49",  "type_name": "国产动漫"},
    {"type_id": "50",  "type_name": "日韩动漫"},
    {"type_id": "51",  "type_name": "欧美动漫"},
    {"type_id": "52",  "type_name": "动漫电影"},
    {"type_id": "53",  "type_name": "港台动漫"},
    {"type_id": "54",  "type_name": "海外动漫"},
    {"type_id": "61",  "type_name": "有声动漫"},
    {"type_id": "62",  "type_name": "女频恋爱"},
    {"type_id": "63",  "type_name": "反转爽剧"},
    {"type_id": "64",  "type_name": "脑洞悬疑"},
    {"type_id": "65",  "type_name": "年代穿越"},
    {"type_id": "66",  "type_name": "古装仙侠"},
    {"type_id": "67",  "type_name": "现代都市"},
    {"type_id": "69",  "type_name": "爽文短剧"},
]

DROP_TIDS = ("55", "60")

TYPE_PIDS = {
    "1": "0", "2": "0", "3": "0", "4": "0", "30": "0",
    "5": "1", "6": "1", "7": "1", "8": "1", "9": "1",
    "10": "1", "11": "1", "12": "1", "28": "1", "29": "1",
    "13": "2", "14": "2", "15": "2", "16": "2", "32": "2",
    "33": "2", "34": "2", "42": "2",
    "45": "3", "46": "3", "47": "3", "48": "3",
    "49": "4", "50": "4", "51": "4", "52": "4",
    "53": "4", "54": "4",
    "61": "30", "62": "30", "63": "30", "64": "30",
    "65": "30", "66": "30", "67": "30", "69": "30",
}

# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a\b[^>]*?href="(/gygvod/(\d+)\.html)"[^>]*>',
    re.I)

_RE_IMG = re.compile(
    r'<img[^>]*data-src="([^"]+)"'
    r'|<img[^>]*data-original="([^"]+)"'
    r'|<img[^>]*src="(https?://[^"\s]+)"',
    re.I)

_RE_TITLE = re.compile(r'title="([^"]*)"')
_RE_ALT = re.compile(r'<img[^>]*alt="([^"]*)"', re.I)
_RE_TIP = re.compile(r'class="[^"]*v-tips[^"]*"[^>]*>([^<]*)<')

# 详情
_RE_OG_TITLE = re.compile(r'property="og:title"\s+content="([^"]*)"', re.I)
_RE_OG_IMG = re.compile(r'property="og:image"\s+content="([^"]*)"', re.I)
_RE_OG_DESC = re.compile(r'property="og:description"\s+content="([^"]*)"', re.I)
_RE_OG_ACTOR = re.compile(r'property="og:video:actor"\s+content="([^"]*)"', re.I)
_RE_OG_DIRECTOR = re.compile(r'property="og:video:director"\s+content="([^"]*)"', re.I)
_RE_OG_AREA = re.compile(r'property="og:video:area"\s+content="([^"]*)"', re.I)
_RE_OG_CLASS = re.compile(r'property="og:video:class"\s+content="([^"]*)"', re.I)
_RE_OG_DATE = re.compile(r'property="og:video:release_date"\s+content="([^"]*)"', re.I)

# 线路 tab：<a id="1">无尽资源</a>
_RE_TAB = re.compile(r'<a[^>]*id="(\d+)"[^>]*>(.*?)</a>', re.S | re.I)

# 选集：ul.play_num_list 内的 a
_RE_EP = re.compile(
    r'<a[^>]*title="([^"]*)"[^>]*href="(/gygplayer/(\d+)-(\d+)-(\d+)\.html)"[^>]*>',
    re.S | re.I)

# 播放直链
_RE_NOW = re.compile(r'var\s+now="([^"]*)"', re.I)
_RE_NOW2 = re.compile(r'var\s+now\s*=\s*["\']([^"\']+)["\']', re.I)
_RE_M3U8 = re.compile(r'(https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?)', re.I)


class Spider(Spider):

    def getName(self):
        return "未来影院"

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
        self._detail_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _ensure(self):
        if not getattr(self, 'headers', None):
            self.headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not getattr(self, 'site_url', None):
            self.site_url = HOST
        if not getattr(self, '_play_cache', None):
            self._play_cache = {}
        if not getattr(self, '_detail_cache', None):
            self._detail_cache = {}
        if not getattr(self, 'default_pic', None):
            self.default_pic = DEFAULT_PIC

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=20, headers=None):
        self._ensure()
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
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
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _line_name(self, txt):
        nm = re.sub(r'<sup.*?</sup>', '', txt, flags=re.S)
        nm = re.sub(r'<[^>]+>', '', nm)
        nm = re.sub(r'\s+', ' ', nm).strip()
        nm = re.sub(r'\d+[集期话]?$', '', nm).strip()
        if nm and not nm.endswith('资源'):
            nm = nm.rstrip('资源') + '资源'
        return nm

    # ===================== 列表卡片 =====================
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href = m.group(1)
            vid = m.group(2)
            if not vid or vid in seen:
                continue
            seen.add(vid)

            tag = m.group(0)
            blk = html[max(0, m.start() - 500):m.end() + 500]

            nm = ""
            tm = _RE_TITLE.search(tag)
            if tm:
                nm = tm.group(1)
            if not nm:
                am = _RE_ALT.search(blk)
                if am:
                    nm = am.group(1)
            if not nm:
                nm = vid

            pic = ""
            im = _RE_IMG.search(blk)
            if im:
                pic = im.group(1) or im.group(2) or im.group(3) or ""

            tip = ""
            tp = _RE_TIP.search(blk)
            if tp:
                tip = tp.group(1).strip()

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(nm)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": tip,
            })
        return videos

    def _page_count(self, html, tid, cur=1):
        if not html:
            return 1
        mx = cur
        for m in re.finditer(r'/gyglist/%s-(\d+)\.html' % re.escape(tid), html):
            try:
                n = int(m.group(1))
                if n > mx:
                    mx = n
            except Exception:
                pass
        return mx

    # ===================== 六接口 =====================
    def homeContent(self, filter=False):
        self._ensure()
        classes = [c for c in CLASSES if c["type_id"] not in DROP_TIDS]
        for c in classes:
            c["type_pid"] = TYPE_PIDS.get(c["type_id"], "0")
        return {"class": classes}

    def homeVideoContent(self):
        self._ensure()
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos[:36]}

    def categoryContent(self, tid, pg, filter, extend):
        self._ensure()
        self._warm_up()
        page = int(pg) if pg else 1
        tid = str(tid)

        if page <= 1:
            url = "%s/gyglist/%s.html" % (self.site_url, tid)
        else:
            url = "%s/gyglist/%s-%d.html" % (self.site_url, tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, tid, page)

        for v in videos:
            v["type_id"] = tid
            v["type_name"] = next(
                (c["type_name"] for c in CLASSES if c["type_id"] == tid), "")

        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 36,
            "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        self._ensure()
        self._warm_up()
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search.php?searchword=%s" % (self.site_url, keyword)
        if page > 1:
            url += "&page=%d" % page

        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        if not videos:
            videos = self._search_items(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": max(len(videos), 24),
            "total": len(videos),
        }

    def _search_items(self, html):
        items = []
        seen = set()
        for m in re.finditer(
            r'class="[^"]*item clearfix[^"]*"(.*?)(?=class="[^"]*item clearfix|$)',
            html, re.S):
            blk = m.group(1)
            v = re.search(r'href="(/gygvod/(\d+)\.html)"', blk)
            if not v:
                continue
            vid = v.group(2)
            if vid in seen:
                continue
            seen.add(vid)

            pic = ""
            pm = re.search(r'<img[^>]*data-src="([^"]+)"|<img[^>]*src="(https?://[^"\s]+)"', blk, re.I)
            if pm:
                pic = pm.group(1) or pm.group(2) or ""

            nm = ""
            nm_m = re.search(r'<strong>([^<]*)</strong>', blk)
            if nm_m:
                nm = nm_m.group(1)
            if not nm:
                alt_m = re.search(r'<img[^>]*alt="([^"]*)"', blk)
                if alt_m:
                    nm = alt_m.group(1)

            items.append({
                "vod_id": v.group(1),
                "vod_name": self._clean(nm)[:100] or vid,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return items

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ===================== 详情 =====================
    def detailContent(self, ids):
        self._ensure()
        if not ids:
            return {"list": []}

        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        # 缓存
        now = int(time.time())
        if url in self._detail_cache:
            ts, res = self._detail_cache[url]
            if now - ts < 900:
                return res

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 名称
        name = ""
        m = _RE_OG_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                t = self._clean(m.group(1))
                mt = re.match(r'《([^》]*)》', t)
                name = mt.group(1) if mt else re.sub(r'[【】\-_].*$', '', t).strip()
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_OG_IMG.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介（强制前缀）
        content = ""
        m = _RE_OG_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'class="[^"]*infor_intro[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if m:
                content = self._clean(m.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 元信息
        actor = ""
        m = _RE_OG_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))

        director = ""
        m = _RE_OG_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        area = ""
        m = _RE_OG_AREA.search(html)
        if m:
            area = self._clean(m.group(1))

        vod_class = ""
        m = _RE_OG_CLASS.search(html)
        if m:
            vod_class = self._clean(m.group(1))

        year = ""
        m = _RE_OG_DATE.search(html)
        if m:
            ym = re.search(r'(\d{4})', m.group(1))
            if ym:
                year = ym.group(1)

        # 备注
        remarks = ""
        m = re.search(r'class="[^"]*v-tips[^"]*"[^>]*>([^<]*)<', html)
        if m:
            remarks = m.group(1).strip()

        # ===== 线路 + 选集 =====
        froms, urls = self._parse_lines(html, vod_id)

        res = {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_class": vod_class,
            "vod_year": year,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url":  "$$$".join(urls),
        }]}

        self._detail_cache[url] = (now, res)
        self.log("  剧集: %s" % {f: len(u.split("#")) for f, u in zip(froms, urls)})
        return res

    def _parse_lines(self, html, vid):
        # 线路名：从 #playNumTab 取，避免误抓页面其它数字 id
        tab_names = []
        mtab = re.search(r'id="playNumTab".*?</div>', html, re.S) or \
               re.search(r'id="playNumTab".*?</ul>', html, re.S)
        tab_h = mtab.group(0) if mtab else html

        for m in _RE_TAB.finditer(tab_h):
            nm = self._line_name(m.group(2))
            if nm:
                tab_names.append((m.group(1), nm))

        if not tab_names:
            tab_names = [("1", "默认线路")]

        # 选集：ul.play_num_list，DOM 序与 tab 一致
        uls = re.findall(r'<ul class="[^"]*play_num_list[^"]*"(.*?)</ul>', html, re.S)

        froms, urls = [], []
        for i, ul in enumerate(uls):
            eps = []
            for m in _RE_EP.finditer(ul):
                ep_name = m.group(1).strip() or "第%d集" % (len(eps) + 1)
                ep_url = m.group(2)
                nid = int(m.group(5) or 0)
                eps.append((nid, ep_name, ep_url))

            if not eps:
                continue

            eps.sort(key=lambda x: x[0])
            fname = tab_names[i][1] if i < len(tab_names) else ("线路%d" % (i + 1))
            froms.append(fname)
            urls.append("#".join("%s$%s" % (n, self.site_url + u if u.startswith("/") else u)
                                 for _, n, u in eps))

        return froms, urls

    # ===================== 播放 =====================
    def playerContent(self, flag, id, vipFlags):
        self._ensure()

        raw = str(id) if id else ""
        if "$" in raw:
            raw = raw.split("$", 1)[1]

        # 已经是 m3u8 直链
        if re.search(r'\.m3u8', raw, re.I):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        play_page = raw if raw.startswith("http") else self._fix_url(raw)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page, timeout=10)
        m3u8 = ""
        if html:
            m = _RE_NOW.search(html) or _RE_NOW2.search(html)
            if m:
                m3u8 = m.group(1).strip()
            if not m3u8:
                m = _RE_M3U8.search(html)
                if m:
                    m3u8 = m.group(1)

        if m3u8:
            if m3u8.startswith("//"):
                m3u8 = "https:" + m3u8
            elif m3u8.startswith("/"):
                m3u8 = self.site_url + m3u8

            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => m3u8: %s" % m3u8[:160])
            return res

        # 兜底
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    # ===================== 杂项 =====================
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
        try:
            self._play_cache.clear()
            self._detail_cache.clear()
        except Exception:
            pass

    def close(self):
        self.destroy()
