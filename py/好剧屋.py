# coding=utf-8
"""
好剧屋 www.haojuwu1.cc | TVBox Python 爬虫 (V3.0 好剧影视约定版)

参照「好剧影视」写法，修正以下壳子约定：
  - vod_id 只存数字
  - vod_play_url 格式: 剧集名$vid-sid-nid
  - 所有方法返回 parse=0, jx=0
  - homeContent 里带首页推荐 list
  - header 用 json.dumps 字符串
  - categoryContent 用 12 段位 URL
  - 播放页 player_aaaa.url 直链 m3u8
"""
import re
import sys
import json
import time
import random
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
                self._session.trust_env = False
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, timeout=15, verify=False, **kw):
            r = self._sess.get(url, headers=headers, timeout=timeout,
                               verify=verify, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, headers=None, data=None, timeout=15, verify=False):
            r = self._sess.post(url, headers=headers, data=data,
                                timeout=timeout, verify=verify)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[haojuwu]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.haojuwu1.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/jianbai/statics/img/favicon.ico"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类 =====================
CATEGORIES = [
    ('1',  '电影'),
    ('2',  '电视剧'),
    ('20', '短剧'),
    ('3',  '综艺'),
    ('4',  '动漫'),
    ('42', '其它'),
    ('43', '体育'),
]

# ===================== 筛选器 =====================
_SORTS = [
    {"n": "默认", "v": ""},
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "泰国", "v": "泰国"}, {"n": "法国", "v": "法国"},
    {"n": "英国", "v": "英国"}, {"n": "德国", "v": "德国"},
    {"n": "其他", "v": "其他"},
]

_FILTERS_MAP = {
    "1":  [("全部", "1"), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"),
           ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"),
           ("记录片", "21"), ("悬疑片", "22"), ("动画片", "23"), ("犯罪片", "24"),
           ("奇幻片", "25"), ("惊悚片", "40"), ("伦理片", "41")],
    "2":  [("全部", "2"), ("国产剧", "13"), ("AI漫剧", "50"), ("香港剧", "14"),
           ("台湾剧", "15"), ("美国剧", "16"), ("韩国剧", "26"), ("日本剧", "27"),
           ("泰国剧", "28"), ("海外剧", "29")],
    "3":  [("全部", "3"), ("大陆综艺", "35"), ("日韩综艺", "36"),
           ("欧美综艺", "37"), ("港台综艺", "38")],
    "4":  [("全部", "4"), ("国产动漫", "30"), ("日韩动漫", "31"),
           ("欧美动漫", "32"), ("港台动漫", "33"), ("海外动漫", "34")],
    "42": [("全部", "42"), ("国创", "48"), ("番剧", "49")],
    "43": [("全部", "43"), ("足球", "44"), ("篮球", "45"),
           ("网球", "46"), ("斯诺克", "47")],
    "20": [("全部", "20")],
}

FILTERS = {}
for tid, tname in CATEGORIES:
    FILTERS[tid] = [
        {"key": "tid", "name": "类型",
         "value": [{"n": n, "v": v}
                   for n, v in _FILTERS_MAP.get(tid, [("全部", tid)])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "by", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
_RE_PAGENUM = re.compile(r'<a>(\d+)/(\d+)</a>')
_RE_PLAYER_AA_START = re.compile(r'player_aaaa\s*=\s*(\{)', re.S)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)


def _extract_js_object(html, start_pos):
    depth = 0
    i = start_pos
    in_str = False
    quote = ''
    escape = False
    n = len(html)
    while i < n:
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return html[start_pos:i + 1]
        i += 1
    return ""


class Spider(Spider):

    name = '好剧屋'
    host = HOST + '/'
    VIDEO_EXT = ('.m3u8', '.mp4', '.flv', '.mkv', '.avi', '.ts', '.m3u', '.mpd')

    # 苹果CMS v10 段位
    SHOW_LEN = 12
    SHOW_SEG = {'tid': 0, 'area': 1, 'by': 2, 'class': 3,
                'lang': 4, 'letter': 5, 'page': 8, 'year': 11}

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._debug = True
        self._last_ts = {}

    def getName(self):
        return self.name

    def init(self, extend=''):
        try:
            if extend:
                self.extend = json.loads(extend)
            else:
                self.extend = {}
        except Exception:
            self.extend = {}
        if self.extend.get('site'):
            self.host = self.extend['site'].rstrip('/') + '/'
        self._log('init: host=%s' % self.host)
        return {}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).split('?')[0].lower()
        return u.endswith(self.VIDEO_EXT)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _log(self, msg):
        if self._debug:
            try:
                print('[%s] %s' % (self.name, msg))
            except Exception:
                pass

    def _headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or (self.host),
        }

    def _fetch(self, url, referer=None, retries=2, timeout=20):
        for i in range(retries):
            try:
                if i > 0:
                    time.sleep(random.uniform(0.5, 1.2))
                r = self.fetch(url, headers=self._headers(referer),
                               timeout=timeout, verify=False)
                if getattr(r, 'status_code', 0) == 200:
                    r.encoding = 'utf-8'
                    return r.text or ''
            except Exception as e:
                self._log('fetch异常 [%s]: %s (%d/%d)' % (url, e, i + 1, retries))
        return ''

    def _fix(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host.rstrip('/') + url
        if not url.startswith('http'):
            return urllib.parse.urljoin(self.host, url)
        return url

    @staticmethod
    def _txt(s):
        if not s:
            return ''
        s = re.sub(r'<[^>]+>', ' ', str(s))
        s = s.replace('\xa0', ' ').replace('&nbsp;', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    def _show_url(self, tid, page=1, extend=None):
        """12 段位 vodshow URL"""
        ext = extend if isinstance(extend, dict) else {}
        segs = [''] * self.SHOW_LEN

        real_tid = str(ext.get('tid') or '').strip() or str(tid)
        segs[self.SHOW_SEG['tid']] = real_tid

        for k in ('area', 'by', 'class', 'lang', 'year', 'letter'):
            v = str(ext.get(k) or '').strip()
            if v:
                segs[self.SHOW_SEG[k]] = urllib.parse.quote(v, safe='')

        p = int(page or 1)
        if p > 1:
            segs[self.SHOW_SEG['page']] = str(p)

        return '%svodshow/%s.html' % (self.host, '-'.join(segs))

    def _parse_list(self, html):
        """解析 stui-vodlist 卡片，vod_id 只存数字"""
        items, seen = [], set()
        if not html:
            return items

        # 用正则解析：<a class="stui-vodlist__thumb lazyload" href="/voddetail/xxx.html" title="xxx" ... data-original="xxx">
        pattern = re.compile(
            r'<a\b[^>]*?href="(/voddetail/(\d+)\.html)"[^>]*?'
            r'title="([^"]*)"[^>]*?'
            r'(?:data-original|data-src)="([^"]*?)"',
            re.S | re.I)
        matches = pattern.findall(html)

        # 兜底：属性顺序不同
        if not matches:
            pattern2 = re.compile(
                r'<a\b[^>]*?title="([^"]*)"[^>]*?'
                r'href="(/voddetail/(\d+)\.html)"[^>]*?'
                r'(?:data-original|data-src)="([^"]*?)"',
                re.S | re.I)
            for title, href, vid, pic in pattern2.findall(html):
                matches.append((href, vid, title, pic))

        for href, vid, title, pic in matches:
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                'vod_id':      vid,
                'vod_name':    self._txt(title)[:200] or vid,
                'vod_pic':     self._fix(pic),
                'vod_remarks': '',
            })
        return items

    @staticmethod
    def _pagecount(html, page):
        page = int(page or 1)
        if not html:
            return page
        m = re.search(r'class="active num"[^>]*>\s*<a[^>]*>\s*(\d+)\s*/\s*(\d+)',
                      html)
        if m:
            return max(page, int(m.group(2)))
        m = re.search(r'href="(/vod(?:show|search)/[^"]+)"[^>]*>\s*尾页\s*<',
                      html)
        if m:
            nums = re.findall(r'-(\d+)-', m.group(1))
            if nums:
                return max(page, max(int(x) for x in nums))
        return page

    # ==================================================================
    # TVBox 接口
    # ==================================================================

    def homeContent(self, filter=True):
        classes = [{'type_id': t, 'type_name': n} for t, n in CATEGORIES]
        result = {
            'class': classes,
            'filters': FILTERS,
            'parse': 0,
            'jx': 0,
        }
        try:
            html = self._fetch(self.host)
            result['list'] = self._parse_list(html)[:40]
        except Exception as e:
            self._log('homeContent 异常: %s' % e)
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            html = self._fetch(self.host)
            return {'list': self._parse_list(html)[:40], 'parse': 0, 'jx': 0}
        except Exception as e:
            self._log('homeVideoContent 异常: %s' % e)
            return {'list': [], 'parse': 0, 'jx': 0}

    def categoryContent(self, tid, pg, filter=True, extend=None):
        page = int(pg) if pg else 1
        try:
            url = self._show_url(tid, page, extend)
            self._log('category: %s' % url)
            html = self._fetch(url)
            self._log('  HTML 长度: %d' % len(html))
            items = self._parse_list(html)
            self._log('  解析到: %d 条' % len(items))
            pc = self._pagecount(html, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pc,
                'limit': len(items) or 24,
                'total': pc * (len(items) or 24),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log('categoryContent 异常: %s' % e)
            return {'list': [], 'page': page, 'pagecount': 1,
                    'limit': 24, 'total': 0, 'parse': 0, 'jx': 0}

    def searchContent(self, key, quick=False, pg='1'):
        page = int(pg) if pg else 1
        try:
            # POST /vodsearch/-------------.html
            post_url = self.host + 'vodsearch/-------------.html'
            r = self.post(post_url,
                          headers=self._headers(),
                          data={'wd': key, 'submit': ''},
                          timeout=15, verify=False)
            html = r.text or ''
            self._log('search POST: %s (%d 字节)' % (key, len(html)))

            # POST 无结果 → GET
            if html.count('voddetail') < 2:
                enc = urllib.parse.quote(key)
                get_url = '%svodsearch/%s-------------.html' % (self.host, enc)
                html = self._fetch(get_url)
                self._log('search GET: %s (%d 字节)' % (get_url, len(html)))

            items = self._parse_list(html)
            pc = self._pagecount(html, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pc,
                'limit': len(items) or 24,
                'total': pc * (len(items) or 24),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log('searchContent 异常: %s' % e)
            return {'list': [], 'page': page, 'pagecount': 1,
                    'limit': 24, 'total': 0, 'parse': 0, 'jx': 0}

    def searchContentPage(self, key, quick=False, pg='1'):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        vid = re.sub(r'\D', '', vid) or vid
        url = '%svoddetail/%s.html' % (self.host, vid)
        self._log('detail: %s' % url)
        try:
            html = self._fetch(url, referer=self.host)
            if not html:
                return self._empty_detail(vid)
            return {'list': [self._parse_detail(vid, html)], 'parse': 0, 'jx': 0}
        except Exception as e:
            self._log('detailContent 异常: %s' % e)
            return self._empty_detail(vid)

    def _empty_detail(self, vid):
        return {'list': [{
            'vod_id': vid, 'vod_name': '获取失败', 'vod_pic': '',
            'vod_play_from': '默认', 'vod_play_url': '',
        }], 'parse': 0, 'jx': 0}

    def _parse_detail(self, vid, html):
        # --- 标题 ---
        name = ''
        m = re.search(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._txt(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._txt(m.group(1).split('-')[0].split('_')[0])
        name = re.sub(r'\s*\(\d{4}\)\s*$', '', name).strip() or vid

        # --- 封面 ---
        pic = ''
        m = re.search(
            r'<div class="stui-content__thumb">[\s\S]*?'
            r'<img[^>]*data-original="([^"]*)"', html, re.S | re.I)
        if m:
            pic = m.group(1)

        # --- 信息行 ---
        info = {}
        for pm in re.finditer(r'<p[^>]*class="data"[^>]*>([\s\S]*?)</p>',
                              html, re.I):
            t = self._txt(pm.group(1))
            for part in t.split(' / '):
                mm = re.match(r'^(类型|地区|年份|语言|状态|导演|主演|更新)[：:]\s*(.*)$',
                              part.strip())
                if mm and mm.group(2):
                    k, v = mm.group(1), mm.group(2).strip()
                    if k not in info or len(v) > len(info[k]):
                        info[k] = v

        # --- 简介 ---
        content = ''
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>',
                      html, re.S | re.I)
        if m:
            content = self._txt(m.group(1))
        if not content:
            m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"',
                          html, re.I)
            if m:
                content = self._txt(m.group(1))
        content = (INTRO_PREFIX + '\n' + content) if content else INTRO_PREFIX

        # --- 播放线路 ---
        tab_map = {}
        for a in re.finditer(
                r'<li><a\s+href="#(playlist\d+)"\s+data-toggle="tab">([^<]+)</a></li>',
                html, re.I):
            tab_map[a.group(1)] = self._txt(a.group(2))

        froms, urls = [], []
        # 找所有 playlistN div 块
        for blk in re.finditer(
                r'<div[^>]*id="(playlist\d+)"[^>]*>([\s\S]*?)</div>',
                html, re.I):
            did = blk.group(1)
            inner = blk.group(2)
            eps = []
            for a in re.finditer(
                    r'<li[^>]*>\s*<a[^>]*href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                    inner, re.I):
                ep_name = self._txt(a.group(5))
                play_id = '%s-%s-%s' % (a.group(2), a.group(3), a.group(4))
                eps.append('%s$%s' % (ep_name, play_id))
            if eps:
                froms.append(tab_map.get(did, did))
                urls.append('#'.join(eps))

        if not froms:
            froms = ['默认']
            urls = ['正片$%s-1-1' % vid]

        return {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': self._fix(pic),
            'type_name': info.get('类型', ''),
            'vod_year': info.get('年份', ''),
            'vod_area': info.get('地区', ''),
            'vod_lang': info.get('语言', ''),
            'vod_remarks': info.get('状态', '') or info.get('更新', ''),
            'vod_actor': info.get('主演', ''),
            'vod_director': info.get('导演', ''),
            'vod_content': content,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }

    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or '').strip()
        headers = {
            'User-Agent': UA,
            'Referer': self.host,
        }
        try:
            # 已是直链
            if pid.startswith('http') and self.isVideoFormat(pid):
                return self._play(pid, headers, parse=0)

            # 解析 vid-sid-nid
            if not re.match(r'^\d+-\d+-\d+$', pid):
                m = re.search(r'(\d+-\d+-\d+)', pid)
                if not m:
                    return self._play('', headers, parse=1, play_url=pid)
                pid = m.group(1)

            play_page = '%svodplay/%s.html' % (self.host, pid)
            self._log('player: %s' % play_page)

            html = self._fetch(play_page, referer=self.host)
            if not html:
                return self._play('', headers, parse=1, play_url=play_page)

            # 解析 player_aaaa
            real_url = ''
            m = _RE_PLAYER_AA_START.search(html)
            if m:
                obj_str = _extract_js_object(html, m.start(1))
                if obj_str:
                    try:
                        obj = json.loads(obj_str)
                        real_url = obj.get('url', '') or ''
                        self._log('  player_aaaa.url = %s' % real_url[:160])
                    except Exception as e:
                        self._log('  JSON 解析失败: %s' % e)
                        mm = re.search(r'"url"\s*:\s*"([^"]+)"', obj_str)
                        if mm:
                            real_url = mm.group(1).replace('\\/', '/')

            if real_url and self.isVideoFormat(real_url):
                return self._play(real_url, headers, parse=0)

            # 兜底：交给 TVBox 嗅探
            return self._play('', headers, parse=1, play_url=play_page)
        except Exception as e:
            self._log('playerContent 异常: %s' % e)
            return self._play('', headers, parse=1, play_url=pid)

    @staticmethod
    def _play(url, headers, parse=0, play_url=''):
        return {
            'parse': parse,
            'playUrl': '',
            'url': url or play_url,
            'header': json.dumps(headers),   # ← 字符串！
            'jx': 0,
            'contentType': 'application/vnd.apple.mpegurl'
                           if '.m3u8' in str(url) else '',
        }

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                url = param.get('url') or ''
            else:
                url = str(param or '')
            if not url.startswith('http'):
                return None
            r = self.fetch(url, headers={
                'User-Agent': UA, 'Referer': self.host}, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            return [200, ct, r.content]
        except Exception:
            return None

    def close(self):
        self.destroy()
