# -*- coding: utf-8 -*-
"""
奇速电影网 (qisudy.com) T4 Python 源
CMS: 苹果CMS V10 + 首涂模板028
URL结构:
  首页: /
  分类: /type/{id}.html  (电影1 电视剧2 综艺3 动漫4 短剧5)
  详情: /html/{vod_id}.html
  播放: /play/{vod_id}-{sid}-{nid}.html
  搜索: /search/{wd}-------------.html
播放解析: 播放页内嵌 player_aaaa JSON, url字段为m3u8直链(URL编码,需unquote)
"""

import re
import json
import sys
from urllib.parse import quote, unquote, urljoin

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    HOST = "https://www.qisudy.com"

    CATEGORIES = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "电视剧"},
        {"type_id": "3", "type_name": "综艺"},
        {"type_id": "4", "type_name": "动漫"},
        {"type_id": "5", "type_name": "短剧"},
    ]

    def init(self, extend=""):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
            "Referer": self.HOST + "/",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        except ImportError:
            self.session = None

    def getName(self):
        return "奇速电影网"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    # ---------------- HTTP ----------------
    def _fetch(self, url):
        if not url:
            return ""
        if self.session:
            try:
                r = self.session.get(url, timeout=15, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception as e:
                print("[qisudy] req err: {}".format(str(e)[:80]))
        fetch = getattr(self, "fetch", None)
        if callable(fetch):
            try:
                t = fetch(url, headers=self.headers)
                if isinstance(t, bytes):
                    return t.decode('utf-8', errors='replace')
                return str(t)
            except Exception:
                pass
        try:
            import urllib.request, ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception:
            return ""

    def _pic(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.HOST + url
        return urljoin(self.HOST + "/", url)

    @staticmethod
    def _clean(text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    # ---------------- 列表解析 ----------------
    def _parse_list(self, html):
        """
        苹果CMS标准影片卡片:
        <a class="hl-item-thumb hl-lazy" href="/html/107246.html" title="冬城猎凶"
           data-original="/upload/vod/xxx.jpg">
          ...
          <div class="hl-pic-text"><span class="hl-lc-1 remarks">更新至12集</span></div>
        </a>
        <div class="hl-item-title"><a href="/html/107246.html" title="冬城猎凶">冬城猎凶</a></div>
        """
        videos = []
        seen = set()
        # 匹配详情页链接 /html/{id}.html
        for m in re.finditer(
            r'<a[^>]+class="[^"]*hl-item-thumb[^"]*"[^>]+href="(/html/(\d+)\.html)"[^>]*title="([^"]*)"[^>]*>',
            html, re.DOTALL
        ):
            detail_url = m.group(1)
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            name = self._clean(m.group(3))

            # 从当前 a 标签之后的一小段里找封面和备注
            tail = html[m.end():m.end() + 600]

            pic = ""
            pm = re.search(r'data-original="([^"]+)"', m.group(0))
            if pm:
                pic = self._pic(pm.group(1))
            if not pic:
                pm = re.search(r'data-original="([^"]+)"', tail)
                if pm:
                    pic = self._pic(pm.group(1))

            remark = ""
            rm = re.search(r'<span[^>]*class="[^"]*remarks[^"]*"[^>]*>(.*?)</span>', tail, re.DOTALL)
            if rm:
                remark = self._clean(rm.group(1))

            if name and vid:
                videos.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
        return videos

    # ---------------- 六接口 ----------------
    def homeContent(self, filter):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                   for c in self.CATEGORIES]
        html = self._fetch(self.HOST + "/")
        videos = self._parse_list(html)
        return {"class": classes, "list": videos}

    def homeVideoContent(self):
        html = self._fetch(self.HOST + "/")
        return {"list": self._parse_list(html)[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1

        if page == 1:
            url = "{}/type/{}.html".format(self.HOST, tid)
        else:
            url = "{}/type/{}-{}.html".format(self.HOST, tid, page)

        html = self._fetch(url)
        videos = self._parse_list(html)

        # 分页总数: 从分页链接提取最大页码
        pagecount = page
        pages = re.findall(r'/type/{}-(\d+)\.html'.format(tid), html)
        if pages:
            pagecount = max(int(p) for p in pages)

        return {
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": len(videos) or 20,
            "total": max(pagecount, page) * 20,
            "list": videos,
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        m = re.search(r'(\d+)', vid)
        if m:
            vid = m.group(1)

        html = self._fetch("{}/html/{}.html".format(self.HOST, vid))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h2[^>]*class="[^"]*hl-dc-title[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
            if m:
                name = self._clean(m.group(1)).split("-")[0].split("|")[0].strip()

        # 封面
        pic = ""
        m = re.search(r'<span[^>]*class="[^"]*hl-item-thumb[^"]*"[^>]*data-original="([^"]+)"', html)
        if m:
            pic = self._pic(m.group(1))

        # 简介
        content = ""
        m = re.search(r'<span[^>]*class="[^"]*hl-content-text[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'og:description"\s+content="([^"]+)"', html)
            if m:
                content = self._clean(m.group(1))

        # 类型/年份/地区/备注
        vod_type = ""
        m = re.search(r'类型：</em>(.*?)</li>', html, re.DOTALL)
        if m:
            vod_type = self._clean(m.group(1))

        remarks = ""
        m = re.search(r'状态：</em><span[^>]*>(.*?)</span>', html, re.DOTALL)
        if m:
            remarks = self._clean(m.group(1))

        # 播放列表: <ul id="hl-plays-list"> 里的 /play/{vid}-{sid}-{nid}.html
        play_urls = []
        seen_ep = set()
        for em in re.finditer(
            r'<a[^>]+href="(/play/{}-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>'.format(vid),
            html, re.DOTALL
        ):
            ep_url = em.group(1)
            sid = em.group(2)
            nid = em.group(3)
            ep_name = self._clean(em.group(4))
            key = "{}-{}".format(sid, nid)
            if key in seen_ep:
                continue
            seen_ep.add(key)
            if not ep_name:
                ep_name = "第{}集".format(nid)
            full_url = self.HOST + ep_url
            play_urls.append("{}${}".format(ep_name, full_url))

        if not play_urls:
            play_urls.append("第1集${}/play/{}-1-1.html".format(self.HOST, vid))

        vod = {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": content,
            "vod_type": vod_type,
            "vod_remarks": remarks,
            "vod_play_from": "奇速电影网",
            "vod_play_url": "#".join(play_urls),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """
        播放解析:
        vod_play_url 存的是播放页完整URL (https://www.qisudy.com/play/{vid}-{sid}-{nid}.html)
        请求播放页, 从 player_aaaa JSON 的 url 字段取 m3u8 直链(URL编码, 需unquote)
        """
        play = str(id or "")
        if "$" in play:
            play = play.split("$", 1)[-1]

        if not play:
            return {"parse": 0, "url": ""}

        # 如果已经是m3u8直链, 直接返回
        if play.startswith("http") and (".m3u8" in play or ".mp4" in play):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play,
                "header": {"User-Agent": self.headers["User-Agent"],
                           "Referer": self.HOST + "/"}
            }

        html = self._fetch(play)
        if not html:
            return {"parse": 1, "playUrl": play, "url": play,
                    "header": {"User-Agent": self.headers["User-Agent"],
                               "Referer": self.HOST + "/"}}

        hdr = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.HOST + "/",
        }

        # 提取 player_aaaa
        m3u8 = ""
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                raw_url = data.get("url") or ""
                if raw_url:
                    m3u8 = unquote(raw_url)
            except (json.JSONDecodeError, ValueError):
                um = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if um:
                    m3u8 = unquote(um.group(1))

        # 兜底: 直接从HTML提取m3u8
        if not m3u8:
            m = re.search(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', html)
            if m:
                m3u8 = m.group(1).replace("\\/", "/")
            else:
                # 也许是被URL编码的
                m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                if m:
                    decoded = unquote(m.group(1))
                    if ".m3u8" in decoded or ".mp4" in decoded:
                        m3u8 = decoded

        if m3u8:
            return {"parse": 0, "playUrl": "", "url": m3u8, "header": hdr}
        else:
            return {"parse": 1, "playUrl": play, "url": play, "header": hdr}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1
        # 苹果CMS伪静态搜索: /search/{wd}-------------.html
        # 分页: /search/{wd}-------------{page}.html
        kw = quote(key)
        if page == 1:
            url = "{}/search/{}-------------.html".format(self.HOST, kw)
        else:
            url = "{}/search/{}-------------{}.html".format(self.HOST, kw, page)
        html = self._fetch(url)
        videos = self._parse_list(html)
        return {"list": videos, "page": page}

    def localProxy(self, param):
        return [200, "text/plain", b"ok"]
