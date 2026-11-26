# coding=utf-8
"""
番茄酱影视 fanqe.cc | TVBox Python 爬虫 
关键机关(全部死磕源码+实测破解):
  1. 苹果CMS V10(fq 模板), 无 PoW 无验证盾 — 明文请求直接通
  2. 播放三线路(顺序与站点 tab 完全一致): 番茄 / 超清1 / 超清2
     - 番茄(kkytest): player_aaaa.url 是票号 "svmhhk-1-1", 另带 kky 签名票
       → /noad/kky_play.php?vid=票号 + X-Kky-Token: kky → 直链 MP4(byteimg 伪装域)
       实测: 该接口校验"发票端指纹一致性"且后端多节点, 部分节点宽松 → 必须短重试,
       平均约 1/3 命中; 全失败则用同页 lines 里其他线路的同集地址兜底
     - 超清1(jsm3u8): player_aaaa.url 就是裸 m3u8 直链 → 直接 parse=0
     - 超清2(xiguam3u8): url 是 "na:xiguam3u8:..." 票 → /noad/parse.php?t=票
       同样多节点/签名校验 → 短重试; 命中后返回 svip.xgplay17.com 的 m3u8
  3. 播放页内嵌 fqPreheat.lines 数组 = 该集"全部线路"地址(实测同集等效),
     是番茄/故障线路的最佳兜底(优先 jsm3u8 http 直链, 否则拿 na: 票换票)
  4. m3u8 必须无 Referer 请求(站点前端 referrerPolicy:'no-referrer')
  5. 分类筛选自由组合: /vod/show/by/{排序}/id/{tid}/page/{页}/year/{年}.html,
     子分类直接换 id 段(如 /id/22.html = 日本剧); 页码取分页器最大 /page/N 链接
     (页面 "N页" 文本是虚标: 电视剧标 772 实为 695)
  6. 副标题取详情页 "备注 :" 字段(与站点显示一致)
"""
import re
import sys
import json
import time
import threading
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
                print("[fanqe]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://fanqe.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/ds3/img/cover-empty.webp"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点导航 + 子类筛选面板, 线上实证） =====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "46", "type_name": "体育"},
]

# 站点筛选面板: 类型(子分类, 换 type_id) / 年份 / 排序(by 段) — 与网页完全一致
_SUB_MAP = {
    "1": [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
          ("10", "恐怖片"), ("11", "剧情片"), ("12", "战争片"), ("20", "记录片"),
          ("37", "动画片"), ("49", "悬疑片"), ("50", "犯罪片"), ("51", "灾难片"),
          ("52", "奇幻片")],
    "2": [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
          ("21", "台湾剧"), ("22", "日本剧"), ("23", "海外剧"), ("24", "泰国剧")],
    "3": [("25", "大陆综艺"), ("26", "港台综艺"), ("27", "日韩综艺"), ("28", "欧美综艺")],
    "4": [("29", "国产动漫"), ("30", "日韩动漫"), ("31", "欧美动漫"),
          ("32", "港台动漫"), ("33", "海外动漫")],
    "46": [("47", "足球"), ("48", "篮球")],
}

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2020, -1)] + \
         [{"n": "2020年前", "v": "2020年前"}, {"n": "2010年前", "v": "2010年前"},
          {"n": "2000年前", "v": "2000年前"}]

_SORTS = [{"n": "按最新", "v": "time"},
          {"n": "按最热", "v": "hits"},
          {"n": "按评分", "v": "score"}]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "sub", "name": "类型",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": i} for i, n in _SUB_MAP.get(_tid, [])]},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 列表卡片(首页/分类同构): exp链接+标题 → 封面 data-src → 备注 prb
# ⚠️ 封面必须取 data-src(gen img 的 src=base64 占位图在前, src 会命中占位图)
_RE_CARD = re.compile(
    r'class="public-list-exp"\s+href="([^"]+)"[^>]*?title="([^"]*)"'
    r'[\s\S]{0,600}?'
    r'data-src="([^"]+)"'
    r'(?:[\s\S]{0,500}?class="public-list-prb[^"]*"[^>]*>([\s\S]{0,80}?)</span>)?',
    re.S | re.I)
# 搜索结果卡片(search-box 专用结构, 无 title 属性, 名字在 thumb-txt)
_RE_CARD_SEARCH = re.compile(
    r'class="public-list-box search-box[\s\S]{0,400}?'
    r'class="public-list-exp"\s+href="([^"]+)"'
    r'[\s\S]{0,600}?'
    r'data-src="([^"]+)"'
    r'(?:[\s\S]{0,400}?class="public-list-prb[^"]*"[^>]*>([\s\S]{0,80}?)</span>)?'
    r'[\s\S]{0,800}?class="thumb-txt[^"]*"[^>]*>\s*<a[^>]*>([^<]*)</a>',
    re.S | re.I)
_RE_HREF = re.compile(
    r'href="(/index\.php/vod/detail/id/\d+\.html)"', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="slide-info-title[^"]*">([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([^<]*)</title>', re.I)
# 详情封面: img 的 src 是 base64 占位图(1px gif), 真图在 data-src
_RE_PIC = re.compile(
    r'class="detail-pic"[\s\S]{0,900}?data-src="([^"]+)"', re.S | re.I)
_RE_PIC_SRC = re.compile(
    r'class="detail-pic"[\s\S]{0,900}?<img[^>]*?src="((?!data:)[^"]+)"', re.S | re.I)
# 副标题(站点正式字段): <strong class="r6">备注 :</strong>更新至第44集</div>
_RE_REMARK = re.compile(
    r'<strong[^>]*class="r6"[^>]*>\s*备注\s*[:：]\s*</strong>([\s\S]{0,200}?)</div>',
    re.S | re.I)
_RE_META_LI = re.compile(
    r'<li>\s*<em class="cor4">([^<]*)</em>([\s\S]*?)</li>', re.S | re.I)
_RE_INTRO = re.compile(r'id="height_limit"[^>]*>([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路面板: tab(data-form, 无 4K) 与 box(剧集链接) 按 DOM 顺序一一对应
_RE_LINE_TAB = re.compile(
    r'<a[^>]*data-form="([^"]*)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PLAY_EP = re.compile(
    r'href="(/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([^<]*)</a>', re.I)

# 播放页
_RE_PLAYER_AA = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</', re.S)
_RE_LINES = re.compile(
    r'"lines"\s*:\s*(\[\s*\{[\s\S]*?\}\s*\])', re.S)

# 分页(取最大 /page/N 链接 — "N页"文本是虚标, 不可信)
_RE_PAGE_LINK = re.compile(r'/page/(\d+)', re.I)

# 线路别名(与站点 tab 文字一致, 站点本身即中文)
# 线路别名(仅当详情页 tab 结构异常取不到名字时兜底)
_LINE_ALIAS = {
    "kkytest": "番茄", "jsm3u8": "超清1", "xiguam3u8": "超清2",
    "yzxm3u8": "超清HD", "dyttm3u8": "电影天堂",
}
# 站点 tab 顺序(实测): 番茄 → 超清1 → 超清2
_LINE_ORDER = ["番茄", "超清1", "超清2", "超清HD", "电影天堂"]


# ===================== exec 抢跑（站点单页 8~12s, 壳子启动即预抓首页） =====================
# 经验: exec 里同步一把梭很脆弱(网络未就绪就静默失败且无人补) —
# 这里改为后台线程 + Event 放行 + 接口侧短轮询, 抢跑失败接口仍会现场抓, 不会空数据。
_MODULE_DATA = {"home": None}
_WARM_EVENT = threading.Event()


def _module_warm():
    """后台线程预抓首页; 失败静默重试, 全程不阻塞 exec。"""
    for _ in range(3):
        try:
            sp = Spider()
            sp.init("")
            html = sp._fetch(sp.site_url + "/", timeout=30)
            vids = sp._extract_videos(html)
            if vids:
                _MODULE_DATA["home"] = vids
                break
        except Exception:
            pass
        time.sleep(2)
    _WARM_EVENT.set()


class Spider(Spider):

    def getName(self):
        return "番茄酱影视"

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
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=60, headers=None):
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

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        # 搜索结果页(search-box 专用卡片, 无 title 属性)优先尝试
        matches_s = _RE_CARD_SEARCH.findall(html)
        if matches_s:
            self.log("  搜索卡片: %d 条" % len(matches_s))
            for href, pic, prb, title in matches_s:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(title)[:100],
                    "vod_pic":     self._fix_url(pic.replace("&amp;", "&")) or self.default_pic,
                    "vod_remarks": self._clean(prb),
                })
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, title, pic, prb in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                pic = pic.replace("&amp;", "&")
                remark = self._clean(prb)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(title)[:100],
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": remark,
                })
            return videos

        hrefs = _RE_HREF.findall(html)
        self.log("  兜底: href=%d" % len(hrefs))
        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    href.rstrip("/").split("/")[-1].replace(".html", ""),
                "vod_pic":     self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        """真实末页 = 分页器最大 /page/N 链接(页面"N页"文本是虚标, 电视剧标 772 实为 695)。"""
        if not html:
            return 1
        try:
            pages = [int(p) for p in _RE_PAGE_LINK.findall(html)]
            if pages:
                return max(pages)
        except Exception:
            pass
        return 1

    def _build_show_path(self, tid, page, by="", year="", sub=""):
        """与站点完全同构的组合筛选路由(段序与站点分页链接一致):
        /vod/show/by/{排序}/id/{tid}/page/{页}/year/{年}.html"""
        t = str(sub) if sub else str(tid)
        q = urllib.parse.quote
        segs = []
        if by:
            segs += ["by", q(str(by))]
        segs += ["id", t]
        page = int(page) if page else 1
        if page > 1:
            segs += ["page", str(page)]
        if year:
            segs += ["year", q(str(year))]
        return "/index.php/vod/show/" + "/".join(segs) + ".html"

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        # 0) exec 抢跑数据(壳子启动即抓, 首页请求通常已就绪 → 秒回)
        mv = _MODULE_DATA.get("home")
        if mv:
            self.log("home 使用抢跑数据 %d 条" % len(mv))
            return {"list": mv}
        # 0.5) 抢跑未就绪: 0.2s 短轮询等(最多 4s, 数据一到立即放行, 不傻等满超时)
        if not _WARM_EVENT.is_set():
            for _ in range(20):
                d = _MODULE_DATA.get("home")
                if d:
                    self.log("home 等到抢跑数据 %d 条" % len(d))
                    return {"list": d}
                if _WARM_EVENT.is_set():
                    break
                time.sleep(0.2)
        # 1) 现场抓取
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        if not videos:
            # 兜底: 首页板块偶发为空 → 各分类第一页合并(宁旧勿空)
            self.log("  首页为空, 分类合并兜底")
            seen, merged = set(), []
            for tid in ("2", "1", "4", "3"):
                th = self._fetch(self.site_url + self._build_show_path(tid, 1))
                for v in self._extract_videos(th):
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        merged.append(v)
                if len(merged) >= 60:
                    break
            videos = merged[:60]
        if videos:
            _MODULE_DATA["home"] = videos   # 回写, 下次清缓存 exec 之外也有底
        self.log("  最终: %d 条" % len(videos))
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

        url = self.site_url + self._build_show_path(
            tid, page,
            by=extend.get("by") or "",
            year=extend.get("year") or "",
            sub=extend.get("sub") or "")
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 40, "total": pagecount * 40,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        if page > 1:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (
                self.site_url, page, keyword)
        else:
            url = "%s/index.php/vod/search/wd/%s.html" % (self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 10, "total": 1000,
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
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = _RE_TITLE_TAG.search(html)
                if m:
                    name = self._clean(m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = re.sub(r"\s*[(（]\d{4}[)）]\s*$", "", name).strip() or vod_id

        # 封面(优先 data-src 真图, 兜底 src 且排除 base64 占位)
        pic = self.default_pic
        try:
            m = _RE_PIC.search(html) or _RE_PIC_SRC.search(html)
            if m:
                pic = self._fix_url(m.group(1)) or pic
        except Exception:
            pass

        # 元信息 li: 片名/状态/主演/导演/年份/地区/类型/频道/上映/语言/更新
        metas = {}
        try:
            for mm in _RE_META_LI.finditer(html):
                k = mm.group(1).replace("：", "").replace(":", "").strip()
                v = re.sub(r"<[^>]+>", " ", mm.group(2))
                metas[k] = self._clean(v)
        except Exception:
            pass
        actor = metas.get("主演", "")
        director = metas.get("导演", "")
        remarks = metas.get("状态", "")          # 兜底: meta li 的状态
        try:
            m = _RE_REMARK.search(html)          # 优先站点正式「备注 :」字段
            if m:
                _rm = self._clean(m.group(1))
                if _rm:
                    remarks = _rm
        except Exception:
            pass
        vod_year = metas.get("年份", "")
        vod_area = metas.get("地区", "")
        vod_class = metas.get("类型", "").replace(" ", ",").strip(",")

        # 简介
        content = ""
        try:
            m = _RE_INTRO.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ===== 线路与剧集(tab 与 box 按 DOM 顺序一一对应, 4K tab 无 data-form 自然排除) =====
        tab_names = []
        try:
            for tm in _RE_LINE_TAB.finditer(html):
                form, inner = tm.group(1), tm.group(2)
                # 先去集数 badge, 再由 _clean 去掉 <i> 图标标签/&nbsp;, 保留线路名
                nm = re.sub(r'<span[^>]*class="badge[^"]*"[^>]*>[\s\S]*?</span>', "", inner)
                nm = self._clean(nm) or _LINE_ALIAS.get(form, form)
                if nm:
                    tab_names.append(nm)
        except Exception:
            pass
        self.log("  线路tab: %s" % tab_names)

        boxes = []
        try:
            parts = re.split(r'class="anthology-list-box', html)
            for part in parts[1:]:
                eps = _RE_PLAY_EP.findall(part)
                if eps:
                    boxes.append(eps)
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)
        self.log("  线路box: %s" % [len(b) for b in boxes])

        # 对齐兜底: 个别影片多出 4K 剧集 box(4K tab 无 data-form 被排除) → 补 "4K";
        # 若 tab 结构异常仍缺口, 按站点固定线路顺序兜底命名, 不让线路名错位
        if len(boxes) > len(tab_names):
            extra = len(boxes) - len(tab_names)
            if "fq-4k-line" in html and extra == 1:
                tab_names.append("4K")
                extra = 0
            for _ in range(extra):
                idx = len(tab_names)
                tab_names.append(_LINE_ORDER[idx] if idx < len(_LINE_ORDER)
                                 else "线路%d" % (idx + 1))

        if not boxes:
            return {"list": []}

        play_from = []
        play_url = []
        for i, eps in enumerate(boxes):
            if i < len(tab_names):
                alias = tab_names[i]
            else:
                alias = "线路%d" % (i + 1)
            play_from.append(alias)
            play_url.append("#".join(
                "%s$%s" % (self._clean(n), h) for h, _s, _n, n in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks or ("%d条线路" % len(boxes)),
            "type_name": vod_class,
            "vod_area": vod_area,
            "vod_year": vod_year,
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
        aa = {}
        if html:
            try:
                m = _RE_PLAYER_AA.search(html)
                if m:
                    aa = json.loads(m.group(1))
            except Exception:
                try:
                    aa = json.loads(m.group(1).replace("\\/", "/"))
                except Exception:
                    aa = {}
        real_url = (aa.get("url") or "").replace("\\/", "/").replace("&amp;", "&")
        frm = aa.get("from") or ""
        kky = aa.get("kky") or ""
        self.log("  from=%s url=%s" % (frm, real_url[:80]))

        # ⚠️ 站点前端明确 referrerPolicy:'no-referrer' 模拟播放器防盗链 — m3u8 严禁带 Referer
        header = {"User-Agent": UA}

        # 情况 A: 明文直链 m3u8/mp4 (jsm3u8 超清1 等)
        if real_url.startswith("http"):
            self.log("  => 直链: %s" % real_url[:120])
            res = {"parse": 0, "playUrl": "", "url": real_url, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 情况 B: 番茄线路 kkytest (url 为票号 "svmhhk-1-1", kky 为签名票)
        # 实测: /noad/kky_play.php 后端是负载均衡, 仅约 1/6 节点校验签名放行
        #       → 必须短重试(命中不校验的节点即可换出 byteimg 直链 MP4)
        if frm == "kkytest" and kky and real_url:
            u = self._kky_exchange(real_url, kky, play_page)
            if u:
                res = {"parse": 0, "playUrl": "", "url": u, "header": header}
                self._play_cache[play_page] = (now, res)
                return res

        # 情况 C: 超清2 xiguam3u8 na:票 → parse.php 换票(多数影片此路可通)
        if real_url.startswith("na:"):
            _u = self._parse_na(real_url, play_page)
            if _u:
                res = {"parse": 0, "playUrl": "", "url": _u, "header": header}
                self._play_cache[play_page] = (now, res)
                return res

        # 情况 D: 播放页 fqPreheat.lines 数组自带"全部线路本集地址" —
        # 同集等效兜底: 先 http 直链(优先 jsm3u8), 再拿 na: 票换票
        m3u8_fb = self._extract_line_fallback(html, play_page, skip_from=frm)
        if m3u8_fb:
            self.log("  => lines 同集兜底: %s" % m3u8_fb[:120])
            res = {"parse": 0, "playUrl": "", "url": m3u8_fb, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 交 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _kky_exchange(self, vid, token, referer="", tries=6):
        """番茄 kkytest 换票: 票号+kky签名票 → 直链 MP4。
        后端多节点, 部分节点校验签名(403 token) → 短重试换节点。"""
        if not vid or not token:
            return ""
        api = self.site_url + "/noad/kky_play.php?vid=" + urllib.parse.quote(vid)
        for _ in range(tries):
            try:
                rsp = self.fetch(api, headers={
                    "User-Agent": UA,
                    "Referer": self.site_url + "/static/player/kkytest.html?v=8",
                    "X-Kky-Token": token,
                    "Accept": "*/*",
                }, timeout=10)
                j = json.loads(rsp.text if hasattr(rsp, "text") else str(rsp))
                u = str(j.get("url") or "")
                if j.get("code") == 200 and u.startswith("http"):
                    self.log("  => kky 换票成功: %s" % u[:100])
                    return u
            except Exception:
                pass
        self.log("  kky 换票 %d 次均被节点拒" % tries)
        return ""

    def _parse_na(self, ticket, referer="", tries=6):
        """na: 票 → /noad/parse.php 换票(同样多节点, 约 1/6 节点放行)。"""
        if not ticket:
            return ""
        api = self.site_url + "/noad/parse.php?t=" + urllib.parse.quote(ticket)
        for _ in range(tries):
            try:
                rsp = self.fetch(api, headers={
                    "User-Agent": UA,
                    "Referer": referer or (self.site_url + "/"),
                    "Accept": "*/*",
                }, timeout=10)
                j = json.loads(rsp.text if hasattr(rsp, "text") else str(rsp))
                u = str(j.get("url") or "")
                if j.get("code") == 200 and u.startswith("http"):
                    self.log("  => parse 换票成功: %s" % u[:100])
                    return u
            except Exception:
                pass
        self.log("  parse 换票 %d 次均被节点拒" % tries)
        return ""

    def _extract_line_fallback(self, html, play_page="", skip_from=""):
        """播放页 fqPreheat.lines: 取同集其他线路地址(优先 jsm3u8 http 直链,
        否则 na: 票换票), 保证番茄/故障线路也能播。"""
        if not html:
            return ""
        try:
            m = _RE_LINES.search(html)
            if not m:
                return ""
            lines = json.loads(m.group(1))
        except Exception:
            return ""
        http_us, na_ts = [], []
        try:
            for ln in lines:
                u = (ln.get("url") or "").replace("\\/", "/")
                f = ln.get("from") or ""
                if not u or f == skip_from:
                    continue
                if u.startswith("http"):
                    http_us.append((f, u))
                elif u.startswith("na:"):
                    na_ts.append((f, u))
        except Exception:
            return ""
        for f, u in http_us:
            if f == "jsm3u8":
                return u
        if http_us:
            return http_us[0][1]
        for f, u in na_ts:
            got = self._parse_na(u, play_page)
            if got:
                return got
        return ""

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
            # 兼容两种壳子: fetch 返回响应对象(.content) 或 直接返回 str
            content = getattr(rsp, "content", None)
            if content is None:
                content = str(rsp).encode("utf-8", "ignore")
            ctype = ""
            try:
                ctype = rsp.headers.get("Content-Type", "") or ""
            except Exception:
                ctype = ""
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


# ===================== exec 抢跑启动（放在类定义之后, 保证 Spider 已就绪） =====================
try:
    _t = threading.Thread(target=_module_warm)
    _t.setDaemon(True)
    _t.start()
except Exception:
    _WARM_EVENT.set()
