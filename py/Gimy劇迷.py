# coding=utf-8
"""
Gimy 劇迷 gimytv.biz | TVBox Python 爬虫 
关键机关(全部死磕源码+实测破解):
  1. 苹果CMS V10(gimy 自研模板, 繁体站), 无 PoW 无验证盾 — 明文请求直接通
  2. 筛选路由 12 段连字符拼接: /vodshow/{id}-{地區}-{?}x6-{頁碼}-{?}x2-{年份}.html
     段1=id 段2=地區(多值逗号拼接,如"中國大陸,大陸") 段9=页码 段12=年份
     第一页页码段留空; 面板三行: 類型(子类走同构 vodshow 路由)/地區/年份
  3. 短劇(type 54)为独立一级分类(用户指定): 筛选面板仅年份行 2026/2025/2024,
     89 页(末页 12 部)= 88×36+12 = 3180 部; 短剧页同样有"今日熱播"侧栏需剥除
  4. 详情页剧集列表站点自带 data-gimy-episode-order="reverse"(倒序展示)!
     → 必须按 nid 数字升序重排输出(用户硬性要求: 集数正序)
  5. 多线路机关(V2.0 重构核心):
     - 剧集块 <ul id="con_playlist_{源ID}">, 每集链接带 #sid={源ID};
       同源另有 conmobi_playlist_{N} 移动端块 — 只取 con_playlist 首个非空块
     - 线路定义藏三处: 桌面 li[data-source-id]>a.gico{frm} 名 / 注释掉的
       playTab(<a class="gico {frm}" href="#con_playlist_{N}">名</a>) /
       playlist-mobile 块(gico+span 名) — 短剧模板 pill 在 HTML 注释里!
     - 单集名: 取"第N集/全集"等集次词(episode-card-link 卡片内含冗长标题, 弃)
     - frm→线路名对照表兜底(modum3u8=DYun 等 16 组, 站点实测)
     - 陆剧页 16 线路(DYun/GYun/NYun/BYun/XLYun/WYun/SYun/Uyun/JYun/BYun/
       SZyun/ZYun/FYun/HYun/IKYun/JSyun), 与站点"播放來源"顺序一致
  6. 播放页换线路靠 Cookie: changeSid() 设 document.cookie="sid={源ID}" 后刷新,
     服务端按 sid cookie 渲染对应线路的 player_aaaa → 请求播放页必须带
     Cookie: sid={源ID}(实测: sid=13→gsm3u8, sid=1→bfzym3u8, sid=8→ukm3u8)
  7. player_aaaa 明文 m3u8 直链, 无 Referer 即 200(实测) → parse=0
  8. 搜索两格式: 第1页 /vodsearch/{词}-------------.html(13连字符),
     第N页 /vodsearch/{词}----------{N}---.html(10连字符+页+3连字符)
  9. 简介添加指定前缀; 副标题取详情页"狀態"字段(与站点显示一致)
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

# ===================== 分类(与站点导航一致 + 短剧独立一级分类) =====================
CLASSES = [
    {"type_id": "2", "type_name": "電視劇"},
    {"type_id": "4", "type_name": "動漫"},
    {"type_id": "3", "type_name": "綜藝"},
    {"type_id": "1", "type_name": "電影"},
    {"type_id": "54", "type_name": "短劇"},
]

# 類型行(子分类) — 与站点筛选面板逐项一致(繁体名)
# 短劇(54)按用户要求提升为一级分类, 不再挂在電視劇子类型下
_SUBS = {
    "2": [("13", "陸劇"), ("15", "韓劇"), ("16", "美劇"), ("20", "日劇"),
          ("14", "台劇"), ("21", "海外劇"), ("22", "港劇"), ("23", "紀錄片")],
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

# 短劇分类页筛选面板站点原样: 仅年份行 2026/2025/2024(无類型/地區行)
_YEARS_54 = [{"n": "全部", "v": ""}] + \
            [{"n": str(y), "v": str(y)} for y in (2026, 2025, 2024)]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _rows = []
    if _tid in _SUBS:
        _rows.append({"key": "cat", "name": "類型",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": n, "v": i} for i, n in _SUBS[_tid]]})
    if _tid in _AREAS_MAP:
        _rows.append({"key": "area", "name": "地區",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": n, "v": v} for n, v in _AREAS_MAP[_tid]]})
    _rows.append({"key": "year", "name": "年份",
                  "value": _YEARS_54 if _tid == "54" else _YEARS})
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

# 播放来源定义(三种藏法, 按优先级):
#   ① 桌面源选择器: <li data-source-id="7"><a class="gico modum3u8" ...>DYun</a>
#   ② 注释掉的 playTab(短剧模板): <a class="gico modum3u8" href="#con_playlist_1">DYun
#   ③ 移动端块: <div class="playlist-mobile..."><i class="gico modum3u8"...><span>DYun</span>...con_playlist_1
_RE_SRC_TAB = re.compile(
    r'data-source-id="(\d+)"[^>]*>\s*<a class="gico ([\w]+)"[^>]*>\s*([^<]+?)\s*</a>', re.I)
_RE_SRC_COMMENT = re.compile(
    r'<a class="gico ([\w]+)"\s+href="#con_playlist_(\d+)"[^>]*>\s*([^<]+?)\s*</a>', re.I)
_RE_SRC_MOBILE = re.compile(
    r'playlist-mobile[^>]*>\s*<i class="gico ([\w]+)"[\s\S]{0,300}?'
    r'<span[^>]*>([^<]+)</span>[\s\S]{0,300}?id="con_playlist_(\d+)"', re.I)

# 剧集块(桌面): <ul id="con_playlist_{源ID}"> ... </ul>
# 移动端块 id 为 conmobi_playlist_N, 不匹配 — 只取每源首个块
_RE_PLAYLIST_UL = re.compile(
    r'<ul[^>]*id="con_playlist_(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)

# 块内剧集(通用, 不挑 class): href 含 #sid 或裸链接, 标题取"第N集/全集"集次词
_RE_EP_ANY = re.compile(
    r'<a[^>]*href="(/video/\d+-(\d+)\.html[^"]*)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_WORD = re.compile(r'(第\s*\d+\s*集|全集|第\s*\d+\s*話|第\s*\d+\s*期|預告|花絮)')

# frm → 线路名对照表(站点 16 源实测; ③无标签时兜底)
_FRM_ALIAS = {
    "modum3u8": "DYun", "gsm3u8": "GYun", "lzm3u8": "NYun",
    "bfzym3u8": "BYun", "xlm3u8": "XLYun", "wjm3u8": "WYun",
    "sdm3u8": "SYun", "ukm3u8": "Uyun", "jinyingm3u8": "JYun",
    "subm3u8": "BYun", "snm3u8": "SZyun", "zuidam3u8": "ZYun",
    "ffm3u8": "FYun", "hnm3u8": "HYun", "ikm3u8": "IKYun",
    "jsm3u8": "JSyun",
}

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
        """从分页组件解析总页数。
        中间页: 尾頁是链接 <a ...>尾頁</a>, 链接 /vodshow/...---N---/sid/1.html
        末页:   尾頁变 disabled <span>尾頁</span>, 总页数在 "89/89" 徽标里"""
        m = _RE_LAST_PAGE.search(html)
        if m:
            seg = html[max(0, m.start() - 500):m.start()]
            last = 1
            for u in re.findall(r'/vod(?:show|search)/([^"]+)/sid/\d+\.html', seg):
                p = u.split("-")
                # vodshow 页码段9(index 8); vodsearch 页码段11(index 10)
                for idx in (8, 10):
                    if idx < len(p) and p[idx].isdigit():
                        last = max(last, int(p[idx]))
            return last
        m2 = re.search(r'class="num"\s*>\s*\d+/(\d+)\s*<', html)
        if m2:
            return int(m2.group(1))
        return 1

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

        # ===== 剧集(多线路: con_playlist_{源ID} × 三种线路定义来源) =====
        # 1) 线路定义: 源ID -> (frm, 线路名), 按站点展示顺序
        src_defs = {}   # pid -> (frm, alias)
        src_order = []
        for pid, frm, alias in _RE_SRC_TAB.findall(html):
            pid = str(pid)
            if pid not in src_defs:
                src_defs[pid] = (frm, self._clean(alias))
                src_order.append(pid)
        if not src_order:
            for frm, pid, alias in _RE_SRC_COMMENT.findall(html):
                pid = str(pid)
                if pid not in src_defs:
                    src_defs[pid] = (frm, self._clean(alias))
                    src_order.append(pid)
        if not src_order:
            for frm, alias, pid in _RE_SRC_MOBILE.findall(html):
                pid = str(pid)
                if pid not in src_defs:
                    src_defs[pid] = (frm, self._clean(alias))
                    src_order.append(pid)

        # 2) 剧集块: 每源取首个 <ul id="con_playlist_{pid}">(含桌面卡片/普通列
        #    表/移动端复用块三种形态; 移动端独立块 id 是 conmobi_*, 天然排除)
        blocks = {}
        for m in _RE_PLAYLIST_UL.finditer(html):
            pid = m.group(1)
            if pid not in blocks:
                blocks[pid] = m.group(2)

        play_from, play_url = [], []
        # 顺序: 有线路定义的按定义顺序; 无定义的块按 pid 升序兜底
        ordered_pids = [p for p in src_order if p in blocks]
        for pid in sorted(k for k in blocks if k not in src_order):
            ordered_pids.append(pid)

        for pid in ordered_pids:
            eps = []
            seen_nid = set()
            for href, nid, inner in _RE_EP_ANY.findall(blocks[pid]):
                nid = int(nid)
                if nid in seen_nid:
                    continue
                seen_nid.add(nid)
                # 集名: 块内文本中取"第N集/全集"等集次词(卡片长标题只留集次)
                mw = _RE_EP_WORD.search(inner)
                label = re.sub(r"\s+", "", mw.group(1)) if mw else "第%02d集" % nid
                # ⚠️ TVBox 以 "#" 作为集分隔符 — 剧集 URL 里绝不能带 #sid 片段!
                #    改用 ?sid={源ID} 查询参数编码(playerContent 解析后还原 cookie)
                href = re.sub(r"#sid=\d+", "", href)
                if "sid=" not in href:
                    href = href + "?sid=" + pid
                eps.append((nid, label, href))
            if not eps:
                continue
            # ⚠️ 站点剧集 DOM 倒序(reverse) — 强制按 nid 升序(用户硬性要求)
            eps.sort(key=lambda x: x[0])
            frm, alias = src_defs.get(pid, ("", ""))
            if not alias:
                alias = _FRM_ALIAS.get(frm) or ("源%s" % pid)
            play_from.append(alias)
            play_url.append("#".join(
                "%s$%s" % (label, self._fix_url(href))
                for nid, label, href in eps))

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
        raw = str(id)
        # id 形如 /video/{vid}-{nid}.html?sid={源ID} — 换线路靠 cookie(sid)
        # (?sid 是我们自编码的, 请求时剥离; 站点真实机制见下)
        path = re.sub(r"[?&]sid=\d+", "", raw)
        msid = re.search(r"sid=(\d+)", raw)
        sid = msid.group(1) if msid else ""
        play_page = path if path.startswith("http") else self._fix_url(path)
        self.log("player: %s (sid=%s)" % (play_page, sid or "default"))

        now = int(time.time())
        if raw in self._play_cache:
            ts, res = self._play_cache[raw]
            if now - ts < 600:
                return res

        headers = {"User-Agent": UA}
        if sid:
            # ⚠️ 站点 changeSid 机制: 服务端按 cookie sid 渲染对应线路的
            #    player_aaaa(实测 sid=13→gsm3u8, sid=1→bfzym3u8, sid=8→ukm3u8)
            headers["Cookie"] = "sid=" + sid
        html = self._fetch(play_page, headers=headers)
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
            self._play_cache[raw] = (now, res)
            return res

        # 兜底: 交 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[raw] = (now, res)
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
