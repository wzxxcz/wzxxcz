# coding=utf-8
"""
SA视频 lsjys11.com | TVBox Python 爬虫 (V1.1 最终修正版)
修正记录：
  - 修正搜索接口参数名为 keywords
  - 优化短剧/无 data-title 剧集的提取
  - 播放统一走 parse:1 (因 API 请求加密无法伪造)
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
                print("[savideo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.lsjys11.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/favicon.ico"

CLASSES = [
    {"type_id": "13", "type_name": "电影"},
    {"type_id": "12", "type_name": "连续剧"},
    {"type_id": "11", "type_name": "综艺"},
    {"type_id": "16", "type_name": "短剧"},
    {"type_id": "14", "type_name": "动漫"},
    {"type_id": "15", "type_name": "纪录片"},
]

_RE_NUXT = re.compile(
    r'<script\s+id="__NUXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>',
    re.S | re.I)


class Spider(Spider):

    def getName(self):
        return "SA视频"

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

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
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

    # ---------------- 列表解析 ----------------
    def _extract_videos(self, html):
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.log("缺少 BeautifulSoup, 请先 pip install beautifulsoup4")
            return []

        videos = []
        seen = set()
        if not html:
            return videos

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.c-movie-list-item')
        self.log("  DOM items: %d" % len(items))

        for item in items:
            try:
                a_tag = item.select_one('a')
                if not a_tag:
                    continue
                href = a_tag.get('href', '') or ''
                if '/link?' in href or not href:
                    continue
                if href in seen:
                    continue
                seen.add(href)

                vod_id = href.rstrip('/').split('/')[-1]

                img_tag = item.select_one('img')
                pic = ''
                if img_tag:
                    pic = img_tag.get('src', '') or img_tag.get('data-src', '')
                if not pic or pic.startswith('data:'):
                    pic = self.default_pic
                pic = self._fix_url(pic)

                name = ''
                for sel in ['.line-clamp-2', '[class*="line-clamp-2"]',
                            '[class*="series-name"]', '.truncate', 'p']:
                    tag = item.select_one(sel)
                    if tag:
                        t = tag.text.strip()
                        if t and len(t) < 100:
                            name = t
                            break
                if not name and img_tag:
                    name = (img_tag.get('alt') or '').strip()
                if not name:
                    name = vod_id

                score = '0'
                for sel in ['[class*="FF7231"]', '[class*="text-"]']:
                    tag = item.select_one(sel)
                    if tag:
                        m = re.search(r'\d+\.\d+', tag.text)
                        if m:
                            score = m.group(0)
                            break

                remark = ''
                for tag in item.find_all(['div', 'span']):
                    txt = tag.text.strip()
                    if not txt or len(txt) > 20:
                        continue
                    if ('集' in txt or '更新' in txt or '全' in txt):
                        remark = txt
                        break

                videos.append({
                    "vod_id":      vod_id,
                    "vod_name":    name[:100],
                    "vod_pic":     pic,
                    "vod_remarks": remark,
                    "vod_score":   score,
                })
            except Exception:
                continue

        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = []
        for pat in [r'/movie/list/(\d+)', r'[?&]page=(\d+)']:
            pages += re.findall(pat, html)
        nums = [int(x) for x in pages if str(x).isdigit()]
        return max(nums) if nums else 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES}

    def homeVideoContent(self):
        html = self._fetch("%s/movie/list?cat_id=13" % self.site_url)
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page <= 1:
            url = "%s/movie/list?cat_id=%s" % (self.site_url, tid)
        else:
            url = "%s/movie/list/%d?cat_id=%s" % (self.site_url, page, tid)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        kw = urllib.parse.quote(key)
        page = int(pg) if pg else 1
        # ⚠️ 修正：参数名为 keywords
        url = "%s/search?keywords=%s&page=%d" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  命中 %d 条" % len(videos))
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情页解析 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = str(ids[0])

        if raw.startswith("http"):
            url = raw
            vod_id = url.rstrip('/').split('/')[-1]
        else:
            vod_id = raw
            url = "%s/movie/detail/%s" % (self.site_url, vod_id)

        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return {"list": []}

        soup = BeautifulSoup(html, 'html.parser')

        name = ''
        h1 = soup.select_one('h1')
        if h1:
            name = self._clean(h1.text)
        if not name:
            t = soup.select_one('title')
            if t:
                name = self._clean(t.text.split('_')[0].split('-')[0])

        content = ''
        for tag in soup.find_all(['div', 'p', 'span']):
            cls = ' '.join(tag.get('class') or [])
            if 'break-all' in cls or 'description' in cls.lower():
                txt = self._clean(tag.text)
                if len(txt) > 20:
                    content = txt
                    break
        if not content:
            for tag in soup.find_all('div'):
                txt = self._clean(tag.text)
                if len(txt) > 30 and len(txt) < 3000:
                    content = txt
                    break

        pic = self.default_pic
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if 'uploads' in src or 'movie_cover' in src or 'cover' in src:
                pic = self._fix_url(src)
                break

        director = ''
        actor = ''
        score = ''
        for div in soup.find_all('div'):
            txt = div.text
            m = re.search(r'导演\s*[:：]\s*([^\n]{1,80})', txt)
            if m and not director:
                director = self._clean(m.group(1))
            m = re.search(r'主演\s*[:：]\s*([^\n]{1,300})', txt)
            if m and not actor:
                actor = self._clean(m.group(1))
        m = re.search(r'\b(\d+\.\d)\b', html)
        if m:
            score = m.group(1)

        # ---------- 剧集列表 ----------
        play_from = []
        play_url = []

        nuxt_result = self._extract_nuxt_episodes(html)
        if nuxt_result:
            for line_name, eps in nuxt_result:
                play_from.append(line_name)
                ep_str = "#".join("%s$%s" % (n, i) for n, i in eps)
                play_url.append(ep_str)
            self.log("nuxt 剧集: %d 线路" % len(play_from))

        if not play_from:
            season_divs = soup.select('.season > div')
            self.log("  DOM season divs: %d" % len(season_divs))
            if season_divs:
                eps = []
                for idx, div in enumerate(season_divs):
                    ep_name = self._clean(div.text)
                    if not ep_name:
                        continue
                    ep_id = "%s__%d" % (vod_id, idx + 1)
                    eps.append("%s$%s" % (ep_name, ep_id))
                if eps:
                    play_from.append("SA线路")
                    play_url.append("#".join(eps))

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       pic,
            "vod_content":   content,
            "vod_actor":     actor,
            "vod_director":  director,
            "vod_score":     score,
            "vod_remarks":   ("%d条线路" % len(play_from)) if play_from else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _extract_nuxt_episodes(self, html):
        m = _RE_NUXT.search(html)
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
        except Exception:
            return None
        if not isinstance(data, list):
            return None

        def resolve(ref, depth=0):
            if depth > 5:
                return ref
            if isinstance(ref, int) and 0 <= ref < len(data):
                v = data[ref]
                if isinstance(v, int) and 0 <= v < len(data) and v != ref:
                    return resolve(v, depth + 1)
                return v
            return ref

        movie_data = None
        for it in data:
            if isinstance(it, dict) and 'play_links' in it and 'links' in it:
                movie_data = it
                break
        if not movie_data:
            return None

        links_ref = movie_data.get('links')
        links_arr = []
        if isinstance(links_ref, list):
            for r in links_ref:
                links_arr.append(resolve(r))
        else:
            r = resolve(links_ref)
            if isinstance(r, list):
                links_arr = r
            elif r is not None:
                links_arr = [r]

        result = []
        for group_ref in links_arr:
            group = resolve(group_ref)
            if not isinstance(group, dict):
                continue
            line_name = resolve(group.get('name')) or '线路'
            items_ref = group.get('items')
            items_arr = resolve(items_ref) if not isinstance(items_ref, list) else items_ref
            if not isinstance(items_arr, list):
                continue
            eps = []
            for ep_ref in items_arr:
                ep = resolve(ep_ref)
                if not isinstance(ep, dict):
                    continue
                ep_id = resolve(ep.get('id'))
                ep_name = resolve(ep.get('name'))
                if ep_id and isinstance(ep_id, str) and ep_name:
                    eps.append((str(ep_name), ep_id))
            if eps:
                result.append((str(line_name), eps))

        return result if result else None

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        # 因 SA 视频的播放 API 请求体加密，Python 无法直接伪造
        # 所以我们让 TVBox 使用内置嗅探器 (parse: 1)
        if "__" in id and id.split("__")[-1].isdigit():
            vod_id = "__".join(id.split("__")[:-1])
            target = "%s/movie/detail/%s" % (self.site_url, vod_id)
        elif id.startswith("http"):
            target = id
        else:
            target = self.site_url + "/"

        self.log("player -> %s (parse=1)" % target)
        return {
            "parse": 1,
            "playUrl": "",
            "url": target,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }

    # ---------------- 图片代理 ----------------
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
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }, timeout=15)
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
