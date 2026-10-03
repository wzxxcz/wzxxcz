# -*- coding: utf-8 -*-
# 小宝影院 https://www.xiaobaotv.com/ TVBox 蜘蛛
# 标准 MacCMS 站（mytheme 模板）：5 分类动态；列表 /vod/type/{id}[-{pg}].html；
# 二级筛选走 /vod/show/ 路由（id/class/area/year/lang/by 组合）；详情 /vod/detail/{id}.html；
# 播放 /vod/play/{id}-{sid}-{nid}.html，player_aaaa JSON 中 url 即 m3u8 直链
import re
import json
import base64
import requests
from urllib.parse import quote, unquote, parse_qs
import urllib.request
from base.spider import Spider


# ---------- 公共筛选数据 ----------
_COMMON_AREAS = [
    ("全部", ""), ("中国大陆", "中国大陆"), ("中国香港", "中国香港"),
    ("中国台湾", "中国台湾"), ("欧美", "欧美"), ("韩国", "韩国"),
    ("日本", "日本"), ("泰国", "泰国"), ("新加坡", "新加坡"),
    ("马来西亚", "马来西亚"), ("印度", "印度"), ("英国", "英国"),
    ("法国", "法国"), ("加拿大", "加拿大"), ("西班牙", "西班牙"),
    ("俄罗斯", "俄罗斯"), ("其它", "其它"),
]

_COMMON_YEARS = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 1999, -1)]

_COMMON_LANGS = [
    ("全部", ""), ("汉语普通话", "汉语普通话"), ("英语", "英语"),
    ("粤语", "粤语"), ("韩语", "韩语"), ("日语", "日语"),
    ("法语", "法语"), ("德语", "德语"), ("西班牙语", "西班牙语"),
    ("意大利语", "意大利语"), ("泰语", "泰语"), ("其它", "其它"),
]

_COMMON_ORDER = [("时间", "time"), ("人气", "hits"), ("评分", "score")]


def _opts(pairs):
    return [{"n": n, "v": v} for n, v in pairs]


class Spider(Spider):
    def getName(self):
        return "小宝影院"

    def init(self, extend=""):
        self.host = "https://www.xiaobaotv.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self._filter_cache = {}
        try:
            self.proxy_base = self.getProxyUrl(local=True)
        except Exception:
            self.proxy_base = ""
        return {}

    CATS = [
        ("1", "电影"),
        ("2", "电视剧"),
        ("3", "动漫"),
        ("4", "综艺"),
        ("11", "短剧"),
    ]

    # 每个分类的独立 type（child）列表
    _CHILD = {
        "1": [("全部", ""), ("动作片", "101"), ("喜剧片", "102"), ("爱情片", "103"),
              ("科幻片", "104"), ("剧情片", "105"), ("悬疑片", "106"), ("惊悚片", "107"),
              ("恐怖片", "108"), ("犯罪片", "109"), ("冒险片", "111"), ("奇幻片", "112"),
              ("灾难片", "113"), ("战争片", "114"), ("动画电影片", "115"),
              ("歌舞片", "116"), ("网络电影片", "117"), ("同性片", "118"),
              ("经典片", "121"), ("其它片", "122"), ("记录片", "124")],
        "2": [("全部", ""), ("国产剧", "201"), ("港台剧", "202"), ("台湾剧", "203"),
              ("日韩剧", "204"), ("日本剧", "205"), ("欧美剧", "206"),
              ("泰国剧", "207"), ("海外剧", "208"), ("新马泰剧", "209"),
              ("其他剧", "210")],
        "3": [("全部", ""), ("国产动漫", "301"), ("日韩动漫", "302"),
              ("港台动漫", "304"), ("欧美动漫", "306"), ("其它动漫", "310")],
        "4": [("全部", ""), ("大陆综艺", "401"), ("日韩综艺", "402"),
              ("港台综艺", "404"), ("欧美综艺", "406"), ("新马泰综艺", "407"),
              ("其它综艺", "410")],
        "11": [("全部", "")],
    }

    _CLASS = {
        "1": [("全部", ""), ("爱情", "爱情"), ("古装", "古装"), ("动作", "动作"),
              ("伦理", "伦理"), ("悬疑", "悬疑"), ("犯罪", "犯罪"), ("谍战", "谍战"),
              ("历史", "历史"), ("喜剧", "喜剧"), ("奇幻", "奇幻"), ("科幻", "科幻"),
              ("家庭", "家庭"), ("青春", "青春"), ("剧情", "剧情"), ("冒险", "冒险"),
              ("纪录", "纪录"), ("动画", "动画"), ("人物", "人物"), ("文化", "文化"),
              ("其他", "其他")],
        "2": [("全部", ""), ("爱情", "爱情"), ("古装", "古装"), ("悬疑", "悬疑"),
              ("都市", "都市"), ("喜剧", "喜剧"), ("战争", "战争"), ("剧情", "剧情"),
              ("青春", "青春"), ("历史", "历史"), ("网剧", "网剧"), ("奇幻", "奇幻"),
              ("冒险", "冒险"), ("励志", "励志"), ("犯罪", "犯罪"), ("商战", "商战"),
              ("恐怖", "恐怖"), ("穿越", "穿越"), ("农村", "农村"), ("人物", "人物"),
              ("商业", "商业"), ("生活", "生活"), ("其他", "其他")],
        "3": [("全部", ""), ("冒险", "冒险"), ("战斗", "战斗"), ("搞笑", "搞笑"),
              ("经典", "经典"), ("科幻", "科幻"), ("玄幻", "玄幻"), ("魔幻", "魔幻"),
              ("武侠", "武侠"), ("恋爱", "恋爱"), ("推理", "推理"), ("日常", "日常"),
              ("校园", "校园"), ("悬疑", "悬疑"), ("真人", "真人"), ("历史", "历史"),
              ("竞技", "竞技"), ("其他", "其他")],
        "4": [("全部", ""), ("游戏", "游戏"), ("脱口秀", "脱口秀"), ("音乐", "音乐"),
              ("情感", "情感"), ("生活", "生活"), ("职场", "职场"), ("真人秀", "真人秀"),
              ("搞笑", "搞笑"), ("公益", "公益"), ("艺术", "艺术"), ("访谈", "访谈"),
              ("益智", "益智"), ("体育", "体育"), ("少儿", "少儿"), ("时尚", "时尚"),
              ("人物", "人物"), ("其他", "其他")],
        "11": [("全部", ""), ("古装", "古装"), ("复仇", "复仇"), ("强者", "强者"),
               ("悬疑", "悬疑"), ("甜宠", "甜宠"), ("神豪", "神豪"), ("穿越", "穿越"),
               ("虐恋", "虐恋"), ("逆袭", "逆袭"), ("重生", "重生"), ("萌宝", "萌宝")],
    }

    # ---------- 基础 ----------
    def _fetch(self, url, params=None):
        try:
            r = self.session.get(url, params=params, timeout=20)
            if r.status_code != 200:
                return ""
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self.host + (u if u.startswith("/") else "/" + u)

    def _wrap_pic(self, u):
        if not u:
            return ""
        if not self.proxy_base:
            return u
        try:
            b64 = base64.b64encode(u.encode()).decode()
            return "{}&m=img&u={}".format(self.proxy_base, b64)
        except Exception:
            return u

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        vods = []
        seen = set()
        for m in re.finditer(
                r'<a\b[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'href="(/vod/detail/(\d+)\.html)"', tag)
            tm = re.search(r'title="([^"]*)"', tag)
            if not hm or not tm:
                continue
            vid = hm.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            # 兼容 data-original / data-src
            sm = re.search(r'data-original="([^"]+)"', tag)
            if not sm:
                sm = re.search(r'data-src="([^"]+)"', tag)
            if not sm:
                sm = re.search(r'src="([^"]+)"', tag)
            pic = sm.group(1).strip() if sm else ""
            # 备注：a 标签之后 500 字符内找 pic-text（避免跨卡片）
            tail = html[m.end():m.end() + 500]
            rm = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', tail)
            vods.append({
                "vod_id": vid,
                "vod_name": tm.group(1).strip(),
                "vod_pic": self._wrap_pic(self._abs(pic)),
                "vod_remarks": (rm.group(1).strip() if rm else ""),
            })
        return vods

    # ---------- 二级分类 ----------
    def _opt_keyval(self, href, parent):
        u = unquote(href)
        m = re.search(r"/vod/show/id/(\d+)\.html", u)
        if m:
            return ("child", "") if m.group(1) == parent else ("child", m.group(1))
        m = re.search(r"/vod/show/class/([^/]+)/id/", u)
        if m:
            return ("class", m.group(1))
        m = re.search(r"/vod/show/area/([^/]+)/id/", u)
        if m:
            return ("area", m.group(1))
        m = re.search(r"/vod/show/id/\d+/year/(\d+)", u)
        if m:
            return ("year", m.group(1))
        m = re.search(r"/vod/show/id/\d+/lang/([^/]+?)(?:\.html|/|$)", u)
        if m:
            return ("lang", m.group(1))
        m = re.search(r"/vod/show/by/([^/]+)/id/", u)
        if m:
            return ("by", m.group(1))
        return (None, None)

    def _load_filters(self, cid):
        if cid in self._filter_cache:
            return self._filter_cache[cid]
        html = self._fetch("%s/vod/type/%s.html" % (self.host, cid))
        groups = []
        seen_keys = set()
        for um in re.finditer(
                r'<ul class="myui-screen__list[^"]*"[^>]*>(.*?)</ul>', html, re.S):
            block = um.group(1)
            dm = re.search(r'<li[^>]*>\s*<a[^>]*class="[^"]*text-muted[^"]*"[^>]*>([^<]{1,12})</a>',
                           block)
            dim_name = dm.group(1).strip() if dm else "筛选"
            items = []
            fkey = None
            for href, nm in re.findall(r'<a[^>]*href="(/vod/show/[^"]+)"[^>]*>([^<]+)</a>',
                                       block):
                if nm.strip() == "全部":
                    continue
                key, _ = self._opt_keyval(href, cid)
                if key:
                    fkey = key
                    break
            if not fkey:
                continue
            for href, nm in re.findall(r'<a[^>]*href="(/vod/show/[^"]+)"[^>]*>([^<]+)</a>',
                                       block):
                key, val = self._opt_keyval(href, cid)
                nm = nm.strip()
                if nm == "全部":
                    if not any(x["v"] == "" for x in items):
                        items.insert(0, {"n": "全部", "v": ""})
                    continue
                if key != fkey:
                    continue
                if nm and all(x["n"] != nm for x in items):
                    items.append({"n": nm, "v": val})
            if fkey and fkey not in seen_keys and len(items) > 1:
                seen_keys.add(fkey)
                groups.append({"key": fkey, "name": dim_name, "value": items})
        self._filter_cache[cid] = groups
        return groups

    def _build_filters(self):
        result = {}
        for cid, _name in self.CATS:
            fs = []
            if self._CHILD.get(cid):
                fs.append({"key": "child", "name": "类型",
                           "value": _opts(self._CHILD[cid])})
            if self._CLASS.get(cid):
                fs.append({"key": "class", "name": "剧情",
                           "value": _opts(self._CLASS[cid])})
            fs.append({"key": "area", "name": "地区", "value": _opts(_COMMON_AREAS)})
            fs.append({"key": "year", "name": "年份", "value": _opts(_COMMON_YEARS)})
            fs.append({"key": "lang", "name": "语言", "value": _opts(_COMMON_LANGS)})
            fs.append({"key": "by", "name": "排序", "value": _opts(_COMMON_ORDER)})
            result[cid] = fs
        return result

    def homeContent(self, filter=False):
        classes = [{"type_id": cid, "type_name": cn} for cid, cn in self.CATS]
        result = {"class": classes}
        if filter:
            result["filters"] = self._build_filters()
        return result

    def homeVideoContent(self):
        html = self._fetch(self.host + "/")
        return {"list": self._parse_cards(html), "parse": 0, "jx": 0}

    def _show_url(self, cid, pg, extend):
        ext = extend if isinstance(extend, dict) else {}
        child = (ext.get("child") or "").strip()
        base = "/vod/show/id/%s" % (child if child else cid)
        for key, tmpl in (("class", "/class/%s"), ("area", "/area/%s"),
                          ("year", "/year/%s"), ("lang", "/lang/%s"),
                          ("by", "/by/%s")):
            v = (ext.get(key) or "").strip()
            if v:
                base += tmpl % quote(v)
        if pg > 1:
            base += "/page/%d" % pg
        return self.host + base + ".html"

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            cid = tid if any(tid == c for c, _ in self.CATS) else "1"
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if extend and any((extend.get(k) or "").strip()
                              for k in ("child", "class", "area", "year", "lang", "by")):
                url = self._show_url(cid, pg, extend)
            else:
                url = "%s/vod/type/%s%s.html" % (
                    self.host, cid, "-%d" % pg if pg > 1 else "")
            html = self._fetch(url)
            vods = self._parse_cards(html)
            pagecount = 1
            pages = re.findall(r'/vod/type/%s-(\d+)\.html' % cid, html)
            if pages:
                pagecount = max(int(p) for p in pages)
            else:
                allp = re.findall(r'/page/(\d+)\.html', html)
                if allp:
                    pagecount = max(int(p) for p in allp)
                elif len(vods) < 20:
                    pagecount = pg
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[%s] categoryContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ---------- 简介提取（核心修复区） ----------
    def _extract_desc(self, html):
        """从详情页 HTML 中提取干净简介"""
        desc = ""
        # 按优先级尝试多个苹果CMS/mytheme 常见容器
        patterns = [
            r'<div[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*(?:vod-content|vod_content|detail-content|detail_content|desc)[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*(?:desc|content|detail)[^"]*"[^>]*>(.*?)</p>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                desc = m.group(1)
                break

        # 兜底：从"剧情介绍/简介/剧情"关键词开始
        if not desc:
            m = re.search(
                r'(?:剧情介绍|简介|剧情)[：:]\s*(?:</span>)?\s*(?:<p[^>]*>|<div[^>]*>)?(.*?)(?:</div>|</p>|<div|详情|立即播放|$)',
                html, re.S)
            if m:
                desc = m.group(1)

        if not desc:
            return ""

        # 去 HTML 标签
        desc = re.sub(r'<[^>]+>', '', desc)
        # 替换 HTML 实体
        desc = (desc.replace('&nbsp;', ' ').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'")
                    .replace('&lt;', '<').replace('&gt;', '>'))
        # 强力切断底部导航 / 播放列表误抓文本
        for stop_word in ['详情', '立即播放', '报错', '收藏', '扫一扫',
                          '排序', '播放地址', '第01集', '第1集']:
            if stop_word in desc:
                desc = desc.split(stop_word)[0]
        # 清理多余空白
        desc = re.sub(r'\s+', ' ', desc).strip()
        # 限制长度上限（防止极端情况爆炸）
        return desc[:2000]

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vods = []
        try:
            vid = re.sub(r"\D", "", ids[0] if ids else "")
            html = self._fetch("%s/vod/detail/%s.html" % (self.host, vid))
            if not html:
                return {"list": []}

            vod = {"vod_id": vid}

            # 标题
            m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            if not m:
                m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else vid

            # 封面
            m = re.search(r'myui-content__thumb.*?data-original="([^"]+)"', html, re.S)
            if not m:
                m = re.search(r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"', html)
            vod["vod_pic"] = self._wrap_pic(self._abs(m.group(1).strip() if m else ""))

            # 备注 / 豆瓣分
            m = re.search(r'<span class="text-red">([^<]*)</span>', html)
            vod["vod_remarks"] = m.group(1).strip() if m else ""

            # ===================== 简介 =====================
            vod["vod_content"] = self._extract_desc(html)
            # ==================================================

            # 演员 / 导演
            actors = re.findall(r'/search/actor/[^"]*"[^>]*>([^<]+)</a>', html)
            if not actors:
                actors = re.findall(r'/vod/search/actor[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_actor"] = ",".join(dict.fromkeys(a.strip() for a in actors if a.strip()))[:300]

            directors = re.findall(r'/search/director/[^"]*"[^>]*>([^<]+)</a>', html)
            if not directors:
                directors = re.findall(r'/vod/search/director[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_director"] = ",".join(dict.fromkeys(d.strip() for d in directors if d.strip()))[:200]

            # 年份 / 地区 / 类型 / 语言 (从详情字段区抓)
            def _field(label):
                pat = r'{}[：:]\s*(?:</span>)?\s*(?:<a[^>]*>)?(.*?)(?:</a>|<br|<p|</div|</li|</span>|$)'.format(label)
                mm = re.search(pat, html, re.S)
                if mm:
                    t = re.sub(r'<[^>]+>', '', mm.group(1))
                    return t.replace('&nbsp;', ' ').strip()
                return ""

            vod["vod_year"] = _field("年份")
            vod["vod_area"] = _field("地区")
            vod["vod_lang"] = _field("语言")
            tname = _field("类型")
            if tname:
                vod["type_name"] = tname

            # 播放源
            play_from, play_url = [], []
            tabs = re.findall(r'href="#playlist(\d+)"[^>]*>([^<]+)<', html)
            for num, src_name in tabs:
                src_name = src_name.strip()
                start = html.find('id="playlist%s"' % num)
                if start < 0:
                    continue
                # 截取到下一个 playlist 或文件尾
                nxt_m = re.search(r'id="playlist\d+"', html[start + 10:])
                end = start + 10 + nxt_m.start() if nxt_m else len(html)
                seg = html[start:end]
                eps = []
                for href, nm in re.findall(
                        r'<a[^>]*href="(/vod/play/\d+-\d+-\d+\.html)"[^>]*>([^<]*)</a>',
                        seg):
                    nm = nm.strip() or "正片"
                    eps.append("%s$%s" % (nm, self._abs(href)))
                if eps:
                    play_from.append(src_name)
                    play_url.append("#".join(eps))

            # 兜底：直接扫全页所有播放链接
            if not play_from:
                all_eps = re.findall(
                    r'<a[^>]*href="(/vod/play/(\d+)-([a-z0-9]+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                    html)
                groups = {}
                for href, _vid, sid, _nid, nm in all_eps:
                    groups.setdefault(sid, []).append(
                        ("%s$%s" % (nm.strip() or "正片", self._abs(href))))
                for sid in sorted(groups.keys()):
                    play_from.append("线路%s" % sid)
                    play_url.append("#".join(x[0] for x in groups[sid]))

            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)

            vods.append(vod)
        except Exception as e:
            print("[%s] detailContent 异常: %s" % (self.getName(), e))
        return {"list": vods}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            # MacCMS 搜索常见两种：/search.html?wd= & /vod/search/page/N/wd/K.html
            html = self._fetch("%s/search.html" % self.host,
                               params={"wd": key, "submit": ""})
            vods = self._parse_cards(html)
            if not vods and pg > 1:
                alt = "%s/vod/search/page/%d/wd/%s.html" % (self.host, pg, quote(key))
                html = self._fetch(alt)
                vods = self._parse_cards(html)
            pagecount = 1
            allp = re.findall(r'/page/(\d+)\.html', html or "")
            if allp:
                pagecount = max(int(p) for p in allp)
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": len(vods)}
        except Exception as e:
            print("[%s] searchContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    def playerContent(self, flag, id, vipFlags=None):
        header = {
            "Referer": self.host + "/",
            "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
        }
        try:
            pid = (id or "").strip()
            if "$" in pid:
                pid = pid.split("$")[-1]
            if not pid:
                return {"parse": 0, "url": "", "header": header}

            # 已经是 m3u8 / mp4 直链
            if pid.startswith("http") and (".m3u8" in pid or ".mp4" in pid):
                return {"parse": 0, "url": pid, "header": header}

            # 抓播放页
            page_url = pid if pid.startswith("http") else self._abs(pid)
            html = self._fetch(page_url)
            if not html:
                return {"parse": 1, "url": page_url, "header": header}

            # 优先解析 player_aaaa JSON（非贪婪，避免跨 script）
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>',
                          html, re.S)
            if not m:
                m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
            if m:
                try:
                    data = json.loads(m.group(1))
                except Exception:
                    data = {}
                url = (data.get("url") or "").replace("\\/", "/")
                # encrypt=1 时是 base64
                if data.get("encrypt") == 1 and url:
                    try:
                        url = base64.b64decode(
                            url + "=" * (-len(url) % 4)
                        ).decode("utf-8", "replace").replace("\\/", "/")
                    except Exception:
                        pass
                if url:
                    if url.startswith("//"):
                        url = "https:" + url
                    if ".m3u8" in url or ".mp4" in url:
                        return {"parse": 0, "url": url, "header": header}
                    # 非直链，交给壳嗅探
                    return {"parse": 1, "url": url, "header": header}

            # 兼容原来的 base64decode 形式
            m2 = re.search(r'base64decode\(["\']([^"\']+)["\']\)', html)
            if m2:
                try:
                    b64 = m2.group(1)
                    parser_url = base64.b64decode(
                        b64 + "=" * (-len(b64) % 4)
                    ).decode("utf-8", "replace").replace("\\/", "/").strip()
                    if parser_url.startswith("//"):
                        parser_url = "https:" + parser_url
                    ph = self._fetch(parser_url)
                    mm = re.search(r'(https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*)',
                                   ph or "")
                    if mm:
                        return {"parse": 0,
                                "url": mm.group(1).replace("\\/", "/"),
                                "header": {"Referer": parser_url,
                                           "User-Agent": header["User-Agent"]}}
                    return {"parse": 1, "url": parser_url, "header": header}
                except Exception:
                    pass

            # 最后兜底：直接扫 HTML 里的 m3u8
            mm = re.search(r'(https?:[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
            if mm:
                return {"parse": 0,
                        "url": mm.group(1).replace("\\/", "/"),
                        "header": header}

            return {"parse": 1, "url": page_url, "header": header}
        except Exception as e:
            print("[%s] playerContent 异常: %s" % (self.getName(), e))
            return {"parse": 0, "url": "", "header": header}

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    # ---------- 图片本地代理 ----------
    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                q = parse_qs(param)
                param = {k: v[0] for k, v in q.items() if v}
        if isinstance(param, dict) and param.get("m") == "img":
            try:
                url = base64.b64decode(param.get("u", "")).decode()
                req = urllib.request.Request(url, headers={
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                    "Referer": self.host + "/",
                })
                data = urllib.request.urlopen(req, timeout=15).read()
                mime = "image/jpeg"
                lu = url.lower()
                if ".webp" in lu:
                    mime = "image/webp"
                elif ".png" in lu:
                    mime = "image/png"
                elif ".gif" in lu:
                    mime = "image/gif"
                return [200, {"Content-Type": mime}, data]
            except Exception:
                return [404, {"Content-Type": "text/plain"}, b""]
        return [200, {"Content-Type": "text/plain"}, b""]
