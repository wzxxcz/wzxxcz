# -*- coding: utf-8 -*-
"""
黄瓜短剧 (hgdju.com) T4 Python 源
CMS: 自定义PHP短剧站 (非MacCMS)
URL结构:
  首页: /
  分类: /browse?line={line}&page={page} 或 /{line}
  详情: /drama/dj-{hash}
  播放: /play/dj-{hash}/{ep}
  搜索: /search?q={keyword}
播放解析: 播放页内嵌 window.HG_PLAY JSON变量, episodes数组中当前集hls字段为直链m3u8(带auth_key)
封面: /static/posters/xxx.jpg (相对路径, 需补全域名)
"""

import re
import json
import sys
from urllib.parse import quote, urljoin

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    HOST = "https://hgdju.com"

    # 内容线分类 (与站点导航一致)
    CATEGORIES = [
        {"type_id": "all", "type_name": "全部"},
        {"type_id": "yuanchuang", "type_name": "原创"},
        {"type_id": "mogai", "type_name": "魔改"},
        {"type_id": "manju", "type_name": "AI漫剧"},
        {"type_id": "zhenren", "type_name": "真人短剧"},
        {"type_id": "aiduanju", "type_name": "AI短剧"},
        {"type_id": "aihuanlian", "type_name": "AI换脸"},
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
        return "黄瓜短剧"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    # ================================================================
    #  内部工具: HTTP请求
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
                print("[hgdj] req err: {}".format(str(e)[:80]))
        # 兜底: self.fetch (基类)
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
        # 兜底: urllib
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
        """补全封面URL为绝对路径"""
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
    #  列表解析 (首页/分类/搜索通用)
    # ================================================================

    def _parse_list(self, html):
        """
        卡片结构:
        <div class="card">
          <a class="card-main" href="/play/dj-xxxx" aria-label="播放标题">
            <span class="card-cover">
              <img src="/static/posters/xxx.jpg" alt="...">
              <i class="card-line">原创</i>
              <i class="card-ep num">更新至 N 集</i>
            </span>
            <b class="card-title">标题</b>
          </a>
        </div>
        """
        videos = []
        seen = set()
        # 匹配 card-main a 标签
        for m in re.finditer(
            r'<a[^>]+class="[^"]*card-main[^"]*"[^>]+href="(/play/(dj-[a-f0-9]+))"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            play_url = m.group(1)
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            inner = m.group(3)

            # 标题: 优先 card-title, 兜底 aria-label
            name = ""
            tm = re.search(r'<b[^>]*class="[^"]*card-title[^"]*"[^>]*>(.*?)</b>', inner, re.DOTALL)
            if tm:
                name = self._clean(tm.group(1))
            if not name:
                am = re.search(r'aria-label="播放([^"]+)"', m.group(0))
                if am:
                    name = self._clean(am.group(1))

            # 封面: 优先 src(本站无防盗链), 其次 data-cover-fb(本站fallback), 最后 z-image-loader-url(外部CDN可能防盗链)
            pic = ""
            im = re.search(r'<img[^>]+src="([^"]+)"', inner)
            if not im:
                im = re.search(r'data-cover-fb="([^"]+)"', inner)
            if not im:
                im = re.search(r'z-image-loader-url="([^"]+)"', inner)
            if im:
                raw_pic = im.group(1)
                # 去掉 ?v=xxx 查询参数 (部分播放器不识别带参数的图片)
                raw_pic = re.sub(r'\?v=\d+$', '', raw_pic)
                pic = self._pic(raw_pic)

            # 备注: card-ep (更新至N集)
            remark = ""
            rm = re.search(r'<i[^>]*class="[^"]*card-ep[^"]*"[^>]*>(.*?)</i>', inner, re.DOTALL)
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
    #  六接口
    # ================================================================

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

        # 构建分类URL
        if tid == "all" or not tid:
            url = "{}/browse".format(self.HOST)
        else:
            url = "{}/browse?line={}".format(self.HOST, tid)
        if page > 1:
            sep = "&" if "?" in url else "?"
            url = "{}{}page={}".format(url, sep, page)

        html = self._fetch(url)
        videos = self._parse_list(html)

        # 分页总数: 从分页链接提取最大页码
        pagecount = page
        pages = re.findall(r'[?&]page=(\d+)', html)
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
        # 确保是 dj-xxxx 格式
        if not vid.startswith("dj-"):
            m = re.search(r'(dj-[a-f0-9]+)', vid)
            if m:
                vid = m.group(1)

        html = self._fetch("{}/drama/{}".format(self.HOST, vid))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'og:title"\s+content="([^"]+)"', html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
            if m:
                name = self._clean(m.group(1)).split("-")[0].split("|")[0].strip()

        # 封面
        pic = ""
        m = re.search(r'og:image"\s+content="([^"]+)"', html)
        if m:
            pic = self._pic(m.group(1))
        if not pic:
            m = re.search(r'thumbnailUrl"\s*:\s*"([^"]+)"', html)
            if m:
                pic = self._pic(m.group(1))

        # 简介
        content = ""
        m = re.search(r'<p[^>]*class="[^"]*detail-intro[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'og:description"\s+content="([^"]+)"', html)
            if m:
                content = self._clean(m.group(1))

        # 内容线 (分类)
        vod_type = ""
        m = re.search(r'<span[^>]*class="[^"]*pill-line[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
        if m:
            vod_type = self._clean(m.group(1))

        # 备注 (连载中/更新至N集)
        remarks = ""
        m = re.search(r'<span[^>]*>(连载中[^<]*|已完结[^<]*|更新至[^<]*)</span>', html)
        if m:
            remarks = self._clean(m.group(1))

        # 播放列表: <a class="ep-link" href="/play/dj-xxxx/{n}">n</a>
        play_urls = []
        seen_ep = set()
        for em in re.finditer(
            r'<a[^>]+class="[^"]*ep-link[^"]*"[^>]+href="(/play/dj-[a-f0-9]+/(\d+))"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            ep_url = em.group(1)
            ep_num = em.group(2)
            ep_name = self._clean(em.group(3)) or "第{}集".format(ep_num)
            if ep_num in seen_ep:
                continue
            seen_ep.add(ep_num)
            full_url = self.HOST + ep_url
            play_urls.append("{}${}".format(ep_name, full_url))

        if not play_urls:
            play_urls.append("第1集${}/play/{}/1".format(self.HOST, vid))

        vod = {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_content": content,
            "vod_type": vod_type,
            "vod_remarks": remarks,
            "vod_play_from": "黄瓜短剧",
            "vod_play_url": "#".join(play_urls),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """
        播放解析:
        vod_play_url 中存储的是播放页完整URL (https://hgdju.com/play/dj-xxxx/{ep})
        请求播放页, 从 window.HG_PLAY JSON变量中提取当前集的hls直链m3u8
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
                "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.HOST + "/"}
            }

        # 请求播放页
        html = self._fetch(play)
        if not html:
            return {"parse": 1, "playUrl": play, "url": play,
                    "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.HOST + "/"}}

        # 提取 window.HG_PLAY = {...};
        m3u8 = ""
        m = re.search(r'window\.HG_PLAY\s*=\s*(\{.*?\});', html, re.DOTALL)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                episodes = data.get("episodes", [])
                # 从URL中提取当前集数
                ep_match = re.search(r'/play/dj-[a-f0-9]+/(\d+)', play)
                current_ep = int(ep_match.group(1)) if ep_match else 1
                # 找当前集的hls
                for ep in episodes:
                    if int(ep.get("n", 0)) == current_ep:
                        hls = ep.get("hls") or ""
                        if hls:
                            m3u8 = hls.replace("\\/", "/")
                            break
                # 如果当前集没有hls, 找第一个有hls的
                if not m3u8:
                    for ep in episodes:
                        hls = ep.get("hls") or ""
                        if hls:
                            m3u8 = hls.replace("\\/", "/")
                            break
            except (json.JSONDecodeError, ValueError):
                # JSON解析失败, 用正则提取hls
                hls_m = re.search(r'"hls"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', raw)
                if hls_m:
                    m3u8 = hls_m.group(1).replace("\\/", "/")

        # 兜底: 直接从HTML提取m3u8
        if not m3u8:
            m = re.search(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', html)
            if m:
                m3u8 = m.group(1).replace("\\/", "/")

        hdr = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.HOST + "/",
        }

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
        url = "{}/search?q={}".format(self.HOST, kw)
        if page > 1:
            url = "{}&page={}".format(url, page)
        html = self._fetch(url)
        videos = self._parse_list(html)
        return {"list": videos}

    # ================================================================
    #  localProxy (空实现, 本站封面无需代理)
    # ================================================================

    def localProxy(self, param):
        return [200, "text/plain", b"ok"]
