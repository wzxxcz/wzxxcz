# coding=utf-8
"""
APP影院 MacCMS 蓝幽灵模板 TVBox Python 爬虫
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

    class _BaseSpider(object):
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=30, pool_maxsize=30, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, timeout=15, **kw):
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[appmovie]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.appmovie.art"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/blueghost/img/favicon.ico"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"
_SITE_ORDER = ["1", "5", "2", "3", "4"]

# 本地代理前缀（TVBox 默认 9978）
_PROXY = "http://127.0.0.1:9978/proxy?do=py&type=m3u8&url="

# ★★★ 开关：ts 分片是否也走代理 ★★★
# False = ts 直连（快），大多数情况可以播
# True  = ts 走代理（慢但保险），如果 False 黑屏/403，改成 True
_TS_VIA_PROXY = False

CLASSES = [
    {"type_id": "2", "type_name": "连续剧"},
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

_SORTS = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2011, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
]
_TYPES = {
    "2": ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
          "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "1": ["全部", "动作", "喜剧", "爱情", "科幻", "恐怖", "剧情", "战争", "纪录片"],
    "3": ["全部", "真人秀", "脱口秀", "喜剧", "晚会", "音乐", "游戏", "生活",
          "文化", "美食", "竞技"],
    "4": ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
          "儿童", "国漫", "日常", "爱情", "玄幻", "校园"],
}

def _mk_class(lst):
    return [{"n": x, "v": "" if x == "全部" else x} for x in lst]

FILTERS = {}
for _tid, _clist in _TYPES.items():
    FILTERS[_tid] = [
        {"key": "class", "name": "类型", "value": _mk_class(_clist)},
        {"key": "area",  "name": "地区", "value": _AREAS},
        {"key": "year",  "name": "年份", "value": _YEARS},
        {"key": "by",    "name": "排序", "value": _SORTS},
    ]


_RE_ITEM       = re.compile(r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>([\s\S]*?)</li>', re.I)
_RE_DETAIL_HREF = re.compile(r'href="([^"]*?/index\.php/vod/detail/id/\d+\.html)"', re.I)
_RE_TITLE_ATTR  = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC_ATTR    = re.compile(r'(?:data-original|data-src)="([^"]*)"', re.I)
_RE_REMARK      = re.compile(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)
_RE_H3_TITLE    = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_PLAYLIST_UL = re.compile(r'<ul[^>]*class="[^"]*stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_PLAY_A      = re.compile(r'<a[^>]*href="([^"]*?/index\.php/vod/play/[^"]+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_SID         = re.compile(r'/sid/(\d+)/')
_RE_PLAYER_DATA = re.compile(r'var\s+player_data\s*=\s*(\{[\s\S]*?\})\s*(?:</script>|;)', re.I)
_RE_DETAIL_NAME = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_DETAIL_PIC  = re.compile(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"', re.I)
_RE_DETAIL_DESC = re.compile(r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_META_DESC   = re.compile(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', re.I)
_RE_SCORE       = re.compile(r'vk-badge[^>]*>\s*([\d.]+)\s*<', re.I)


class Spider(Spider):

    def getName(self):
        return "APP影院"

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
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None):
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

    def _g(self, pat, html):
        m = re.search(pat, html, re.I)
        return self._clean(m.group(1)) if m else ""

    def _extract_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for block in _RE_ITEM.findall(html):
            m = _RE_DETAIL_HREF.search(block)
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            name = ""
            mt = _RE_TITLE_ATTR.search(block)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                mt = re.search(r'<a[^>]*>([^<]+)</a>', block, re.I)
                if mt:
                    name = self._clean(mt.group(1))
            pic = ""
            mp = _RE_PIC_ATTR.search(block)
            if mp:
                pic = mp.group(1)
            remark = ""
            mr = _RE_REMARK.search(block)
            if mr:
                remark = self._clean(mr.group(1))
            videos.append({
                "vod_id": href,
                "vod_name": name or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        m = re.search(r'<span class="num">\d+/(\d+)</span>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    def _build_show_url(self, tid, pg, extend):
        parts = ["/index.php/vod/show"]
        cls = extend.get("class")
        if cls:
            parts += ["class", urllib.parse.quote(str(cls))]
        area = extend.get("area")
        if area:
            parts += ["area", urllib.parse.quote(str(area))]
        year = extend.get("year")
        if year:
            parts += ["area", str(year)]
        by = extend.get("by")
        if by:
            parts += ["by", str(by)]
        parts += ["id", str(tid)]
        if pg and int(pg) > 1:
            parts += ["page", str(pg)]
        return self.site_url + "/".join(parts) + ".html"

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
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
        url = self._build_show_url(tid, pg, extend)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_list(html)
        pagecount = self._page_count(html)
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": pagecount * 24}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        wd = urllib.parse.quote(key)
        if pg > 1:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (self.site_url, pg, wd)
        else:
            url = "%s/index.php/vod/search.html?wd=%s" % (self.site_url, wd)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_list(html)
        pagecount = self._page_count(html)
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def _extract_play_groups(self, html):
        groups = {}
        blocks = re.split(r'<div[^>]*class="[^"]*stui-pannel[^"]*"', html, flags=re.I)
        for block in blocks[1:]:
            mt = _RE_H3_TITLE.search(block)
            if not mt:
                continue
            line_name = self._clean(mt.group(1))
            if not line_name or len(line_name) > 20:
                continue
            ml = _RE_PLAYLIST_UL.search(block)
            if not ml:
                continue
            eps = []
            for m in _RE_PLAY_A.finditer(ml.group(1)):
                href = m.group(1).replace("&amp;", "&")
                ep_name = self._clean(m.group(2))
                ms = _RE_SID.search(href)
                sid = ms.group(1) if ms else "1"
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append((sid, ep_name, self._fix_url(href)))
            if not eps:
                continue
            sid = eps[0][0]
            if sid not in groups:
                groups[sid] = {"name": line_name, "eps": []}
            for _, n, u in eps:
                groups[sid]["eps"].append((n, u))
        return groups

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = self._g(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', html)
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = name.strip() or vod_id

        pic = ""
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = m.group(1)

        v_type     = self._g(r'类型：</span><a[^>]*>([^<]+)</a>', html)
        v_area     = self._g(r'地区：</span><a[^>]*>([^<]+)</a>', html)
        v_year     = self._g(r'年份：</span><a[^>]*>([^<]+)</a>', html)
        v_status   = self._g(r'状态：\s*</span>([^<]+)', html)
        v_actor    = self._g(r'主演：</span>([^<]+)', html)
        v_director = self._g(r'导演：</span>([^<]+)', html)
        v_score    = self._g(r'vk-badge[^>]*>\s*([\d.]+)\s*<', html)

        content = ""
        m = _RE_DETAIL_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        groups = self._extract_play_groups(html)
        self.log("  剧集线路: %s" % {k: len(v["eps"]) for k, v in groups.items()})
        if not groups:
            return {"list": []}

        sids = [s for s in _SITE_ORDER if s in groups]
        sids += [s for s in groups if s not in sids]

        play_from = []
        play_url = []
        for sid in sids:
            info = groups[sid]
            play_from.append(info["name"])
            play_url.append("#".join("%s$%s" % (n, u) for n, u in info["eps"]))

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": self._fix_url(pic) or self.default_pic,
            "vod_content": content,
            "vod_actor": v_actor,
            "vod_director": v_director,
            "vod_year": v_year,
            "vod_area": v_area,
            "vod_remarks": v_status or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }
        if v_type:
            vod["type_name"] = v_type
            vod["vod_class"] = v_type
        if v_score:
            vod["vod_score"] = v_score
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 1800:
                return res

        html = self._fetch(play_page, headers={"Referer": self.site_url + "/"})
        real_url = ""
        from_tag = ""

        if html:
            m = _RE_PLAYER_DATA.search(html)
            if m:
                raw = m.group(1)
                data = None
                try:
                    data = json.loads(raw)
                except Exception:
                    try:
                        data = json.loads(raw.replace("\\/", "/"))
                    except Exception:
                        data = None
                if data:
                    real_url = data.get("url") or ""
                    from_tag = data.get("from") or ""
                else:
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if m2: real_url = m2.group(1)
                    m4 = re.search(r'"from"\s*:\s*"([^"]+)"', raw)
                    if m4: from_tag = m4.group(1)

            if not real_url:
                m = re.search(r'(https?://[^"\'\\\s]+?\.m3u8[^"\'\\\s]*)', html, re.I)
                if m:
                    real_url = m.group(1)

        if real_url:
            real_url = (real_url.replace("\\/", "/")
                        .replace("&amp;", "&").replace("\\u0026", "&"))
            if real_url.startswith("//"):
                real_url = "https:" + real_url

            self.log("  => [%s] %s" % (from_tag, real_url[:180]))

            # m3u8 走本地代理（带 Referer 拉取）
            proxy = _PROXY + urllib.parse.quote(real_url, safe="")

            res = {
                "parse": 0,
                "playUrl": "",
                "url": proxy,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    # ---------- 代理 ----------
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
                            url = urllib.parse.unquote(v)
            if not url:
                return [404, "text/plain", b"no url", ""]

            url = url.replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url

            now = int(time.time())

            # m3u8 内容缓存 5 分钟
            cache_key = "m3u8:" + url
            if cache_key in self._play_cache:
                ts, cached = self._play_cache[cache_key]
                if now - ts < 300:
                    return cached

            h = {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            rsp = self.fetch(url, headers=h, timeout=12)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "") or "application/octet-stream"

            # 内容是 m3u8 就处理内部地址
            if b"#EXTM3U" in content[:500] or "mpegurl" in ctype.lower():
                text = content.decode("utf-8", "ignore")
                p = urllib.parse.urlparse(url)
                base = url.rsplit("/", 1)[0] + "/"
                new_lines = []
                for ln in text.splitlines():
                    s = ln.strip()
                    # 处理 #EXT-X-KEY、#EXT-X-MAP 里的 URI
                    if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                        def _replace_uri(mo):
                            uri = mo.group(1)
                            if uri.startswith("http"):
                                full = uri
                            elif uri.startswith("/"):
                                full = "%s://%s%s" % (p.scheme, p.netloc, uri)
                            else:
                                full = base + uri
                            # key 也走代理
                            return 'URI="%s"' % (_PROXY + urllib.parse.quote(full, safe=""))
                        s = re.sub(r'URI="([^"]+)"', _replace_uri, s)
                        new_lines.append(s)
                        continue

                    if s and not s.startswith("#"):
                        if s.startswith("http"):
                            full = s
                        elif s.startswith("/"):
                            full = "%s://%s%s" % (p.scheme, p.netloc, s)
                        else:
                            full = base + s

                        if ".m3u8" in full.lower():
                            # 子 m3u8 继续走代理
                            new_lines.append(_PROXY + urllib.parse.quote(full, safe=""))
                        else:
                            # ts 分片
                            if _TS_VIA_PROXY:
                                new_lines.append(_PROXY + urllib.parse.quote(full, safe=""))
                            else:
                                new_lines.append(full)
                    else:
                        new_lines.append(ln)
                content = "\n".join(new_lines).encode("utf-8")
                ctype = "application/vnd.apple.mpegurl"

            result = [200, ctype, content, ""]

            if ".m3u8" in url.lower():
                self._play_cache[cache_key] = (now, result)
            return result

        except Exception as e:
            self.log("proxy FAIL %s" % e)
            return [500, "text/plain", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
