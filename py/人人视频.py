# coding=utf-8
"""
彩虹影视（追剧神器） www.zhengdasifuyuan.com | TVBox Python 爬虫
站点结构（线上实证 2026-11-18，服务端渲染 HTML 采集站，模板 s10）:
  - 首页:   /
  - 分类:   /marathon/<tid>_<page>.html
            （tid: 1 电影 / 2 电视剧 / 3 综艺 / 4 动漫 / 34 短剧）
  - 搜索:   /search/<URL编码关键词>.html
  - 详情:   /have/<id>.html
      · 片名 h1；副标题(拼音) h1 后首个 muted <p>
      · 评分 绿色 bg-green-500 span（豆瓣 8.0，取数字）
      · 年份/地区：评分所在 flex 内后两个 text-muted-foreground span
      · 状态备注：左上角 rounded font-medium div（全28集 / 已完结 / 第24集已完结）
      · 元信息：label span「导演：/主演：/类型：」+ 值 span（短剧可能无导演）
      · 简介：h3「剧情简介」后 div > p
      · 线路：button data-source="<sid>"，文本为线路名，顺序即站点按钮顺序
      · 选集：div#episodes-<sid> 内 a[href=/player/<vid>-<sid>-<nid>.html][data-idx=nid]
        集名文本 01 / 第01集；选集按集号正序、按集号去重
  - 播放:   /player/<vid>-<sid>-<nid>.html
      · 内联脚本 parts=["b64片段", ...]，拼接后 atob(base64) 即 m3u8 直链；
        站点自身再包一层 /jx/index.html?url=<encodeURIComponent(直链)>，
        爬虫直接取解码后的裸 m3u8 直链 parse=0 播放，失败再交客户端嗅探兜底。

说明（站点服务端防护，非代码阉割）:
  分类墙 /marathon/ 与搜索 /search/ 在站点侧由图片验证码 + WAF 拦截，
  纯 Python（客户端无浏览器、无 OCR 引擎）无法自动通过；爬虫仍按站点真实路由
  实现 categoryContent / searchContent 与同一套卡片解析，一旦运行环境会话
  已通过站点验证（或站点放开校验）即可正常出列表。首页 / 详情 / 播放实测可达。
"""
import re
import sys
import json
import time
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

        def reset_session(self):
            """关闭并丢弃复用坏连接的会话，下次请求重建新连接。"""
            try:
                if self._session is not None:
                    self._session.close()
            except Exception:
                pass
            self._session = None

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[caihong]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zhengdasifuyuan.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点导航 /marathon/<tid>_1.html）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "34", "type_name": "短剧"},
]

# 题材（站点分类页被验证码防护，选项据详情类型字段与站点可见分区归纳，界面展示用）
_GENRE = ["剧情", "喜剧", "动作", "爱情", "恐怖", "科幻", "悬疑", "惊悚", "冒险",
          "奇幻", "犯罪", "战争", "警匪", "动画", "古装", "历史", "武侠", "青春",
          "文艺", "都市", "男频", "女频", "重生", "甜虐爱情", "国产", "短剧"]
_AREA = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
         "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]
_YEAR = [str(y) for y in range(2026, 2009, -1)]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "genre", "name": "类型",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _GENRE]},
        {"key": "area", "name": "地区",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _AREA]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in _YEAR]},
    ]

# ===================== 正则 =====================
_RE_HREF = re.compile(r'href="(/have/(\d+)\.html)"', re.I)
_RE_IMG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_H4 = re.compile(r'<h4[^>]*>([\s\S]*?)</h4>', re.I)
_RE_REMARK = re.compile(r'rounded font-medium">([^<]*)</div>', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_SUBTITLE = re.compile(r'<p[^>]*text-muted-foreground[^>]*>([^<]*)</p>', re.I)
_RE_SCORE = re.compile(r'bg-green-500[^>]*>([\s\S]*?)</span>', re.I)
_RE_MUTED = re.compile(r'<span[^>]*text-muted-foreground[^>]*>([^<]*)</span>', re.I)
_RE_LABEL = re.compile(
    r'<span[^>]*shrink-0[^>]*>(导演|主演|类型|地区|年份|语言)：</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO = re.compile(
    r'剧情简介</h3>\s*<div[^>]*>\s*<p[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_BTN = re.compile(
    r'<button[^>]*data-source="(\d+)"[^>]*>([\s\S]*?)</button>', re.I)
_RE_EP_BOX = re.compile(r'<div id="episodes-(\d+)"[^>]*>([\s\S]*?)(?=<div id="episodes-|$)', re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/player/\d+-\d+-\d+\.html)"[^>]*data-idx="(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_A_FALLBACK = re.compile(
    r'<a[^>]*href="(/player/\d+-(\d+)-(\d+)\.html)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PARTS = re.compile(r'parts\s*=\s*\[([^\]]*)\]', re.S)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)


class Spider(Spider):

    def getName(self):
        return "彩虹影视"

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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _is_upstream_error(self, text):
        if not text:
            return True
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "<title>503", "<title>502", "<title>429", "安全校验", "verify_captcha"))

    def _reset_session(self):
        """best-effort 关闭复用坏连接的会话，下次请求重建新连接。"""
        try:
            if hasattr(self, "reset_session"):
                self.reset_session()
                return
            sess = getattr(self, "_session", None) or getattr(self, "_sess", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            self._session = None
        except Exception:
            pass

    def _fetch(self, url, timeout=15, headers=None):
        def _once():
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)

        text = ""
        for attempt in range(3):
            try:
                text = _once()
            except Exception as e:
                self.log("fetch FAIL %s -> %s" % (url, e))
                text = ""
            if text and not self._is_upstream_error(text):
                return text
            self._reset_session()
            time.sleep(0.8 * (attempt + 1))
        return text

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
        s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif", "load.svg"):
            if bad in low:
                return True
        return False

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        hits = []
        for m in _RE_HREF.finditer(html):
            href, vid = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            hits.append((m.start(), href, vid))

        for pos, href, vid in hits:
            block = html[max(0, pos - 200):pos + 1200]

            # 海报：块内首个 data-original；片名：h4 优先，img alt 兜底（不强求二者顺序）
            pic = ""
            mp = _RE_IMG.search(block)
            if mp:
                pic = mp.group(1)

            title = ""
            mh = _RE_H4.search(block)
            if mh:
                title = self._clean(mh.group(1))
            if not title:
                ma = re.search(r'<img[^>]*?alt="([^"]*)"', block, re.I)
                if ma:
                    title = self._clean(ma.group(1))
            title = self._clean(title)

            pic = self._fix_url(pic)
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

            # 备注：右下角年份 / 状态标签
            mrem = _RE_REMARK.search(block)
            remarks = self._clean(mrem.group(1)) if mrem else ""

            if not title:
                continue
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in re.findall(r'/marathon/\d+_(\d+)\.html', html)]
        if pages:
            return max(1, max(pages))
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._parse_cards(html)
        self.log("home: %d 条" % len(videos))
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

        # 站点分类路由：/marathon/<tid>_<page>.html
        url = "%s/marathon/%s_%d.html" % (self.site_url, str(tid), page)
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        url = "%s/search/%s.html" % (self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        self.log("  搜索结果: %d 条" % len(videos))
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) or 1,
            "limit": 30, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段提取 ----------------
    def _meta_fields(self, html):
        """提取导演/主演/类型/地区/年份/语言 label 字段。"""
        out = {"director": "", "actor": "", "classify": "",
               "area": "", "year": "", "lang": ""}
        keymap = {"导演": "director", "主演": "actor", "类型": "classify",
                  "地区": "area", "年份": "year", "语言": "lang"}
        for m in _RE_LABEL.finditer(html):
            label = self._clean(m.group(1)).rstrip("：:")
            val = self._clean(m.group(2))
            k = keymap.get(label)
            if k and val:
                out[k] = re.sub(r"\s*,\s*", ", ", val)
        return out

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
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
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 副标题（拼音）
        subtitle = ""
        ms = _RE_SUBTITLE.search(html)
        if ms:
            subtitle = self._clean(ms.group(1))

        # 海报
        pic = self.default_pic
        mp = _RE_IMG.search(html)
        if mp:
            pic = self._fix_url(mp.group(1))
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

        # 评分（绿色 span，豆瓣 8.0 -> 8.0）
        score = ""
        msc = _RE_SCORE.search(html)
        if msc:
            raw = self._clean(msc.group(1))
            md = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
            if md:
                score = md.group(1)

        # 年份 / 地区（评分所在 flex 内后两个 muted span）
        year, area = "", ""
        mi = html.find("bg-green-500")
        if mi >= 0:
            seg = html[mi:mi + 600]
            muted = [self._clean(x) for x in _RE_MUTED.findall(seg)]
            muted = [x for x in muted if x and not x.endswith("：") and x != "导演："]
            if len(muted) >= 1:
                year = muted[0]
            if len(muted) >= 2:
                area = muted[1]

        # 状态备注
        remarks = ""
        mrem = _RE_REMARK.search(html)
        if mrem:
            remarks = self._clean(mrem.group(1))

        # label 字段
        meta = self._meta_fields(html)
        if not meta["year"]:
            meta["year"] = year
        if not meta["area"]:
            meta["area"] = area
        director, actor = meta["director"], meta["actor"]
        classify, lang = meta["classify"], meta["lang"]

        # 简介
        content = ""
        mint = _RE_INTRO.search(html)
        if mint:
            content = self._clean(mint.group(1))
        if not content:
            mdesc = _RE_META_DESC.search(html)
            if mdesc:
                content = self._clean(mdesc.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 线路（按钮顺序即站点顺序）=====
        buttons = {}
        for m in _RE_BTN.finditer(html):
            sid, name_line = m.group(1), self._clean(m.group(2))
            buttons[sid] = name_line or ("线路%s" % sid)

        # ===== 选集分组（容器 episodes-<sid>），按集号正序、去重 =====
        groups = {}
        order = []
        for mb in _RE_EP_BOX.finditer(html):
            sid, box = mb.group(1), mb.group(2)
            if sid not in order:
                order.append(sid)
            eps = []
            seen_nid = set()
            for ma in _RE_EP_A.finditer(box):
                href, nid, ep_name = ma.group(1), ma.group(2), self._clean(ma.group(3))
                if nid in seen_nid:
                    continue
                seen_nid.add(nid)
                eps.append((int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href))
            if not eps:
                # 兜底：无 data-idx 的链接
                for ma in _RE_EP_A_FALLBACK.finditer(box):
                    href, sid2, nid, ep_name = ma.group(1), ma.group(2), ma.group(3), self._clean(ma.group(4))
                    if nid in seen_nid:
                        continue
                    seen_nid.add(nid)
                    eps.append((int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href))
            eps.sort(key=lambda x: x[0])  # 正序
            groups[sid] = eps

        # 容器缺省时，按链接 sid 聚合兜底
        if not groups:
            agg = {}
            for ma in _RE_EP_A_FALLBACK.finditer(html):
                href, sid, nid, ep_name = ma.group(1), ma.group(2), ma.group(3), self._clean(ma.group(4))
                agg.setdefault(sid, {})
                if nid not in agg[sid]:
                    agg[sid][nid] = (int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href)
            for sid, d in agg.items():
                groups[sid] = sorted(d.values(), key=lambda x: x[0])
                if sid not in order:
                    order.append(sid)

        # 线路顺序：按钮 data-source 顺序优先，其次容器出现顺序
        sid_order = [s for s in buttons.keys()]
        for s in order:
            if s not in sid_order:
                sid_order.append(s)

        play_from, play_url = [], []
        for sid in sid_order:
            eps = groups.get(sid)
            if not eps:
                continue
            line_name = buttons.get(sid) or ("线路%s" % sid)
            lines = ["%s$%s" % (ep_name, href) for _, ep_name, href in eps]
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join(lines))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": meta["area"] or area,
            "vod_year": meta["year"] or year,
            "vod_lang": lang,
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": subtitle,
            "vod_update": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def _decode_parts(self, html):
        """parts=["b64",...] 拼接后 base64 解码，返回裸 m3u8/mp4 直链。"""
        if not html:
            return ""
        m = _RE_PARTS.search(html)
        if not m:
            return ""
        parts = re.findall(r'"([^"]*)"', m.group(1))
        if not parts:
            return ""
        raw = "".join(parts).strip()
        # 补齐 base64 padding 到 4 的倍数
        raw += "=" * (-len(raw) % 4)
        try:
            decoded = base64.b64decode(raw).decode("utf-8", "ignore")
        except Exception:
            return ""
        decoded = decoded.strip()
        if decoded.startswith("http") and _RE_STREAM.search(decoded):
            return decoded
        return ""

    def _extract_stream(self, html):
        if not html:
            return ""
        stream = self._decode_parts(html)
        if stream:
            return stream
        # 兜底：页面直接出现裸 m3u8/mp4
        m = _RE_STREAM.search(html.replace("\\/", "/"))
        if m:
            url = m.group(0)
            if "zhengdasifuyuan.com" not in url:
                return url
        return ""

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # 传入本身已是裸直链，直接放行
        if _RE_STREAM.search(play_page):
            res = {"parse": 0, "playUrl": "", "url": play_page, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        stream = ""
        if "/player/" in play_page:
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

        if stream:
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链 parse=0 %s" % stream[:140])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        self.log("  => 嗅探兜底 parse=1 %s" % play_page[:120])
        return res

    # ---------------- 其他契约方法 ----------------
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
