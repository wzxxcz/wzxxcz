# coding=utf-8
"""
Gimy 劇迷 gimytv.biz | TVBox Python 爬虫 
关键机关(全部死磕源码+实测破解):
  1. 苹果CMS V10(gimy 自研模板, 繁体站), 无 PoW 无验证盾 — 明文请求直接通
  2. 筛选路由 12 段连字符拼接: /vodshow/{id}-{地區}-{?}x6-{頁碼}-{?}x2-{年份}.html
     段1=id 段2=地區(多值逗号拼接,如"中國大陸,大陸") 段9=页码 段12=年份
     第一页页码段留空; 面板三行: 類型(子类走同构 vodshow 路由)/地區/年份
  3. 列表每页 36 部(父类页纯列表); 子类页额外有"今日熱播"24 部侧栏(需剥除)
  4. 详情页剧集列表站点自带 data-gimy-episode-order="reverse"(倒序展示)!
     → 必须按 nid 数字升序重排输出(用户硬性要求: 集数正序)
  5. 播放页 player_aaaa 明文 m3u8 直链(play.modujx17.com), 无需换票 → parse=0
     m3u8 无 Referer 即 200(实测)
  6. 全站单线路聚合源: DYun(modum3u8), 线路名取自 source-pill
  7. 搜索两格式: 第1页 /vodsearch/{词}-------------.html(13连字符),
     第N页 /vodsearch/{词}----------{N}---.html(10连字符+页+3连字符)
  8. 简介添加指定前缀; 副标题取详情页"狀態"字段(与站点显示一致)
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
                print("[gimytv]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://gimytv.biz"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类(与站点导航完全一致) =====================
CLASSES = [
    {"type_id": "2", "type_name": "電視劇"},
    {"type_id": "4", "type_name": "動漫"},
    {"type_id": "3", "type_name": "綜藝"},
    {"type_id": "1", "type_name": "電影"},
]

# 類型行(子分类) — 与站点筛选面板逐项一致(繁体名)
_SUBS = {
    "2": [("13", "陸劇"), ("15", "韓劇"), ("16", "美劇"), ("20", "日劇"),
          ("14", "台劇"), ("21", "海外劇"), ("22", "港劇"), ("23", "紀錄片"),
          ("54", "短劇")],
    "1": [("6", "動作片"), ("7", "喜劇片"), ("8", "愛情片"), ("9", "科幻片"),
          ("10", "恐怖片"), ("11", "劇情片"), ("12", "戰爭片"), ("24", "動畫電影")],
}

# 地區行 — 值与站点链接逐字一致(多值逗号拼接, 繁简混拼是站点原样)
_AREAS_MAP = {
    "2": [("中國大陸", "中國大陸,大陸"), ("韓國", "韓國,韩国"), ("日本", "日本"),
          ("台灣", "台灣,中國台灣"), ("香港", "香港"), ("美國", "美國,美国"),
          ("歐美", "歐美"), ("泰國", "泰國"), ("英國", "英國"), ("法國", "法國"),
          ("新加坡", "新加坡"), ("其他", "其他"), ("土耳其", "土耳其"),
          ("西班牙", "西班牙")],
    "1": [("中國大陸", "中國大陸,大陸,內地"), ("韓國", "韓國"), ("日本", "日本"),
          ("台灣", "台灣,中國台灣"), ("香港", "香港"), ("美國", "美國"),
          ("歐美", "歐美"), ("泰國", "泰國"), ("英國", "英國"),
          ("新加坡", "新加坡"), ("其他", "其他")],
    "4": [("中國大陸", "中國大陸,中國,大陸,內地"), ("韓國", "韓國"), ("日本", "日本"),
          ("台灣", "台灣,臺灣,中國台灣"), ("香港", "香港"), ("美國", "美國"),
          ("歐美", "歐美")],
    "3": [("中國大陸", "中國大陸,中國,大陸,中国大陆,內地"), ("韓國", "韓國,韩国"),
          ("日本", "日本"), ("台灣", "台灣,臺灣,中国台湾,台湾,中國台灣"),
          ("香港", "香港"), ("美國", "美國"), ("歐美", "歐美")],
}

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2015, -1)]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _rows = []
    if _tid in _SUBS:
        _rows.append({"key": "cat", "name": "類型",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": n, "v": i} for i, n in _SUBS[_tid]]})
    _rows.append({"key": "area", "name": "地區",
                  "value": [{"n": "全部", "v": ""}] +
                           [{"n": n, "v": v} for n, v in _AREAS_MAP.get(_tid, [])]})
    _rows.append({"key": "year", "name": "年份", "value": _YEARS})
    FILTERS[_tid] = _rows


# ===================== 正则 =====================
# 列表卡片(首页/分类页两种属性顺序同构):
#   分类页: <a class="video-pic loading" data-original="图" href=".." title="名">...note
#   首页:   <a class="video-pic" href=".." title="名"><img src="图">...note
_RE_CARD_BLOCK = re.compile(
    r'<a[^>]*class="video-pic[^"]*"[^>]*>[\s\S]{0,600}?</a>', re.S | re.I)
_RE_CARD_HREF = re.compile(r'href="(/voddetail/\d+\.html)"', re.I)
_RE_CARD_TITLE = re.compile(r'title="([^"]+)"')
_RE_CARD_PIC = re.compile(
    r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp|gif)[^"]*)"', re.I)
_RE_CARD_NOTE = re.compile(r'<span class="note[^"]*">([^<]{0,60})</span>', re.I)

# 详情页
_RE_TITLE = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(
    r'class="details-poster-image"[^>]*src="([^"]+)"', re.I)
_RE_META_LABEL = re.compile(
    r'gimy-detail-meta-label">([^<]+)</span>\s*'
    r'<(?:strong|span|a)[^>]*class="gimy-detail-meta-value[^"]*"[^>]*>'
    r'([\s\S]*?)</(?:strong|span|a)>', re.S | re.I)
_RE_DESC = re.compile(r'name="description" content="([^"]+)"', re.I)

# 播放来源 pill: gico {from} gimy-detail-source-pill {active} > 名
_RE_SOURCE = re.compile(
    r'gico\s+([\w]+)\s+gimy-detail-source-pill[^>]*>\s*([^<]+?)\s*<', re.I)

# 剧集块: id="con_playlist_N" ... data-gimy-episode-order="reverse"
_RE_PLAYLIST = re.compile(
    r'id="con_playlist_(\d+)"[^>]*data-gimy-episode-order="(\w+)"', re.I)

# 剧集卡: <a class="episode-card-link" title=".. 第N集" ... href="/video/{id}-{nid}.html">
# (title/href 属性顺序不固定, 整块匹配后块内提取)
_RE_EPISODE_BLOCK = re.compile(
    r'<a[^>]*episode-card-link[^>]*>[\s\S]{0,400}?</a>', re.S | re.I)
_RE_EP_HREF = re.compile(r'href="(/video/\d+-(\d+)\.html)"', re.I)
_RE_EP_TITLE = re.compile(r'title="([^"]+)"')

# 播放页 player_aaaa
_RE_PLAYER_AA = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</', re.I)

# 分页
_RE_LAST_PAGE = re.compile(r'尾頁</a>', re.I)


class Spider(Spider):

    def getName(self):
        return "Gimy劇迷"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-Hant,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=30, headers=None):
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
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # -------- 筛选路由(12 段连字符, 与站点完全同构) --------
    def _build_show_path(self, tid, page=1, area="", year=""):
        """段1=id 段2=地區 段9=页码 段12=年份; 其余留空。
        站点第一页 /vodshow/{id}-----------.html
        第N页   /vodshow/{id}--------{N}---.html"""
        segs = [str(tid)]
        segs.append(urllib.parse.quote(str(area), safe=",") if area else "")
        segs += ["", "", "", "", "", ""]          # 段3-8
        segs.append(str(page) if page and int(page) > 1 else "")   # 段9 页码
        segs += ["", ""]                          # 段10-11
        segs.append(urllib.parse.quote(str(year)) if year else "")  # 段12 年份
        return "/vodshow/" + "-".join(segs) + ".html"

    def _build_search_path(self, kw, page=1):
        """第1页 /vodsearch/{词}-------------.html(13连字符)
        第N页 /vodsearch/{词}----------{N}---.html(10连字符+页+3连字符)"""
        q = urllib.parse.quote(str(kw))
        if page and int(page) > 1:
            return "/vodsearch/%s----------%d---.html" % (q, int(page))
        return "/vodsearch/%s-------------.html" % q

    def _strip_hot_section(self, html):
        """子类列表页有"今日熱播"24 部侧栏(全站热剧, 不属于该子类) — 剥除,
        只留真正的分类列表。"""
        if "今日熱播" not in html:
            return html
        i = html.find("今日熱播")
        # 向前找最近的 <section
        start = html.rfind("<section", 0, i)
        if start < 0:
            return html
        end = html.find("</section>", i)
        if end < 0:
            return html
        return html[:start] + html[end + len("</section>"):]

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for blk in _RE_CARD_BLOCK.finditer(html):
            blk = blk.group(0)
            mh = _RE_CARD_HREF.search(blk)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            mt = _RE_CARD_TITLE.search(blk)
            mp = _RE_CARD_PIC.search(blk)
            mn = _RE_CARD_NOTE.search(blk)
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(mt.group(1) if mt else "")[:100] or href,
                "vod_pic":     self._fix_url(mp.group(1)) if mp else "",
                "vod_remarks": self._clean(mn.group(1)) if mn else "",
            })
        return videos

    def _last_page(self, html):
        """从分页组件"尾頁"链接解析总页数; 链接形如 /vodshow/2--------128---/sid/1.html"""
        m = _RE_LAST_PAGE.search(html)
        if not m:
            return 1
        seg = html[max(0, m.start() - 500):m.start()]
        last = 1
        for u in re.findall(r'/vod(?:show|search)/([^"]+)/sid/\d+\.html', seg):
            p = u.split("-")
            # vodshow 页码段9(index 8); vodsearch 页码段11(index 10)
            if len(p) >= 12:
                if "vodsearch" in seg[max(0, m.start() - 500):m.start()][:40] or \
                        u.startswith("%") or "----" in u and p[8] == "":
                    pass
                for idx in (8, 10):
                    if idx < len(p) and p[idx].isdigit():
                        last = max(last, int(p[idx]))
        return last

    # ================= TVBox 接口 =================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html)
        # 首页板块多(重名片去重由 seen 保证); 顺序即站点展示顺序
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
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        # 類型(子分类)直接换路由 id — 与站点一致(子类走同构 vodshow 路由)
        route_tid = extend.get("cat") or tid
        url = self.site_url + self._build_show_path(
            route_tid, page,
            area=extend.get("area") or "",
            year=extend.get("year") or "")
        self.log("category: %s" % url)
        html = self._fetch(url)
        html = self._strip_hot_section(html)
        videos = self._extract_videos(html)
        pagecount = self._last_page(html)
        self.log("  %d 条, 总页数 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = self.site_url + self._build_search_path(key, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._last_page(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("線上看")[0])
        name = name or vod_id

        # 封面
        pic = ""
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 元信息(label → value)
        meta = {}
        for label, val in _RE_META_LABEL.findall(html):
            meta[label.strip()] = self._clean(val)
        remarks = meta.get("狀態", "")
        vod_class = meta.get("類別", "")
        vod_area = meta.get("國家/地區", "") or meta.get("國家/地区", "")
        vod_lang = meta.get("語言/字幕", "") or meta.get("语言/字幕", "")
        vod_year = meta.get("年代", "")
        actor = meta.get("主演", "")
        director = meta.get("導演", "") or meta.get("导演", "")

        # 简介: meta description 的 "劇情:" 之后部分
        content = ""
        m = _RE_DESC.search(html)
        if m:
            desc = self._clean(m.group(1))
            for sep in ("劇情:", "劇情：", "剧情:", "剧情："):
                if sep in desc:
                    content = desc.split(sep, 1)[1].strip()
                    break
            if not content:
                content = desc
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 剧集(多线路: source pill × con_playlist_N) =====
        sources = _RE_SOURCE.findall(html)
        # 块切分: 每个 con_playlist_N 区域单独提取
        playlists = list(_RE_PLAYLIST.finditer(html))
        play_from, play_url = [], []

        if playlists:
            for idx, pm in enumerate(playlists):
                n = pm.group(1)
                blk_start = pm.end()
                blk_end = playlists[idx + 1].start() if idx + 1 < len(playlists) \
                    else len(html)
                blk = html[blk_start:blk_end]
                eps = []
                for eb in _RE_EPISODE_BLOCK.findall(blk):
                    me = _RE_EP_HREF.search(eb)
                    if not me:
                        continue
                    nid = int(me.group(2))
                    mt = _RE_EP_TITLE.search(eb)
                    eps.append((nid,
                                self._clean(mt.group(1)) if mt else "",
                                me.group(1)))
                if not eps:
                    continue
                # ⚠️ 站点剧集 DOM 倒序(reverse) — 强制按 nid 升序(用户硬性要求)
                eps.sort(key=lambda x: x[0])
                # 线路名: 与 pill 顺序对应
                alias = "DYun"
                frm = "modum3u8"
                if idx < len(sources):
                    frm = sources[idx][0]
                    alias = self._clean(sources[idx][1]) or frm
                play_from.append(alias)
                play_url.append("#".join(
                    "%s$%s" % (title or ("第%02d集" % nid), self._fix_url(href))
                    for nid, title, href in eps))
        else:
            # 兜底: 全页剧集链接(升序)
            eps = []
            for eb in _RE_EPISODE_BLOCK.findall(html):
                me = _RE_EP_HREF.search(eb)
                if not me:
                    continue
                nid = int(me.group(2))
                mt = _RE_EP_TITLE.search(eb)
                eps.append((nid, self._clean(mt.group(1)) if mt else "", me.group(1)))
            eps.sort(key=lambda x: x[0])
            if eps:
                play_from.append("DYun")
                play_url.append("#".join(
                    "%s$%s" % (title or ("第%02d集" % nid), self._fix_url(href))
                    for nid, title, href in eps))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "type_name": vod_class,
            "vod_lang": vod_lang,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real_url = ""
        if html:
            m = _RE_PLAYER_AA.search(html)
            if m:
                try:
                    aa = json.loads(m.group(1))
                    real_url = (aa.get("url") or "").replace("\\/", "/")
                except Exception:
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                    if m2:
                        real_url = m2.group(1).replace("\\/", "/")
        real_url = real_url.replace("&amp;", "&")
        self.log("  url: %s" % (real_url[:120] if real_url else "EMPTY"))

        if real_url.startswith("http"):
            # 站点前端 referrerPolicy 无 Referer 即 200 — 不带 Referer
            res = {"parse": 0, "playUrl": "", "url": real_url,
                   "header": {"User-Agent": UA}}
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 交 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

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
