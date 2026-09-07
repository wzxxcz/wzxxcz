# -*- coding: utf-8 -*-
"""
第九短剧网 (www.gzsns.com) Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV/PeekPro (T4)
【定制版 v11】苹果CMS10 + vfed 模板 — 补全导演/演员等信息解析
"""

import sys
import json
import re
import time
import threading

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

    class Spider:
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = _rq.get(url, headers=headers, timeout=timeout, verify=False, **kw)
            return r

from urllib.parse import quote


# ============================================================
# 常量（全部来自首页/分类页实测）
# ============================================================

HOST = "https://www.gzsns.com"

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")

CLASSES = [
    {"type_name": "电影",   "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "短剧",   "type_id": "3"},
    {"type_name": "动漫",   "type_id": "4"},
    {"type_name": "综艺",   "type_id": "5"},
    {"type_name": "奈飞新剧", "type_id": "48"},
]

# 二级分类（短剧/影视细分）。它们本身是独立分类路由 /show/{id}.html，
# 选定时即把当前分类 id 切到该二级 id，可再叠加 地区/年份/排序。
SUBCATS = {
    "1":  [("剧情片", "6"), ("动作片", "7"), ("冒险片", "8"), ("喜剧片", "9"),
           ("奇幻片", "10"), ("恐怖片", "11"), ("悬疑片", "16"), ("惊悚片", "17")],
    "2":  [("国产剧", "12"), ("港剧", "13"), ("韩剧", "14"), ("日剧", "15"),
           ("泰剧", "23"), ("台剧", "24"), ("欧美剧", "25"), ("新马剧", "26")],
    "3":  [("总裁短剧", "41"), ("神豪短剧", "42"), ("穿越重生短剧", "43"),
           ("都市短剧", "44"), ("年代短剧", "45"), ("长篇剧场", "46")],
    "4":  [("国产动漫", "36"), ("日本动漫", "37"), ("韩国动漫", "38"),
           ("欧美动漫", "39"), ("港台动漫", "40"), ("漫剧", "47")],
    "5":  [("国产综艺", "30"), ("港台综艺", "31"), ("韩国综艺", "32"),
           ("日本综艺", "33"), ("欧美综艺", "35")],
    "48": [("奈飞电影", "49"), ("奈飞自制剧", "50")],
}

# 站点全分类统一筛选值（实测 电影1/电视剧2/短剧3/动漫4/综艺5/奈飞48 的
# 地区 / 年代下拉完全一致，因此全局复用一份即可）
AREAS = ["大陆", "欧美", "香港", "美国", "台湾", "日本", "韩国", "英国",
         "法国", "德国", "俄罗斯", "泰国", "印度", "加拿大", "西班牙",
         "意大利", "新加坡"]
YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
         "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"]
SORTS = [("按时间", "time"), ("按人气", "hits"), ("按评分", "score")]


def _options(pairs):
    return [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in pairs]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    flt = []
    # 类型：二级分类（选定后 id 切到二级子分类路由）
    if tid in SUBCATS:
        flt.append({"key": "sub", "name": "类型", "value": _options(SUBCATS[tid])})
    # 地区
    flt.append({"key": "area", "name": "地区",
                "value": _options([(a, a) for a in AREAS])})
    # 年份
    flt.append({"key": "year", "name": "年份",
                "value": _options([(y, y) for y in YEARS])})
    # 排序
    flt.append({"key": "by", "name": "排序",
                "value": _options(SORTS)})
    FILTERS[tid] = flt


# 搜索路由候选（实测该站 /search.html?wd= 已失效，这里按序尝试并做关键词命中校验）
SEARCH_TPLS = [
    "/search.html?wd=%s",
    "/vod/search/wd/%s.html",
]


# ============================================================
# Spider 主类
# ============================================================

class Spider(Spider):

    def getName(self):
        return "第九短剧网"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""
        self.header = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }
        self._home_cache = []
        self._home_cache_time = 0
        self._home_lock = threading.Lock()
        self._pg_cache = {}
        self._search_tpl = None

    # ===== 网络层 =====
    def _rsp_text(self, rsp):
        try:
            raw = rsp.content
            if raw:
                for enc in ("utf-8", "gb18030"):
                    try:
                        return raw.decode(enc)
                    except Exception:
                        continue
                return raw.decode("utf-8", "ignore")
        except Exception:
            pass
        try:
            return rsp.text or ""
        except Exception:
            return ""

    def _fetch_text(self, url, timeout=(2.5, 4.5), retries=1):
        for i in range(retries + 1):
            try:
                rsp = self.fetch(url, headers=self.header, timeout=timeout)
                text = self._rsp_text(rsp)
                if text and len(text) > 100:
                    return text
            except Exception:
                pass
            if i < retries:
                time.sleep(0.2)
        return ""

    def _match(self, pattern, text, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1) if m else ""

    def _strip_tags(self, s):
        return re.sub(r'<[^>]+>', '', s or '').strip()

    # ===== 卡片解析（vfed 模板，实测结构） =====
    def _parse_cards(self, html):
        cards = []
        seen = set()
        for m in re.finditer(
                r'<li class="fed-list-item[^"]*"[^>]*>(.*?)</li>\s*(?=<li|</ul>)',
                html, re.S):
            block = m.group(1)
            vid = self._match(r'/detail/(\d+)\.html', block)
            if not vid or vid in seen:
                continue
            pic = self._match(r'data-original="([^"]+)"', block)
            if pic and pic.startswith('//'):
                pic = "https:" + pic
            title = self._strip_tags(self._match(
                r'<a class="fed-list-title[^"]*"[^>]*>(.*?)</a>', block, re.S))
            if not title:
                continue
            status = self._strip_tags(self._match(
                r'<span class="fed-list-remarks[^"]*"[^>]*>(.*?)</span>', block, re.S))
            seen.add(vid)
            cards.append({
                "vod_id": vid,
                "vod_name": title[:60],
                "vod_pic": pic or "",
                "vod_remarks": status or "HD",
            })
        return cards

    # ===== 详情/播放 =====
    def _is_direct_media(self, url):
        url = (url or "").lower()
        return any(x in url for x in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".mpd"))

    def _line_names(self, html):
        names = {}
        for m in re.finditer(r'data-target="#playsx(\d+)"[^>]*>(.*?)</a>', html, re.S):
            names[int(m.group(1))] = self._strip_tags(m.group(2))[:10]
        if names:
            return names
        idx = 0
        for m in re.finditer(r'data-target="#[^"]*?(\d+)"[^>]*>(.*?)</a>', html, re.S):
            t = self._strip_tags(m.group(2))
            if t and len(t) <= 12 and not t.startswith(("上一", "下一")):
                names[int(m.group(1))] = t[:10]
        if names:
            return names
        idx = 0
        tab = self._match(r'class="[^"]*play[^"]*tab[^"]*"[^>]*>(.*?)</ul>', html, re.S)
        if tab:
            for m in re.finditer(r'<a[^>]*>(.*?)</a>', tab, re.S):
                t = self._strip_tags(m.group(1))
                if t and t not in ("收起", "展开") and len(t) <= 12:
                    idx += 1
                    names[idx] = t[:10]
        return names

    # ===== 【新增】解析详情页中的元数据项（导演、演员、类型、地区、年份等） =====
    def _parse_meta_items(self, html):
        """
        从 vfed 详情页解析各类元数据。
        返回 dict，包含 director, actor, type_name, area, year, language, update_time 等。
        """
        result = {
            "director": "",
            "actor": "",
            "type_name": "",
            "area": "",
            "year": "",
            "language": "",
            "update_time": "",
            "vod_content": "",
        }
        # 常见 vfed 元数据容器：class="fed-part-info" 或 class="fed-deta-info"
        # 也可能在 class="fed-deta-content" 中
        meta_block = self._match(
            r'<div\s+class="[^"]*fed-part-info[^"]*"[^>]*>(.*?)</div>\s*(?=<div|</div>)',
            html, re.S)
        if not meta_block:
            meta_block = self._match(
                r'<div\s+class="[^"]*fed-deta-info[^"]*"[^>]*>(.*?)</div>\s*(?=<div|</div>)',
                html, re.S)
        if not meta_block:
            # 更宽松的匹配：找包含 "导演" 或 "主演" 的 dl/dt/dd 结构
            meta_block = self._match(
                r'(<dl\s+class="[^"]*fed-deta-info[^"]*"[^>]*>.*?</dl>)',
                html, re.S)
        if not meta_block:
            # 再尝试匹配简化的 li 结构
            meta_block = self._match(
                r'<ul\s+class="[^"]*fed-part-info[^"]*"[^>]*>(.*?)</ul>',
                html, re.S)

        if meta_block:
            # 尝试多种模式提取
            # 导演
            director = self._match(
                r'导演[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not director:
                director = self._match(
                    r'导演[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if not director:
                director = self._match(
                    r'<span[^>]*>导演[：:]</span>\s*<a[^>]*>(.*?)</a>', meta_block, re.S)
            if director:
                result["director"] = self._strip_tags(director).strip()

            # 演员/主演
            actor = self._match(
                r'主演[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not actor:
                actor = self._match(
                    r'主演[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if not actor:
                actor = self._match(
                    r'<span[^>]*>主演[：:]</span>\s*<a[^>]*>(.*?)</a>', meta_block, re.S)
            if actor:
                result["actor"] = self._strip_tags(actor).strip()

            # 类型
            type_name = self._match(
                r'类型[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not type_name:
                type_name = self._match(
                    r'类型[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if type_name:
                result["type_name"] = self._strip_tags(type_name).strip()

            # 地区
            area = self._match(
                r'地区[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not area:
                area = self._match(
                    r'地区[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if area:
                result["area"] = self._strip_tags(area).strip()

            # 年份
            year = self._match(
                r'年份[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not year:
                year = self._match(
                    r'年份[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if year:
                result["year"] = self._strip_tags(year).strip()

            # 语言
            language = self._match(
                r'语言[：:]\s*</span>\s*<[^>]+>(.*?)</a>', meta_block, re.S)
            if not language:
                language = self._match(
                    r'语言[：:]\s*</span>\s*<span[^>]*>(.*?)</span>', meta_block, re.S)
            if language:
                result["language"] = self._strip_tags(language).strip()

            # 更新日期（综艺/剧集常用）
            update_time = self._match(
                r'更新[：:]\s*</span>\s*<[^>]+>(.*?)</span>', meta_block, re.S)
            if not update_time:
                update_time = self._match(
                    r'更新日期[：:]\s*</span>\s*<[^>]+>(.*?)</span>', meta_block, re.S)
            if update_time:
                result["update_time"] = self._strip_tags(update_time).strip()

        # 如果元数据块没解析到，尝试直接从整个 HTML 中提取（备选）
        if not result["director"]:
            result["director"] = self._match(
                r'<span[^>]*>导演[：:]</span>\s*<a[^>]*>([^<]+)</a>', html, re.S)
            result["director"] = result["director"] or self._match(
                r'导演[：:]\s*([^<]+?)(?:<|$)', html, re.S)
        if not result["actor"]:
            result["actor"] = self._match(
                r'<span[^>]*>主演[：:]</span>\s*<a[^>]*>([^<]+)</a>', html, re.S)
            result["actor"] = result["actor"] or self._match(
                r'主演[：:]\s*([^<]+?)(?:<|$)', html, re.S)

        return result

    def _parse_detail_main(self, html, vid):
        """解析一个详情页的“主影片”字段，包含导演/演员等完整信息。"""
        title = self._strip_tags(self._match(r'<h1[^>]*>(.*?)</h1>', html, re.S))[:60]
        if not title:
            title = self._match(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            title = (title or "").strip()[:60]
        if not title:
            return None

        pic = self._match(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
        if not pic:
            pic = self._match(r'data-original="(https?://[^"]+)"', html)
        if pic and pic.startswith('//'):
            pic = "https:" + pic

        # 简介
        content = self._match(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html)
        if not content:
            # 尝试从 .fed-deta-content 中提取简介
            content = self._match(
                r'<div\s+class="[^"]*fed-deta-content[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if content:
                content = self._strip_tags(content)
            else:
                content = ""

        # 备注（状态）
        remarks = self._strip_tags(self._match(
            r'<span class="fed-list-remarks[^"]*"[^>]*>(.*?)</span>', html, re.S))[:20]

        # ===== 【新增】解析导演/演员等元数据 =====
        meta = self._parse_meta_items(html)

        # 构建完整返回
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic or "",
            "vod_remarks": remarks or "",
            "vod_content": (content or "")[:800],
            # ===== 新增字段 =====
            "vod_director": meta.get("director", ""),
            "vod_actor": meta.get("actor", ""),
            "vod_type": meta.get("type_name", ""),
            "vod_area": meta.get("area", ""),
            "vod_year": meta.get("year", ""),
            "vod_language": meta.get("language", ""),
            "vod_update_time": meta.get("update_time", ""),
        }

    # ============================================================
    # 首页
    # ============================================================

    def homeContent(self, filter):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        now = int(time.time())
        with self._home_lock:
            if self._home_cache and now - self._home_cache_time < 600:
                return {"list": list(self._home_cache)}

        result = {}
        def _worker(url):
            try:
                text = self._fetch_text(url, timeout=(2.5, 4.5), retries=0)
                if text:
                    result[url] = self._parse_cards(text)
            except Exception:
                pass

        targets = [HOST + "/"] + [HOST + "/show/%s.html" % c["type_id"]
                                  for c in CLASSES[:5]]
        threads = []
        for u in targets:
            t = threading.Thread(target=_worker, args=(u,))
            t.daemon = True
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=6)

        videos = []
        have = set()
        for u in targets:
            for card in result.get(u, []):
                if card["vod_id"] not in have:
                    videos.append(card)
                    have.add(card["vod_id"])

        if not videos:
            videos = [{"vod_id": "__diag__", "vod_name": "连接失败 点我看原因",
                       "vod_pic": "", "vod_remarks": "点进此卡片"}]

        with self._home_lock:
            self._home_cache = videos[:60]
            self._home_cache_time = int(time.time())
        return {"list": videos[:60]}

    # ============================================================
    # 分类列表（类型/地区/年份/排序 四维 + 翻页）
    # ============================================================

    def _base_list_url(self, tid, extend):
        """根据筛选条件构造不含分页的列表 URL（第1页）。"""
        ext = extend if isinstance(extend, dict) else {}
        if isinstance(extend, str):
            try:
                ext = json.loads(extend)
            except Exception:
                ext = {}
        base = tid
        sub = str(ext.get("sub", "") or "")
        if sub.isdigit():
            base = sub

        path = "/show/%s" % base
        segs = []
        for key, label in (("area", "area"), ("year", "year")):
            v = str(ext.get(key, "") or "").strip()
            if v:
                segs.append("%s/%s" % (label, quote(v)))
        by = str(ext.get("by", "") or "").strip().lower()
        if by in ("time", "hits", "score", "addtime"):
            if by == "addtime":
                by = "time"
            segs.append("by/%s" % by)
        if segs:
            path += "/" + "/".join(segs)
        path += ".html"
        return HOST + path

    def _total_pages(self, html):
        """从 vfed 页码区抽最大页数。"""
        best = 0
        seg = html
        i = html.find('fed-page')
        if i >= 0:
            seg = html[i:i + 4000]
        for m in re.finditer(r'href="[^"]*/(\d+)\.html"[^>]*>\s*(\d+)\s*</a>', seg):
            best = max(best, int(m.group(2)))
        mm = re.search(r'1/(\d+)', seg)
        if mm:
            best = max(best, int(mm.group(1)))
        return best

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1
            key = "%s|%s|%d" % (tid, extend, 1)
            base_url = self._base_list_url(str(tid), extend)

            if page <= 1:
                url = base_url
            else:
                url = base_url[: -len(".html")] + "/page/%d.html" % page

            html = self._fetch_text(url, timeout=(2.5, 4.5), retries=1)
            if not html or "/detail/" not in html:
                return {"page": page, "pagecount": page, "limit": 20,
                        "total": 0, "list": []}

            cards = self._parse_cards(html)
            total = self._total_pages(html)
            pagecount = max(total, page, 1)
            return {"list": cards, "page": page, "pagecount": pagecount,
                    "limit": 20, "total": pagecount * max(len(cards), 1)}
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ============================================================
    # 详情页
    # ============================================================

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vid = str(ids[0])

        if vid == "__diag__":
            return {"list": [{
                "vod_id": vid, "vod_name": "诊断信息", "vod_pic": "",
                "vod_content": "无法连接站点。请检查网络能否打开 https://www.gzsns.com/",
                "vod_play_from": "提示",
                "vod_play_url": "打开站点$https://www.gzsns.com/",
            }]}

        try:
            return self._detail(vid)
        except Exception:
            return {"list": []}

    def _detail(self, vid):
        url = HOST + "/detail/%s.html" % vid
        html = self._fetch_text(url, timeout=(2.5, 4.5), retries=1)
        if not html or len(html) < 500:
            return {"list": []}

        main = self._parse_detail_main(html, vid)
        if not main:
            return {"list": []}

        line_names = self._line_names(html)

        # ===== 播放选集：模式无关提取 =====
        EXCLUDE_PREFIX = ("/detail/", "/show/", "/t/", "/tags", "/ranking",
                          "/map", "/art/", "/label/", "javascript", "#")
        EP_TEXT = re.compile(
            r'^(第?\d{1,4}[集期话回部]?|HD.*|BD.*|TC.*|TS.*|DVD.*|正片.*|预告.*|全集.*|完结.*|上|下|'
            r'\d{1,4}[-—]\d{1,4}|更新至?.*|第.*?[集期])$')

        raw_eps = []
        for m in re.finditer(
                r'<a[^>]+href="((?:https?://[^/"]+)?/[^"<>]+)"[^>]*>(.*?)</a>', html, re.S):
            href, text = m.group(1), self._strip_tags(m.group(2))
            text = re.sub(r'\s+', ' ', text)
            if not text or len(text) > 25:
                continue
            path = href.replace(HOST, '') if href.startswith('http') else href
            if any(path.startswith(p) for p in EXCLUDE_PREFIX):
                continue
            if not (EP_TEXT.match(text) or re.search(r'第\d+', text)):
                continue
            if 'play' not in path and 'vod' not in path and '.html' not in path:
                continue
            raw_eps.append((path, text))

        groups = {}
        order = []
        for path, text in raw_eps:
            base = path.split('?')[0]
            base = re.sub(r'/[^/]+\.[a-zA-Z0-9]+$', '', base) or '/play'
            nums = re.findall(r'(\d+)', path)
            if len(nums) >= 3:
                key = base + '#' + nums[-2]
            else:
                key = base
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((path, text))

        def _ep_key(item):
            text, path = item[1], item[0]
            nums = re.findall(r'(\d{1,8})', text)
            if nums:
                n = int(nums[0])
                if n > 100000:
                    return int(str(n)[-4:])
                return n
            nums2 = re.findall(r'(\d+)', path)
            return int(nums2[-1]) if nums2 else 0

        name_list = [line_names[k] for k in sorted(line_names.keys())]
        play_from, play_url = [], []
        for gi, key in enumerate(order):
            eps = sorted(groups[key], key=_ep_key)
            if gi < len(name_list):
                name = name_list[gi]
            else:
                clean = key.split('#')[0].strip('/').split('/')[-1] or 'play'
                name = clean[:10]
            play_from.append(name)
            play_url.append("#".join(
                "%s$%s" % (t, HOST + p if p.startswith('/') else p) for p, t in eps))

        if not play_url:
            m = re.search(r'(https?://[^"\'<>\s\\]+?\.m3u8[^"\'<>\s\\]*)', html)
            if m:
                play_from, play_url = ["直链"], ["播放$" + m.group(1).replace("\\/", "/")]

        main["vod_play_from"] = "$$$".join(play_from) if play_from else "暂无"
        main["vod_play_url"] = "$$$".join(play_url) if play_url else "暂无$" + url
        return {"list": [main]}

    # ============================================================
    # 搜索（修复：不再把站点详情页的无关推荐当结果）
    # ============================================================

    def searchContent(self, key, quick, pg="1"):
        try:
            kw = quote(key)
            if self._search_tpl:
                return self._search_via(HOST + (self._search_tpl % kw), key)
            for tpl in SEARCH_TPLS:
                res = self._search_via(HOST + (tpl % kw), key)
                if res["list"]:
                    self._search_tpl = tpl
                    return res
            res = self._search_via(HOST + "/search.html?wd=" + kw, key)
            return res
        except Exception:
            return {"list": []}

    def _search_via(self, url, key):
        """请求一个搜索 URL 并做“关键词命中校验”。"""
        try:
            html = self._fetch_text(url, timeout=(2.5, 4.5), retries=0)
            if not html:
                return {"list": []}
            if html.count('<li class="fed-list-item') >= 2:
                cards = self._parse_cards(html)
                if cards:
                    hit = [c for c in cards if self._title_hit(c["vod_name"], key)]
                    if hit:
                        return {"list": hit}
                    return {"list": []}
            if html.count('<li class="fed-list-item') < 2 or '/detail/' in html:
                vid = self._match(r'/detail/(\d+)\.html', html)
                main = self._parse_detail_main(html, vid or "0")
                if main and self._title_hit(main["vod_name"], key):
                    return {"list": [main]}
            return {"list": []}
        except Exception:
            return {"list": []}

    @staticmethod
    def _title_hit(title, key):
        if not title or not key:
            return False
        t = title.lower()
        k = key.lower()
        if k in t:
            return True
        for part in re.split(r'[\s,，]+', k):
            if part and len(part) >= 1 and part in t:
                return True
        return False

    # ============================================================
    # 播放
    # ============================================================

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "playUrl": "", "url": ""}
        url = str(id).replace("\\/", "/")
        if not url.startswith("http"):
            url = HOST + (url if url.startswith("/") else "/" + url)
        hdr = {"User-Agent": UA, "Referer": HOST + "/"}

        if self._is_direct_media(url):
            is_m3u8 = ".m3u8" in url.lower()
            fmt = "application/x-mpegURL" if is_m3u8 else ""
            return {"parse": 0, "playUrl": "", "url": url,
                    "header": hdr, "format": fmt, "contentType": fmt}

        low = url.lower()
        if any(k in low for k in ("mgtv.com", "youku.com", "iqiyi.com", "qiyi.com",
                                  "v.qq.com", "bilibili.com")):
            return {"parse": 1, "playUrl": "", "url": url, "header": hdr}

        html = self._fetch_text(url, timeout=(2, 3), retries=0)
        if html:
            pm = re.search(r'player_data\s*=\s*(\{.*?\})\s*;', html, re.S)
            if pm:
                try:
                    pdata = json.loads(pm.group(1))
                    pu = (pdata.get("url") or "").replace("\\/", "/")
                    if pu.startswith("http") and self._is_direct_media(pu):
                        return {"parse": 0, "playUrl": "", "url": pu, "header": hdr,
                                "format": "application/x-mpegURL",
                                "contentType": "application/x-mpegURL"}
                except Exception:
                    pass
            m = re.search(r'"url"\s*:\s*"((?:https?:)?\\\\?/\\\\?/[^"]+?\.m3u8[^"]*)"', html)
            if m:
                direct = m.group(1).replace("\\/", "/")
                if direct.startswith("//"):
                    direct = "https:" + direct
                if direct.startswith("http") and self._is_direct_media(direct):
                    return {"parse": 0, "playUrl": "", "url": direct, "header": hdr,
                            "format": "application/x-mpegURL",
                            "contentType": "application/x-mpegURL"}
            fm = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if fm:
                fsrc = fm.group(1).replace("&amp;", "&")
                if fsrc.startswith("//"):
                    fsrc = "https:" + fsrc
                elif fsrc.startswith("/"):
                    fsrc = HOST + fsrc
                elif not fsrc.startswith("http"):
                    fsrc = self._extract_origin(url) + fsrc
                fhtml = self._fetch_text(fsrc, timeout=(2, 3), retries=0)
                if fhtml:
                    m = re.search(r'(https?://[^"\'<>\s\\]+?\.m3u8[^"\'<>\s\\]*)', fhtml)
                    if not m:
                        m = re.search(r'"url"\s*:\s*"((?:https?:)?\\?/\\?/[^"]+?\.m3u8[^"]*)"', fhtml)
                    if m:
                        direct = m.group(1).replace("\\/", "/")
                        if direct.startswith("//"):
                            direct = "https:" + direct
                        if direct.startswith("http") and self._is_direct_media(direct):
                            return {"parse": 0, "playUrl": "", "url": direct, "header": hdr,
                                    "format": "application/x-mpegURL",
                                    "contentType": "application/x-mpegURL"}
                    pm2 = re.search(r'player_data\s*=\s*(\{.*?\})\s*;', fhtml, re.S)
                    if pm2:
                        try:
                            pdata = json.loads(pm2.group(1))
                            pu = (pdata.get("url") or "").replace("\\/", "/")
                            if pu.startswith("http") and self._is_direct_media(pu):
                                return {"parse": 0, "playUrl": "", "url": pu, "header": hdr,
                                        "format": "application/x-mpegURL",
                                        "contentType": "application/x-mpegURL"}
                        except Exception:
                            pass
            m = re.search(r'(https?://[^"\'<>\s\\]+?\.m3u8[^"\'<>\s\\]*)', html)
            if m:
                direct = m.group(1).replace("\\/", "/")
                return {"parse": 0, "playUrl": "", "url": direct, "header": hdr,
                        "format": "application/x-mpegURL",
                        "contentType": "application/x-mpegURL"}

        return {"parse": 1, "playUrl": "", "url": url, "header": hdr}

    def _extract_origin(self, url):
        try:
            m = re.match(r'(https?://[^/]+)', url)
            return m.group(1) if m else HOST
        except Exception:
            return HOST

    def localProxy(self, param):
        return [200, "video/MP2T", b"", ""]

    def destroy(self):
        pass

    def close(self):
        pass
