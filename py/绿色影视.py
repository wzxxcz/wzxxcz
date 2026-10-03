from base.spider import Spider
import re
import json
import base64
import gzip
from urllib.parse import quote, unquote
import urllib.request

HOST = "https://www.lvsc168.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CATS = [
{"type_id": "1", "type_name": "电影"},
{"type_id": "2", "type_name": "电视剧"},
{"type_id": "3", "type_name": "综艺"},
{"type_id": "4", "type_name": "动漫"},
{"type_id": "26", "type_name": "短剧"},
{"type_id": "5", "type_name": "动作片"},
{"type_id": "6", "type_name": "爱情片"},
{"type_id": "7", "type_name": "科幻片"},
{"type_id": "8", "type_name": "恐怖片"},
{"type_id": "9", "type_name": "战争片"},
{"type_id": "10", "type_name": "喜剧片"},
{"type_id": "11", "type_name": "纪录片"},
{"type_id": "12", "type_name": "剧情片"},
{"type_id": "13", "type_name": "大陆剧"},
{"type_id": "14", "type_name": "港台剧"},
{"type_id": "15", "type_name": "欧美剧"},
{"type_id": "16", "type_name": "日韩剧"},
{"type_id": "27", "type_name": "泰剧"},
]

def _mk_filters():
    areas = [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in ["大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "英国", "法国"]]
    years = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
    yuyans = [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in ["国语", "粤语", "英语", "韩语", "日语", "泰语"]]
    orders = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hit"}, {"n": "推荐", "v": "commend"}]
    flt = [{"key": "area", "name": "地区", "value": areas}, {"key": "year", "name": "年份", "value": years}, {"key": "yuyan", "name": "语言", "value": yuyans}, {"key": "order", "name": "排序", "value": orders}]
    return {c["type_id"]: flt for c in CATS}

class Spider(Spider):
    def init(self, extend=""):
        pass

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": HOST + "/"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
        return raw.decode("utf-8", "replace")

    def _parse_cards(self, html):
        vids = []
        seen = set()
        pb = self.getProxyUrl(local=True)
        for m in re.finditer(r'<a\s[^>]*?class="[^"]*myui-vodlist__thumb[^"]*"[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'href="(/movie/(\d+)\.html)"', tag)
            tm = re.search(r'title="([^"]*)"', tag)
            if not hm or not tm:
                continue
            url, vid, title = hm.group(1), hm.group(2), tm.group(1).strip()
            if vid in seen or not title:
                continue
            seen.add(vid)
            pic = ""
            dm = re.search(r'data-original="([^"]+)"', tag)
            if dm:
                pic = dm.group(1)
            else:
                sm = re.search(r'style="[^"]*url\(([^)]+)\)', tag)
                if sm:
                    pic = sm.group(1).strip('\'"').replace("&quot;", "")
            if pic.startswith("/img.php?url="):
                pic = unquote(pic.split("url=", 1)[1])
            if pic.startswith("/"):
                pic = HOST + pic
            if pic:
                pic = pb + "&m=img&u=" + base64.b64encode(pic.encode()).decode()
            rm = re.search(r'href="/movie/' + vid + r'\.html".*?<span class="pic-text[^"]*">\s*([^<]*?)\s*</span>', html, re.S)
            remark = rm.group(1).strip() if rm else ""
            vids.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
        return vids

    def _pagecount(self, html):
        pages = re.findall(r"/frim/\d+-(\d+)\.html", html)
        return max([int(p) for p in pages]) if pages else 1

    def homeContent(self, filter=False):
        return {"class": CATS, "filters": _mk_filters() if filter else {}}

    def homeVideoContent(self):
        return self.categoryContent("1", 1, True, {})

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        area = extend.get("area", "") if extend else ""
        year = extend.get("year", "") if extend else ""
        yuyan = extend.get("yuyan", "") if extend else ""
        order = extend.get("order", "time") if extend else ""
        if area or year or yuyan or order != "time":
            url = f"{HOST}/search.php?searchtype=5&tid={tid}&area={quote(area)}&year={year}&yuyan={quote(yuyan)}&order={order}&page={pg}"
        else:
            url = f"{HOST}/frim/{tid}.html" if pg == 1 else f"{HOST}/frim/{tid}-{pg}.html"
        html = self._fetch(url)
        vids = self._parse_cards(html)
        return {"list": vids, "page": pg, "pagecount": self._pagecount(html), "limit": 20, "total": 999999}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        html = self._fetch(f"{HOST}/movie/{vid}.html")
        tm = re.search(r'<h1 class="title[^"]*">([^<]+)', html)
        title = tm.group(1).strip() if tm else vid
        pm = re.search(r'data-original="(/img\.php\?url=[^"]+)"', html)
        if not pm:
            pm = re.search(r'<img class="lazyload" src="(/img\.php\?url=[^"]+)"', html)
        pic = ""
        if pm:
            pic = unquote(pm.group(1).split("url=", 1)[1])
        if pic.startswith("/"):
            pic = HOST + pic
        if pic:
            pic = self.getProxyUrl(local=True) + "&m=img&u=" + base64.b64encode(pic.encode()).decode()
        actor = ""
        am = re.search(r'主演[：:]\s*([^<]+)', html)
        if am:
            actor = am.group(1).strip()
        year = ""
        ym = re.search(r'年份[：:]\s*([^<]+)', html)
        if ym:
            year = ym.group(1).strip()
        desc = ""
        dm = re.search(r'简介[：:]\s*([^<]{10,500})', html)
        if dm:
            desc = dm.group(1).strip()
        plays = {}
        for pm in re.finditer(r'<div id="playlist(\d+)"[^>]*>.*?<p class="text-muted[^"]*">\s*([^<]+?)\s*</p>.*?<ul class="myui-content__list[^"]*"[^>]*>(.*?)</ul>', html, re.S):
            src_name = pm.group(2).strip()
            fidx = str(int(pm.group(1)) - 1)
            eps = []
            for em in re.finditer(r'<a\s[^>]*?href="(/play/\d+-\d+-\d+\.html)"[^>]*?>([^<]*)</a>', pm.group(3)):
                tag, ep_text = em.group(0), em.group(2).strip()
                tm = re.search(r'title="([^"]*)"', tag)
                ep_name = (tm.group(1).strip() if tm and tm.group(1).strip() else ep_text) or f"第{len(eps) + 1}集"
                eps.append(f"{ep_name}${HOST}{em.group(1)}")
            if eps:
                plays[fidx] = (src_name, eps)
        if not plays:
            for em in re.finditer(r'<a\s[^>]*?href="(/play/(\d+)-(\d+)-(\d+)\.html)"[^>]*?>([^<]*)</a>', html):
                tag, ep_url, fidx, pidx, ep_text = em.group(0), em.group(1), em.group(3), em.group(4), em.group(5).strip()
                tm = re.search(r'title="([^"]*)"', tag)
                ep_name = (tm.group(1).strip() if tm and tm.group(1).strip() else ep_text) or f"第{int(pidx) + 1}集"
                if fidx not in plays:
                    plays[fidx] = (f"线路{int(fidx) + 1}", [])
                plays[fidx][1].append(f"{ep_name}${HOST}{ep_url}")
        play_from = []
        play_urls = []
        for fidx in sorted(plays.keys(), key=int):
            play_from.append(plays[fidx][0])
            play_urls.append("#".join(plays[fidx][1]))
        vod = {"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_actor": actor, "vod_year": year, "vod_content": desc, "vod_play_from": "$$$".join(play_from), "vod_play_url": "$$$".join(play_urls)}
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        html = self._fetch(f"{HOST}/search.php?searchword={quote(key)}")
        vids = self._parse_cards(html)
        return {"list": vids}

    def playerContent(self, flag, ids, vipFlags=None):
        play_url = ids[0] if isinstance(ids, list) else ids
        html = self._fetch(play_url)
        m = re.search(r'var now=base64decode\("([A-Za-z0-9+/=]+)"\)', html)
        if not m:
            return {"parse": 0, "url": play_url, "header": {"User-Agent": UA}}
        parser_url = base64.b64decode(m.group(1)).decode("utf-8", "replace").strip()
        try:
            ph = self._fetch(parser_url)
        except Exception:
            return {"parse": 1, "url": parser_url, "header": {"User-Agent": UA}}
        mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', ph)
        if not mm:
            mm = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', ph)
        if mm:
            return {"parse": 0, "url": mm.group(1), "header": {"User-Agent": UA, "Referer": parser_url}}
        return {"parse": 1, "url": parser_url, "header": {"User-Agent": UA}}

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = {}
        if param.get("m") == "img":
            try:
                url = base64.b64decode(param.get("u", "")).decode()
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": HOST + "/"})
                data = urllib.request.urlopen(req, timeout=15).read()
                mime = "image/jpeg"
                lu = url.lower()
                if ".webp" in lu:
                    mime = "image/webp"
                elif ".png" in lu:
                    mime = "image/png"
                elif ".gif" in lu:
                    mime = "image/gif"
                return [200, mime, data]
            except Exception:
                return [404, "text/plain", b""]
        return [200, "text/plain", b""]
