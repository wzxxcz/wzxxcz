# coding=utf-8
"""
SA视频 lsjys11.com | webhtv 爬虫 (V14.0)
已完成:
  - 列表页从 __NUXT_DATA__ 提取
  - 详情页从 data.links[].items[] 提取真实 hash ID
  - 播放 URL: /movie/detail/{vod_id}?lid={ep_id}  ✅ 已验证可播
  - 图片通过 localProxy 代理加 Referer 绕过 CDN 防盗链
  - 详情页信息(上映/导演/主演/简介/评分)全部显示
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
            "Cookie": "i18n_redirected=zh-cn;",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=15, headers=None, raw=False):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if raw:
                return rsp
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            self.log("GET %s -> HTTP %s, Len=%d" % (url, rsp.status_code, len(text)))
            if len(text) < 3000:
                self.log("  短响应前 300 字符: %r" % text[:300])
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return None if raw else ""

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

    def _proxy_pic(self, pic_url):
        """
        把图片 URL 转成代理 URL，让 TVBox 通过 localProxy 请求，
        代理时带上 Referer 绕过 CDN 防盗链。
        """
        if not pic_url:
            return self.default_pic
        pic_url = self._fix_url(pic_url)
        if not pic_url:
            return self.default_pic
        return ("http://127.0.0.1:9978/proxy?do=py&type=proxy_img&url="
                + urllib.parse.quote(pic_url, safe=""))

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

    # ---------------- Nuxt 解析 ----------------
    @staticmethod
    def _resolve_nuxt(raw, idx, depth=0, max_depth=25):
        if depth > max_depth:
            return None
        t = type(idx)
        if t == bool:
            return idx
        if t == int:
            if 0 <= idx < len(raw):
                return Spider._resolve_nuxt(raw, raw[idx], depth + 1, max_depth)
            return idx
        if t == dict:
            return {k: Spider._resolve_nuxt(raw, v, depth + 1, max_depth)
                    for k, v in idx.items()}
        if t == list:
            return [Spider._resolve_nuxt(raw, i, depth + 1, max_depth) for i in idx]
        return idx

    def _parse_nuxt(self, html):
        m = _RE_NUXT.search(html)
        if not m:
            self.log("  __NUXT_DATA__ 正则未匹配")
            return None
        try:
            raw = json.loads(m.group(1))
        except Exception as e:
            self.log("  __NUXT_DATA__ JSON 解析失败: %s" % e)
            return None
        if type(raw) != list:
            self.log("  __NUXT_DATA__ 根不是 list")
            return None
        self.log("  __NUXT_DATA__ 长度=%d" % len(raw))
        return raw

    # ---------------- 列表解析 ----------------
    def _extract_videos_from_nuxt(self, html):
        raw = self._parse_nuxt(html)
        if not raw:
            return None

        candidates = []
        for i, item in enumerate(raw):
            if type(item) != dict:
                continue
            if "data" not in item:
                continue
            if "total" not in item and "last_page" not in item:
                continue
            candidates.append((i, item))

        self.log("  候选响应对象: %d 个" % len(candidates))

        for idx, item in candidates:
            data_ref = item.get("data")
            if type(data_ref) != int:
                continue
            if not (0 <= data_ref < len(raw)):
                continue
            data_list = raw[data_ref]
            if type(data_list) != list or not data_list:
                continue

            videos = []
            for v_ref in data_list:
                try:
                    v = self._resolve_nuxt(raw, v_ref)
                except Exception:
                    continue
                if type(v) != dict:
                    continue
                if v.get("type") == "ad" or v.get("ad_position_code"):
                    continue
                name = v.get("name") or ""
                slug = v.get("slug") or ""
                vid = v.get("id") or ""
                if not name or not vid:
                    continue
                name_clean = re.sub(r"<[^>]+>", "", name)
                vod_id = "%s-%s" % (slug, vid) if slug else str(vid)
                pic = v.get("img") or ""
                score = v.get("score") or "0"
                remarks = v.get("duration") or ""
                videos.append({
                    "vod_id":      str(vod_id),
                    "vod_name":    name_clean[:100],
                    "vod_pic":     self._proxy_pic(pic) if pic else self.default_pic,
                    "vod_remarks": str(remarks),
                    "vod_score":   str(score),
                })

            if videos:
                self.log("  解析成功: %d 部" % len(videos))
                return videos
        return None

    def _extract_videos(self, html):
        if not html:
            return []
        try:
            result = self._extract_videos_from_nuxt(html)
            if result:
                return result
        except Exception as e:
            self.log("  _extract_videos 异常: %s" % e)
        return []

    # ---------------- 首页/分类/搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch("%s/movie/list?cat_id=13" % self.site_url)
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        self.log("categoryContent: tid=%r pg=%r" % (tid, pg))
        self._warm_up()
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

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
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

        for item in raw:
            if type(item) != dict:
                continue
            if "data" not in item or type(item["data"]) != int:
                continue
            data_ref = item["data"]
            if not (0 <= data_ref < len(raw)):
                continue
            data_obj = raw[data_ref]
            if type(data_obj) != dict:
                continue
            if "name" not in data_obj or "id" not in data_obj:
                continue

            v = self._resolve_nuxt(raw, data_obj)
            if type(v) != dict:
                continue

            name = v.get("name") or vod_id
            content = v.get("description") or ""
            pic = v.get("img") or self.default_pic
            score = v.get("score") or ""
            director = v.get("director") or ""
            actor = v.get("actor") or v.get("actors") or ""
            year = v.get("issue_date") or ""

            # 拼接详情页所有信息到 vod_content（兼容所有皮肤）
            content_parts = []
            if year:
                content_parts.append("上映: %s" % year)
            if director:
                content_parts.append("导演: %s" % director)
            if actor:
                content_parts.append("主演: %s" % actor)
            if score:
                content_parts.append("评分: %s" % score)
            if content:
                content_parts.append("简介: %s" % self._clean(content))

            full_content = "\n".join(content_parts)

            # 剧集提取
            play_from = []
            play_url = []
            links = v.get("links")
            if type(links) == list:
                for group in links:
                    if type(group) != dict:
                        continue
                    line_name = group.get("name") or "SA线路"
                    items = group.get("items") or []
                    eps = []
                    for ep in items:
                        if type(ep) != dict:
                            continue
                        ep_name = ep.get("name") or ""
                        ep_id = ep.get("id") or ""
                        if ep_name and ep_id:
                            eps.append("%s$%s/%s" % (ep_name, vod_id, ep_id))
                    if eps:
                        play_from.append(str(line_name))
                        play_url.append("#".join(eps))

            if play_from:
                self.log("  详情: %s, %d 线路, 首线路 %d 集"
                         % (name, len(play_from),
                            len(play_url[0].split("#")) if play_url else 0))
                return {
                    "vod_id":        vod_id,
                    "vod_name":      str(name),
                    "vod_pic":       self._proxy_pic(pic),
                    "vod_content":   full_content,
                    "vod_score":     str(score),
                    "vod_director":  str(director),
                    "vod_actor":     str(actor),
                    "vod_year":      str(year),
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url":  "$$$".join(play_url) if play_url else "",
                }
        return None

    def detailContent(self, ids):
        self.log("detailContent: ids=%r" % (ids,))
        if not ids:
            return {"list": []}
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
        self.log("  详情解析失败")
        return {"list": []}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        """
        id 格式：`vod_id/ep_id`
        正确播放 URL：/movie/detail/{vod_id}?lid={ep_id}
        例：https://www.lsjys11.com/movie/detail/lanxiangrugu-33f5fd0e81a046a0?lid=b4b5b58b137086406c417a1bffea26bd
        """
        self.log("playerContent: flag=%r id=%r" % (flag, id))

        if id.startswith("http"):
            target = id
        elif "/" in id:
            parts = id.split("/")
            vod_part = parts[0]
            ep_part = parts[1] if len(parts) > 1 else ""
            target = "%s/movie/detail/%s?lid=%s" % (self.site_url, vod_part, ep_part)
        else:
            target = "%s/movie/detail/%s" % (self.site_url, id)

        self.log("  播放目标: %s" % target)

        headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        return {
            "parse": 1,
            "playUrl": "",
            "url": target,
            "header": headers,
        }

    # ---------------- 图片代理 ----------------
    def localProxy(self, param):
        """
        处理图片代理请求。
        param 可能是:
          - dict: {"type": "proxy_img", "url": "https%3A%2F%2F..."}
          - str:  "do=py&type=proxy_img&url=https%3A%2F%2F..."
        """
        try:
            url = ""
            ptype = ""
            if isinstance(param, dict):
                url = param.get("url", "")
                ptype = param.get("type", "")
            else:
                s = str(param)
                for pair in s.split("&"):
                    if "=" not in pair:
                        continue
                    k, v = pair.split("=", 1)
                    if k == "url":
                        url = v
                    elif k == "type":
                        ptype = v

            if not url:
                return [200, "image/jpeg", b"", ""]

            # URL decode
            if "%" in url:
                url = urllib.parse.unquote(url)

            self.log("localProxy: type=%s url=%s" % (ptype, url[:120]))

            # 请求图片（带 Referer 绕过 CDN 防盗链）
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }, timeout=15)

            content = rsp.content if hasattr(rsp, "content") else b""
            ctype = "image/jpeg"
            if hasattr(rsp, "headers"):
                ctype = rsp.headers.get("Content-Type", "image/jpeg") or "image/jpeg"
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception as e:
            self.log("localProxy fail: %s" % e)
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
