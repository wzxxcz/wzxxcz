# -*- coding: utf-8 -*-
# 奇优影院 https://www.qivod.com/  TVBox 蜘蛛
# 架构: MacCMS + stui 模板, 伪静态 URL
# 分类 /vod-type-id-{id}-pg-{pg}.html
# 筛选 /vod-list-id-{id}-pg-{pg}-order--by--class--year-{year}-letter--area-{area}-lang-.html
# 详情 /vod-detail-id-{id}.html
# 播放 /vod-play-id-{id}-src-{src}-num-{num}.html
#   播放数据在 <script>var mac_flag='play',...mac_url<随机>=unescape('%uXXXX...') 中
#   $$$ 分播放源, # 分集, $ 分集名与地址, 与 mac_from 顺序一一对应
# 搜索 GET /index.php?m=vod-search&wd=关键词, 翻页 /vod-search-pg-{pg}-wd-{关键词}.html
import re
import urllib.parse
import requests

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.qivod.com"
        self.name = "奇优影院"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.qivod.com/",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._seen = set()

    def init(self, extend=""):
        if extend and isinstance(extend, str) and extend.startswith("{"):
            try:
                import json
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("url") or self.host).rstrip("/")
            except Exception:
                pass

    def getName(self):
        return self.name

    def _get(self, url, **kw):
        r = self.session.get(url, timeout=20, **kw)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self.host + (u if u.startswith("/") else "/" + u)

    def _reset_seen(self):
        self._seen = set()

    def _dedup(self, items):
        out = []
        for v in items:
            vid = (v or {}).get("vod_id") or ""
            if not vid or vid in self._seen:
                continue
            self._seen.add(vid)
            out.append(v)
        return out

    def _parse_list(self, html):
        items = []
        for m in re.finditer(r'href="(/vod-detail-id-(\d+)\.html)"[^>]*?title="([^"]+)"[^>]*?data-original="([^"]+)"', html):
            href, vid, title, pic = m.group(1), m.group(2), m.group(3), m.group(4)
            tail = html[m.end():m.end() + 500]
            rm = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', tail)
            remark = rm.group(1).strip() if rm else ""
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": remark,
            })
        return self._dedup(items)

    def _pagecount(self, html, pg, per_page=48):
        m = re.search(r'href="[^"]*?-pg-(\d+)[^"]*?"[^>]*>(尾页|末页)</a>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        n = len(re.findall(r'/vod-detail-id-\d+\.html', html)) // 2
        if n < per_page:
            return pg
        return 9999

    def _filter_options(self, html, label):
        opts = [{"n": "全部", "v": ""}]
        seen = {""}
        for bm in re.finditer(r'class="stui-screen__list[^"]*"', html):
            seg = html[bm.start():bm.start() + 4000]
            lm = re.search(r'<span class="text-muted">([^<]*)</span>', seg)
            if not lm or label not in lm.group(1):
                continue
            for am in re.finditer(r"<a href='[^']*'[^>]*>([^<]{1,14})</a>", seg):
                name = am.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    opts.append({"n": name, "v": name})
            break
        return opts

    def homeContent(self, filter):
        self._reset_seen()
        try:
            html = self._get(self.host + "/")
        except Exception:
            html = ""
        classes = []
        seen_c = set()
        want = ["电影", "连续剧", "综艺", "动漫"]
        for m in re.finditer(r'<a[^>]*href="(/vod-type-id-(\d+)-pg-1\.html)"[^>]*>([^<]+)</a>', html):
            tid, name = m.group(2), m.group(3).strip()
            if tid in seen_c or name not in want:
                continue
            seen_c.add(tid)
            classes.append({"type_id": tid, "type_name": name})
        classes.sort(key=lambda c: want.index(c["type_name"]))
        result = {"class": classes}
        if filter:
            try:
                fhtml = self._get(self.host + "/vod-type-id-1-pg-1.html")
            except Exception:
                fhtml = ""
            result["filters"] = {
                "1": [
                    {"key": "area", "name": "地区", "value": self._filter_options(fhtml, "按地区")},
                    {"key": "year", "name": "年份", "value": self._filter_options(fhtml, "按年份")},
                ]
            }
            for c in classes:
                if c["type_id"] != "1":
                    result["filters"][c["type_id"]] = result["filters"]["1"]
        return result

    def homeVideoContent(self):
        self._reset_seen()
        try:
            html = self._get(self.host + "/")
        except Exception:
            return {"list": []}
        return {"list": self._parse_list(html)}

    def _extend_dict(self, extend):
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str) and extend.strip().startswith("{"):
            try:
                import json
                d = json.loads(extend)
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        self._reset_seen()
        pg = int(pg) if str(pg).isdigit() else 1
        ext = self._extend_dict(extend)
        area = (ext.get("area") or "").strip()
        year = (ext.get("year") or "").strip()
        if area or year:
            url = "%s/vod-list-id-%s-pg-%d-order--by--class--year-%s-letter--area-%s-lang-.html" % (
                self.host, tid, pg,
                urllib.parse.quote(year), urllib.parse.quote(area))
        else:
            url = "%s/vod-type-id-%s-pg-%d.html" % (self.host, tid, pg)
        try:
            html = self._get(url)
        except Exception:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 48, "total": 0}
        items = self._parse_list(html)
        return {"list": items, "page": pg, "pagecount": self._pagecount(html, pg), "limit": 48, "total": 99999}

    def detailContent(self, ids):
        vid = str(ids[0])
        try:
            html = self._get(self.host + "/vod-detail-id-%s.html" % vid)
        except Exception:
            return {"list": []}
        vod = {"vod_id": vid}
        m = re.search(r'<h3 class="title">([^<]+)</h3>', html)
        vod["vod_name"] = m.group(1).strip() if m else ""
        m = re.search(r'<a class="stui-vodlist__thumb[^"]*"[^>]*data-original="([^"]+)"', html)
        vod["vod_pic"] = m.group(1).strip() if m else ""
        m = re.search(r'主演：</span>(.*?)</p>', html, re.S)
        if m:
            vod["vod_actor"] = ", ".join(re.findall(r'>([^<>]+)</a>', m.group(1))).strip(", ")
        m = re.search(r'导演：</span>(.*?)</p>', html, re.S)
        if m:
            vod["vod_director"] = ", ".join(re.findall(r'>([^<>]+)</a>', m.group(1))).strip(", ")
        m = re.search(r'类型：</span><a[^>]*>([^<]+)</a>', html)
        vod["vod_type"] = m.group(1).strip() if m else ""
        m = re.search(r'地区：</span><a[^>]*>([^<]+)</a>', html)
        vod["vod_area"] = m.group(1).strip() if m else ""
        m = re.search(r'年份：</span>([^<&\s]+)', html)
        vod["vod_year"] = m.group(1).strip() if m else ""
        m = re.search(r'<span class="detail-content"[^>]*>(.*?)</span>', html, re.S)
        if m:
            desc = re.sub(r'<[^>]+>', "", m.group(1))
            vod["vod_content"] = re.sub(r'\s+', " ", desc).strip()
        else:
            m = re.search(r'<span class="detail-sketch">([^<]*)</span>', html)
            vod["vod_content"] = m.group(1).strip() if m else ""
        m = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', html[:html.find("stui-content__detail") if "stui-content__detail" in html else 4000])
        vod["vod_remarks"] = m.group(1).strip() if m else ""
        play_from, play_url = [], []
        for pm in re.finditer(r'<h3 class="title"><img src="/statics/icon/icon_\d+\.png"/>([^<]+)</h3>.*?<ul class="stui-content__playlist[^"]*">(.*?)</ul>', html, re.S):
            sname, ul = pm.group(1).strip(), pm.group(2)
            if sname in ("猜你喜欢",):
                continue
            eps = []
            for em in re.finditer(r"title='([^']+)'\s+href='(/vod-play-id-\d+-src-\d+-num-\d+\.html)'", ul):
                eps.append("%s$%s" % (em.group(1).strip(), em.group(2)))
            if eps:
                play_from.append(sname)
                play_url.append("#".join(eps))
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url)
        return {"list": [vod]}

    def _unescape_mac(self, s):
        def rep(x):
            if x.group(1):
                return chr(int(x.group(1), 16))
            return chr(int(x.group(2), 16))
        return re.sub(r'%u([0-9a-fA-F]{4})|%([0-9a-fA-F]{2})', rep, s)

    def playerContent(self, flag, id, vipFlags):
        m = re.search(r'vod-play-id-(\d+)-src-(\d+)-num-(\d+)', str(id))
        if not m:
            return {"parse": 0, "playUrl": "", "url": str(id)}
        vid, src, num = m.group(1), int(m.group(2)), int(m.group(3))
        try:
            html = self._get("%s/vod-play-id-%s-src-%d-num-%d.html" % (self.host, vid, src, num))
        except Exception:
            return {"parse": 0, "playUrl": "", "url": str(id)}
        fm = re.search(r"mac_flag='play'", html)
        dm = re.search(r"mac_url\w*\s*=\s*unescape\((['\"])(.*?)\1\)", html, re.S)
        if not fm or not dm:
            return {"parse": 0, "playUrl": "", "url": str(id)}
        data = self._unescape_mac(dm.group(2))
        groups = data.split("$$$")
        url = ""
        try:
            grp = groups[src - 1] if 0 <= src - 1 < len(groups) else ""
            eps = [e for e in grp.split("#") if e]
            if 0 <= num - 1 < len(eps):
                url = eps[num - 1].split("$", 1)[-1].strip()
            elif eps:
                url = eps[0].split("$", 1)[-1].strip()
        except Exception:
            url = ""
        if not url:
            return {"parse": 0, "playUrl": "", "url": str(id)}
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    def searchContent(self, key, quick, pg="1"):
        self._reset_seen()
        pg = int(pg) if str(pg).isdigit() else 1
        qk = urllib.parse.quote(key)
        if pg == 1:
            url = "%s/index.php?m=vod-search&wd=%s" % (self.host, qk)
        else:
            url = "%s/vod-search-pg-%d-wd-%s.html" % (self.host, pg, qk)
        try:
            html = self._get(url)
        except Exception:
            return {"list": []}
        items = self._parse_list(html)
        return {"list": items, "page": pg, "pagecount": self._pagecount(html, pg), "limit": 48, "total": 99999}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/mpeg", None, ""]
