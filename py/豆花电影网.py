# coding=utf-8
"""
豆花电影网 dhvideo.cc | TVBox Python 爬虫 (V6.3 短剧修复版)
关键:
  - 破解服务端 SHA1 PoW 挑战 (attack_key)
  - 解析 box.dyrs.com.de 的 master m3u8，提取真实子 m3u8
  - 简介添加指定前缀
  - 兼容无 data-title 的剧集（短剧）+ 直链 m3u8（modujx17）
"""
import re
import sys
import json
import time
import hashlib
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
                print("[douhua]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://dhvideo.cc"
SION_ID = "6ac4b6643b9fea31774d1157"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/douhua/douhua.me.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

_SORTS = [{"n": "热度最高", "v": "play_hot"},
          {"n": "豆瓣评分", "v": "group_douban"}]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
    {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
]

_FILTERS_MAP = {
    "dianying":  ["全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
                  "悬疑", "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争",
                  "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片"],
    "dianshiju": ["全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
                  "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
                  "武侠", "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装"],
    "zongyi":    ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
                  "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
                  "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技"],
    "dongman":   ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
                  "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
                  "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园"],
    "duanju":    ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
                  "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
                  "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'href="(/(?:movie|tv)/[^"]+?\.html)[^"]*"[^>]*>'
    r'[\s\S]{0,200}?'
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)

_RE_HREF = re.compile(r'href="(/(?:movie|tv)/[^"]+?\.html)', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)

# 剧集：兼容有/无 data-title
_RE_EPISODE_A = re.compile(
    r'<a\s+href="([^"]+)"([^>]*?)>(.*?)</a>',
    re.S | re.I)
_RE_DATA_ORIGIN = re.compile(r'data-origin="([^"]+)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]+)"', re.I)
_RE_BTN_TITLE = re.compile(r'<button[^>]*>([^<]+)</button>', re.I)

_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)

# 简介提取（多层兜底）
_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO_DIV = re.compile(
    r'<div[^>]*class="[^"]*text-\[#555\][^"]*reset-style[^"]*"[^>]*>'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)

# 元信息正则
_RE_DIRECTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">导演</span>\s*'
    r'<span[^>]*>([^<]*)</span>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">主演</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.S | re.I)
_RE_SCORE = re.compile(
    r'vk-badge[^>]*>\s*([\d.]+)\s*<', re.I)
_RE_HOT = re.compile(
    r'([\d,]+)\s*\(电视剧排名:\s*(\d+),\s*总排名:\s*(\d+)\)', re.I)

# PoW 挑战页特征
_RE_POW_HASH = re.compile(r"var\s+hash\s*=\s*['\"]([a-f0-9]{40})['\"]")
_RE_POW_TARGET = re.compile(r"var\s+target\s*=\s*['\"]([a-f0-9]{40})['\"]")

_LINE_PRIORITY = ["vip", "1080zyk", "wztv", "bfzym3u8", "dyttm3u8",
                  "ffm3u8", "lzm3u8", "modum3u8", "jsm3u8", "mtm3u8"]
_LINE_ALIAS = {
    "vip": "VIP线路", "modum3u8": "魔都M3U8", "jsm3u8": "极速M3U8",
    "mtm3u8": "茅台M3U8", "1080zyk": "1080资源", "lzm3u8": "量子M3U8",
    "bfzym3u8": "暴风资源", "dyttm3u8": "电影天堂", "ffm3u8": "非凡M3U8",
    "wztv": "王者TV",
}

BOX_HOST = "https://box.dyrs.com.de"


class Spider(Spider):

    def getName(self):
        return "豆花电影"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.sion_id  = self.extend.get("sion_id") or SION_ID
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self.log("init: site=%s sid=%s" % (self.site_url, self.sion_id))

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/?sion_id=" + self.sion_id, timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _solve_pow(self, html):
        m1 = _RE_POW_HASH.search(html)
        m2 = _RE_POW_TARGET.search(html)
        if not m1 or not m2:
            self.log("PoW: 未找到 hash/target")
            return None

        hash_prefix = m1.group(1)
        target = m2.group(1)
        self.log("PoW: hash=%s target=%s" % (hash_prefix[:16], target[:16]))

        max_i = 10 * 1000 * 1000
        start = time.time()
        prefix_b = hash_prefix.encode()

        for i in range(max_i):
            s = hashlib.sha1(prefix_b + str(i).encode()).hexdigest()
            if s == target:
                cost = time.time() - start
                self.log("PoW 破解成功: i=%d 耗时=%.2fs" % (i, cost))
                return i
            if (i + 1) % 1000000 == 0:
                cost = time.time() - start
                self.log("PoW 进度: %d 万, 已耗时 %.1fs" % ((i + 1) // 10000, cost))
                if cost > 60:
                    self.log("PoW 超时 (>60s)")
                    return None

        self.log("PoW 未在范围内破解")
        return None

    def _fetch(self, url, timeout=60, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)

            if ("正在检测" in text) or ("sha1(hash" in text and "attack_key" in text):
                self.log("⚠️ 遇到 PoW 挑战, 开始破解...")
                attack_key = self._solve_pow(text)
                if attack_key is not None:
                    sep = "&" if "?" in url else "?"
                    new_url = url + sep + "attack_key=" + str(attack_key)
                    self.log("带 attack_key 重新请求")
                    rsp2 = self.fetch(new_url, headers=h, timeout=timeout)
                    text2 = ""
                    if hasattr(rsp2, "text"):
                        text2 = rsp2.text or ""
                    elif hasattr(rsp2, "content"):
                        text2 = rsp2.content.decode("utf-8", "ignore")
                    self.log("PoW 后 HTML 长度: %d" % len(text2))

                    if "正在检测" in text2 and "sha1(hash" in text2:
                        self.log("⚠️ 再次遇到挑战, 再破一次...")
                        attack_key2 = self._solve_pow(text2)
                        if attack_key2 is not None:
                            sep2 = "&" if "?" in new_url else "?"
                            new_url2 = new_url + sep2 + "attack_key=" + str(attack_key2)
                            rsp3 = self.fetch(new_url2, headers=h, timeout=timeout)
                            text2 = rsp3.text if hasattr(rsp3, "text") else str(rsp3)
                    return text2
                else:
                    self.log("PoW 破解失败")
                    return text
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
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, alt, pic in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100],
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  分开: href=%d img=%d" % (len(hrefs), len(imgs)))

        if hrefs and imgs:
            for i, href in enumerate(hrefs):
                if href in seen:
                    continue
                seen.add(href)
                alt, pic = ("", "")
                if i < len(imgs):
                    alt, pic = imgs[i]
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100] or href,
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    href.split("/")[-1].split("-")[0],
                "vod_pic":     self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        url = "%s/?sion_id=%s" % (self.site_url, self.sion_id)
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
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

        params = {
            "page": page - 1,
            "sort_field": extend.get("sort_field") or "play_hot",
            "sion_id": self.sion_id,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]

        url = "%s/%s.html?%s" % (self.site_url, tid, urllib.parse.urlencode(params))
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/s?name=%s&sion_id=%s&page=%d" % (
            self.site_url, keyword, self.sion_id, page - 1)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    name = self._clean(m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        try:
            m = _RE_PIC_ID.search(html)
            if m:
                pic = self.site_url + m.group(0)
        except Exception:
            pass

        # 简介
        content = ""
        try:
            m = _RE_INTRO.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_INTRO_DIV.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 元信息
        director = ""
        try:
            m = _RE_DIRECTOR.search(html)
            if m:
                director = self._clean(m.group(1))
        except Exception:
            pass

        actor = ""
        try:
            m = _RE_ACTOR.search(html)
            if m:
                actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))
        except Exception:
            pass

        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        hot_info = ""
        try:
            m = _RE_HOT.search(html)
            if m:
                hot_info = "热度%s (排名%s)" % (m.group(1), m.group(2))
        except Exception:
            pass

        # ===== 剧集提取（兼容有/无 data-title）=====
        groups = {}
        try:
            for m in _RE_EPISODE_A.finditer(html):
                href = m.group(1)
                attrs = m.group(2)
                inner = m.group(3)

                mo = _RE_DATA_ORIGIN.search(attrs)
                if not mo:
                    continue
                origin = mo.group(1)
                if not origin:
                    continue

                href = href.replace("&amp;", "&")
                if href.startswith("/"):
                    href = self.site_url + href

                ep_name = ""
                mt = _RE_DATA_TITLE.search(attrs)
                if mt:
                    ep_name = self._clean(mt.group(1))
                if not ep_name:
                    mt = _RE_BTN_TITLE.search(inner)
                    if mt:
                        ep_name = self._clean(mt.group(1))
                if not ep_name:
                    ep_name = "第%s集" % (len(groups.get(origin, [])) + 1)

                groups.setdefault(origin, []).append((ep_name, href))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        sorted_origins = sorted(
            groups.keys(),
            key=lambda x: (_LINE_PRIORITY.index(x)
                           if x in _LINE_PRIORITY else 999))

        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            alias = _LINE_ALIAS.get(origin, origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": hot_info or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        api_url = self._extract_api_m3u8(html) if html else ""
        self.log("  api_url: %s" % (api_url[:200] if api_url else "EMPTY"))

        if api_url:
            # ========== 情况 A：aa.url 直接是 m3u8 直链 (短剧常见) ==========
            if api_url.startswith("http") and ".m3u8" in api_url.lower():
                self.log("  => 直链 m3u8 (无需转换): %s" % api_url[:200])
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": api_url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self.site_url + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

            # ========== 情况 B：/api/m3u8?... 需要 302 转换 ==========
            if api_url.startswith("/"):
                api_url = self.site_url + api_url

            real_m3u8 = self._resolve_to_real_m3u8(api_url, referer=play_page)
            if real_m3u8:
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_m3u8,
                    "header": {
                        "User-Agent": UA,
                        "Referer": BOX_HOST + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链 m3u8: %s" % real_m3u8[:160])
                return res

        # 兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_api_m3u8(self, html):
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            m2 = re.search(r'(/api/m3u8\?[^"\'\\\s]+)', html)
            if m2:
                return m2.group(1).replace("&amp;", "&")
            return ""
        raw = m.group(1)
        raw = (raw.replace("\\\\u0026", "&").replace("\\u0026", "&")
                  .replace("\\\\u0022", '"').replace("\\u0022", '"')
                  .replace("\\/", "/"))
        try:
            aa = json.loads(raw)
            return aa.get("url", "")
        except Exception:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""

    def _resolve_to_real_m3u8(self, api_url, referer=None):
        try:
            try:
                rsp = self.fetch(api_url, headers={
                    "User-Agent": UA,
                    "Referer": referer or (self.site_url + "/"),
                    "Accept": "text/html,application/json,*/*",
                }, timeout=15, allow_redirects=False)
            except TypeError:
                rsp = self.fetch(api_url, headers={
                    "User-Agent": UA,
                    "Referer": referer or (self.site_url + "/"),
                    "Accept": "text/html,application/json,*/*",
                }, timeout=15)
        except Exception as e:
            self.log("resolve#1 fail: %s" % e)
            return ""

        loc = ""
        if hasattr(rsp, "headers"):
            loc = (rsp.headers.get("Location", "") or
                   rsp.headers.get("location", ""))

        if not loc:
            text = ""
            try:
                text = rsp.text if hasattr(rsp, "text") else ""
            except Exception:
                text = ""
            if "#EXTM3U" in text:
                self.log("api 直接返回 m3u8")
                return api_url
            return ""

        if loc.startswith("//"):
            loc = "https:" + loc
        loc = loc.replace("&amp;", "&")
        self.log("  box master: %s" % loc[:150])

        try:
            rsp2 = self.fetch(loc, headers={
                "User-Agent": UA,
                "Referer": api_url,
                "Accept": "*/*",
            }, timeout=15)
            text2 = ""
            if hasattr(rsp2, "text"):
                text2 = rsp2.text or ""
            elif hasattr(rsp2, "content"):
                text2 = rsp2.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log("resolve#2 fail: %s" % e)
            return loc

        if "#EXTM3U" not in text2:
            self.log("  master 无 m3u8 头")
            return loc

        lines = [ln.strip() for ln in text2.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                if i + 1 < len(lines):
                    sub = lines[i + 1].strip()
                    if sub.startswith("http"):
                        full = sub
                    elif sub.startswith("/"):
                        full = BOX_HOST + sub
                    else:
                        full = BOX_HOST + "/" + sub
                    self.log("  子 m3u8: %s" % full[:160])
                    return full

        self.log("  无子 m3u8, 返回 master")
        return loc

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
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
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
