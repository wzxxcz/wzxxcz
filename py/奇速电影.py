# -*- coding: utf-8 -*-
"""
奇速电影网 (qisudy.com) T4 Python 源
CMS: 苹果CMS V10 + 首涂模板028
URL结构:
  首页: /
  分类: /type/{id}.html  (电影1 电视剧2 综艺3 动漫4 短剧5)
  筛选: /show/{type_id}-{class}-{area}-{lang}-{letter}-{year}-{by}-{page}.html
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

    # 筛选维度: (extend里的key, 页面显示的维度名)
    FILTER_DIMS = [
        ("class", "分类"),
        ("area", "地区"),
        ("lang", "语言"),
        ("letter", "字母"),
        ("year", "年份"),
        ("by", "排序"),
    ]

    # ================================================================
    #  生命周期
    # ================================================================

    def init(self, extend=""):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
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

    # ================================================================
    #  内部工具
    # ================================================================

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
            for fn in (lambda: fetch(url, headers=self.headers),
                       lambda: fetch(url, self.headers),
                       lambda: fetch(url)):
                try:
                    t = fn()
                    if t:
                        if isinstance(t, bytes):
                            return t.decode('utf-8', errors='replace')
                        return str(t)
                except Exception:
                    continue
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

    # ================================================================
    #  列表解析
    # ================================================================

    def _parse_list(self, html):
        """
        苹果CMS标准影片卡片:
        <a class="hl-item-thumb hl-lazy" href="/html/107246.html" title="冬城猎凶"
           data-original="/upload/vod/xxx.jpg">
          <div class="hl-pic-text"><span class="hl-lc-1 remarks">更新至12集</span></div>
        </a>
        <div class="hl-item-title"><a href="/html/107246.html" title="冬城猎凶">冬城猎凶</a></div>
        """
        videos = []
        seen = set()
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

    # ================================================================
    #  筛选解析
    # ================================================================

    def _parse_filters(self, html, tid):
        """
        从 /show/{tid}-----------.html 里解析筛选维度。
        页面结构:
          <div class="hl-filter-wrap ...">
            <div class="hl-filter-item hl-filter-text"><span>地区</span></div>
            <ul class="hl-filter-list ...">
              <li><a href="javascript:void(0)" class="hl-text-conch active">全部</a></li>
              <li><a href="/show/2-%E5%A4%A7%E9%99%86----------.html">大陆</a></li>
              ...
            </ul>
          </div>
        """
        filters = []
        for dim_key, dim_name in self.FILTER_DIMS:
            # 定位到「维度名」对应的那个 filter-wrap 里的 ul
            pattern = (
                r'<span>\s*' + re.escape(dim_name) + r'\s*</span>'
                r'.*?<ul[^>]*>(.*?)</ul>'
            )
            m = re.search(pattern, html, re.DOTALL)
            if not m:
                continue
            block = m.group(1)

            options = []
            for om in re.finditer(
                r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                block, re.DOTALL
            ):
                href = om.group(1).strip()
                label = self._clean(om.group(2))
                if not label or label == "全部":
                    continue
                if href.startswith("javascript"):
                    continue
                if not href.startswith("/show/"):
                    continue
                # href 形如 /show/2-大陆----------.html
                # 把 /show/ 前缀和 .html 后缀去掉，按 - 切
                path = href[len("/show/"):]
                if path.endswith(".html"):
                    path = path[:-len(".html")]
                parts = path.split("-")
                # 第一个位置是 type_id，跳过
                val = ""
                for i, p in enumerate(parts):
                    if i == 0:
                        continue
                    if p:
                        val = unquote(p)
                        break
                if not val:
                    continue
                options.append({"n": label, "v": val})

            if options:
                filters.append({
                    "key": dim_key,
                    "name": dim_name,
                    "value": [{"n": "全部", "v": ""}] + options
                })
        return filters

    # ================================================================
    #  六接口
    # ================================================================

    def homeContent(self, filter):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                   for c in self.CATEGORIES]

        # 逐主分类抓筛选页，填充 filters
        filters = {}
        for c in self.CATEGORIES:
            tid = c["type_id"]
            try:
                url = "{}/show/{}-----------.html".format(self.HOST, tid)
                html = self._fetch(url)
                f = self._parse_filters(html, tid)
                if f:
                    filters[tid] = f
            except Exception as e:
                print("[qisudy] filter err {}: {}".format(tid, str(e)[:80]))

        html = self._fetch(self.HOST + "/")
        videos = self._parse_list(html)
        return {"class": classes, "filters": filters, "list": videos}

    def homeVideoContent(self):
        html = self._fetch(self.HOST + "/")
        return {"list": self._parse_list(html)[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1

        extend = extend or {}

        # 判断是否有筛选条件被选中
        use_filter = False
        for k, _ in self.FILTER_DIMS:
            if extend.get(k):
                use_filter = True
                break

        if use_filter:
            # /show/{tid}-{class}-{area}-{lang}-{letter}-{year}-{by}-{page}.html
            parts = [str(tid)]
            for k, _ in self.FILTER_DIMS:
                v = extend.get(k, "") or ""
                parts.append(quote(v))
            path = "-".join(parts)
            url = "{}/show/{}-{}.html".format(self.HOST, path, page)
        else:
            # /type/{tid}.html 或 /type/{tid}-{page}.html
            if page == 1:
                url = "{}/type/{}.html".format(self.HOST, tid)
            else:
                url = "{}/type/{}-{}.html".format(self.HOST, tid, page)

        html = self._fetch(url)
        videos = self._parse_list(html)

        # 分页总数: 优先从当前 URL 里取最大页
        pagecount = page
        try:
            # 匹配 /show/...-{n}.html 或 /type/{tid}-{n}.html
            nums = re.findall(r'-(\d{1,5})\.html', html)
            if nums:
                cand = [int(n) for n in nums if 1 < int(n) < 10000]
                if cand:
                    pagecount = max(cand)
        except Exception:
            pass

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

        # 类型
        vod_type = ""
        m = re.search(r'类型：</em>(.*?)</li>', html, re.DOTALL)
        if m:
            vod_type = self._clean(m.group(1))

        # 备注
        remarks = ""
        m = re.search(r'状态：</em><span[^>]*>(.*?)</span>', html, re.DOTALL)
        if m:
            remarks = self._clean(m.group(1))

        # ------- 播放列表：只在 hl-plays-list 区块里找 -------
        list_block = ""
        m = re.search(r'<ul[^>]+id="hl-plays-list"[^>]*>(.*?)</ul>', html, re.DOTALL)
        if m:
            list_block = m.group(1)

        play_urls = []
        seen_ep = set()
        if list_block:
            for em in re.finditer(
                r'<a[^>]+href="(/play/{}-(\d+)-(\d+)\.html)"[^>]*>(.*?)</a>'.format(vid),
                list_block, re.DOTALL
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

        if play.startswith("http") and (".m3u8" in play or ".mp4" in play):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play,
                "header": {"User-Agent": self.headers["User-Agent"],
                           "Referer": self.HOST + "/"}
            }

        html = self._fetch(play)
        hdr = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.HOST + "/",
        }
        if not html:
            return {"parse": 1, "playUrl": play, "url": play, "header": hdr}

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

        if not m3u8:
            m = re.search(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', html)
            if m:
                m3u8 = m.group(1).replace("\\/", "/")
            else:
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
        kw = quote(key)
        if page == 1:
            url = "{}/search/{}-------------.html".format(self.HOST, kw)
        else:
            url = "{}/search/{}-------------{}.html".format(self.HOST, kw, page)
        html = self._fetch(url)
        videos = self._parse_list(html)
        return {"list": videos, "page": page}

    # ================================================================
    #  localProxy (空实现)
    # ================================================================

    def localProxy(self, param):
        return [200, "text/plain", b"ok"]
