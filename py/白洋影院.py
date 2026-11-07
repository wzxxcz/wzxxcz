# -*- coding: utf-8 -*-
# !/usr/bin/python
"""
森林影院 TVBox 爬虫  https://www.lundashiye.com/
站点：苹果CMS + ewave one 模板

路由：
  首页            /
  大分类          /sort/{id}.html
  分类第 n 页     /sort/{id}-{n}.html
  二级分类/筛选   /choice/[by/{sort}/][class/{剧情}/][area/{地区}/]id/{id}/[lang/{语言}/][letter/{字母}/][year/{年}/][page/{n}].html
  详情            /works/{vod_id}.html
  播放            /line/{vod_id}/{sid}/{nid}.html      -> player_aaaa
  搜索            /scan/wd/{关键词}.html
"""

import sys
import re
import json
import time
from urllib.parse import quote, unquote, urljoin

sys.path.append('..')

try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

import requests


# ==================== 常量配置 ====================

# 简介前缀
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

HOST = "https://www.lundashiye.com"

# 占位图，需过滤
PLACEHOLDER_IMG = "/static/images/load.png"

# 播放缓存有效时间（秒）
PLAY_CACHE_TTL = 600

# 线路优先级：数值越小越靠前（排在 vod_play_from 前面）
# 站点标签顺序：极速高清 / 量子高清 / 天堂高清 / 无尽4K
# 但 sid 顺序是：1=量子高清 2=无尽4K 3=天堂高清 4=极速高清
# 这里按「站点点开即用的推荐度」排序：量子高清为默认线路，放第一位
LINE_PRIORITY = {
    "量子高清": 1,
    "极速高清": 2,
    "天堂高清": 3,
    "无尽4K": 4,
}

# 线路别名归一（sid -> 站内名称），用于标签缺失时兜底
SID_NAME_MAP = {
    "1": "量子高清",
    "2": "无尽4K",
    "3": "天堂高清",
    "4": "极速高清",
}

# 线路简称（太长的名字压一下，TVBox 上更好看）
LINE_ALIAS = {
    "量子高清": "量子高清",
    "极速高清": "极速高清",
    "天堂高清": "天堂高清",
    "无尽4K": "无尽4K",
}

# 顶级分类：名称 -> (大分类id, 二级分类列表)
CATEGORY_TREE = [
    ("电影", "1", [
        ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
        ("剧情片", "10"), ("战争片", "11"), ("动画片", "41"), ("记录片", "12"),
        ("恐怖片", "39"),
    ]),
    ("电视剧", "2", [
        ("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"), ("欧美剧", "16"),
        ("台湾剧", "22"), ("日本剧", "21"), ("泰国剧", "20"), ("海外剧", "23"),
    ]),
    ("综艺", "3", [
        ("大陆综艺", "25"), ("日韩综艺", "26"), ("港台综艺", "27"), ("欧美综艺", "28"),
    ]),
    ("动漫", "4", [
        ("国产动漫", "29"), ("日本动漫", "30"), ("港台动漫", "42"), ("欧美动漫", "31"),
        ("海外动漫", "43"),
    ]),
    ("短剧", "24", [
        ("短剧大全", "40"), ("AI漫剧", "44"),
    ]),
]

# 二级分类 id -> 名称
SUB_CATE_NAME = {}
# 二级分类过滤：哪些 id 属于「短剧」体系（只有 类型/字母/排序，没有 剧情/地区/年份/语言）
SHORT_DRAMA_IDS = {"40", "44"}

for _top_name, _top_id, _subs in CATEGORY_TREE:
    for _sub_name, _sub_id in _subs:
        SUB_CATE_NAME[_sub_id] = _sub_name

# 筛选值表（兜底用；实际解析时优先从页面 href 里提取，保证与站点完全一致）
FILTER_DB = {
    # 电影
    "1": {
        "class": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
                  "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "灾难", "伦理",
                  "微电影", "网络电影", "记录", "其它", "经典", "青春", "古装", "家庭"],
        "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
                 "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "year": [str(y) for y in range(2026, 2003, -1)],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
        "by": ["time", "hits", "score"],
    },
    # 电视剧
    "2": {
        "class": ["古装", "战争", "青春偶像", "家庭", "犯罪", "动作", "奇幻", "剧情",
                  "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "year": [str(y) for y in range(2026, 2003, -1)],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
        "by": ["time", "hits", "score"],
    },
    # 综艺
    "3": {
        "class": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
                  "曲艺", "生活", "游戏互动", "财经", "求职"],
        "area": ["内地", "港台", "日韩", "欧美"],
        "year": [str(y) for y in range(2026, 2003, -1)],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
        "by": ["time", "hits", "score"],
    },
    # 动漫
    "4": {
        "class": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
                  "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
                  "亲子", "益智", "励志", "其他"],
        "area": ["国产", "日本", "欧美", "其他"],
        "year": [str(y) for y in range(2026, 2003, -1)],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
        "by": ["time", "hits", "score"],
    },
    # 短剧
    "24": {
        "by": ["time", "hits", "score"],
    },
}

LETTERS = [chr(i) for i in range(65, 91)] + ["0-9"]


# ==================== 工具函数 ====================

def _clean(text):
    """去标签、去空白、反转义"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&") \
               .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"') \
               .replace("&#039;", "'").replace("&ldquo;", "“").replace("&rdquo;", "”") \
               .replace("&hellip;", "…")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _abs(url):
    """补全为绝对地址"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return HOST + url
    return urljoin(HOST + "/", url)


def _norm_img(url):
    """图片地址归一，过滤占位图"""
    url = _abs(url)
    if not url or PLACEHOLDER_IMG in url:
        return ""
    return url


# ==================== 主类 ====================

class Spider(Spider):
    """森林影院"""

    def __init__(self):
        self._play_cache = {}      # url -> (ts, dict)
        self._detail_cache = {}    # vod_id -> (ts, html)
        self._session = None

    # ---------- 基础 ----------

    def getName(self):
        return "森林影院"

    def init(self, extend=""):
        """
        extend 可传 JSON，用于覆盖域名：
        {"host": "https://www.lundashiye.com"}
        """
        global HOST
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else dict(extend)
                h = str(cfg.get("host") or cfg.get("site") or "").strip()
                if h:
                    if not h.startswith("http"):
                        h = "https://" + h
                    HOST = h.rstrip("/")
            except Exception:
                pass
        return self

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower().split("?")[0]
        for ext in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mov", ".webm"):
            if u.endswith(ext):
                return True
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._play_cache.clear()
        self._detail_cache.clear()
        self._session = None
        return True

    def close(self):
        return self.destroy()

    # ---------- 请求层 ----------

    @property
    def _sess(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update(self._headers())
            self._session = s
        return self._session

    def _headers(self, referer=None):
        return {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer or (HOST + "/"),
        }

    def fetch(self, url, headers=None, **kw):
        """GET，返回文本；失败返回空串"""
        url = _abs(url)
        h = self._headers()
        if headers:
            h.update(headers)
        kw.setdefault("timeout", 15)
        kw.setdefault("verify", False)
        for _ in range(2):
            try:
                r = self._sess.get(url, headers=h, **kw)
                r.encoding = r.apparent_encoding or "utf-8"
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception as e:
                self.log("fetch err %s %s" % (url, e))
                time.sleep(0.3)
        return ""

    def log(self, msg):
        try:
            print("[森林影院] %s" % msg)
        except Exception:
            pass

    # ==================== 首页 ====================

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}

        # 分类树
        for top_name, top_id, subs in CATEGORY_TREE:
            result["class"].append({"type_id": top_id, "type_name": top_name})

        if not filter:
            return result

        # 筛选（按顶级分类 id 给）
        for top_name, top_id, subs in CATEGORY_TREE:
            f = self._build_filters(top_id)
            if f:
                result["filters"][top_id] = f

        return result

    def _build_filters(self, top_id):
        """构造某个大分类的筛选器"""
        db = FILTER_DB.get(top_id)
        if not db:
            return []

        out = []
        # 类型（二级分类）
        subs = []
        for top_name, tid, slist in CATEGORY_TREE:
            if tid == top_id:
                subs = slist
                break
        if subs:
            vals = [{"n": "全部", "v": ""}]
            for sname, sid in subs:
                vals.append({"n": sname, "v": sid})
            out.append({"key": "sub", "name": "类型", "value": vals})

        # 短剧只有 类型 + 字母 + 排序
        if top_id in ("24",):
            out.append({"key": "letter", "name": "字母",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": x, "v": x} for x in LETTERS]})
            out.append({"key": "by", "name": "排序",
                        "value": [{"n": "时间", "v": "time"},
                                  {"n": "人气", "v": "hits"},
                                  {"n": "评分", "v": "score"}]})
            return out

        # 剧情
        if db.get("class"):
            out.append({"key": "class", "name": "剧情",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": x, "v": x} for x in db["class"]]})
        # 地区
        if db.get("area"):
            out.append({"key": "area", "name": "地区",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": x, "v": x} for x in db["area"]]})
        # 年份
        if db.get("year"):
            out.append({"key": "year", "name": "年份",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": x, "v": x} for x in db["year"]]})
        # 语言
        if db.get("lang"):
            out.append({"key": "lang", "name": "语言",
                        "value": [{"n": "全部", "v": ""}] +
                                 [{"n": x, "v": x} for x in db["lang"]]})
        # 字母
        out.append({"key": "letter", "name": "字母",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": x, "v": x} for x in LETTERS]})
        # 排序
        out.append({"key": "by", "name": "排序",
                    "value": [{"n": "时间", "v": "time"},
                              {"n": "人气", "v": "hits"},
                              {"n": "评分", "v": "score"}]})
        return out

    def homeVideoContent(self):
        html = self.fetch(HOST + "/")
        videos = self._parse_video_list(html)
        if not videos:
            # 首页抓不到就退化为最近更新
            html = self.fetch(HOST + "/label/new.html")
            videos = self._parse_video_list(html)
        return {"list": videos}

    # ==================== 分类 ====================

    def categoryContent(self, tid, page, filter, ext):
        """
        tid   : 分类 id（可能是二级 id，也可能是顶级 id）
        page  : 1 起（TVBox 内部 0/1 起都兼容，这里做保护）
        filter: 筛选选择，形如 {"sub":"13","class":"","area":"","year":"","lang":"","letter":"","by":"time"}
        """
        try:
            page = int(page or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        tid = str(tid or "").strip()
        flt = self._norm_filter(filter, ext)

        url = self._build_category_url(tid, page, flt)
        html = self.fetch(url)

        # 兜底：第一页没数据时用大分类
        if not html:
            html = self.fetch(self._build_category_url(tid, page, {}))

        videos = self._parse_video_list(html)
        pagecount, total = self._parse_pager(html)

        # pagecount 兜底
        if pagecount <= 1:
            pagecount = page if videos else page
            if videos and len(videos) >= 20:
                pagecount = max(page + 1, pagecount)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": total or pagecount * 24,
        }

    def _norm_filter(self, filter, ext):
        """把 TVBox 传进来的筛选统一成 dict（string->string）"""
        out = {}
        candidates = []
        if isinstance(filter, dict):
            candidates.append(filter)
        if isinstance(ext, dict):
            candidates.append(ext)
            for k in ("filter", "filters", "extend"):
                v = ext.get(k)
                if isinstance(v, dict):
                    candidates.append(v)
                elif isinstance(v, str) and v.strip().startswith("{"):
                    try:
                        candidates.append(json.loads(v))
                    except Exception:
                        pass
        if isinstance(filter, str) and filter.strip().startswith("{"):
            try:
                candidates.append(json.loads(filter))
            except Exception:
                pass

        for c in candidates:
            for k, v in c.items():
                if k in ("sub", "class", "area", "year", "lang", "letter", "by", "id", "page"):
                    sv = "" if v is None else str(v).strip()
                    if sv:
                        out.setdefault(k, sv)
        return out

    def _build_category_url(self, tid, page, flt):
        """
        拼分类 URL。

        站点的筛选段顺序不固定（跟排序有关），这里按最常见的生成顺序：
        /choice/by/{by}/class/{class}/area/{area}/id/{id}/lang/{lang}/letter/{letter}/year/{year}/page/{page}.html
        同时保证：任一筛选为空则整段省略；page=1 时省略 page 段。
        """
        tid = str(tid).strip()

        # 类型（二级分类）优先，其次才是顶级
        cate_id = flt.get("sub") or tid
        if not cate_id:
            cate_id = tid

        # 判断是否走 /choice/ 路由
        by = flt.get("by", "")
        cls = flt.get("class", "")
        area = flt.get("area", "")
        lang = flt.get("lang", "")
        letter = flt.get("letter", "")
        year = flt.get("year", "")

        # 无任何筛选 + 分页 -> 走 /sort/{id}-{page}.html，最稳
        if not any([by, cls, area, lang, letter, year]):
            if page <= 1:
                return "%s/sort/%s.html" % (HOST, cate_id)
            return "%s/sort/%s-%d.html" % (HOST, cate_id, page)

        segs = ["by/" + (by or "time")]
        if cls:
            segs.append("class/" + quote(cls))
        if area:
            segs.append("area/" + quote(area))
        segs.append("id/" + cate_id)
        if lang:
            segs.append("lang/" + quote(lang))
        if letter:
            segs.append("letter/" + quote(letter))
        if year:
            segs.append("year/" + quote(year))
        if page > 1:
            segs.append("page/%d" % page)

        return "%s/choice/%s.html" % (HOST, "/".join(segs))

    # ==================== 详情 ====================

    def detailContent(self, array):
        """
        array: ["https://www.lundashiye.com/works/770210.html"] 或 ["770210"]
        """
        if not array:
            return {"list": []}

        raw = str(array[0]).strip()
        vod_id = self._extract_vod_id(raw)
        if not vod_id:
            return {"list": []}

        html = self._get_detail_html(vod_id)
        if not html:
            return {"list": []}

        vod = self._parse_detail(html, vod_id)
        return {"list": [vod]}

    def _extract_vod_id(self, raw):
        m = re.search(r"/works/(\d+)\.html", raw)
        if m:
            return m.group(1)
        m = re.search(r"/line/(\d+)/", raw)
        if m:
            return m.group(1)
        m = re.search(r"(\d{2,})", raw)
        if m:
            return m.group(1)
        return ""

    def _get_detail_html(self, vod_id):
        now = time.time()
        cache = self._detail_cache.get(vod_id)
        if cache and now - cache[0] < PLAY_CACHE_TTL:
            return cache[1]
        html = self.fetch("%s/works/%s.html" % (HOST, vod_id))
        if html:
            if len(self._detail_cache) > 60:
                self._detail_cache.clear()
            self._detail_cache[vod_id] = (now, html)
        return html

    def _parse_detail(self, html, vod_id):
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_lang": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 标题
        m = re.search(r'<h1[^>]*class="[^"]*detail-info-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
        if not m:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        vod["vod_name"] = _clean(m.group(1)) if m else ""

        # 封面
        m = re.search(r'<div\s+class="block-fea[^"]*"\s+data-original="([^"]+)"', html)
        if not m:
            m = re.search(r'class="block-fea[^"]*"[^>]*data-original="([^"]+)"', html)
        vod["vod_pic"] = _norm_img(m.group(1)) if m else ""

        # 面包屑 -> 类型名
        m = re.search(r'<div class="position-link[^"]*">(.*?)</div>', html, re.S)
        if m:
            links = re.findall(r'<a[^>]*>(.*?)</a>', m.group(1), re.S)
            links = [_clean(x) for x in links if _clean(x)]
            if len(links) >= 2:
                vod["type_name"] = links[-1]
            elif links:
                vod["type_name"] = links[0]

        # 分类标签（vodlist_top 里的 em）兜底
        if not vod["type_name"]:
            m = re.search(r'<span class="vodlist_top"><em[^>]*>(.*?)</em>', html, re.S)
            if m:
                vod["type_name"] = _clean(m.group(1))

        # 详情字段区
        info_block = ""
        m = re.search(r'<div class="detail-info-text[^"]*">(.*?)(?:<a class="visible-xs|<h3>)', html, re.S)
        if m:
            info_block = m.group(1)

        def grab(label):
            mm = re.search(r'<span>\s*' + label + r'\s*[：:]\s*</span>(.*?)</p>',
                           info_block, re.S)
            if mm:
                return _clean(mm.group(1))
            return ""

        vod["vod_remarks"] = grab("状态")
        vod["vod_area"] = grab("地区")
        vod["vod_year"] = grab("年份")
        vod["vod_lang"] = grab("语言")

        # 导演：取 a 文本合集
        director = ""
        mm = re.search(r'<span>\s*导演\s*[：:]\s*</span>(.*?)</p>', info_block, re.S)
        if mm:
            names = re.findall(r'<a[^>]*>(.*?)</a>', mm.group(1), re.S)
            names = [_clean(x) for x in names if _clean(x)]
            director = ",".join(names) if names else _clean(mm.group(1))
        vod["vod_director"] = director

        # 演员：取 a 文本合集
        actor = ""
        mm = re.search(r'<span>\s*演员\s*[：:]\s*</span>(.*?)</p>', info_block, re.S)
        if mm:
            names = re.findall(r'<a[^>]*>(.*?)</a>', mm.group(1), re.S)
            names = [_clean(x) for x in names if _clean(x)]
            actor = ",".join(names) if names else _clean(mm.group(1))
        vod["vod_actor"] = actor

        # 剧情简介：优先 #desc 区块的完整简介，其次详情里的「剧情：」，最后 meta
        content = ""
        mm = re.search(
            r'id="desc".*?<div class="col-pd[^"]*content[^"]*">(.*?)</div>', html, re.S)
        if mm:
            content = _clean(mm.group(1))
        if not content:
            mm = re.search(r'<span>\s*剧情\s*[：:]\s*</span>(.*?)</p>', info_block, re.S)
            if mm:
                content = _clean(mm.group(1))
                content = re.sub(r'更多\s*$', '', content).strip()
        if not content:
            mm = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
            if mm:
                content = _clean(mm.group(1))
        # 去掉结尾的省略号和「更多」
        content = re.sub(r'(\.{3,}|。{3,}|…+)\s*$', '', content).strip()
        vod["vod_content"] = (INTRO_PREFIX + content) if content else INTRO_PREFIX

        # ---------- 线路 + 剧集 ----------
        froms, urls = self._parse_playlist(html, vod_id)
        vod["vod_play_from"] = "$$$".join(froms)
        vod["vod_play_url"] = "$$$".join(urls)

        return vod

    def _parse_playlist(self, html, vod_id):
        """
        解析播放列表。
        标签：<li class="swiper-slide ewave-tab " data-target="#ewave-playlist-4"><a>极速高清</a></li>
        剧集：<ul id="ewave-playlist-4"><li class="ewave-playlist-item"><a href="/line/770210/4/1.html">第1集</a></li>
        返回 (froms, urls)，均已按优先级排序
        """
        # 1) 标签 -> sid 映射
        tab_map = {}   # sid -> 线路名
        for m in re.finditer(
                r'<li[^>]*class="[^"]*ewave-tab[^"]*"[^>]*data-target="#ewave-playlist-(\d+)"[^>]*>'
                r'\s*<a[^>]*>(.*?)</a>', html, re.S):
            sid = m.group(1)
            name = _clean(m.group(2))
            if name:
                tab_map[sid] = name

        # 2) 每个 ul 的剧集
        blocks = []
        # 找所有 id="ewave-playlist-N" 的 ul
        for m in re.finditer(r'<ul[^>]*id="ewave-playlist-(\d+)"[^>]*>(.*?)</ul>', html, re.S):
            sid = m.group(1)
            inner = m.group(2)
            eps = []
            for em in re.finditer(r'<a[^>]*href="(/line/[^"]+)"[^>]*>(.*?)</a>', inner, re.S):
                href = em.group(1)
                name = _clean(em.group(2))
                if not name:
                    # 从 URL 抠 nid 作名字
                    mm = re.search(r"/line/\d+/\d+/(\d+)\.html", href)
                    name = ("第%s集" % mm.group(1)) if mm else "正片"
                # 从 href 校正 sid
                mm2 = re.search(r"/line/(\d+)/(\d+)/(\d+)\.html", href)
                if mm2:
                    real_sid = mm2.group(2)
                else:
                    real_sid = sid
                nid_m = re.search(r"/line/\d+/\d+/(\d+)\.html", href)
                nid = nid_m.group(1) if nid_m else ""
                eps.append({
                    "name": name,
                    "url": _abs(href),
                    "sid": real_sid,
                    "nid": nid,
                })
            if eps:
                # 线路名：优先标签，其次 sid 映射
                line_name = tab_map.get(sid) or SID_NAME_MAP.get(sid) or ("线路%s" % sid)
                blocks.append({
                    "sid": sid,
                    "name": line_name,
                    "eps": eps,
                })

        # 3) 标签存在但没有 ul 的情况（极少），忽略
        # 4) 去重（同一个 sid 只保留第一个）
        seen = set()
        uniq = []
        for b in blocks:
            if b["sid"] in seen:
                continue
            seen.add(b["sid"])
            uniq.append(b)

        # 5) 排序：按 LINE_PRIORITY
        uniq.sort(key=lambda x: (LINE_PRIORITY.get(x["name"], 99), int(x["sid"]) if x["sid"].isdigit() else 99))

        froms = []
        urls = []
        for b in uniq:
            fname = LINE_ALIAS.get(b["name"], b["name"])
            # 线路名去重，避免同名导致 TVBox 合并
            base = fname
            idx = 2
            while fname in froms:
                fname = "%s%d" % (base, idx)
                idx += 1
            froms.append(fname)

            play_list = []
            for e in b["eps"]:
                # 剧集名里的 $ 和 # 要替换，避免破坏协议
                nm = e["name"].replace("$", " ").replace("#", " ").strip() or "正片"
                play_list.append("%s$%s" % (nm, e["url"]))
            urls.append("#".join(play_list))

        return froms, urls

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}
        url = "%s/scan/wd/%s.html" % (HOST, quote(key))
        html = self.fetch(url)
        videos = self._parse_video_list(html)
        return {"list": videos}

    def searchContentPage(self, key, quick, pg="1"):
        """站点搜索结果无分页，直接复用"""
        key = (key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        url = "%s/scan/wd/%s.html" % (HOST, quote(key))
        html = self.fetch(url)
        videos = self._parse_video_list(html)
        return {
            "list": videos,
            "page": 1,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
        """
        flag: 线路名（vod_play_from 之一）
        id  : 播放页地址 /line/{vod_id}/{sid}/{nid}.html
        """
        result = {
            "parse": 0,
            "playUrl": "",
            "url": "",
            "header": json.dumps(self._headers(), ensure_ascii=False),
        }
        if not id:
            return result

        # 已经是直链
        if self.isVideoFormat(id):
            result["url"] = id
            return result

        # 播放页 -> player_aaaa
        now = time.time()
        cached = self._play_cache.get(id)
        if cached and now - cached[0] < PLAY_CACHE_TTL:
            return cached[1]

        info = self._parse_player(id)
        if not info:
            # 解析失败，交给 TVBox 嗅探
            result["parse"] = 1
            result["url"] = _abs(id)
            result["header"] = json.dumps(self._headers(referer=_abs(id)), ensure_ascii=False)
            return result

        url = info.get("url", "")
        encrypt = info.get("encrypt", 0)
        from_flag = (info.get("from") or "").lower()
        server = str(info.get("server") or "")

        # encrypt=1 的站点是 url 做了 escape/unescape，这里做兼容
        if str(encrypt) == "1" and url:
            url = unquote(url)

        if url and self.isVideoFormat(url):
            # 直链 m3u8 / mp4
            result["parse"] = 0
            result["url"] = url
            result["header"] = json.dumps(
                self._headers(referer=_abs(id)), ensure_ascii=False)
        elif url:
            # 是解析页而非直链
            if from_flag in ("lzm3u8", "m3u8", "lzm3u8.com") or ".m3u8" in url:
                result["parse"] = 0
                result["url"] = url
                result["header"] = json.dumps(
                    self._headers(referer=_abs(id)), ensure_ascii=False)
            else:
                result["parse"] = 1
                result["url"] = url
                result["header"] = json.dumps(
                    self._headers(referer=_abs(id)), ensure_ascii=False)
        else:
            result["parse"] = 1
            result["url"] = _abs(id)

        if len(self._play_cache) > 200:
            self._play_cache.clear()
        self._play_cache[id] = (now, result)
        return result

    def _parse_player(self, play_url):
        """
        抓播放页，正则取 player_aaaa JSON。
        """
        html = self.fetch(play_url, headers={"Referer": HOST + "/"})
        if not html:
            return None
        return self._parse_player_html(html)

    def _parse_player_html(self, html):
        """
        从播放页 HTML 中提取 player_aaaa。
        里面 url 有 \/ 转义，先替换再 loads。
        """
        if not html:
            return None

        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*[;\n]', html, re.S)
        if not m:
            return None

        raw = m.group(1).strip()
        raw = raw.replace("\\/", "/")
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 兜底：手动抠字段
        info = {}
        mm = re.search(r'"url"\s*:\s*"(.*?)"', raw, re.S)
        if mm:
            info["url"] = mm.group(1).replace("\\/", "/")
        mm = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
        info["encrypt"] = int(mm.group(1)) if mm else 0
        mm = re.search(r'"from"\s*:\s*"(.*?)"', raw)
        info["from"] = mm.group(1) if mm else ""
        mm = re.search(r'"server"\s*:\s*"(.*?)"', raw)
        info["server"] = mm.group(1) if mm else ""
        return info if info.get("url") else None

    def localProxy(self, param):
        return None

    # ==================== 列表解析 ====================

    def _parse_video_list(self, html):
        """
        通用卡片解析：
        <div class="video-content-item">
          <a class="video-img lazyload" href="/works/xxx.html" data-original="..." title="名称">
            <span class="vodlist_top"><em class="voddate voddate_year">国产剧</em></span>
            <span class="video-title ...">第27集完结</span>
          </a>
          <p class="video-name"><a href="/works/xxx.html" title="名称">名称</a></p>
          <p class="video-actor ...">演员</p>
        </div>
        """
        videos = []
        if not html:
            return videos

        # 按卡片切分
        parts = re.split(r'<div class="video-content-item">', html)
        if len(parts) <= 1:
            # 兼容单引号 / 多类名
            parts = re.split(r'<div[^>]*class="[^"]*video-content-item[^"]*"[^>]*>', html)
        if len(parts) <= 1:
            return videos

        seen = set()
        for part in parts[1:]:
            # 只取到下一个卡片前
            block = part

            # 链接 + 标题
            m = re.search(r'<a[^>]*class="[^"]*video-img[^"]*"[^>]*>', block)
            href = ""
            pic = ""
            title = ""
            if m:
                tag = m.group(0)
                h = re.search(r'href="([^"]+)"', tag)
                href = h.group(1) if h else ""
                d = re.search(r'data-original="([^"]+)"', tag)
                pic = d.group(1) if d else ""
                t = re.search(r'title="([^"]*)"', tag)
                title = t.group(1) if t else ""
                if not href:
                    # 有时 href 在后面
                    h2 = re.search(r'<a[^>]*href="(/works/\d+\.html)"', block)
                    href = h2.group(1) if h2 else ""

            if not href:
                continue

            # 名称
            name = title
            if not name:
                nm = re.search(r'<p class="video-name">\s*<a[^>]*>(.*?)</a>', block, re.S)
                if nm:
                    name = _clean(nm.group(1))
            if not name:
                nm = re.search(r'<p class="video-name">\s*<a[^>]*title="([^"]*)"', block)
                name = nm.group(1) if nm else ""
            name = _clean(name)

            # 副标题（备注）
            remarks = ""
            rm = re.search(r'<span class="video-title[^"]*">(.*?)</span>', block, re.S)
            if rm:
                remarks = _clean(rm.group(1))

            # 分类名
            type_name = ""
            tm = re.search(r'<em class="voddate[^"]*">(.*?)</em>', block, re.S)
            if tm:
                type_name = _clean(tm.group(1))

            # 演员
            actor = ""
            am = re.search(r'<p class="video-actor[^"]*">(.*?)</p>', block, re.S)
            if am:
                actor = _clean(am.group(1))
                if actor in ("内详", "未知", "暂无"):
                    actor = ""

            # 去重
            if href in seen:
                continue
            seen.add(href)

            videos.append({
                "vod_id": _abs(href),
                "vod_name": name,
                "vod_pic": _norm_img(pic),
                "vod_remarks": remarks,
                "type_name": type_name,
                "vod_actor": actor,
            })

        return videos

    def _parse_pager(self, html):
        """解析总页数，返回 (pagecount, total)"""
        pagecount = 0
        total = 0
        if not html:
            return 0, 0

        # 移动端 li.current 里的 "2<span>/1315</span>"
        m = re.search(r'<li class="current[^"]*"><a[^>]*>\s*\d+\s*<span>/(\d+)</span>', html)
        if m:
            pagecount = int(m.group(1))
        if not pagecount:
            # 尾页 title="第1315页"
            ms = re.findall(r'title="第(\d+)页"', html)
            if ms:
                pagecount = max(int(x) for x in ms)
        if not pagecount:
            # 所有 /sort/{id}-{n}.html 里的最大 n
            ms = re.findall(r'/sort/\d+-(\d+)\.html', html)
            if ms:
                pagecount = max(int(x) for x in ms)
        if pagecount:
            total = pagecount * 24
        return pagecount, total


# ==================== 本地调试 ====================

if __name__ == "__main__":
    sp = Spider()
    sp.init("")

    print("name:", sp.getName())

    hc = sp.homeContent(True)
    print("class:", hc["class"])
    print("filters keys:", list(hc["filters"].keys()))

    hv = sp.homeVideoContent()
    print("home list:", len(hv["list"]))
    if hv["list"]:
        print("first:", hv["list"][0])

    cc = sp.categoryContent("13", 1, {
        "sub": "", "class": "", "area": "", "year": "",
        "lang": "", "letter": "", "by": "time"}, None)
    print("cate page1:", len(cc["list"]), "pagecount:", cc["pagecount"])
    if cc["list"]:
        print("first:", cc["list"][0])

    sc = sp.searchContent("老舅", False, "1")
    print("search:", len(sc["list"]))
    if sc["list"]:
        print("first:", sc["list"][0])

    dc = sp.detailContent(["/works/770210.html"])
    if dc["list"]:
        v = dc["list"][0]
        print("detail:", v["vod_name"], v["vod_remarks"], v["type_name"], v["vod_year"])
        print("content:", v["vod_content"][:80])
        print("froms:", v["vod_play_from"])
        print("urls head:", v["vod_play_url"][:160])

        first_url = v["vod_play_url"].split("$$$")[0].split("#")[0].split("$")[-1]
        print("first ep:", first_url)
        pc = sp.playerContent("量子高清", first_url, "")
        print("player:", pc)
