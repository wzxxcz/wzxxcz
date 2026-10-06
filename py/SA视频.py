# coding=utf-8
"""
SA视频 lsjys11.com | TVBox Python 爬虫 (V7.0)
修正:
  - __NUXT_DATA__ 引用解析：data_list[0] 是 int 引用，不是 dict
  - 列表筛选响应字段严格化（要求 total/last_page）
  - 详情页从 links[].items[] 提取真实剧集 hash ID
  - playerContent 返回详情页 URL，parse=1 让 TVBox 嗅探
  - 补全 6 大分类筛选
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

# ---------- 公共筛选块 ----------
_AREA = [
    {"n": "全部", "v": ""}, {"n": "内地剧", "v": "内地剧"},
    {"n": "美剧", "v": "美剧"}, {"n": "日剧", "v": "日剧"},
    {"n": "韩剧", "v": "韩剧"}, {"n": "港剧", "v": "港剧"},
    {"n": "泰剧", "v": "泰剧"}, {"n": "台剧", "v": "台剧"},
    {"n": "印度剧", "v": "印度剧"},
]
_LANGUAGE = [
    {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
    {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"},
    {"n": "韩语", "v": "韩语"}, {"n": "粤语", "v": "粤语"},
    {"n": "泰语", "v": "泰语"}, {"n": "法语", "v": "法语"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "德语", "v": "德语"},
    {"n": "意大利", "v": "意大利"}, {"n": "其他", "v": "其他"},
]
_YEAR = [
    {"n": "全部", "v": ""}, {"n": "今年", "v": "current"},
    {"n": "去年", "v": "last"}, {"n": "更早", "v": "before"},
    {"n": "90年代", "v": "90"}, {"n": "80年代", "v": "80"},
    {"n": "怀旧", "v": "old"},
]
_ORDER = [
    {"n": "全部", "v": ""}, {"n": "上映时间", "v": "issue_date"},
    {"n": "人气高低", "v": "hot"}, {"n": "评分高低", "v": "score"},
]
_STATUS = [
    {"n": "全部", "v": ""}, {"n": "全集", "v": "1"}, {"n": "连载", "v": "0"},
]

FILTERS = {
    "13": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "近期热门", "v": "33"},
            {"n": "剧情片", "v": "219"}, {"n": "喜剧片", "v": "227"},
            {"n": "动作片", "v": "222"}, {"n": "爱情片", "v": "235"},
            {"n": "科幻片", "v": "226"}, {"n": "奇幻片", "v": "225"},
            {"n": "犯罪片", "v": "239"}, {"n": "悬疑片", "v": "231"},
            {"n": "惊悚片", "v": "234"}, {"n": "恐怖片", "v": "236"},
            {"n": "战争片", "v": "259"}, {"n": "动画电影片", "v": "245"},
            {"n": "网络电影片", "v": "243"}, {"n": "冒险片", "v": "242"},
            {"n": "同性片", "v": "255"}, {"n": "灾难片", "v": "280"},
            {"n": "歌舞片", "v": "240"}, {"n": "经典片", "v": "303"},
        ]},
        {"key": "area", "name": "地区", "value": _AREA},
        {"key": "language", "name": "语言", "value": _LANGUAGE},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
    "12": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "国产剧", "v": "220"},
            {"n": "欧美剧", "v": "307"}, {"n": "韩剧", "v": "295"},
            {"n": "日剧", "v": "303"}, {"n": "港剧", "v": "274"},
            {"n": "台剧", "v": "299"}, {"n": "泰剧", "v": "278"},
            {"n": "男男剧", "v": "238"}, {"n": "其他剧", "v": "233"},
            {"n": "百合剧", "v": "237"}, {"n": "新马剧", "v": "291"},
        ]},
        {"key": "area", "name": "地区", "value": _AREA},
        {"key": "language", "name": "语言", "value": _LANGUAGE},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "update_status", "name": "状态", "value": _STATUS},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
    "11": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "国产综艺", "v": "216"},
            {"n": "韩国综艺", "v": "224"}, {"n": "日本综艺", "v": "267"},
            {"n": "欧美综艺", "v": "251"}, {"n": "港台综艺", "v": "261"},
            {"n": "耽美综艺", "v": "254"}, {"n": "新马泰综艺", "v": "281"},
            {"n": "其他综艺", "v": "274"},
        ]},
        {"key": "area", "name": "地区", "value": _AREA},
        {"key": "language", "name": "语言", "value": _LANGUAGE},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
    "16": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "逆袭", "v": "263"},
            {"n": "都市", "v": "308"}, {"n": "重生", "v": "265"},
            {"n": "穿越", "v": "269"}, {"n": "甜宠", "v": "264"},
            {"n": "虐恋", "v": "268"}, {"n": "强者", "v": "262"},
            {"n": "职场", "v": "311"}, {"n": "系统", "v": "41"},
            {"n": "萌宝", "v": "810"}, {"n": "民国", "v": "312"},
            {"n": "现代", "v": "313"}, {"n": "ai", "v": "40"},
            {"n": "年代", "v": "310"}, {"n": "架空", "v": "314"},
            {"n": "乡村", "v": "309"}, {"n": "宫廷", "v": "316"},
            {"n": "古代", "v": "317"}, {"n": "神豪", "v": "809"},
            {"n": "校园", "v": "36"}, {"n": "复仇", "v": "37"},
            {"n": "韩国", "v": "277"}, {"n": "bl", "v": "256"},
        ]},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
    "14": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "四月新番", "v": "34"},
            {"n": "日本动漫", "v": "221"}, {"n": "国产动漫", "v": "223"},
            {"n": "耽美动漫", "v": "257"}, {"n": "欧美动漫", "v": "248"},
            {"n": "港台动漫", "v": "296"}, {"n": "韩国动漫", "v": "305"},
            {"n": "其他动漫", "v": "290"},
        ]},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
    "15": [
        {"key": "tag_id", "name": "分类", "value": [
            {"n": "全部", "v": ""}, {"n": "纪录片", "v": "230"},
            {"n": "冒险", "v": "298"},
        ]},
        {"key": "year", "name": "年份", "value": _YEAR},
        {"key": "order", "name": "排序", "value": _ORDER},
    ],
}

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

    # ---------------- Nuxt 引用解析（核心修正） ----------------
    @staticmethod
    def _resolve_nuxt(raw, idx, depth=0, max_depth=25):
        """
        Nuxt __NUXT_DATA__ 是一个扁平数组，元素之间通过整数索引互相引用。
        本函数递归把 int 索引替换为实际值。
        - idx 是 int  → 从 raw[idx] 取值并继续递归
        - idx 是 dict → 对 value 逐个递归
        - idx 是 list → 对元素逐个递归
        - 其它       → 直接返回
        """
        if depth > max_depth:
            return None
        if isinstance(idx, int):
            if 0 <= idx < len(raw):
                return Spider._resolve_nuxt(raw, raw[idx], depth + 1, max_depth)
            return idx
        if isinstance(idx, dict):
            return {k: Spider._resolve_nuxt(raw, v, depth + 1, max_depth)
                    for k, v in idx.items()}
        if isinstance(idx, list):
            return [Spider._resolve_nuxt(raw, i, depth + 1, max_depth) for i in idx]
        return idx

    def _parse_nuxt(self, html):
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

    # ---------------- 列表解析（关键修正） ----------------
    def _extract_videos_from_nuxt(self, html):
        raw = self._parse_nuxt(html)
        if not raw:
            return None

        # 优先寻找 API 响应结构：{data: <int>, total: <int>, ...}
        # 排除 Pinia 的 state（有 data 但无 total）
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "data" not in item:
                continue
            # 严格化：必须有 total 或 last_page，说明是列表响应
            if "total" not in item and "last_page" not in item:
                continue
            data_ref = item["data"]
            if not isinstance(data_ref, int):
                continue
            if not (0 <= data_ref < len(raw)):
                continue
            data_list = raw[data_ref]
            if not isinstance(data_list, list) or not data_list:
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
                # 详情 ID 格式：slug-id，如 yuhongjiushi-aa56cccd30f76823
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
                self.log("  Nuxt 列表解析成功: %d 部" % len(videos))
                return videos

        return None

    def _extract_videos(self, html):
        if not html:
            return []
        return self._extract_videos_from_nuxt(html) or []

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch("%s/movie/list?cat_id=13" % self.site_url)
        return {"list": self._extract_videos(html)}

    # ---------------- 分类页 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        params = {k: v for k, v in extend.items() if v and v != "全部"}
        if page <= 1:
            url = "%s/movie/list?cat_id=%s" % (self.site_url, tid)
        else:
            url = "%s/movie/list/%d?cat_id=%s" % (self.site_url, page, tid)
        if params:
            url += "&" + urllib.parse.urlencode(params)
        html = self._fetch(url)
        return {
            "list": self._extract_videos(html), "page": page, "pagecount": 999,
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

    # ---------------- 详情页 ----------------
    def _extract_detail_from_nuxt(self, html, vod_id):
        raw = self._parse_nuxt(html)
        if not raw:
            return None
        # 详情页响应结构：{"data": <int>, "seo": <int>}
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "data" not in item or not isinstance(item["data"], int):
                continue
            data_ref = item["data"]
            if not (0 <= data_ref < len(raw)):
                continue
            data_obj = raw[data_ref]
            if not isinstance(data_obj, dict):
                continue
            if "name" not in data_obj or "id" not in data_obj:
                continue

            v = self._resolve_nuxt(raw, data_obj)
            if not isinstance(v, dict):
                continue

            name = v.get("name") or vod_id
            content = v.get("description") or ""
            pic = v.get("img") or self.default_pic

            play_from = []
            play_url = []

            # links 结构：[{"name": "1-34", "items": [{"id": "...", "name": "第N集"}]}]
            links = v.get("links")
            if isinstance(links, list):
                for group in links:
                    if not isinstance(group, dict):
                        continue
                    line_name = group.get("name") or "SA线路"
                    items = group.get("items") or []
                    eps = []
                    for ep in items:
                        if not isinstance(ep, dict):
                            continue
                        ep_name = ep.get("name") or ""
                        ep_id = ep.get("id") or ""
                        if ep_name and ep_id:
                            # 格式：名称$vod_id/ep_id
                            eps.append("%s$%s/%s" % (ep_name, vod_id, ep_id))
                    if eps:
                        play_from.append(str(line_name))
                        play_url.append("#".join(eps))

            if play_from:
                self.log("  Nuxt 详情: %s, %d 线路" % (name, len(play_from)))
                return {
                    "vod_id":        vod_id,
                    "vod_name":      str(name),
                    "vod_pic":       self._fix_url(pic),
                    "vod_content":   self._clean(content),
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url":  "$$$".join(play_url) if play_url else "",
                }
        return None

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
        detail = self._extract_detail_from_nuxt(html, vod_id)
        if detail:
            return {"list": [detail]}
        return {"list": []}

    # ---------------- 播放（嗅探模式） ----------------
    def playerContent(self, flag, id, vipFlags):
        """
        id 格式：`vod_id/ep_id`
        返回详情页 URL，parse=1 让 TVBox 用 WebView 打开并嗅探 m3u8。
        """
        if id.startswith("http"):
            target = id
        elif "/" in id:
            parts = id.split("/")
            vod_part = parts[0]
            ep_part = parts[1] if len(parts) > 1 else ""
            target = "%s/movie/detail/%s?ep=%s" % (self.site_url, vod_part, ep_part)
        else:
            target = "%s/movie/detail/%s" % (self.site_url, id)

        self.log("playerContent -> %s" % target)

        headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        return {
            "parse": 1,
            "playUrl": "",
            "url": target,
            "header": headers,
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
