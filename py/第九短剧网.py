# -*- coding: utf-8 -*-
"""
第九短剧网 (www.gzsns.com) Python Spider — 兼容 FongMi/TV (T3) 与 WebHomeTV/PeekPro (T4)
【定制版 v11-fix】苹果CMS10 + vfed模板 — 修复多主演/导演解析、新增vod_state状态字段
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
    {"type_name": "电影", "type_id": "1"},
    {"type_name": "电视剧", "type_id": "2"},
    {"type_name": "短剧", "type_id": "3"},
    {"type_name": "动漫", "type_id": "4"},
    {"type_name": "综艺", "type_id": "5"},
    {"type_name": "奈飞新剧", "type_id": "48"},
]

SUBCATS = {
    "1": [("剧情片", "6"), ("动作片", "7"), ("冒险片", "8"), ("喜剧片", "9"),
          ("奇幻片", "10"), ("恐怖片", "11"), ("悬疑片", "16"), ("惊悚片", "17")],
    "2": [("国产剧", "12"), ("港剧", "13"), ("韩剧", "14"), ("日剧", "15"),
          ("泰剧", "23"), ("台剧", "24"), ("欧美剧", "25"), ("新马剧", "26")],
    "3": [("总裁短剧", "41"), ("神豪短剧", "42"), ("穿越重生短剧", "43"),
          ("都市短剧", "44"), ("年代短剧", "45"), ("长篇剧场", "46")],
    "4": [("国产动漫", "36"), ("日本动漫", "37"), ("韩国动漫", "38"),
          ("欧美动漫", "39"), ("港台动漫", "40"), ("漫改", "47")],
    "5": [("国产综艺", "30"), ("港台综艺", "31"), ("韩国综艺", "32"),
          ("日本综艺", "33"), ("欧美综艺", "35")],
    "48": [("奈飞电影", "49"), ("奈飞剧集", "50")],
}

AREAS = ["大陆", "欧美", "香港", "美国", "台湾", "日本", "韩国", "英国",
         "法国", "德国", "俄罗斯", "泰国", "印度", "加拿大", "西班牙",
         "意大利", "新加坡"]
YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
         "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"]
SORTS = [("按时间", "time"), ("按人气", "hits"), ("按评分", "score")]


def _make_opt(pairs):
    return [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in pairs]


FILTERS = {}
for cls in CLASSES:
    tid = cls["type_id"]
    fl = []
    if tid in SUBCATS:
        fl.append({"key": "sub", "name": "子类", "value": _make_opt(SUBCATS[tid])})
    fl.append({"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in AREAS]})
    fl.append({"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in YEARS]})
    fl.append({"key": "by", "name": "排序", "value": _make_opt(SORTS)})
    FILTERS[tid] = fl

SEARCH_TPLS = [
    "/search.php?wd=%s",
    "/vod/search/wd/%s.html",
]


# ============================================================
# Spider实现
# ============================================================
class Spider(Spider):
    def getName(self):
        return "第九短剧网"

    def init(self, extend=""):
        if isinstance(extend, list):
            self.extend = ""
        else:
            self.extend = extend or ""
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate"
        }
        self._home_cache = []
        self._home_cache_ts = 0
        self._lock = threading.Lock()
        self._search_tpl = None

    def _rsp_text(self, rsp):
        try:
            raw = rsp.content
            for enc in ("utf-8", "gbk", "gb2312"):
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return rsp.text or ""

    def _fetch_text(self, url, timeout=(2.5, 4.5), retries=1):
        for _ in range(retries + 1):
            try:
                rsp = self.fetch(url, headers=self.headers, timeout=timeout)
                txt = self._rsp_text(rsp)
                if txt and len(txt) > 100:
                    return txt
            except Exception:
                pass
            time.sleep(0.2)
        return ""

    def _re_match(self, pat, text, flags=0):
        m = re.search(pat, text, flags)
        return m.group(1) if m else ""

    def _strip_tags(self, s):
        return re.sub(r"<[^>]+>", "", s or "").strip()

    def _parse_cards(self, html):
        cards = []
        seen = set()
        for m in re.finditer(r'<li class="fed-list-item[^"]*"[^>]*>(.*?)</li>(?=\s*<li|\s*</ul>)', html, re.S):
            blk = m.group(1)
            vid = self._re_match(r'/detail/(\d+)\.html', blk)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            pic = self._re_match(r'data-original="([^"]+)"', blk)
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            title = self._strip_tags(self._re_match(r'<a class="fed-list-title[^"]*"[^>]*>(.*?)</a>', blk, re.S))
            remark = self._strip_tags(self._re_match(r'<span class="fed-list-remarks[^"]*"[^>]*>(.*?)</span>', blk, re.S))
            cards.append({
                "vod_id": vid,
                "vod_name": title[:60],
                "vod_pic": pic or "",
                "vod_remarks": remark or "HD"
            })
        return cards

    def _is_direct_media(self, url):
        u = (url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".mpd"))

    def _parse_player_names(self, html):
        names = {}
        for m in re.finditer(r'data-target="#playsx(\d+)"[^>]*>(.*?)</a>', html, re.S):
            idx = int(m.group(1))
            nm = self._strip_tags(m.group(2))[:10]
            names[idx] = nm
        if names:
            return names
        idx = 0
        m_tab = re.search(r'class="[^"]*play[^"]*tab[^"]*"[^>]*>(.*?)</ul>', html, re.S)
        if m_tab:
            for ma in re.finditer(r'<a[^>]*>(.*?)</a>', m_tab.group(1), re.S):
                t = self._strip_tags(ma.group(1))
                if t and t not in ("收起", "展开") and len(t) <= 12:
                    idx += 1
                    names[idx] = t
        return names

    def _parse_meta_items(self, html):
        """从详情页解析元数据 - 增强版，支持多导演/多演员"""
        result = {
            "director": "",
            "actor": "",
            "type_name": "",
            "area": "",
            "year": "",
            "language": "",
            "update_time": "",
            "vod_state": "",
            "vod_content": "",
        }
        
        # 策略1: 尝试从 fed-part-info 或 fed-deta-info 中提取
        meta_blocks = []
        
        # 尝试多种可能的容器
        for pattern in [
            r'<div\s+class="[^"]*fed-part-info[^"]*"[^>]*>(.*?)</div>\s*(?=<div|</div>|$)',
            r'<div\s+class="[^"]*fed-deta-info[^"]*"[^>]*>(.*?)</div>\s*(?=<div|</div>|$)',
            r'<dl\s+class="[^"]*fed-deta-info[^"]*"[^>]*>(.*?)</dl>',
            r'<ul\s+class="[^"]*fed-part-info[^"]*"[^>]*>(.*?)</ul>',
            r'<div\s+class="[^"]*fed-deta-content[^"]*"[^>]*>(.*?)</div>',
        ]:
            block = self._re_match(pattern, html, re.S)
            if block:
                meta_blocks.append(block)
        
        # 合并所有找到的块
        meta_text = " ".join(meta_blocks)
        
        if meta_text:
            # 定义字段映射
            field_map = {
                "director": ["导演", "导演："],
                "actor": ["主演", "主演："],
                "type_name": ["类型", "类型："],
                "area": ["地区", "地区："],
                "year": ["年份", "年份："],
                "language": ["语言", "语言："],
                "update_time": ["更新", "更新日期", "更新：", "更新日期："],
                "vod_state": ["状态", "状态："],
            }
            
            for field, labels in field_map.items():
                for label in labels:
                    # 尝试多种模式
                    patterns = [
                        # 模式1: <span>标签</span>后面跟着内容
                        rf'<span[^>]*>{label}[：:]</span>\s*(.*?)(?=<span|</div>|</li>|$)',
                        # 模式2: 只有文本标签
                        rf'{label}[：:]\s*(.*?)(?=<span|<div|</li>|$)',
                    ]
                    
                    for pat in patterns:
                        m = re.search(pat, meta_text, re.S)
                        if m:
                            content = m.group(1).strip()
                            # 提取所有 <a> 标签中的内容
                            links = re.findall(r'<a[^>]*>(.*?)</a>', content, re.S)
                            if links:
                                values = [self._strip_tags(x).strip() for x in links if self._strip_tags(x).strip()]
                                if values:
                                    result[field] = "，".join(values)
                                    break
                            else:
                                # 没有链接，直接提取文本
                                clean = self._strip_tags(content)
                                if clean:
                                    result[field] = clean
                                    break
                    if result[field]:
                        break
        
        # 策略2: 如果上面没解析到，直接从整个 HTML 中兜底提取
        if not result["director"]:
            m = re.search(r'导演[：:]\s*([^<]+?)(?:<span|<div|</li>|$)', html, re.S)
            if m:
                result["director"] = self._strip_tags(m.group(1)).strip()
        
        if not result["actor"]:
            m = re.search(r'主演[：:]\s*([^<]+?)(?:<span|<div|</li>|$)', html, re.S)
            if m:
                result["actor"] = self._strip_tags(m.group(1)).strip()
        
        if not result["vod_state"]:
            m = re.search(r'状态[：:]\s*([^<]+?)(?:<span|<div|</li>|$)', html, re.S)
            if m:
                result["vod_state"] = self._strip_tags(m.group(1)).strip()
        
        return result

    def _parse_detail_main(self, html, vid):
        title = self._strip_tags(self._re_match(r'<h1[^>]*>(.*?)</h1>', html, re.S))[:60]
        if not title:
            title = self._re_match(r'<meta property="og:title" content="([^"]+)"', html)
        if not title:
            return None

        pic = self._re_match(r'<meta property="og:image" content="([^"]+)"', html)
        if pic and pic.startswith("//"):
            pic = "https:" + pic

        content = self._re_match(r'<meta name="description" content="([^"]+)"', html)
        if not content:
            m_con = re.search(r'<div\s+class="[^"]*fed-deta-content[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if m_con:
                content = self._strip_tags(m_con.group(1))
        content = content or ""

        remarks = self._strip_tags(self._re_match(r'<span class="fed-list-remarks[^"]*"[^>]*>(.*?)</span>', html, re.S))[:20]
        meta = self._parse_meta_items(html)

        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic or "",
            "vod_remarks": remarks or meta.get("vod_state", ""),
            "vod_content": content[:800],
            "vod_director": meta.get("director", ""),
            "vod_actor": meta.get("actor", ""),
            "vod_type": meta.get("type_name", ""),
            "vod_area": meta.get("area", ""),
            "vod_year": meta.get("year", ""),
            "vod_language": meta.get("language", ""),
            "vod_update_time": meta.get("update_time", ""),
            "vod_state": meta.get("vod_state", ""),
        }

    def _detail(self, vid):
        url = HOST + "/detail/" + vid + ".html"
        html = self._fetch_text(url)
        if not html or len(html) < 500:
            return {"list": []}
        main = self._parse_detail_main(html, vid)
        if not main:
            return {"list": []}
        name_map = self._parse_player_names(html)

        exclude_prefix = ("/detail/", "/show/", "/t/", "/tags", "/ranking", "/map", "/art/", "/label/", "javascript", "#")
        ep_pat = re.compile(r'^(第?\d{1,4}[集期话回部]?|HD.*|BD.*|TC.*|TS.*|DVD.*|正片.*|预告.*|全集.*|完结.*|上|下|\d{1,4}[-—]\d{1,4}|更新至.*)$')
        raw_eps = []
        for m in re.finditer(r'<a[^>]+href="((?:https?://[^/]+)?/[^"<>]+)"[^>]*>(.*?)</a>', html, re.S):
            href, txt = m.groups()
            txt = self._strip_tags(txt).replace("\n", "").strip()
            if not txt or len(txt) > 25:
                continue
            path = href.replace(HOST, "") if href.startswith("http") else href
            if any(path.startswith(p) for p in exclude_prefix):
                continue
            if not (ep_pat.match(txt) or re.search(r'第\d+', txt)):
                continue
            raw_eps.append((path, txt))

        groups = {}
        order = []
        for path, txt in raw_eps:
            base = path.split("?")[0]
            base = re.sub(r'/[^/]+\.[a-zA-Z0-9]+$', '', base) or "/play"
            nums = re.findall(r'(\d+)', path)
            if len(nums) >= 3:
                key = base + "#" + nums[-2]
            else:
                key = base
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((txt, path))

        def _ep_sort_key(item):
            t, p = item
            ns = re.findall(r'(\d+)', t)
            if ns:
                n = int(ns[0])
                if n > 100000:
                    n = int(str(n)[-4:])
                return n
            ns2 = re.findall(r'(\d+)', p)
            if ns2:
                return int(ns2[-1])
            return 0

        play_from = []
        play_url = []
        name_list = [name_map[k] for k in sorted(name_map.keys())]
        for idx, gkey in enumerate(order):
            eps = sorted(groups[gkey], key=_ep_sort_key)
            if idx < len(name_list):
                pname = name_list[idx]
            else:
                pname = gkey.strip("/").split("/")[-1] or "播放"
                pname = pname[:10]
            play_from.append(pname)
            seg = "#".join([f"{t}${HOST}{pa}" if pa.startswith("/") else f"{t}${pa}" for t, pa in eps])
            play_url.append(seg)

        if not play_url:
            m_m3u8 = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', html)
            if m_m3u8:
                play_from = ["直链"]
                play_url = ["播放$" + m_m3u8.group(1)]

        main["vod_play_from"] = "$$$".join(play_from) if play_from else "暂无"
        main["vod_play_url"] = "$$$".join(play_url) if play_url else "暂无$" + url
        return {"list": [main]}

    def homeContent(self, filter):
        now = time.time()
        with self._lock:
            if self._home_cache and (now - self._home_cache_ts) < 600:
                return {"class": CLASSES, "filters": FILTERS, "list": list(self._home_cache)}

        res = {}

        def worker(u):
            try:
                t = self._fetch_text(u, retries=0)
                if t:
                    res[u] = self._parse_cards(t)
            except Exception:
                pass

        threads = []
        home_url = HOST + "/"
        threads.append(threading.Thread(target=worker, args=(home_url,)))
        for cls in CLASSES[:5]:
            tu = HOST + "/show/" + cls["type_id"] + ".html"
            threads.append(threading.Thread(target=worker, args=(tu,)))
        for th in threads:
            th.daemon = True
            th.start()
        for th in threads:
            th.join(timeout=6.0)

        all_cards = []
        seen_id = set()
        for lst in res.values():
            for card in lst:
                if card["vod_id"] not in seen_id:
                    seen_id.add(card["vod_id"])
                    all_cards.append(card)

        with self._lock:
            self._home_cache = all_cards[:60]
            self._home_cache_ts = time.time()
        return {"class": CLASSES, "filters": FILTERS, "list": list(self._home_cache)}

    def categoryContent(self, tid, pg, filter, extend):
        ext = extend or filter
        try:
            ext_obj = json.loads(ext) if isinstance(ext, str) else ext
        except Exception:
            ext_obj = {}
        sub = ext_obj.get("sub", "")
        area = ext_obj.get("area", "")
        year = ext_obj.get("year", "")
        by = ext_obj.get("by", "")

        real_tid = sub if sub else tid
        
        # 构建基础URL
        url = HOST + "/show/" + str(real_tid) + ".html"
        
        # 处理分页
        if pg and int(pg) > 1:
            # 如果有筛选参数，需要先去掉 .html 再加 page
            if "?" in url:
                base_url = url.split("?")[0]
                qs = url.split("?")[1] if "?" in url else ""
                url = base_url[:-5] + "/page/" + str(pg) + ".html" + ("?" + qs if qs else "")
            else:
                url = url[:-5] + "/page/" + str(pg) + ".html"
        
        # 添加筛选参数
        qs = []
        if area:
            qs.append("area=" + quote(area))
        if year:
            qs.append("year=" + quote(year))
        if by:
            qs.append("by=" + quote(by))
        if qs:
            url = url + ("&" if "?" in url else "?") + "&".join(qs)

        html = self._fetch_text(url)
        if not html or "/detail/" not in html:
            return {"page": pg, "pagecount": 0, "limit": 20, "total": 0, "list": []}
        cards = self._parse_cards(html)
        page_cnt = 1
        m_pc = re.search(r'共(\d+)页', html)
        if m_pc:
            page_cnt = int(m_pc.group(1))
        return {
            "page": pg,
            "pagecount": page_cnt,
            "limit": 20,
            "total": page_cnt * 20,
            "list": cards
        }

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vid = str(ids[0])
        if vid == "__diag__":
            return {"list": [{
                "vod_id": "__diag__",
                "vod_name": "网络诊断",
                "vod_pic": "",
                "vod_content": "无法访问站点，请检查网络或代理，访问：" + HOST,
                "vod_play_from": "提示",
                "vod_play_url": "打开站点$" + HOST
            }]}
        try:
            return self._detail(vid)
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg=1):
        kw = quote(key)
        if self._search_tpl:
            url = HOST + (self._search_tpl % kw)
            html = self._fetch_text(url, retries=0)
            if html:
                return self._search_inner(html, key)
        for tpl in SEARCH_TPLS:
            url = HOST + (tpl % kw)
            html = self._fetch_text(url, retries=0)
            if not html:
                continue
            ret = self._search_inner(html, key)
            if ret["list"]:
                self._search_tpl = tpl
                return ret
        return {"page": 1, "pagecount": 0, "limit": 20, "total": 0, "list": []}

    def _search_inner(self, html, keyword):
        cards = self._parse_cards(html)
        hit = []
        kw_low = keyword.lower()
        for c in cards:
            if kw_low in c["vod_name"].lower():
                hit.append(c)
        if len(cards) < 2:
            m_vid = re.search(r'/detail/(\d+)\.html', html)
            if m_vid:
                vid = m_vid.group(1)
                d = self._detail(vid)
                if d and d.get("list"):
                    item = d["list"][0]
                    if kw_low in item["vod_name"].lower():
                        hit.append(item)
        return {"page": 1, "pagecount": 1, "limit": 20, "total": len(hit), "list": hit}

    def playerContent(self, flag, vid, vipFlags):
        url = str(vid).replace("\\/", "/")
        if not url:
            return {"parse": 0, "playUrl": "", "url": ""}
        if not url.startswith("http"):
            url = HOST + (url if url.startswith("/") else "/" + url)
        hdr = {"User-Agent": UA, "Referer": HOST + "/"}
        if self._is_direct_media(url):
            return {"parse": 0, "playUrl": "", "url": url, "header": hdr}

        html = self._fetch_text(url, timeout=(2, 3), retries=0)
        if html:
            pm = re.search(r'player_data\s*=\s*(\{.*?\})\s*;', html, re.S)
            if pm:
                try:
                    j = json.loads(pm.group(1))
                    pu = j.get("url", "").replace("\\/", "/")
                    if pu and self._is_direct_media(pu):
                        return {"parse": 0, "playUrl": "", "url": pu, "header": hdr}
                except Exception:
                    pass
            m_m3u8 = re.search(r'"url"\s*:\s*"((?:https?:)?\\?/\\?/[^"]+\.m3u8[^"]*)"', html)
            if m_m3u8:
                pu = m_m3u8.group(1).replace("\\/", "/")
                if pu.startswith("//"):
                    pu = "https:" + pu
                return {"parse": 0, "playUrl": "", "url": pu, "header": hdr}
            m_iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if m_iframe:
                iframe_src = m_iframe.group(1).replace("&amp;", "&")
                if iframe_src.startswith("//"):
                    iframe_src = "https:" + iframe_src
                elif not iframe_src.startswith("http"):
                    iframe_src = HOST + iframe_src
                iframe_html = self._fetch_text(iframe_src, timeout=(2, 3), retries=0)
                if iframe_html:
                    pm2 = re.search(r'player_data\s*=\s*(\{.*?\})\s*;', iframe_html, re.S)
                    if pm2:
                        try:
                            j2 = json.loads(pm2.group(1))
                            pu2 = j2.get("url", "").replace("\\/", "/")
                            if pu2 and self._is_direct_media(pu2):
                                return {"parse": 0, "playUrl": "", "url": pu2, "header": hdr}
                        except Exception:
                            pass
                    m3 = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', iframe_html)
                    if m3:
                        return {"parse": 0, "playUrl": "", "url": m3.group(1), "header": hdr}
        return {"parse": 1, "playUrl": "", "url": url, "header": hdr}

    def localProxy(self, param):
        return [200, "video/MP2T", b""]

    def destroy(self):
        pass
