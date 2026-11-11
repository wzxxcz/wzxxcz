# coding=utf-8
"""
追剧大人 com.okbyrk.zjdr.dre | TVBox Python 爬虫 

关键:
  - APP 接口伪装 Dart 客户端 (UA + version + pk-id + build-time 头) 拉首页/搜索/封面
  - 8 条采集线路并行聚合剧集, 播放列表严格按 LINES 顺序落地 (追剧1 -> 专线·4K)
  - 详情页 副标题/简介/演员/导演/年份/地区/语言/评分/总集数 取自采集站匹配条目
  - 分类筛选 (分类/地区/语言/年份/排序) 与站点 type_extend 对齐, 分类词走飞速站真过滤
"""
import re
import sys
import json
import time
import base64
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider(object):
        """本地调试兜底：模拟 base.spider.Spider 的最小能力"""

        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = requests.Session()
                self._session.verify = False
                adapter = requests.adapters.HTTPAdapter(
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
                print("[zhuiju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 站点常量 =====================
APP_HOST = 'http://23.224.111.70:7788'

# APP 端签名头：少了 version / pk-id 会被服务端降级或返回空列表
APP_HDR = {
    'user-agent': 'Dart/3.13 (dart:io)',
    'version': '2.1.6',
    'version-number': '2108',
    'pk-id': 'com.okbyrk.zjdr.dre',
    'build-time': '1789369676921',
    'platform': 'android',
    'platform-version': 'PJZ110_16.0.10.501(CN01)',
    'content-type': 'text/plain',
    'accept-encoding': 'gzip',
}

UA = ('Mozilla/5.0 (Linux; Android 13; PJZ110 Build/TP1A) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36')

# 导航分类（顺序即首页分类顺序，与 APP 底部/顶栏一致）
TYPES = [('2', '剧集'), ('1', '电影'), ('4', '动漫'), ('3', '综艺'),
         ('27', '纪录'), ('28', '短剧'), ('29', '少儿')]

# 分类 -> 采集站 type 参数（多值用 %2C 逗号连接，采集站按 t 过滤）
CAT_T = {
    '2': '13%2C14%2C15%2C16%2C21%2C22%2C23%2C24',   # 剧集
    '1': '6%2C7%2C8%2C9%2C10%2C11%2C12%2C45',        # 电影
    '4': '29%2C30%2C31%2C32%2C33',                   # 动漫
    '3': '25%2C26%2C27%2C28',                        # 综艺
    '27': '20',                                      # 纪录
    '28': '46',                                      # 短剧
    '29': '49',                                      # 少儿
}

# 主采集（量子）与备采集（飞速）：飞速站支持 class 过滤，量子站量大但忽略 class
S_CAT = 'https://cj.lziapi.com/api.php/provide/vod/at/json/?ac=detail&t=%s&pg=%s'
S_CAT2 = 'https://cj.ffzyapi.com/api.php/provide/vod/at/json/?ac=detail&t=%s&pg=%s'

# 解析器：4K 线路需先过 4kys，直链失效时统一走 ff.php 兜底
PARSER = 'http://49.233.180.127:880'
TAG_PARSER = {'k4': PARSER + '/4kys.php?url='}

# 搜索源（8 条线路各一个 wd 接口）
S_LZ = 'https://cj.lziapi.com/api.php/provide/vod/at/json/?ac=detail&wd='
S_FF = 'https://cj.ffzyapi.com/api.php/provide/vod/at/json/?ac=detail&wd='
S_ZUI = 'https://api.zuidapi.com/api.php/provide/vod/at/json/?ac=detail&wd='
S_JS = 'https://jszyapi.com/api.php/provide/vod/at/json/?ac=detail&wd='
S_HN = 'https://www.hongniuzy2.com/api.php/provide/vod/at/json/?ac=detail&wd='
S_MD = 'https://caiji.moduapi.cc/api.php/provide/vod/at/json/?ac=detail&wd='
S_YZ = 'https://api.yzzyapi.com/api.php/provide/vod/?ac=detail&wd='
S_YZI = 'https://api.yzzyapi.com/api.php/provide/vod/?ac=videolist&ids='
S_K4 = 'https://www.4kvm.top'

# 线路表：元组顺序 = vod_play_from 的落地顺序 = TVBox 里看到的线路排序，勿随意调整
LINES = [('追剧1', 'lz', S_LZ),
         ('专线·飞速', 'ff', S_FF),
         ('专线·最大', 'zui', S_ZUI),
         ('专线·极速', 'js', S_JS),
         ('专线·红牛', 'hn', S_HN),
         ('专线·魔都', 'md', S_MD),
         ('专线·宇宙', 'yz', S_YZ),
         ('专线·4K', 'k4', S_K4)]

LINE_ORDER = [x[1] for x in LINES]          # ['lz','ff','zui','js','hn','md','yz','k4']
LINE_NAME = dict((x[1], x[0]) for x in LINES)

VIDEO_EXTS = 'm3u8|mp4|flv|mkv|avi|ts'
SITE_KEY = 'zhuijudaren'
TO = 10          # 单请求超时
TO_DETAIL = 12   # 详情页并行聚合总预算
CACHE_MAX = 240  # 内存缓存条目上限，防止长跑进程涨内存

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


# ===================== 筛选项（取自站点 type_extend，与 APP 分类页一致）=====================
# 年份：站点下发 1996-2026，此处保持同样区间
_YEARS = [{"n": str(y), "v": str(y)} for y in range(2026, 1995, -1)]

# 地区显示名（合规写法）与传参值（站点原值）分离
_AREA_DISPLAY = {'香港': '中国香港', '台湾': '中国台湾'}

_SORTS = [{"n": "最新更新", "v": "time"},
          {"n": "最多播放", "v": "hits"},
          {"n": "最高评分", "v": "score"}]

# 各分类的 class / area / lang 词表，逐字取自 APP 的 type_extend
_EXT = {
    "1": {
        "class": "喜剧,爱情,恐怖,动作,科幻,剧情,战争,警匪,犯罪,动画,奇幻,武侠,冒险,枪战,悬疑,惊悚,谍战,灾难,经典青春,文艺,微电影,古装,历史,运动,农村,儿童,网络电影,歌舞,传记,纪录,其他",
        "area": "大陆,香港,台湾,美国,法国,英国,日本,韩国,德国,泰国,印度,意大利,西班牙,加拿大,其他",
        "lang": "国语,英语,粤语,闽南语,韩语,日语,法语,德语,其它",
    },
    "2": {
        "class": "喜剧,古装,家庭,犯罪,动作,奇幻,武侠,爱情,青春,悬疑,惊悚,科幻,警匪,谍战,商战,偶像,军事,神话,战争,青春偶像,剧情,历史,经典,乡村,情景,网剧,其他",
        "area": "大陆,韩国,香港,台湾,日本,美国,泰国,英国,新加坡,其他",
        "lang": "国语,英语,粤语,闽南语,韩语,日语,法语,德语,其它",
    },
    "3": {
        "class": "脱口秀,真人秀,搞笑,访谈,生活,晚会,美食,游戏,亲子,旅游,文化,体育,时尚,纪实,益智,演艺,歌舞,音乐,播报,选秀,情感,曲艺,游戏互动,财经,求职",
        "area": "大陆,香港,台湾,美国,韩国,日本,法国,英国,德国,泰国,印度,其他",
        "lang": "国语,英语,粤语,闽南语,韩语,日语,法语,德语,其它",
    },
    "4": {
        "class": "情感,科幻,热血,推理,搞笑,冒险,萝莉,校园,动作,机战,运动,战争,少年,少女,社会,原创,亲子,益智,励志,格斗,恋爱,美少女,LOLI,神魔,真人,青春,魔法,神话,竞技,童话,教育,剧情,历史,其他",
        "area": "大陆,香港,台湾,美国,韩国,日本,法国,英国,德国,泰国,印度,其他",
        "lang": "国语,英语,粤语,闽南语,韩语,日语,其它",
    },
    # 27/28/29 APP 首页未下发 type_extend，按采集站实际分类词补齐
    "27": {
        "class": "纪录片,犯罪,音乐,传记,喜剧,历史,自然,社会,人文,军事,探索,美食,旅行,体育,科学",
        "area": "大陆,香港,台湾,美国,英国,日本,法国,韩国,德国,其他",
        "lang": "国语,英语,粤语,日语,其它",
    },
    "28": {
        "class": "爱情,剧情,悬疑,犯罪,古装,短片,科幻,奇幻,都市,爽文,穿越,重生,逆袭,战神,甜宠,家庭,喜剧,动作,冒险,惊悚",
        "area": "大陆,香港,台湾,美国,韩国,日本,其他",
        "lang": "国语,英语,粤语,其它",
    },
    "29": {
        "class": "动画,喜剧,剧情,冒险,奇幻,动作,爱情,家庭,音乐,歌舞,传记,历史,益智,亲子,教育",
        "area": "大陆,香港,台湾,美国,日本,韩国,英国,其他",
        "lang": "国语,英语,粤语,日语,其它",
    },
}


def _vals(csv, display=False):
    """把逗号串转成 TVBox 的 value 列表"""
    out = [{"n": "全部", "v": ""}]
    seen = set()
    for x in (csv or '').split(','):
        x = x.strip()
        if not x or x in seen:
            continue
        seen.add(x)
        n = _AREA_DISPLAY.get(x, x) if display else x
        out.append({"n": n, "v": x})
    return out


FILTERS = {}
for _tid, _ in TYPES:
    _e = _EXT.get(_tid, {})
    FILTERS[_tid] = [
        {"key": "class", "name": "分类", "value": _vals(_e.get("class"))},
        {"key": "area", "name": "地区", "value": _vals(_e.get("area"), True)},
        {"key": "lang", "name": "语言", "value": _vals(_e.get("lang"))},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
_RE_CDATA = re.compile(r'<!\[CDATA\[|\]\]>')
_RE_TAG = re.compile(r'<[^>]+>')
_RE_BR = re.compile(r'<br\s*/?>', re.I)
_RE_WS = re.compile(r'[ \t\r\f\v]+')
_RE_NL = re.compile(r'\n{2,}')
_RE_NORM = re.compile(r'[^\u4e00-\u9fa5A-Za-z0-9]')
_RE_EPSAFE = re.compile(r'[#$|]')

# 4K 站：详情页里的分集锚点 + 标题
_RE_4K_PLAY = re.compile(r'href="(/play/[a-z0-9]+)"')
_RE_4K_PLAY_TXT = re.compile(r'href="(/play/[a-z0-9]+)"[^>]*>(.{0,200}?)</a>', re.S)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S)

# 播放器地址提取（4kys / ff.php 返回里捞 m3u8、mp4）
_RE_MEDIA = re.compile(r'https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*', re.I)
_RE_VIDEO_EXT = re.compile(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, re.I)

_ENTITIES = [('&nbsp;', ' '), ('&amp;', '&'), ('&quot;', '"'),
             ('&#39;', "'"), ('&lt;', '<'), ('&gt;', '>')]

# 片名后缀词：APP 名常带"解说版/完整版"等尾巴，去掉后才能对上采集站正名
_NAME_SUFFIX = ['深度解读', '疑点揭秘', '剧情解析', '精彩片段', '电影解说', '解说版',
                '解说', '预告片', '预告', '花絮', '合集', '特辑', '完整版', '抢先版',
                '高清版', '国语版', '粤语版', '超清', '蓝光', '正片', '加长版']
_CN_NUM = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
           '六': '6', '七': '7', '八': '8', '九': '9'}
_RE_SEASON = re.compile(r'第[一二三四五六七八九十\d]+季|season\s*\d+|[Ss]\d{1,2}$', re.I)
_RE_BRACKET = re.compile(r'[《》【】\[\]()（）"\'\s]')

NO_SOURCE_TIP = ('\n\n⚠️ 该片在 8 条采集线路中均未收录片源（APP 私有库独有内容），'
                 '可尝试在其它源搜索同名影片。')


class Spider(Spider):

    def getName(self):
        return "追剧大人"

    def init(self, extend=''):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.base = (self.extend.get('host') or APP_HOST).rstrip('/')
        self.ua = UA
        self._c = {}
        self._lock = threading.Lock()
        self.s = requests.Session()
        self.s.headers.update({'user-agent': UA})

        # 后台预热：先把 8 条线路与 7 个分类的 TCP/TLS 连接建好，首屏不等
        try:
            threading.Thread(target=self._warm, daemon=True).start()
        except Exception:
            pass
        self.log("init: host=%s" % self.base)

    # ===================== 基础请求 =====================
    def _warm(self):
        """预热线路与分类，失败静默（不影响主流程）"""
        try:
            for _, _, u in LINES:
                try:
                    self.s.get(u + 'x', timeout=8)
                except Exception:
                    pass
            for tid, _ in TYPES:
                t = CAT_T.get(tid)
                if t:
                    try:
                        self._catlist(S_CAT % (t, 1))
                    except Exception:
                        pass
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _rq(self, url, headers=None, timeout=TO):
        """带重试的 GET（会话复用，UA 缺省用移动端）"""
        for _ in range(2):
            try:
                return self.s.get(url, headers=headers or None, timeout=timeout)
            except Exception:
                pass
        return None

    def _cache_put(self, key, val):
        with self._lock:
            if len(self._c) > CACHE_MAX:
                self._c.clear()
            self._c[key] = val

    def _app(self, path):
        """APP JSON 接口（带 Dart 头 + 进程内缓存）"""
        if path in self._c:
            return self._c[path]
        r = self._rq(self.base + path, APP_HDR)
        d = None
        if r is not None and r.status_code == 200:
            try:
                d = r.json()
            except Exception:
                d = None
        if d is not None:
            self._cache_put(path, d)
        return d

    def _applist(self, pg=1, limit=50):
        j = self._app('/index.php/ajax/data?mid=1&page=%d&limit=%d' % (pg, limit))
        return (j.get('list') or []) if isinstance(j, dict) else []

    def _suggest(self, key):
        """APP 搜索建议：只返回 id/name/pic/en，无副标题，需详情页补齐"""
        j = self._app('/index.php/ajax/suggest?mid=1&wd=' +
                      urllib.parse.quote(key or ''))
        return (j.get('list') or []) if isinstance(j, dict) else []

    # ===================== 通用工具 =====================
    def _wid(self, s):
        """vod_id = 'z' + urlsafe_base64(片名)，详情页靠它反查 8 条线路"""
        return 'z' + base64.urlsafe_b64encode((s or '').encode('utf-8')).decode().rstrip('=')

    def _unid(self, s):
        s = re.sub(r'^[zw]', '', str(s or ''))
        try:
            return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')
        except Exception:
            return ''

    def _clean(self, s):
        """采集站字段去标签/实体/多余空白（vod_content 里带 <p>）"""
        if not s:
            return ''
        s = str(s)
        s = _RE_BR.sub('\n', s)
        s = _RE_TAG.sub('', s)
        s = _RE_CDATA.sub('', s)
        for a, b in _ENTITIES:
            s = s.replace(a, b)
        s = s.replace('\u3000', ' ').replace('\xa0', ' ')
        s = _RE_WS.sub(' ', s)
        s = _RE_NL.sub('\n', s)
        return s.strip()

    def _norm(self, s):
        return _RE_NORM.sub('', s or '')

    def _match(self, want, got):
        a, b = self._norm(want), self._norm(got)
        return bool(a and b and (a == b or a in b or b in a))

    def _pic_ok(self, pic):
        """站点会用 '/'、'-' 当占位图，一律视为无图；相对路径补 host"""
        pic = str(pic or '').strip()
        if pic in ('', '/', '-', 'null', 'None'):
            return ''
        if pic.startswith('//'):
            return 'https:' + pic
        if pic.startswith('/'):
            return getattr(self, 'base', APP_HOST) + pic
        return pic

    def _item(self, name, pic='', remark='', year=''):
        return {'vod_id': self._wid(name), 'vod_name': name or '', 'vod_pic': self._pic_ok(pic),
                'vod_remarks': remark or '', 'vod_year': year or ''}

    def _items(self, lst):
        return [self._item(v.get('vod_name'), v.get('vod_pic'),
                           v.get('vod_remarks'), v.get('vod_year'))
                for v in lst if v.get('vod_name')]

    def _meta_of(self, v):
        """把采集站条目翻成详情页要用的元信息（副标题/简介/演职员等）"""
        return {
            'name': v.get('vod_name') or '',
            'sub': self._clean(v.get('vod_sub')) or '',
            'remarks': self._clean(v.get('vod_remarks')) or '',
            'pic': v.get('vod_pic') or '',
            'year': str(v.get('vod_year') or ''),
            'area': self._clean(v.get('vod_area')) or '',
            'lang': self._clean(v.get('vod_lang')) or '',
            'class': self._clean(v.get('vod_class')) or '',
            'actor': self._clean(v.get('vod_actor')) or '',
            'director': self._clean(v.get('vod_director')) or '',
            'score': str(v.get('vod_score') or ''),
            'content': self._clean(v.get('vod_content')) or self._clean(v.get('vod_blurb')),
        }

    # ===================== 首页 / 分类 =====================
    def homeContent(self, filter=False):
        return {
            'class': [{'type_id': k, 'type_name': v} for k, v in TYPES],
            'filters': FILTERS,
            'list': self._items(self._applist(1, 20)[:20]),
        }

    def homeVideoContent(self):
        self.log("home: 拉取 APP 首页")
        vids = self._items(self._applist(1, 20)[:20])
        self.log("  home 共 %d 条" % len(vids))
        return {'list': vids}

    def _catfetch(self, url):
        """单页采集（短超时，避免拖垮整页）"""
        try:
            r = requests.get(url, headers={'user-agent': UA}, timeout=(5, 8))
            if r.status_code != 200:
                self.log("  cat HTTP %s" % r.status_code)
                return [], 9999, []
            j = r.json()
            L = j.get('list') or []
            out = [self._item(v.get('vod_name'), v.get('vod_pic'),
                              v.get('vod_remarks'), v.get('vod_year'))
                   for v in L if v.get('vod_name')]
            return out, int(j.get('pagecount') or 9999), L
        except Exception as e:
            self.log("  cat FAIL %s" % e)
            return [], 9999, []

    def _catlist(self, url):
        """分类页缓存 + 12s 硬超时（采集站偶尔挂起）"""
        key = 'c:' + url
        if key in self._c:
            return self._c[key]
        ex = ThreadPoolExecutor(max_workers=1)
        fu = ex.submit(self._catfetch, url)
        try:
            out, pc, raws = fu.result(timeout=12)
        except Exception:
            out, pc, raws = [], 9999, []
        ex.shutdown(wait=False)
        if out:
            self._cache_put(key, (out, pc, raws))
        return out, pc, raws

    def _build_url(self, tpl, t, pn, ext):
        """拼分类 URL：筛选参数直接透传（不支持的站会忽略，不会报错）"""
        url = tpl % (t, pn)
        qs = []
        if ext.get('class'):
            qs.append('class=' + urllib.parse.quote(ext['class']))
        if ext.get('area'):
            qs.append('area=' + urllib.parse.quote(ext['area']))
        if ext.get('lang'):
            qs.append('lang=' + urllib.parse.quote(ext['lang']))
        if ext.get('year'):
            qs.append('year=' + urllib.parse.quote(ext['year']))
        if ext.get('sort'):
            qs.append('by=' + urllib.parse.quote(ext['sort']))
        return url + ('&' + '&'.join(qs) if qs else '')

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        pn = max(int(str(pg) or 1), 1)
        t = CAT_T.get(str(tid))
        if not t:
            self.log("category: 未知分类 %s" % tid)
            return {'list': [], 'page': pn, 'pagecount': 9999, 'limit': 20, 'total': 0}

        ext = self._norm_extend(extend)
        self.log("category: tid=%s pg=%s filter=%s" % (tid, pn, ext))

        # 主站（量子）忽略 class，备站（飞速）支持 class：
        # 带分类词时先问飞速，再回量子（回退时本地按 vod_class 兜底过滤）
        alt = '36' if t == '46' else t
        if ext.get('class'):
            urls = [self._build_url(S_CAT2, alt, pn, ext),
                    self._build_url(S_CAT, t, pn, ext)]
        else:
            urls = [self._build_url(S_CAT, t, pn, ext),
                    self._build_url(S_CAT2, alt, pn, ext)]

        out, pc = [], 9999
        best = None
        for u in urls:
            o, p, raws = self._catlist(u)
            if not o:
                continue
            cand = None
            if ext.get('class'):
                # 双保险：站内已过滤则保留，未过滤则本地按 vod_class 兜底
                keep = [v for v in raws
                        if ext['class'] in str(v.get('vod_class') or '')]
                if keep:
                    cand = ([self._item(v.get('vod_name'), v.get('vod_pic'),
                                        v.get('vod_remarks'), v.get('vod_year'))
                             for v in keep if v.get('vod_name')], p)
                    self.log("  class 命中 %d/%d (%s)" % (len(cand[0]), len(o), u[:38]))
                else:
                    self.log("  该站未按 class 过滤，换下一线路")
            else:
                cand = (o, p)
            if cand and (best is None or len(cand[0]) > len(best[0])):
                best = cand
            if best and len(best[0]) >= 15:
                break

        if best:
            out, pc = best

        self.log("  最终: %d 条, 总页数 %d" % (len(out), pc))
        return {'list': out, 'page': pn, 'pagecount': pc,
                'limit': 20, 'total': 999999}

    def _norm_extend(self, extend):
        """筛选参数归一：空值/全部 一律丢掉，避免污染采集站查询"""
        if isinstance(extend, str):
            try:
                extend = json.loads(extend or '{}')
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        out = {}
        for k in ('class', 'area', 'lang', 'year', 'sort'):
            v = extend.get(k)
            if v in (None, '', '全部', '0'):
                continue
            out[k] = str(v)
        if not out.get('sort'):
            out['sort'] = 'time'
        return out

    # ===================== 搜索 =====================
    def searchContent(self, key, quick=False, pg='1'):
        self.log("search: %s" % key)
        out, seen = [], set()
        for v in self._suggest(key):
            nm = (v.get('name') or '').strip()
            if not nm or nm in seen:
                continue
            seen.add(nm)
            out.append(self._item(nm, v.get('pic')))
        if not out:
            # 建议接口空返回时，扫首页最新列表兜底
            for v in self._applist(1, 50):
                nm = v.get('vod_name') or ''
                if key and key in nm and nm not in seen:
                    seen.add(nm)
                    out.append(self._item(nm, v.get('vod_pic'),
                                          v.get('vod_remarks'), v.get('vod_year')))
        self.log("  命中 %d 条" % len(out))
        return {'list': out}

    def searchContentPage(self, key, quick, pg='1'):
        return self.searchContent(key, quick, pg)

    # ===================== 剧集解析（8 条线路）=====================
    def _pick(self, groups):
        """线路内多分组择优：优先真 m3u8，其次 m3u8，再次非网盘，最后兜底"""
        for g in groups:
            if 'm3u8' in g and '/share/' not in g:
                return g
        for g in groups:
            if 'm3u8' in g:
                return g
        for g in groups:
            if '/share/' not in g:
                return g
        return groups[0] if groups else ''

    def _rank(self, want, L):
        """同名优先：精确同名排前，包含关系排后（重制版/多季不串集）"""
        if not want:
            return list(L)
        w = self._norm(want)
        if not w:
            return list(L)
        exact, fuzzy = [], []
        for v in L:
            n = self._norm(v.get('vod_name'))
            if not n:
                continue
            if n == w:
                exact.append(v)
            elif w in n or n in w:
                fuzzy.append(v)
        return exact + fuzzy

    def _parse_segs(self, pick, tag):
        """把 '第1集$url#第2集$url' 拆成 [(集名, 'tag|url')]"""
        eps = []
        for seg in (pick or '').split('#'):
            if '$' not in seg:
                continue
            nm, u = seg.split('$', 1)
            u = _RE_CDATA.sub('', u).strip()
            if u.startswith('//'):
                u = 'https:' + u
            if not (u.startswith('http') or u.startswith('//')):
                continue
            nm = _RE_EPSAFE.sub('', nm).strip() or ('第%d集' % (len(eps) + 1))
            eps.append((nm, '%s|%s' % (tag, u)))
        return eps

    def _ep_from_json(self, tag, host_url, want=''):
        """苹果CMS JSON 采集：取详情条目里的 vod_play_url 分组"""
        r = self._rq(host_url, None, TO)
        if r is None or r.status_code != 200:
            return [], {}
        try:
            L = r.json().get('list') or []
        except Exception:
            return [], {}
        for v in self._rank(want, L):
            pu = v.get('vod_play_url') or ''
            if not pu:
                continue
            pick = self._pick([g for g in pu.split('$$$') if '$' in g])
            if not pick:
                continue
            eps = self._parse_segs(pick, tag)
            if eps:
                return eps, self._meta_of(v)
        return [], {}

    def _ep_yz(self, tag, name):
        """宇宙站走 XML：先按名查 id，再按 id 取播放列表"""
        r = self._rq(S_YZ + urllib.parse.quote(name), None, TO)
        if r is None or r.status_code != 200:
            return [], {}
        ids = []
        for blk in re.findall(r'<video>(.*?)</video>', r.text, re.S):
            mm = re.search(r'<name>(.*?)</name>', blk, re.S)
            nmv = _RE_CDATA.sub('', mm.group(1)).strip() if mm else ''
            mi = re.search(r'<id>(\d+)</id>', blk)
            if mi and (not name or self._match(name, nmv)):
                ids.append(mi.group(1))
        for vid in ids[:2]:
            r2 = self._rq(S_YZI + vid, None, TO)
            if r2 is None or r2.status_code != 200:
                continue
            grp = [m.group(1) for m in re.finditer(r'<dd flag="[^"]*">(.*?)</dd>', r2.text, re.S)]
            if not grp:
                mu = re.search(r'<play_url>(.*?)</play_url>', r2.text, re.S)
                grp = [mu.group(1)] if mu else []
            pick = self._pick([_RE_CDATA.sub('', g) for g in grp])
            eps = self._parse_segs(pick, tag)
            if eps:
                meta = {}
                ml = re.search(r'<name>(.*?)</name>', r2.text, re.S)
                if ml:
                    meta['name'] = _RE_CDATA.sub('', ml.group(1)).strip()
                mp = re.search(r'<pic>(.*?)</pic>', r2.text, re.S)
                if mp:
                    meta['pic'] = _RE_CDATA.sub('', mp.group(1)).strip()
                return eps, meta
        return [], {}

    def _ep_4kvm(self, name):
        """4K 站：搜索 -> 详情 -> 同前缀分集序列（至少 2 集才算有效）"""
        r = self._rq(S_K4 + '/search?q=' + urllib.parse.quote(name), None, TO)
        if r is None or r.status_code != 200:
            return [], {}
        hit = ''
        for m in _RE_4K_PLAY_TXT.finditer(r.text):
            if name and name in _RE_TAG.sub('', m.group(2)):
                hit = m.group(1)
                break
        if not hit:
            m = _RE_4K_PLAY.search(r.text)
            hit = m.group(1) if m else ''
        if not hit:
            return [], {}
        r2 = self._rq(S_K4 + hit, None, TO)
        if r2 is None or r2.status_code != 200:
            return [], {}
        tm = _RE_TITLE.search(r2.text)
        if name and tm and not self._match(name, _RE_TAG.sub('', tm.group(1))):
            return [], {}
        pre = hit[:7]
        seq = []
        for s2 in _RE_4K_PLAY.findall(r2.text):
            if s2.startswith(pre) and s2 not in seq:
                seq.append(s2)
        if len(seq) < 2:
            return [], {}
        eps = [('第%02d集' % i, 'k4|' + S_K4 + s) for i, s in enumerate(seq, 1)]
        return eps, {'pic': '', 'name': name}

    def _line_eps(self, nm, tag, src, name):
        """单线路探测（任何异常都吞掉，保证其它线路能出结果）"""
        try:
            if tag == 'k4':
                return self._ep_4kvm(name)
            if tag == 'yz':
                return self._ep_yz(tag, name)
            return self._ep_from_json(tag, src + urllib.parse.quote(name), name)
        except Exception as e:
            self.log("  线路 %s 异常: %s" % (nm, e))
            return [], {}

    # ===================== 详情页 =====================
    def detailContent(self, ids, quick='1'):
        vid = str(ids[0] if isinstance(ids, list) else ids or '')
        name = self._unid(vid)
        if not name and not re.match(r'^[zw][A-Za-z0-9_\-=]+$', vid):
            name = vid.strip()   # 兼容直接传片名调试
        if not name:
            self.log("detail: vod_id 解码失败 %s" % vid)
            return {'list': [{'vod_id': vid, 'vod_name': ''}]}

        key = 'd:' + name
        if key in self._c:
            return self._c[key]

        self.log("detail: %s" % name)

        # 8 条线路并行，总预算 TO_DETAIL 秒；超时的进 miss 再补 4 秒
        ex = ThreadPoolExecutor(max_workers=8)
        fus = [ex.submit(self._line_eps, nm, tag, src, name) for nm, tag, src in LINES]
        end = time.time() + TO_DETAIL
        got, metas, miss = {}, {}, []
        for i, fu in enumerate(fus):
            try:
                eps, meta = fu.result(timeout=max(0.5, end - time.time()))
            except Exception:
                eps, meta = [], {}
            if eps:
                got[i] = eps
                if meta:
                    metas[i] = meta
            else:
                miss.append(i)
        for i in miss:
            try:
                eps, meta = fus[i].result(timeout=4)
            except Exception:
                eps, meta = [], {}
            if eps:
                got[i] = eps
                if meta:
                    metas[i] = meta
        ex.shutdown(wait=False)

        # 线路顺序固定按 LINES 落地，TVBox 线路栏顺序即站点优先级
        lines = [(LINES[i][0], got[i]) for i in range(len(LINES)) if i in got]
        self.log("  线路命中: %s" % [(x[0], len(x[1])) for x in lines])

        # 元信息：按线路优先级取第一个非空值，避免不同站字段缺失
        m = {}
        for i in range(len(LINES)):
            mm = metas.get(i)
            if not mm:
                continue
            for k2, v2 in mm.items():
                if v2 and not m.get(k2):
                    m[k2] = v2

        # 8 条线路全空 -> 用「去后缀核心名 / 副标题别名」再搜一轮，严格同名才采用
        mark = ''
        if not lines:
            kws = self._fallback_kws(name, m.get('sub'))
            eps, meta2, tag2, used = self._fallback_eps(kws)
            if eps:
                lines = [(LINE_NAME.get(tag2, tag2) + '·同名', eps)]
                for k2, v2 in (meta2 or {}).items():
                    if v2 and not m.get(k2):
                        m[k2] = v2
                mark = '（%s 同名源）' % used
                self.log("  兜底命中: kw=%s 集数=%d" % (used, len(eps)))
            else:
                self.log("  兜底未命中，该片确无公开源")

        # 片名：APP 建议接口精确命中优先（APP 名带季数更准），其次采集站
        hit_name = ''
        for v in self._suggest(name):
            if (v.get('name') or '').strip() == name:
                hit_name = v.get('name')
                break
        title = hit_name or m.get('name') or name

        # 封面：APP 建议优先，其次采集站，最后按名搜一次量子
        pic = ''
        for v in self._suggest(name):
            if (v.get('name') or '').strip() == name and v.get('pic'):
                pic = v.get('pic')
                break
        pic = self._pic_ok(pic)
        if not pic:
            pic = self._pic_ok(m.get('pic')) or self._pic(name)

        # 简介：采集站正文 -> 简介 -> 空，统一加前缀
        intro = m.get('content') or ''
        content = (INTRO_PREFIX + '\n' + intro) if intro else INTRO_PREFIX
        if not lines:
            content = content + NO_SOURCE_TIP

        total = max([len(x[1]) for x in lines]) if lines else 0
        remarks = m.get('remarks') or (('共%d集' % total) if total else '')
        if not remarks:
            remarks = m.get('sub') or ''   # 副标题兜底，保证卡片上不空
        if not lines:
            remarks = '暂无片源'
        elif mark:
            remarks = (remarks + mark) if remarks else mark.strip('（）')
        d = {
            'vod_id': vid,
            'vod_name': title,
            'vod_sub': m.get('sub') or '',
            'vod_pic': pic,
            'vod_content': content,
            'vod_actor': m.get('actor') or '',
            'vod_director': m.get('director') or '',
            'vod_year': m.get('year') or '',
            'vod_area': m.get('area') or '',
            'vod_lang': m.get('lang') or '',
            'vod_class': m.get('class') or '',
            'vod_score': m.get('score') or '',
            'vod_total': total,
            'vod_remarks': remarks,
        }
        if lines:
            d['vod_play_from'] = '$$$'.join(x[0] for x in lines)
            d['vod_play_url'] = '$$$'.join(
                '#'.join('%s$%s' % (n, u) for n, u in x[1]) for x in lines)

        r = {'list': [d]}
        if lines:
            self._cache_put(key, r)   # 无源结果不缓存，便于下次重试
        self.log("  详情: sub=%s | 集数=%d | 线路=%d" % (d['vod_sub'][:20], total, len(lines)))
        return r

    # ===================== 兜底补源（核心名 / 别名）=====================
    def _core_name(self, s):
        """去书名号、季数、'解说版'等尾巴，得到能对上采集站正名的核心名"""
        raw = s or ''
        out = _RE_BRACKET.sub('', raw)
        out = _RE_SEASON.sub('', out)
        for w in _NAME_SUFFIX:
            out = out.replace(w, '')
        out = out.strip('之-· ')
        return out or _RE_BRACKET.sub('', raw)

    def _num_norm(self, s):
        """数字归一：'二' 与 '2' 互通，避免 '第二季/第2季' 对不上"""
        s = s or ''
        for k, v in _CN_NUM.items():
            s = s.replace(k, v)
        return s

    def _same_name(self, a, b):
        """严格同名判定：核心名相等，或数字归一后相等（不做模糊，防串片）"""
        ca, cb = self._core_name(a), self._core_name(b)
        na, nb = self._norm(ca), self._norm(cb)
        if na and na == nb:
            return True
        na, nb = self._norm(self._num_norm(ca)), self._norm(self._num_norm(cb))
        return bool(na and na == nb)

    def _split_alias(self, sub):
        """副标题里的别名，如 '庆余年2 / Joy of Life 2' -> ['庆余年2']"""
        out = []
        for part in re.split(r'[/|、,，;；]', sub or ''):
            part = part.strip()
            if len(self._norm(part)) >= 2 and not re.match(r'^[A-Za-z0-9\s]+$', part):
                out.append(part)
        return out

    def _fallback_kws(self, name, sub):
        kws = []
        for k in [self._core_name(name)] + self._split_alias(sub):
            if k and len(self._norm(k)) >= 2 and k not in kws:
                kws.append(k)
        return kws[:4]

    def _fallback_eps(self, kws):
        """按核心名/别名逐站严格同名查源，命中返回 (eps, meta, tag, kw)"""
        for kw in kws:
            for src, tag in ((S_LZ, 'lz'), (S_FF, 'ff')):
                try:
                    r = self._rq(src + urllib.parse.quote(kw), None, TO)
                    if r is None or r.status_code != 200:
                        continue
                    L = r.json().get('list') or []
                except Exception:
                    continue
                for v in L:
                    if not self._same_name(kw, v.get('vod_name')):
                        continue
                    pu = v.get('vod_play_url') or ''
                    pick = self._pick([g for g in pu.split('$$$') if '$' in g])
                    eps = self._parse_segs(pick, tag)
                    if eps:
                        return eps, self._meta_of(v), tag, kw
        return [], {}, '', ''

    def _pic(self, name):
        """兜底封面：量子站按名搜图"""
        r = self._rq(S_LZ + urllib.parse.quote(name), None, TO)
        if r is None or r.status_code != 200:
            return ''
        try:
            for v in (r.json().get('list') or []):
                if self._match(name, v.get('vod_name')) and v.get('vod_pic'):
                    return v.get('vod_pic')
        except Exception:
            pass
        return ''

    # ===================== 播放 =====================
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or '')
        tag, _, payload = raw.partition('|')
        real = payload.strip()
        self.log("player: tag=%s url=%s" % (tag, real[:120]))

        # 4K 线路先过 4kys 解析器；解析失败则原样交给播放器再兜底
        pre = TAG_PARSER.get(tag)
        if pre and real.startswith('http'):
            r = self._rq(pre + urllib.parse.quote(real, safe=''),
                         {'user-agent': 'okhttp/3.12.0', 'accept-encoding': 'gzip'}, 12)
            if r is not None:
                try:
                    j = r.json()
                    if str(j.get('code')) == '200' and j.get('url'):
                        real = j.get('url')
                except Exception:
                    mm = _RE_MEDIA.search(r.text or '')
                    if mm:
                        real = mm.group(0)

        if real.startswith('//'):
            real = 'https:' + real

        # 直链可用性预检：200 且非空才直出，否则走 ff.php 换源
        if real.startswith('http') and '49.233.180.127' not in real:
            r = self._rq(real, {'user-agent': UA}, 6)
            if r is None or r.status_code != 200 or len(r.content) < 16:
                alt = self._via_parser(real)
                if alt:
                    self.log("  换源: %s" % alt[:120])
                    real = alt

        return {'parse': 0, 'playUrl': '', 'url': real,
                'header': {'User-Agent': UA}}

    def _via_parser(self, url):
        """万能解析兜底（ff.php 返回 JSON 或裸地址）"""
        r = self._rq(PARSER + '/ff.php?url=' + urllib.parse.quote(url, safe=''),
                     {'user-agent': 'okhttp/3.12.0', 'accept-encoding': 'gzip'}, 12)
        if r is None:
            return ''
        try:
            j = r.json()
            if str(j.get('code')) == '200' and j.get('url'):
                return j.get('url')
        except Exception:
            pass
        return ''

    # ===================== TVBox 钩子 =====================
    def isVideoFormat(self, url):
        if not url:
            return False
        if _RE_VIDEO_EXT.search(url):
            return True
        # 与原版保持一致：无扩展名的直链也交给播放器，不阻断
        return str(url).startswith('http')

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ''

    def progressVideo(self, speed, time, end):
        return False

    def setVideoFlags(self, siteKey, flags):
        return None

    def localProxy(self, param):
        # 全部走直链，无需图片/视频代理
        return None

    def destroy(self):
        try:
            self._c.clear()
        except Exception:
            pass

    def close(self):
        self.destroy()
