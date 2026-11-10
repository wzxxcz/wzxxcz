# coding=utf-8
# TVBox 影视爬虫 —— 爱剧网 www.zachiska.com
# 模板：ewave（/template/laoniu_jo3/）｜后端 MacCMS
# 结构：首页分区 → /vs/{tid}/{class}/{area}/{lang}/{year}/{order}/{page}.html
#       详情 /info/{id}.html → 播放 /live/{id}-{sid}-{ep}.html（集序号从 1 开始）
#       搜索 /search.html?wd={kw}&page={page}
import re
import json
import time
import urllib.parse
from base.spider import Spider

HOST = "https://www.zachiska.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_PIC = HOST + "/template/laoniu_jo3/static/img/1.svg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_SIZE = 24      # 分类/筛选页每页 24 条
SEARCH_SIZE = 10    # 搜索页每页 10 条
CACHE_TTL = 180

# 一级分类 + 二级分类（与站方 channel-slide 完全一致）
CLASSES = [
    ("2", "电视剧"),
    ("1", "电影"),
    ("5", "动漫"),
    ("37", "综艺"),
    ("59", "AI漫剧"),
    ("29", "短剧"),
    ("30", "国产剧"), ("15", "韩剧"), ("14", "美剧"), ("13", "港剧"), ("16", "日剧"), ("27", "台剧"), ("28", "泰剧"),
    ("6", "动作片"), ("7", "爱情片"), ("58", "动画片"), ("8", "科幻片"), ("9", "恐怖片"), ("11", "喜剧片"), ("12", "剧情片"), ("24", "纪录片"),
    ("17", "国产动漫"), ("47", "日本动漫"), ("49", "欧美动漫"), ("18", "香港动漫"), ("48", "韩国动漫"), ("46", "台湾动漫"),
    ("38", "大陆综艺"), ("43", "欧美综艺"), ("39", "香港综艺"), ("41", "日本综艺"),
    ("55", "都市短剧"),
]

# 二级分类 → 一级分类（筛选条件继承父级）
FILTER_PARENT = {
    "30": "2", "15": "2", "14": "2", "13": "2", "16": "2", "27": "2", "28": "2",
    "6": "1", "7": "1", "58": "1", "8": "1", "9": "1", "11": "1", "12": "1", "24": "1",
    "17": "5", "47": "5", "49": "5", "18": "5", "48": "5", "46": "5",
    "38": "37", "43": "37", "39": "37", "41": "37",
    "55": "29",
}

# 需要抓筛选块的顶层分类
FILTER_ROOTS = ["2", "1", "5", "37", "59", "29"]

_RE_INFO = re.compile(r'href="(/info/(\d+)\.html)"')
_RE_THUMB_TAG = re.compile(r'<(?:a|div)[^>]*class="[^"]*ewave-vodlist__thumb[^"]*"[^>]*>', re.I)
_RE_HREF = re.compile(r'href="([^"]+)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC = re.compile(r'data-original="([^"]*)"', re.I)
_RE_PIC_TEXT = re.compile(r'class="pic-text[^"]*"[^>]*>\s*([^<]*?)\s*<', re.I)
_RE_PIC_TAG = re.compile(r'class="pic-tag[^"]*"[^>]*>\s*([^<]*?)\s*<', re.I)
_RE_ACTOR = re.compile(r'class="[^"]*text-actor[^"]*"[^>]*>\s*([\s\S]*?)</p>', re.I)
_RE_H4_A = re.compile(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h4>', re.I)
_RE_H3_A = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_LI = re.compile(r'<li(?:\s[^>]*)?>([\s\S]*?)</li>')

# 分页：尾页链接（分类 /category/{tid}-{n}.html 或 搜索 /search/page/{n}/wd/{kw}.html）
_RE_TAIL_CAT = re.compile(r'<a[^>]*href="[^"]*/category/\d+-(\d+)\.html"[^>]*>\s*尾页\s*</a>')
_RE_TAIL_SEARCH = re.compile(r'<a[^>]*href="[^"]*/search/page/(\d+)/wd/[^"]*"[^>]*>\s*尾页\s*</a>')
_RE_TAIL_ANY = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>\s*尾页\s*</a>')

# 详情
_RE_DATA_UL = re.compile(r'<ul class="data[^"]*">([\s\S]*?)</ul>', re.I)
_RE_DATA_LI = re.compile(r'<li(?:\s[^>]*)?>\s*<span class="text-muted">\s*([^<]+?)\s*</span>([\s\S]*?)</li>', re.I)
_RE_PLAYLIST_POS = re.compile(r'<div id="playlist(\d+)"')
_RE_TAB_NAME = re.compile(r'href="#playlist(\d+)"[^>]*>\s*([^<]*?)\s*</a>')
_RE_LIVE = re.compile(r'href="(/live/[^"]+)"[^>]*>\s*([^<]*?)\s*</a>')
_RE_DESC = re.compile(r'<p class="desc[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_SCORE = re.compile(r'<span class="score">\s*([\d.]+)\s*</span>')

# 播放
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>')
_RE_PLAYER2 = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;')

# 筛选块
_RE_SCREEN = re.compile(r'<div class="ewave-screen__list[^"]*"[^>]*>([\s\S]*?)</ul>\s*</div>\s*</div>')
_RE_SCREEN_NAME = re.compile(r'<span class="text-muted">\s*([^<]+?)\s*</span>')
_RE_SLIDE = re.compile(r'class="type-slide ([a-z-]+)"')
_RE_SCREEN_A = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>\s*([^<]*?)\s*</a>')
_SLIDE_KEY = {"class-slide": "class", "area-slide": "area", "lang-slide": "lang", "year-slide": "year"}


def _clean(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
    s = s.replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', s).strip()


def _abs(u):
    if not u:
        return ""
    u = u.strip()
    if u.startswith('//'):
        return 'https:' + u
    if u.startswith('http'):
        return u
    if u.startswith('/'):
        return HOST + u
    return HOST + '/' + u


def _q(s):
    return urllib.parse.quote(str(s or '').strip())


def _split3(s):
    """取前 n 个逗号分隔项，用于主演/导演精简"""
    if not s:
        return []
    return [x.strip() for x in re.split(r'[,，/、]', s) if x.strip()]


class Spider(Spider):

    # ---------------------------------------------------------------- 基础
    def getName(self):
        return "爱剧网"

    def init(self, extend=""):
        self.header = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self._cache = {}
        self._filters = None
        self._filters_ts = 0.0
        return None

    def _fetch(self, url, retry=1):
        now = time.time()
        hit = self._cache.get(url)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        text = ""
        # 控制请求节奏，避免触发站点限流
        gap = now - getattr(self, "_last_req", 0.0)
        if gap < 0.2:
            time.sleep(0.2 - gap)
        self._last_req = time.time()
        for i in range(retry + 1):
            try:
                r = self.session.get(url, headers=self.header, timeout=20, verify=False)
                if r.status_code == 200 and r.text and len(r.text) > 500:
                    text = r.text
                    break
            except Exception as e:
                self.log("fetch err %s %s" % (url, e))
            if i < retry:
                time.sleep(0.8)
        if text:
            self._cache[url] = (now, text)
        return text

    @property
    def session(self):
        s = getattr(self, "_sess", None)
        if s is None:
            import requests
            s = requests.Session()
            s.verify = False
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
            self._sess = s
        return s

    def _search_fetch(self, url):
        """搜索专用：站点对同会话连续搜索会返回 500，故每次新建会话并限速"""
        now = time.time()
        hit = self._cache.get(url)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        gap = now - getattr(self, "_last_search", 0.0)
        if gap < 1.2:
            time.sleep(1.2 - gap)
        text = ""
        for i in range(3):
            s = None
            try:
                import requests
                s = requests.Session()
                s.verify = False
                r = s.get(url, headers=self.header, timeout=20)
                self._last_search = time.time()
                if r.status_code == 200 and r.text and len(r.text) > 5000 and "System Error" not in r.text:
                    text = r.text
                    break
            except Exception as e:
                self.log("search err %s %s" % (url, e))
                self._last_search = time.time()
            finally:
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass
            time.sleep(1.5 * (i + 1))
        if text:
            self._cache[url] = (time.time(), text)
        return text

    # ---------------------------------------------------------------- 列表解析
    def _card_from_block(self, block):
        tag_m = _RE_THUMB_TAG.search(block)
        if not tag_m:
            return None
        tag = tag_m.group(0)
        info_m = _RE_INFO.search(block)
        if not info_m:
            return None
        vid = info_m.group(2)

        # 标题：thumb 的 title → h4/h3 title 的 a → a 文本 → img alt
        name = ""
        t = _RE_TITLE.search(tag)
        if t:
            name = _clean(t.group(1))
        if not name:
            for reg in (_RE_H4_A, _RE_H3_A):
                m = reg.search(block)
                if m:
                    name = _clean(m.group(1))
                    if name:
                        break
        if not name:
            m = re.search(r'alt="([^"]+)"', tag)
            if m:
                name = _clean(m.group(1))
        if not name:
            return None

        # 图片
        pic = ""
        p = _RE_PIC.search(tag)
        if p:
            pic = _abs(p.group(1))
        if not pic:
            m = re.search(r'(?:data-src|src)="([^"]+)"', tag)
            if m:
                pic = _abs(m.group(1))
        if not pic:
            pic = DEFAULT_PIC

        # 副标题（更新状态）
        remark = ""
        m = _RE_PIC_TEXT.search(block)
        if m:
            remark = _clean(m.group(1))

        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
        }

    def _parse_cards(self, h):
        out = []
        seen = set()
        for m in _RE_LI.finditer(h or ""):
            b = m.group(1)
            if "ewave-vodlist__thumb" not in b:
                continue
            card = self._card_from_block(b)
            if not card or card["vod_id"] in seen:
                continue
            seen.add(card["vod_id"])
            out.append(card)
        return out

    def _total_page(self, h, kind="cat"):
        n = 0
        reg = _RE_TAIL_SEARCH if kind == "search" else _RE_TAIL_CAT
        m = reg.search(h or "")
        if m:
            try:
                n = int(m.group(1))
            except Exception:
                n = 0
        if n <= 0:
            m = _RE_TAIL_ANY.search(h or "")
            if m:
                nums = re.findall(r'(\d+)', m.group(1))
                if nums:
                    n = int(nums[-1])
        return max(n, 1)

    # ---------------------------------------------------------------- 首页
    def homeVideoContent(self):
        h = self._fetch(HOST + "/")
        videos = []
        parts = h.split('<div class="ewave-pannel ewave-pannel-bg clearfix">')
        for p in parts[1:]:
            m = re.search(r'<h3 class="title">([\s\S]*?)</h3>', p)
            name = _clean(m.group(1)) if m else ""
            cards = self._parse_cards(p)
            if not cards:
                continue
            videos.append({
                "name": name or "推荐",
                "videos": cards[:12],
            })
        return {"list": videos}

    def _parse_filters(self, h):
        out = []
        for b in _RE_SCREEN.findall(h or ""):
            nm = _RE_SCREEN_NAME.search(b)
            sl = _RE_SLIDE.search(b)
            if not (nm and sl):
                continue
            key = _SLIDE_KEY.get(sl.group(1))
            if not key:
                continue
            vals = []
            for _href, txt in _RE_SCREEN_A.findall(b):
                txt = _clean(txt)
                if not txt:
                    continue
                v = "" if txt == "全部" else txt
                if any(x["v"] == v for x in vals):
                    continue
                vals.append({"n": txt, "v": v})
            if len(vals) <= 1:
                continue
            out.append({
                "key": key,
                "name": _clean(nm.group(1)).rstrip("：:"),
                "value": vals,
            })
        return out

    def _get_filters(self):
        now = time.time()
        if self._filters is not None and now - self._filters_ts < 1800:
            return self._filters
        res = {}
        for tid in FILTER_ROOTS:
            h = self._fetch("%s/vs/%s.html" % (HOST, tid))
            f = self._parse_filters(h)
            if f:
                res[tid] = f
        # 二级分类继承父级筛选
        for sub, parent in FILTER_PARENT.items():
            if parent in res:
                res[sub] = res[parent]
        self._filters = res
        self._filters_ts = now
        return res

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name in CLASSES]
        try:
            filters = self._get_filters()
        except Exception as e:
            self.log("filters err %s" % e)
            filters = {}
        return {
            "class": classes,
            "filters": filters,
            "list": self.homeVideoContent().get("list", []),
        }

    # ---------------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "2")
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        ext = extend or {}
        cls = _q(ext.get("class") or "all")
        area = _q(ext.get("area") or "all")
        lang = _q(ext.get("lang") or "all")
        year = _q(ext.get("year") or "all")
        order = _q(ext.get("order") or "all")
        url = "%s/vs/%s/%s/%s/%s/%s/%s/%s.html" % (HOST, tid, cls, area, lang, year, order, pg)
        h = self._fetch(url)
        if not h:
            # 兜底：普通分类分页
            url2 = "%s/category/%s%s.html" % (HOST, tid, "" if pg == 1 else "-%d" % pg)
            h = self._fetch(url2)
        videos = self._parse_cards(h)
        pagecount = self._total_page(h, "cat")
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount if videos else 1,
            "limit": PAGE_SIZE,
            "total": pagecount * PAGE_SIZE if videos else 0,
        }

    # ---------------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        url = "%s/search.html?wd=%s&page=%d" % (HOST, _q(key), pg)
        h = self._search_fetch(url)
        videos = self._parse_cards(h)
        pagecount = self._total_page(h, "search")
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount if videos else 1,
            "limit": SEARCH_SIZE,
            "total": pagecount * SEARCH_SIZE if videos else 0,
        }

    # ---------------------------------------------------------------- 详情
    def _detail_data(self, h):
        data = {}
        m = _RE_DATA_UL.search(h or "")
        if not m:
            return data
        for li in _RE_DATA_LI.findall(m.group(1)):
            k = _clean(li[0]).rstrip("：:").strip()
            v = _clean(li[1])
            if k and k not in data:
                data[k] = v
        return data

    def _build_intro(self, name, year, area, kind, director, actor, remarks):
        kind = _clean(kind).split()[0] if _clean(kind) else ""
        area_s = "、".join(_split3(area)[:3])
        dir_s = "、".join(_split3(director)[:2])
        act_s = "、".join(_split3(actor)[:3])

        if year and area_s:
            seg = "《%s》是%s年%s出品的%s" % (name, year, area_s, kind or "影视作品")
        elif year:
            seg = "《%s》是%s年的%s" % (name, year, kind or "影视作品")
        elif kind:
            seg = "《%s》是一部%s" % (name, kind)
        else:
            seg = "《%s》是一部影视作品" % name

        if dir_s:
            seg += "，由%s执导" % dir_s
        if act_s:
            seg += "，%s等主演" % act_s
        if remarks:
            seg += "，目前%s" % _clean(remarks)
        seg += "。"
        return INTRO_PREFIX + seg

    def detailContent(self, ids):
        vid = str(ids[0]).split("$$$")[0].strip()
        vid = re.sub(r'[^\d]', '', vid) or vid
        h = self._fetch("%s/info/%s.html" % (HOST, vid))
        if not h:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1 class="title">([\s\S]*?)</h1>', h)
        if m:
            name = _clean(re.sub(r'<span class="score">[\s\S]*?</span>', '', m.group(1)))
        if not name:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', h)
            if m:
                name = _clean(m.group(1))
        if not name:
            m = re.search(r'<title>([^<]+)</title>', h)
            if m:
                name = _clean(m.group(1)).split("-")[0].split("_")[0].strip()

        # 封面
        pic = ""
        m = re.search(r'<div class="ewave-content__thumb">([\s\S]*?)</div>', h)
        if m:
            p = _RE_PIC.search(m.group(1)) or re.search(r'(?:data-src|src)="([^"]+)"', m.group(1))
            if p:
                pic = _abs(p.group(1))
        if not pic:
            m = re.search(r'<meta property="og:image" content="([^"]+)"', h)
            if m:
                pic = _abs(m.group(1))
        if not pic:
            pic = DEFAULT_PIC

        data = self._detail_data(h)
        remarks = data.get("状态") or data.get("备注") or ""
        year = data.get("年份") or ""
        area = data.get("地区") or ""
        type_ = data.get("类型") or ""
        actor = data.get("主演") or ""
        director = data.get("导演") or ""
        if not year:
            m = re.search(r'<span class="text-muted">\s*年份：\s*</span>\s*(\d{4})', h)
            if m:
                year = m.group(1)

        score = ""
        m = _RE_SCORE.search(h)
        if m:
            score = m.group(1)

        # 线路：playlist{N} 与 /live/{id}-{N}-{ep}.html 一一对应，按 N 升序
        tab_names = {}
        mt = re.search(r'<div class="playlist-slide">([\s\S]*?)</div>', h)
        if mt:
            for n, t in _RE_TAB_NAME.findall(mt.group(1)):
                tab_names[int(n)] = _clean(t)

        pos = [(int(m.group(1)), m.start()) for m in _RE_PLAYLIST_POS.finditer(h)]
        pos.sort(key=lambda x: x[1])
        play_from = []
        play_url = []
        for i, (n, st) in enumerate(pos):
            end = pos[i + 1][1] if i + 1 < len(pos) else len(h)
            seg = h[st:end]
            eps = []
            seen = set()
            for href, epname in _RE_LIVE.findall(seg):
                if href in seen:
                    continue
                seen.add(href)
                epname = _clean(epname) or ("第%02d集" % (len(eps) + 1))
                eps.append("%s$%s%s" % (epname, HOST, href))
            if not eps:
                continue
            play_from.append(tab_names.get(n) or ("线路%d" % n))
            play_url.append("#".join(eps))

        if not play_from:
            # 兜底：全页 /live/ 链接单线路
            eps = []
            for href, epname in _RE_LIVE.findall(h):
                eps.append("%s$%s%s" % (_clean(epname) or "正片", HOST, href))
            if eps:
                play_from.append("线路一")
                play_url.append("#".join(eps))

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_year": year,
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": self._build_intro(name, year, area, type_, director, actor, remarks),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        if score:
            vod["vod_score"] = score
        if type_:
            vod["vod_class"] = _clean(type_).split()[0] if _clean(type_).split() else type_
        return {"list": [vod]}

    # ---------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith("http") else HOST + str(id)
        header = dict(self.header)
        header["Referer"] = HOST + "/"

        h = self._fetch(url, retry=1)
        d = None
        if h:
            m = _RE_PLAYER.search(h) or _RE_PLAYER2.search(h)
            if m:
                try:
                    d = json.loads(m.group(1))
                except Exception:
                    try:
                        d = json.loads(m.group(1).replace("\\/", "/"))
                    except Exception:
                        d = None

        if not d:
            return {"parse": 1, "playUrl": "", "url": url, "header": header}

        play = (d.get("url") or "").strip()
        enc = d.get("encrypt", 0)
        try:
            enc = int(enc)
        except Exception:
            enc = 0

        if play and enc == 0:
            if play.startswith("//"):
                play = "https:" + play
            elif play.startswith("/"):
                play = HOST + play
            return {"parse": 0, "playUrl": "", "url": play, "header": header}

        if play and enc != 0:
            # 站方加密线路：交给嗅探器解析播放页
            return {"parse": 1, "playUrl": "", "url": url, "header": header}

        return {"parse": 1, "playUrl": "", "url": url, "header": header}

    # ---------------------------------------------------------------- 其它
    def isVideoFormat(self, url):
        u = (url or "").lower()
        for x in (".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi", ".m4a", ".mp3"):
            if x in u:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        try:
            if getattr(self, "_sess", None) is not None:
                self._sess.close()
        except Exception:
            pass
        self._sess = None
        self._cache = {}
        return None
