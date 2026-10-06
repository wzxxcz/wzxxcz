# coding=utf-8
"""
SA视频 lsjys11.com | TVBox Python 爬虫 (V3.0 Nuxt SSR 适配版)
修正:
  - 修正 __NUXT_DATA__ 正则（id 属性不在首位）
  - 列表页优先从 Nuxt JSON 提取（该站为 Nuxt SSR，DOM 中无详情链接）
  - 详情页优先从 Nuxt JSON 提取剧集
  - 保留原有 HTML 降级逻辑作为兜底
"""
import re
import sys
import json
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

# 筛选配置
FILTERS = {
    "13": [  # 电影
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "剧情", "v": "219"}, {"n": "喜剧", "v": "227"},
            {"n": "动作", "v": "222"}, {"n": "爱情", "v": "235"}, {"n": "惊悚", "v": "234"},
            {"n": "犯罪", "v": "239"}, {"n": "恐怖", "v": "236"}, {"n": "悬疑", "v": "231"},
            {"n": "科幻", "v": "226"}, {"n": "奇幻", "v": "225"}, {"n": "动画", "v": "245"}]},
        {"key": "area", "name": "地区", "value": [
            {"n": "全部", "v": ""}, {"n": "内地", "v": "内地剧"}, {"n": "美国", "v": "美剧"},
            {"n": "日本", "v": "日剧"}, {"n": "韩国", "v": "韩剧"}, {"n": "香港", "v": "港剧"},
            {"n": "泰国", "v": "泰剧"}, {"n": "台湾", "v": "台剧"}]},
        {"key": "year", "name": "年份", "value": [
            {"n": "全部", "v": ""}, {"n": "今年", "v": "current"},
            {"n": "去年", "v": "last"}, {"n": "更早", "v": "before"}]},
        {"key": "order", "name": "排序", "value": [
            {"n": "全部", "v": ""}, {"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}
    ],
    "12": [  # 连续剧
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "国产剧", "v": "220"}, {"n": "美剧", "v": "307"},
            {"n": "日剧", "v": "303"}, {"n": "韩剧", "v": "295"}, {"n": "港剧", "v": "274"},
            {"n": "泰剧", "v": "278"}, {"n": "台剧", "v": "299"}]},
        {"key": "area", "name": "地区", "value": [
            {"n": "全部", "v": ""}, {"n": "内地", "v": "内地剧"}, {"n": "美国", "v": "美剧"},
            {"n": "日本", "v": "日剧"}, {"n": "韩国", "v": "韩剧"}, {"n": "香港", "v": "港剧"},
            {"n": "泰国", "v": "泰剧"}]},
        {"key": "year", "name": "年份", "value": [
            {"n": "全部", "v": ""}, {"n": "今年", "v": "current"},
            {"n": "去年", "v": "last"}, {"n": "更早", "v": "before"}]},
    ],
    "11": [],  # 综艺
    "16": [],  # 短剧
    "14": [],  # 动漫
    "15": [],  # 纪录片
}

# 修正正则：id 属性可能在 type/data-* 之后
_RE_NUXT = re.compile(
    r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Cookie": "i18n_redirected=zh-cn;",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            self.log("GET %s -> HTTP %s, Len=%d" % (url, rsp.status_code, len(text)))
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
        return s.strip()

    # ---------------- Nuxt 引用解析工具 ----------------
    @staticmethod
    def _resolve_nuxt(raw, idx, depth=0, max_depth=15):
        """
        Nuxt 的 __NUXT_DATA__ 是一个扁平数组，所有对象/数组都是通过整数索引引用。
        该函数递归把引用替换成实际值。
        """
        if depth > max_depth:
            return None
        if isinstance(idx, int) and 0 <= idx < len(raw):
            val = raw[idx]
            if isinstance(val, list):
                return [Spider._resolve_nuxt(raw, i, depth + 1, max_depth) for i in val]
            elif isinstance(val, dict):
                return {k: Spider._resolve_nuxt(raw, v, depth + 1, max_depth)
                        for k, v in val.items()}
            else:
                return val
        return idx

    def _parse_nuxt(self, html):
        """解析 __NUXT_DATA__ 为 python 对象，失败返回 None"""
        m = _RE_NUXT.search(html)
        if not m:
            return None
        try:
            raw = json.loads(m.group(1))
        except Exception as e:
            self.log("  __NUXT_DATA__ JSON 解析失败: %s" % e)
            return None
        if not isinstance(raw, list):
            return None
        return raw

    # ---------------- 列表解析：Nuxt 优先 ----------------
    def _extract_videos_from_nuxt(self, html):
        """从 __NUXT_DATA__ 提取影片列表"""
        raw = self._parse_nuxt(html)
        if not raw:
            return None

        # 遍历顶层字典，寻找包含 {data: <int>, total: ..., current_page: ...} 的响应
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "data" not in item or not isinstance(item.get("data"), int):
                continue
            data_ref = item["data"]
            if not (0 <= data_ref < len(raw)):
                continue
            data_list = raw[data_ref]
            if not isinstance(data_list, list) or not data_list:
                continue

            first = data_list[0]
            if not isinstance(first, dict):
                continue
            # 原始字段检查
            if "name" not in first or "id" not in first:
                continue
            # 解析第一个，确认是影片对象
            first_resolved = self._resolve_nuxt(raw, first, max_depth=6)
            if not isinstance(first_resolved, dict):
                continue
            if not first_resolved.get("name") or not first_resolved.get("id"):
                continue

            videos = []
            for v_ref in data_list:
                v = self._resolve_nuxt(raw, v_ref)
                if not isinstance(v, dict):
                    continue
                # 跳过广告
                if v.get("type") == "ad" or v.get("ad_position_code"):
                    continue

                name = v.get("name") or ""
                slug = v.get("slug") or ""
                vid = v.get("id") or ""
                if not name or not vid:
                    continue

                vod_id = "%s-%s" % (slug, vid) if slug else str(vid)

                pic = v.get("img") or ""
                score = v.get("score") or "0"
                remarks = v.get("duration") or ""

                videos.append({
                    "vod_id":      str(vod_id),
                    "vod_name":    str(name)[:100],
                    "vod_pic":     self._fix_url(pic) if pic else self.default_pic,
                    "vod_remarks": str(remarks),
                    "vod_score":   str(score),
                })

            if videos:
                self.log("  Nuxt 解析成功，提取 %d 部影片" % len(videos))
                return videos

        return None

    # ---------------- 列表解析：HTML 降级 ----------------
    def _extract_videos_from_html(self, html):
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.log("缺少 BeautifulSoup")
            return []

        videos = []
        seen = set()
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.c-movie-list-item')
        self.log("  HTML 降级解析: .c-movie-list-item 共 %d 个" % len(items))

        for item in items:
            try:
                # 跳过广告卡片
                cls = item.get('class') or []
                if 'c-movie-list-item--ad' in cls:
                    continue

                # 名称
                name_tag = item.select_one('div[class*="series-name-color"]')
                if not name_tag:
                    continue
                name = self._clean(name_tag.text)
                if not name or len(name) > 100:
                    continue

                # 评分
                score = '0'
                score_tag = item.select_one('div[class*="italic"]')
                if score_tag:
                    m = re.search(r'(\d+\.\d+)', score_tag.text)
                    if m:
                        score = m.group(1)

                # 海报：优先取 movie-overlay 里的 img
                pic = ''
                img_tag = item.select_one('div[class*="movie-overlay"] img')
                if img_tag:
                    pic = img_tag.get('src', '')
                if not pic:
                    pic = self.default_pic

                # 更新状态
                remarks = ''
                remark_tag = item.select_one('div[class*="bottom-0"] div[class*="text-right"]')
                if remark_tag:
                    remarks = self._clean(remark_tag.text)

                # 没有详情链接时用名称做临时 id（不可播放，仅作提示）
                vod_id = name
                if vod_id in seen:
                    continue
                seen.add(vod_id)

                videos.append({
                    "vod_id":      vod_id,
                    "vod_name":    name[:100],
                    "vod_pic":     self._fix_url(pic),
                    "vod_remarks": remarks,
                    "vod_score":   score,
                })
            except Exception:
                continue

        self.log("  HTML 降级解析提取 %d 部影片" % len(videos))
        return videos

    def _extract_videos(self, html):
        if not html:
            return []
        # 优先 Nuxt
        videos = self._extract_videos_from_nuxt(html)
        if videos:
            return videos
        # 降级 HTML
        return self._extract_videos_from_html(html)

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch("%s/movie/list?cat_id=13" % self.site_url)
        return {"list": self._extract_videos(html)}

    # ---------------- 分类页（含筛选） ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        params = {}
        for k, v in extend.items():
            if v and v != "全部":
                params[k] = v

        if page <= 1:
            url = "%s/movie/list?cat_id=%s" % (self.site_url, tid)
        else:
            url = "%s/movie/list/%d?cat_id=%s" % (self.site_url, page, tid)

        if params:
            url += "&" + urllib.parse.urlencode(params)

        html = self._fetch(url)
        videos = self._extract_videos(html)

        return {
            "list": videos, "page": page, "pagecount": 999,
            "limit": 24, "total": 9999,
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        kw = urllib.parse.quote(key)
        url = "%s/search?keywords=%s" % (self.site_url, kw)
        html = self._fetch(url)
        return {
            "list": self._extract_videos(html),
            "page": 1, "pagecount": 1, "limit": 24, "total": 0,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情页：Nuxt 优先 ----------------
    def _extract_detail_from_nuxt(self, html, vod_id):
        raw = self._parse_nuxt(html)
        if not raw:
            return None

        # 遍历寻找影片详情对象：含 name + (links/play_links/play_list)
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "name" not in item:
                continue
            if not any(k in item for k in ("links", "play_links", "play_list", "play_urls")):
                continue

            v = self._resolve_nuxt(raw, item)
            if not isinstance(v, dict):
                continue

            name = v.get("name") or vod_id
            content = v.get("description") or ""
            pic = v.get("img") or self.default_pic

            play_from = []
            play_url = []

            for link_key in ("links", "play_links", "play_list", "play_urls"):
                links = v.get(link_key)
                if not isinstance(links, list):
                    continue
                for group in links:
                    if not isinstance(group, dict):
                        continue
                    line_name = (group.get("name") or group.get("source")
                                 or group.get("line") or "SA线路")
                    items = (group.get("items") or group.get("episodes")
                             or group.get("urls") or [])
                    eps = []
                    for ep in items:
                        if not isinstance(ep, dict):
                            continue
                        ep_name = ep.get("name") or ep.get("title") or ""
                        ep_id = (ep.get("id") or ep.get("url")
                                 or ep.get("play_url") or ep.get("link") or "")
                        if ep_name and ep_id:
                            eps.append("%s$%s" % (ep_name, ep_id))
                    if eps:
                        play_from.append(str(line_name))
                        play_url.append("#".join(eps))

            if play_from:
                self.log("  Nuxt 详情解析成功: %s (%d 线路)" % (name, len(play_from)))
                return {
                    "vod_id":        vod_id,
                    "vod_name":      str(name),
                    "vod_pic":       self._fix_url(pic),
                    "vod_content":   self._clean(content),
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url":  "$$$".join(play_url),
                }

        return None

    def _extract_detail_from_html(self, html, vod_id):
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        name = self._clean(soup.select_one('h1').text) if soup.select_one('h1') else vod_id

        content = ""
        for tag in soup.find_all(['div', 'p', 'span']):
            cls = ' '.join(tag.get('class') or [])
            if 'break-all' in cls:
                content = self._clean(tag.text)
                break

        play_from = []
        play_url = []

        # 兜底 1：从 Nuxt 提取剧集（旧逻辑）
        nuxt_result = self._extract_nuxt_episodes(html)
        if nuxt_result:
            for line_name, eps in nuxt_result:
                play_from.append(line_name)
                play_url.append("#".join("%s$%s" % (n, i) for n, i in eps))

        # 兜底 2：直接从 DOM 选剧集按钮
        if not play_from:
            eps = []
            for div in soup.select('.season > div, button, a[href*="/movie/play/"]'):
                ep_name = self._clean(div.text)
                if ep_name and len(ep_name) < 20:
                    eps.append("%s$%s__%d" % (ep_name, vod_id, len(eps) + 1))
            if eps:
                play_from = ["SA线路"]
                play_url = ["#".join(eps)]

        return {
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       self.default_pic,
            "vod_content":   content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }

    def detailContent(self, ids):
        raw = str(ids[0])
        if raw.startswith("http"):
            url = raw
            vod_id = raw.rstrip('/').split('/')[-1]
        else:
            vod_id = raw
            url = "%s/movie/detail/%s" % (self.site_url, vod_id)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 优先 Nuxt
        detail = self._extract_detail_from_nuxt(html, vod_id)
        if detail and detail.get("vod_play_from"):
            return {"list": [detail]}

        # 降级 HTML
        detail = self._extract_detail_from_html(html, vod_id)
        if detail and detail.get("vod_play_from"):
            return {"list": [detail]}

        # 最后的兜底：至少返回元数据
        if detail:
            return {"list": [detail]}
        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      vod_id,
            "vod_pic":       self.default_pic,
            "vod_content":   "",
            "vod_play_from": "",
            "vod_play_url":  "",
        }]}

    def _extract_nuxt_episodes(self, html):
        """旧版剧集提取（保留作为兜底）"""
        raw = self._parse_nuxt(html)
        if not raw:
            return None

        for it in raw:
            if isinstance(it, dict) and 'links' in it:
                links = it['links']
                if isinstance(links, list) and links and isinstance(links[0], int):
                    result = []
                    for group_ref in links:
                        group = raw[group_ref] if group_ref < len(raw) else None
                        if isinstance(group, dict) and 'name' in group and 'items' in group:
                            line_name = (raw[group['name']]
                                         if isinstance(group['name'], int) else group['name'])
                            eps = []
                            for ep_ref in group['items']:
                                ep = raw[ep_ref] if ep_ref < len(raw) else None
                                if isinstance(ep, dict) and 'id' in ep and 'name' in ep:
                                    ep_id = (raw[ep['id']]
                                             if isinstance(ep['id'], int) else ep['id'])
                                    ep_name = (raw[ep['name']]
                                               if isinstance(ep['name'], int) else ep['name'])
                                    eps.append((str(ep_name), str(ep_id)))
                            if eps:
                                result.append((str(line_name), eps))
                    return result if result else None
        return None

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        # id 可能是 slug-id 或 URL
        if id.startswith("http"):
            target = id
        else:
            target = "%s/movie/detail/%s" % (self.site_url, id.split("__")[0])
        return {
            "parse": 1,
            "playUrl": "",
            "url": target,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
