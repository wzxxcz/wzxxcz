# -*- coding: utf-8 -*-
# ============================================================
#  大米电影网 — 由 Spider AutoGen v2 (Scrapling 版) 自动生成
#  适用：hipy / drpy-node / FongMi TVBox Python 内核（type=4 亦可配 app.py）
#  抓取：优先 Scrapling（Chrome TLS 指纹防拦截），未安装自动降级 requests
#  解析：纯正则实现，不依赖 lxml/bs4，任何环境都能跑
# ============================================================
import re
import json
from urllib.parse import urljoin, quote

try:
    from base.spider import Spider as _Base
except Exception:
    class _Base(object):
        def log(self, *args):
            pass

WARN_TEXT = """"""

NAME = '大米电影网'
HOST = 'https://www.hn-ntm.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
EXTRA_HEADERS = {}
INTRO_PREFIX = '🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！'
CLASSES = [
    {"type_id": '1', "type_name": '电影'},
    {"type_id": '2', "type_name": '电视剧'},
    {"type_id": '3', "type_name": '综艺'},
    {"type_id": '4', "type_name": '动漫'},
]
YEARS = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010', '2009', '2008', '2007']
AREAS = ['中国大陆', '美国', '日本', '韩国', '中国香港', '中国台湾', '英国', '法国']
CAT_TPLS = {
    '7': '/vodshow/7--------2---{page}.html',
    '13': '/vodshow/13--------2---{page}.html',
    '27': '/vodshow/27--------2---{page}.html',
    '31': '/vodshow/31--------2---{page}.html',
    '20': '/vodshow/20--------2---{page}.html',
}
DEFAULT_TPL = '/vodshow/{tid}--------2---{page}.html'
SEARCH_TPL = '/vodsearch/{wd}----------{page}---.html'

# ---------- 抓取引擎：Scrapling 可用则用，不可用自动降级 ----------
try:
    from scrapling.fetchers import Fetcher as _SL
    HAS_SL = True
except Exception:
    HAS_SL = False

if not HAS_SL:
    import requests
    import urllib3
    urllib3.disable_warnings()

_HEADERS = {
    "User-Agent": UA,
    "Referer": HOST + "/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
_HEADERS.update(EXTRA_HEADERS)


def _get(self, url, render=False):
    """返回 HTML 字符串。优先 Scrapling（Chrome TLS 指纹），失败降级 requests。"""
    html = ""
    if HAS_SL:
        try:
            p = _SL.get(url, headers=_HEADERS, impersonate="chrome",
                        stealthy_headers=True, timeout=15)
            body = getattr(p, "body", b"") or b""
            html = body.decode("utf-8", "ignore") if isinstance(body, bytes) else str(body)
            if "<" not in html[:600]:
                html = body.decode("gb18030", "ignore")
        except Exception as e:
            self.log("scrapling get fail: %s %s" % (url, e))
    if not html:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=15, verify=False)
            if r.encoding is None or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
        except Exception as e:
            self.log("requests get fail: %s %s" % (url, e))
    return html or ""


def _clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<") \
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"[\s\u3000\xa0]+", " ", s).strip()


def _abs(u, base):
    if not u:
        return ""
    u = u.replace("&amp;", "&").strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    try:
        return urljoin(base or HOST + "/", u)
    except Exception:
        return u


# ---------- 正则：卡片 ----------
_RE_CARD = re.compile(
    r'href=["\']([^"\']*?(?:voddetail|/detail/|/movie/|/tv/|/video/|/anime/|/dianshiju/'
    r'|/dongman/|/zongyi/|/duanju/|/show/)/?\d+[^"\']*?\.html?)["\']', re.I)
_RE_TITLE = re.compile(r'(?:title|alt)=["\']([^"\']{2,120})["\']')
_RE_CLS_TITLE = re.compile(r'class="[^"]*(?:title|name)[^"]*"[^>]*>([^<]{2,120})<')
_RE_PIC = re.compile(
    r'(?:data-original|data-src|data-lazy-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']',
    re.I)
_RE_REMARK = re.compile(
    r'class="[^"]*(?:note|remarks|remark|score|time|info|video-title|pic-text)[^"]*"[^>]*>([^<]{1,20})<')
_RE_NOISE = re.compile(r"登录|注册|APP|下载|专题|排行|公告|更多|首页|全部|求片|反馈")


def _cards(self, html, base=""):
    """从列表页 HTML 提取影片卡片。"""
    items, seen = [], set()
    for m in _RE_CARD.finditer(html or ""):
        href = m.group(1)
        if href in seen:
            continue
        seen.add(href)
        seg = html[m.end(): m.end() + 1500]
        tm = _RE_TITLE.search(seg[:600])
        name = _clean(tm.group(1)) if tm else ""
        if not name:
            tm = _RE_CLS_TITLE.search(seg[:600])
            if tm:
                name = _clean(tm.group(1))
        if not name or _RE_NOISE.search(name):
            continue
        pm = _RE_PIC.search(seg)
        rm = _RE_REMARK.search(seg[:1200])
        items.append({
            "vod_id": _abs(href, base),
            "vod_name": name[:100],
            "vod_pic": _abs(pm.group(1), base) if pm else "",
            "vod_remarks": _clean(rm.group(1)) if rm else "",
        })
        if len(items) >= 60:
            break
    return items


# ---------- 正则：详情 / 剧集 / 播放 ----------
_RE_H1 = re.compile(r"<h1[^>]*>([^<]{1,120})<")
_RE_EP_A = re.compile(
    r'<a[^>]*?href=["\']([^"\']*?/(?:play|vodplay)/[^"\']+)["\']([^>]*)>(.*?)</a>', re.I | re.S)
_RE_ORIGIN = re.compile(r'data-origin=["\']([^"\']+)["\']')
_RE_LINE_HINT = re.compile(r'/play/([a-z0-9_]+)/', re.I)
_RE_M3U8 = re.compile(r'["\']([^"\']*?\.m3u8[^"\']*?)["\']', re.I)
_RE_PLAYER_VAR = re.compile(r'player_aaaa\s*=\s*(\{.*?\})\s*<', re.S)
_RE_JSON_URL = re.compile(r'"url"\s*:\s*"([^"]+)"')
_RE_META = re.compile(r'(导演|主演|类型|地区|语言|年份|日期)\s*[:：]\s*([^<\n]{1,80})<')
_RE_DESC = re.compile(
    r'class="[^"]*(?:desc|content|intro|sketch|detail)[^"]*"[^>]*>([\s\S]{20,4000}?)</',
    re.I)


def _strip(s):
    return _clean(s)


class Spider(_Base):

    def getName(self):
        return NAME

    def init(self, extend=""):
        self._play_cache = {}
        self.log(NAME + " init ok, scrapling=%s" % HAS_SL)

    def isVideoFormat(self, url):
        return True

    def destroy(self):
        pass

    def close(self):
        pass

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        result = {"class": CLASSES}
        if filter:
            result["filters"] = {c["type_id"]: {
                "year": {"key": "year", "name": "年份",
                         "value": [{"n": y, "v": y} for y in YEARS]},
                "area": {"key": "area", "name": "地区",
                         "value": [{"n": a, "v": a} for a in AREAS]},
            } for c in CLASSES}
        try:
            result["list"] = _cards(self, _get(self, HOST + "/"), HOST)
        except Exception:
            result["list"] = []
        return result

    def homeVideoContent(self):
        return {"list": []}

    # ---------------- 分类 ----------------
    def _cat_url(self, tid, pg, ext):
        tpl = CAT_TPLS.get(tid) or DEFAULT_TPL
        u = tpl.replace("{tid}", str(tid))
        e = ext
        if isinstance(e, str):
            try:
                e = json.loads(e)
            except Exception:
                e = {}
        if isinstance(e, dict) and e:
            vals = dict((k, str(v)) for k, v in e.items() if v)
            if vals:
                segs = u.split("-")
                if "vodshow" in u and len(segs) >= 9 and "area" in vals:
                    segs[1] = quote(vals["area"], safe="")
                    u = "-".join(segs)
                else:
                    q = "&".join("%s=%s" % (k, quote(v)) for k, v in vals.items())
                    u = u + ("&" if "?" in u else "?") + q
        return u.replace("{page}", str(pg))

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        url = self._cat_url(tid, pg, extend)
        if url.startswith("/"):
            url = HOST + url
        html = _get(self, url)
        lst = _cards(self, html, url)
        return {"list": lst, "page": pg, "pagecount": 9999,
                "limit": 60, "total": 999999}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        u = SEARCH_TPL.replace("{wd}", quote(str(key), safe="")) \
                      .replace("{page}", str(pg))
        if u.startswith("/"):
            u = HOST + u
        html = _get(self, u)
        return {"list": _cards(self, html, u), "page": pg}

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        if "$" in vid:
            vid = vid.split("$")[-1]
        html = _get(self, vid)
        name, pic, content = "", "", ""
        m = _RE_H1.search(html)
        if m:
            name = _strip(m.group(1)).strip("《》")
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = _clean(m.group(1).split("_")[0].split("-")[0]).strip("《》")
        m = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                      html, re.I)
        if m:
            pic = _abs(m.group(1), vid)
        m = _RE_DESC.search(html)
        if m:
            content = _strip(m.group(1))[:2000]
        vod = {
            "vod_id": vid,
            "vod_name": name or "未知",
            "vod_pic": pic,
            "type_name": "",
            "vod_year": "", "vod_area": "", "vod_remarks": "",
            "vod_actor": "", "vod_director": "",
            "vod_content": (INTRO_PREFIX or "") + content,
        }
        for mm in _RE_META.finditer(html[:60000]):
            k, v = mm.group(1), _strip(mm.group(2))[:50]
            if k == "导演" and not vod["vod_director"]:
                vod["vod_director"] = v
            elif k == "主演" and not vod["vod_actor"]:
                vod["vod_actor"] = v
            elif k == "地区" and not vod["vod_area"]:
                vod["vod_area"] = v
            elif k == "年份":
                ym = re.search(r"(19|20)\d{2}", v)
                if ym and not vod["vod_year"]:
                    vod["vod_year"] = ym.group(0)

        # 剧集：按线路分组（data-origin 或 /play/线路名/）
        buckets, seen = {}, set()
        for m in _RE_EP_A.finditer(html):
            href, attrs, inner = m.group(1), m.group(2), m.group(3)
            if href.startswith(("javascript", "#")):
                continue
            ep = _strip(inner) or "第1集"
            if len(ep) > 40:
                ep = "第%d集" % (len(buckets.get("默认线路", [])) + 1)
            om = _RE_ORIGIN.search(attrs)
            lm = _RE_LINE_HINT.search(href)
            vm = re.search(r'/vodplay/\d+-(\d+)-', href)
            line = (om.group(1) if om else
                    ("线路" + vm.group(1)) if vm else
                    (lm.group(1) if lm else "默认线路"))
            ep_url = _abs(href, vid)
            if ep_url in seen:
                continue
            seen.add(ep_url)
            buckets.setdefault(line, []).append((ep, ep_url))
        if not buckets:
            for m in re.finditer(
                    r'<a[^>]*?href=["\']([^"\']*?(?:/player/|\?play=|/play\?)[^"\']+)["\'][^>]*>(.*?)</a>',
                    html, re.I | re.S):
                href, ep = m.group(1), _strip(m.group(2)) or "第1集"
                ep_url = _abs(href, vid)
                if ep_url in seen:
                    continue
                seen.add(ep_url)
                buckets.setdefault("默认线路", []).append((ep, ep_url))
        lines = list(buckets.items()) or [("默认线路", [("第1集", vid)])]
        names, urls = [], []
        for line, eps in lines:
            names.append(line)
            urls.append("#".join("%s$%s" % (ep, u) for ep, u in eps))
        vod["vod_play_from"] = "$$$".join(names)
        vod["vod_play_url"] = "$$$".join(urls)
        return vod

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        pid = id
        if "___" in pid:
            pid = pid.split("___")[0]
        if "$" in pid:
            pid = pid.split("$")[-1]
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        html = _get(self, pid)
        url = ""
        if html:
            m = _RE_PLAYER_VAR.search(html)
            if m:
                try:
                    j = json.loads(m.group(1).replace("'", '"'))
                    url = (j.get("url") or "").replace("\\/", "/")
                except Exception:
                    m2 = _RE_JSON_URL.search(m.group(1))
                    if m2:
                        url = m2.group(1).replace("\\/", "/")
            if not url:
                m = _RE_M3U8.search(html.replace("\\/", "/"))
                if m:
                    url = m.group(1)
        if not url:
            return {"parse": 1, "playUrl": "", "url": pid, "header": headers}
        url = _abs(url, pid)
        if ".m3u8" not in url and ".mp4" not in url:
            return {"parse": 1, "playUrl": "", "url": url, "header": headers}
        return {"parse": 0, "playUrl": "", "url": url, "header": headers}
