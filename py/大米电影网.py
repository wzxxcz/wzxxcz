# coding=utf-8
"""
大米电影网 | TVBox Python 爬虫（Scrapling 引擎）
由 Spider AutoGen for Scrapling 自动生成

运行环境: pip install "scrapling[fetchers]" && scrapling install
"""
import re
import json
import urllib.parse

try:
    from base.spider import Spider
except ImportError:
    import requests

    class Spider(object):
        def fetch(self, url, headers=None, **kw):
            r = requests.get(url, headers=headers, timeout=kw.get('timeout', 15), verify=False)
            r.encoding = 'utf-8'
            return r

        def log(self, *a):
            print('[spider]', *a)

from scrapling.fetchers import Fetcher
from scrapling.parser import Selector

HOST = 'https://www.hn-ntm.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
EXTRA_HEADERS = {}
INTRO_PREFIX = '🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！'
DETAIL_PREFIX = '/vod/'
# 分类路径模板：粘贴了哪个分类页就写死哪个；没贴的走 DEFAULT_CAT_TPL 兜底
CAT_TPLS = {
    '7': '/vodshow/7--------2---{page}.html',
    '13': '/vodshow/13--------2---{page}.html',
    '27': '/vodshow/27--------2---{page}.html',
    '31': '/vodshow/31--------2---{page}.html',
}
DEFAULT_CAT_TPL = '/vodshow/{tid}--------2---{page}.html'
SEARCH_TPL = '/vodsearch/{wd}----------{page}---.html'

CLASSES = [
    {"type_id": '1', "type_name": '电影'},
    {"type_id": '6', "type_name": '动作电影'},
    {"type_id": '7', "type_name": '喜剧电影'},
    {"type_id": '8', "type_name": '爱情电影'},
    {"type_id": '9', "type_name": '科幻电影'},
    {"type_id": '10', "type_name": '恐怖电影'},
    {"type_id": '11', "type_name": '剧情电影'},
    {"type_id": '12', "type_name": '战争电影'},
    {"type_id": '21', "type_name": '纪录电影'},
    {"type_id": '26', "type_name": '动漫电影'},
    {"type_id": '2', "type_name": '电视剧'},
    {"type_id": '13', "type_name": '国产剧'},
    {"type_id": '14', "type_name": '港剧'},
    {"type_id": '15', "type_name": '台剧'},
    {"type_id": '16', "type_name": '日剧'},
    {"type_id": '22', "type_name": '韩剧'},
    {"type_id": '23', "type_name": '泰剧'},
    {"type_id": '24', "type_name": '美剧'},
    {"type_id": '25', "type_name": '海外剧'},
    {"type_id": '3', "type_name": '综艺'},
    {"type_id": '27', "type_name": '大陆综艺'},
    {"type_id": '28', "type_name": '日韩综艺'},
    {"type_id": '29', "type_name": '港台综艺'},
    {"type_id": '30', "type_name": '欧美综艺'},
    {"type_id": '4', "type_name": '动漫'},
    {"type_id": '31', "type_name": '国产动漫'},
    {"type_id": '32', "type_name": '日韩动漫'},
    {"type_id": '33', "type_name": '港台动漫'},
    {"type_id": '34', "type_name": '欧美动漫'},
    {"type_id": '35', "type_name": '海外动漫'},
]

_YEARS = [{'n': '全部', 'v': ''}] + [{'n': y, 'v': y} for y in ('2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010', '2009', '2008', '2007')]
_AREAS = [{'n': '全部', 'v': ''}] + [{'n': a, 'v': a} for a in ('中国大陆', '美国', '日本', '韩国', '中国香港', '中国台湾', '英国', '法国')]

FILTERS = {
    c["type_id"]: [
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "area", "name": "地区", "value": _AREAS},
    ] for c in CLASSES
}

_RE_M3U8 = re.compile(r'["\']?url["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.I)


class Spider(Spider):

    def getName(self):
        return '大米电影网'

    def init(self, extend=''):
        self.headers = {'User-Agent': UA, 'Referer': HOST + '/'}
        self._play_cache = {}

    def _get(self, url, render=False, wait_selector=None):
        """用 Scrapling 抓页面；render=True 时走无头浏览器跑 JS。"""
        try:
            if render:
                from scrapling.fetchers import StealthyFetcher
                return StealthyFetcher.fetch(url, headless=True,
                                             wait_selector=wait_selector,
                                             timeout=20000, disable_resources=True)
            return Fetcher.get(url, headers={**self.headers, **EXTRA_HEADERS}, impersonate='chrome',
                               stealthy_headers=True, timeout=15)
        except Exception as e:
            self.log('fetch fail:', url, e)
            return None

    def _fix(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('http'): return u
        if u.startswith('/'): return HOST + u
        return urllib.parse.urljoin(HOST + '/', u)

    def _cards(self, page):
        """把 Scrapling Response/Selector 解析成 TVBox 列表。"""
        items = []
        for a in page.css('a'):
            href_raw = a.attrib.get('href') or ''
            # 通用详情链接形态：/任意前缀/数字.html
            if not re.match(r'^/[A-Za-z][\w-]*/\d+\.(?:html?|htm)$', href_raw):
                continue
            href = self._fix(href_raw)
            name = a.attrib.get('title') or ''
            img = a.css('img')[0] if a.css('img') else None
            if not name and img is not None:
                name = img.attrib.get('alt', '')
            if not name:
                name = (a.text or '').strip()[:60]
            if not name or not href: continue
            pic = ''
            if img is not None:
                pic = img.attrib.get('data-original') or img.attrib.get('data-src') or img.attrib.get('src', '')
            items.append({'vod_id': href, 'vod_name': name[:100],
                          'vod_pic': self._fix(pic), 'vod_remarks': ''})
        return items

    def homeContent(self, filter=False):
        return {'class': CLASSES, 'filters': FILTERS}

    def homeVideoContent(self):
        page = self._get(HOST + '/')
        return {'list': self._cards(page) if page is not None else []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except Exception: extend = {}
        extend = {k: v for k, v in (extend or {}).items() if v and v != '全部'}
        url = HOST + (CAT_TPLS.get(str(tid)) or DEFAULT_CAT_TPL)
        url = url.replace('{tid}', str(tid)).replace('{page}', str(page))
        if extend:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(extend)
        html_page = self._get(url)
        videos = self._cards(html_page) if html_page is not None else []
        return {'list': videos, 'page': page, 'pagecount': 999, 'limit': 24, 'total': 999}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        url = HOST + SEARCH_TPL.replace('{wd}', urllib.parse.quote(key)).replace('{page}', str(page))
        html_page = self._get(url)
        return {'list': self._cards(html_page) if html_page is not None else [],
                'page': page, 'pagecount': 999}

    def detailContent(self, ids):
        if not ids: return {'list': []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith('http') else self._fix(vod_id)
        page = self._get(url)
        if page is None: return {'list': []}
        name = ''
        h1 = page.css('h1')
        if h1: name = h1[0].text.strip()[:120]
        if not name and page.css('title'): name = page.css('title::text').get() or ''
        name = name.split('_')[0].split('-')[0].strip() or vod_id
        pic = ''
        og = page.css('meta[property=\"og:image\"]')
        if og: pic = self._fix(og[0].attrib.get('content', ''))
        if not pic and page.css('img'):
            img = page.css('img')[0]
            pic = self._fix(img.attrib.get('data-original') or img.attrib.get('src', ''))
        content = ''
        md = page.css('meta[name=description]')
        if md: content = (md[0].attrib.get('content') or '').strip()
        all_text = page.get_all_text()
        def _grab(k):
            m = re.search(k + r'\s*[:：]\s*([^,，。;；\n]{1,80})', all_text)
            return m.group(1).strip() if m else ''
        director, actor = _grab('导演'), _grab('主演')
        year_m = re.search(r'年份\s*[:：]\s*\D*((?:19|20)\d{2})', all_text)
        year = year_m.group(1) if year_m else ''
        area = _grab('地区')
        groups, seen = {}, set()
        for a in page.css('a'):
            href = a.attrib.get('href', '')
            if not href or href.startswith(('javascript', '#')): continue
            ep = a.text.strip()
            if not re.search(r'第\s*\d+\s*[集话期]|play|vodplay', ep + ' ' + href, re.I): continue
            ep_url = self._fix(href)
            if ep_url in seen: continue
            seen.add(ep_url)
            origin = a.attrib.get('data-origin') or 'default'
            groups.setdefault(origin, []).append((ep or '第1集', ep_url))
        play_from, play_url = [], []
        for o, eps in groups.items():
            play_from.append(o if o != 'default' else '默认线路')
            play_url.append('#'.join('%s$%s' % (n, h) for n, h in eps))
        full_content = (INTRO_PREFIX + chr(10) + content) if (content and INTRO_PREFIX) else (content or INTRO_PREFIX)
        vod = {'vod_id': vod_id, 'vod_name': name, 'vod_pic': pic,
               'vod_content': full_content,
               'vod_director': director, 'vod_actor': actor,
               'vod_year': year, 'vod_area': area,
               'vod_remarks': '%d条线路' % len(groups),
               'vod_play_from': '$$$'.join(play_from) or '默认线路',
               'vod_play_url': '$$$'.join(play_url)}
        return {'list': [vod] if play_url else []}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else self._fix(id)
        now = int(__import__('time').time())
        cache = getattr(self, '_play_cache', None) or {}
        if play_page in cache and now - cache[play_page][0] < 600:
            return cache[play_page][1]
        page = self._get(play_page)
        url = ''
        if page is not None:
            blobs = page.css('script::text').getall() + [page.get_all_text()]
            for blob in blobs:
                m = _RE_M3U8.search(blob)
                if m:
                    url = m.group(1)
                    break
        if url and url.startswith('/'): url = HOST + url
        if url:
            res = {'parse': 0, 'playUrl': '', 'url': url,
                   'header': json.dumps({'User-Agent': UA, 'Referer': HOST + '/'})}
        else:
            res = {'parse': 1, 'playUrl': '', 'url': play_page, 'header': '{}'}
        if not hasattr(self, '_play_cache'): self._play_cache = {}
        self._play_cache[play_page] = (now, res)
        return res

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url

    def destroy(self):
        pass
    def close(self):
        self.destroy()
