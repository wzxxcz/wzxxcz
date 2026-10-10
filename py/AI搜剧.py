# coding=utf-8
"""
AI搜剧 TVBox Python 爬虫
站点：http://dysou.de5.net/
"""
import re
import sys
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                    pool_connections=20, pool_maxsize=20, max_retries=0)
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
                print("[dysou]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "http://dysou.de5.net"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "hot_movie", "type_name": "电影"},
    {"type_id": "hot_tv",    "type_name": "电视剧"},
    {"type_id": "variety",   "type_name": "综艺"},
    {"type_id": "jp",        "type_name": "短剧"},
    {"type_id": "dm",        "type_name": "动漫"},
]

# ============ 内联采集源 API ============
API_SITES = [
    {"key": "dyttzy",  "name": "天堂 HD",  "api": "http://caiji.dyttzyapi.com/api.php/provide/vod"},
    {"key": "heimuer", "name": "豪华 HD",  "api": "https://hhzyapi.com/api.php/provide/vod"},
    {"key": "ruyi",    "name": "如意 HD",  "api": "https://cj.rycjapi.com/api.php/provide/vod"},
    {"key": "bfzy",    "name": "暴风 HD",  "api": "https://bfzyapi.com/api.php/provide/vod"},
    {"key": "tyyszy",  "name": "天涯 HD",  "api": "https://tyyszy.com/api.php/provide/vod"},
    {"key": "ffzy",    "name": "非凡 HD",  "api": "http://ffzy5.tv/api.php/provide/vod"},
    {"key": "zy360",   "name": "360资源",  "api": "https://360zy.com/api.php/provide/vod"},
    {"key": "wolong",  "name": "西瓜 HD",  "api": "https://caiji.xgzyapi.com/api.php/provide/vod/"},
    {"key": "jisu",    "name": "极速 HD",  "api": "https://jszyapi.com/api.php/provide/vod"},
    {"key": "dbzy",    "name": "量子 HD",  "api": "https://cj.lziapi.com/api.php/providedown/vod/"},
    {"key": "mdzy",    "name": "魔都 HD",  "api": "https://mdzyapi.com/api.php/provide/vod/"},
    {"key": "wujin",   "name": "无尽 HD",  "api": "https://api.wujinapi.me/api.php/provide/vod"},
    {"key": "ikun",    "name": "新浪 HD",  "api": "https://api.xinlangapi.com/xinlangapi.php/provide/vod/"},
    {"key": "mzzy",    "name": "速播 HD",  "api": "https://subocj.com/api.php/provide/vod"},
]

SOURCE_NAME = {s["key"]: s["name"] for s in API_SITES}


class Spider(Spider):

    def getName(self):
        return "AI搜剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.host = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        self.log("init: host=%s" % self.host)

    # ============ 工具 ============
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "http:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

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

    def _fetch(self, url, timeout=20, extra_headers=None):
        try:
            h = dict(self.headers)
            if extra_headers:
                h.update(extra_headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    # ============ 首页 ============
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        # 调分类接口拿第一页
        videos = []
        seen = set()
        for tid in ["hot_movie", "hot_tv"]:
            one = self.categoryContent(tid, "1", False, {})
            for v in one.get("list", []):
                if v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                videos.append(v)
        return {"list": videos}

    # ============ 分类（AJAX JSON） ============
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = "%s/%s.php?ajax=1&page=%d" % (self.host, tid, page)
        self.log("category: %s" % url)

        text = self._fetch(url)
        if not text:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        try:
            data = json.loads(text)
        except Exception as e:
            self.log("category json fail: %s" % e)
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        items = data.get("list") or []
        videos = []
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            poster = item.get("poster") or ""
            # 若图片是外链，包一层你自己的 image_proxy
            if poster.startswith("http"):
                pic = "%s/image_proxy.php?url=%s" % (
                    self.host, urllib.parse.quote(poster, safe=""))
            else:
                pic = self._fix_url(poster)

            videos.append({
                "vod_id": title,   # 详情按片名查
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": item.get("rate") or "",
            })

        has_more = len(videos) >= 12
        pagecount = page + 1 if has_more else page

        self.log("category 得到 %d 条" % len(videos))
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ============ 搜索 ============
    def _search_one(self, site, keyword):
        url = site["api"] + "?ac=detail&wd=" + urllib.parse.quote(keyword) + "&pg=1"
        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": site["api"],
                "Accept": "application/json,*/*",
            }, timeout=8)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
            items = data.get("list") or []
            out = []
            for item in items:
                name = (item.get("vod_name") or "").strip()
                if not name:
                    continue
                out.append({
                    "vod_id": "%s|%s|%s" % (site["key"],
                                              str(item.get("vod_id") or ""),
                                              name),
                    "vod_name": name,
                    "vod_pic": item.get("vod_pic") or "",
                    "vod_remarks": item.get("vod_remarks") or "",
                    "source": site["key"],
                    "source_name": site["name"],
                    "vod_time": item.get("vod_time") or "",
                })
            return out
        except Exception as e:
            self.log("  search %s fail: %s" % (site["key"], e))
            return []

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        self.log("search: %s" % key)

        all_results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(self._search_one, s, key) for s in API_SITES]
            for f in as_completed(futures, timeout=12):
                try:
                    all_results.extend(f.result())
                except Exception:
                    pass

        # 去重
        seen = set()
        unique = []
        for item in all_results:
            k = item["vod_name"] + "_" + item["source"]
            if k in seen:
                continue
            seen.add(k)
            unique.append(item)

        # 按时间倒序
        def _t(x):
            v = x.get("vod_time") or ""
            try:
                return time.mktime(time.strptime(v, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                return 0
        unique.sort(key=_t, reverse=True)

        # 图片包装
        for item in unique:
            pic = item.get("vod_pic") or ""
            if pic.startswith("http"):
                item["vod_pic"] = "%s/image_proxy.php?url=%s" % (
                    self.host, urllib.parse.quote(pic, safe=""))
            else:
                item["vod_pic"] = self._fix_url(pic)

        limit = 24
        total = len(unique)
        pagecount = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit

        self.log("search 共 %d 条" % total)
        return {
            "list": unique[start:end],
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ============ 详情 ============
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])

        if "|" in vod_id:
            # 从搜索来的：source|raw_id|name
            parts = vod_id.split("|", 2)
            source, raw_id, name = parts[0], parts[1], parts[2]
            return self._detail_by_source(source, raw_id, name)
        else:
            # 从分类/首页来的：就是片名
            return self._detail_by_name(vod_id)

    def _detail_by_name(self, name):
        """抓 detail.php?wd=xxx 页面"""
        url = "%s/detail.php?wd=%s" % (self.host, urllib.parse.quote(name))
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = name
        m = re.search(r'<div class="detail-title">[\s\S]*?</i>\s*([^<]+?)\s*</div>', html)
        if m:
            title = self._clean(m.group(1))

        # 封面
        pic = ""
        m = re.search(r'<img\s+src="([^"]+)"\s+class="detail-poster"', html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = re.search(r'<div class="detail-desc">([\s\S]*?)</div>', html)
        if m:
            content = self._clean(m.group(1))

        # 年份/地区
        year = ""
        area = ""
        badges = re.findall(r'<span class="detail-badge"[^>]*>([^<]+)</span>', html)
        if len(badges) >= 2:
            year = badges[0].strip()
            area = badges[1].strip()

        # 从页面里拿第一个 play.php 按钮的 source + id
        m = re.search(
            r'href="play\.php\?source=([^&]+)&id=([^&]+)&from=([^&]+)&episode=\d+"',
            html)
        if not m:
            # 没有播放按钮
            return {"list": [{
                "vod_id": name, "vod_name": title, "vod_pic": pic,
                "vod_content": content, "vod_year": year, "vod_area": area,
                "vod_play_from": "", "vod_play_url": "",
            }]}

        source = m.group(1)
        raw_id = m.group(2)

        # 调站里的 source_concurrent.php 拿所有线路和 m3u8
        play_info = self._fetch_source_concurrent(title, raw_id, "")

        return {"list": [{
            "vod_id": name,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_year": year,
            "vod_area": area,
            "vod_play_from": play_info["from"],
            "vod_play_url": play_info["url"],
        }]}

    def _detail_by_source(self, source, raw_id, name):
        play_info = self._fetch_source_concurrent(name, raw_id, "")
        info = self._fetch_from_source(source, raw_id)
        pic = ""
        if info:
            pic = info.get("vod_pic") or ""
            name = info.get("vod_name") or name

        return {"list": [{
            "vod_id": "%s|%s|%s" % (source, raw_id, name),
            "vod_name": name,
            "vod_pic": self._fix_url(pic),
            "vod_content": (info or {}).get("vod_content") or "",
            "vod_year": (info or {}).get("vod_year") or "",
            "vod_area": (info or {}).get("vod_area") or "",
            "vod_play_from": play_info["from"],
            "vod_play_url": play_info["url"],
        }]}

    def _fetch_from_source(self, source_key, raw_id):
        site = next((s for s in API_SITES if s["key"] == source_key), None)
        if not site:
            return None
        url = site["api"] + "?ac=detail&ids=" + urllib.parse.quote(str(raw_id))
        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": site["api"]}, timeout=10)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
            if data.get("list"):
                return data["list"][0]
        except Exception as e:
            self.log("fetch_from_source fail: %s" % e)
        return None

    def _fetch_source_concurrent(self, vod_name, vod_id, vod_type):
        """调目标站 api/source_concurrent.php"""
        url = "%s/api/source_concurrent.php?vod_name=%s&vod_id=%s&type=%s" % (
            self.host, urllib.parse.quote(vod_name),
            urllib.parse.quote(str(vod_id)),
            urllib.parse.quote(vod_type or ""))
        self.log("source_concurrent: %s" % url[:120])

        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": self.host + "/",
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=25)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            data = json.loads(text)
        except Exception as e:
            self.log("source_concurrent fail: %s" % e)
            return {"from": "", "url": ""}

        if data.get("code") != 200 or not data.get("data"):
            return {"from": "", "url": ""}

        src_map = data["data"]
        from_list = []
        url_list = []

        for src_key, src_data in src_map.items():
            play_lists = src_data.get("play_lists") or {}
            for from_key, eps in play_lists.items():
                if not isinstance(eps, list) or not eps:
                    continue
                m3u8_eps = [e for e in eps
                            if isinstance(e.get("url"), str)
                            and ".m3u8" in e["url"].lower()]
                if not m3u8_eps:
                    continue

                line_name = SOURCE_NAME.get(src_key, src_key)
                ep_strs = []
                for ep in m3u8_eps:
                    ep_name = ep.get("name") or "正片"
                    ep_url = ep.get("url") or ""
                    if not ep_url:
                        continue
                    ep_strs.append("%s$%s|%s" % (ep_name, src_key, ep_url))

                if not ep_strs:
                    continue

                from_list.append(line_name)
                url_list.append("#".join(ep_strs))

        self.log("source_concurrent: %d 条线路" % len(from_list))
        return {"from": "$$$".join(from_list), "url": "$$$".join(url_list)}

    # ============ 播放 ============
    def playerContent(self, flag, id, vipFlags):
        """id 格式： source|m3u8_url"""
        url = id
        if "|" in url:
            url = url.split("|", 1)[1]
        url = self._fix_url(url)

        self.log("player: %s" % url[:120])

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": UA,
                "Referer": self.host + "/",
            },
        }

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
