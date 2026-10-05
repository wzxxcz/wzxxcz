# coding=utf-8
import sys, re, json, ssl, gzip
import urllib.request as ur
from urllib.parse import unquote, quote, urljoin

sys.path.append('..')

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self, extend=''):
            pass

        def fetch(self, url, headers=None, timeout=10):
            return ''

CTX = ssl._create_unverified_context()


class Spider(BaseSpider):
    name = '1234影视'
    host = 'https://www.1234sp.cc'
    ua = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')
    proxy = 'https://ttss.langfeng888.com'

    CATEGORIES = {
        'A2xeflx0UY1tu': '连续剧',
        'A2mOC0y4HbZ3l': '电影',
        'A2ttqWI1YGgTu': '动漫',
        'A2b7iFz0ozYru': '综艺',
    }

    def __init__(self, extend=''):
        try:
            super(Spider, self).__init__(extend)
        except Exception:
            pass
        self.extend = extend

    def init(self, extend=''):
        if extend:
            self.extend = extend
        return True

    def getName(self):
        return self.name

    # ------------------------------------------------------------------ 网络
    def _get(self, url, referer='', retry=2):
        for _ in range(retry):
            try:
                h = {
                    'User-Agent': self.ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
                if referer:
                    h['Referer'] = referer
                r = ur.urlopen(ur.Request(url, headers=h), timeout=15, context=CTX)
                b = r.read()
                if str(r.headers.get('Content-Encoding', '')).lower() == 'gzip':
                    try:
                        b = gzip.decompress(b)
                    except Exception:
                        pass
                return b.decode('utf-8', 'ignore')
            except Exception:
                continue
        return ''

    def _jget(self, url, referer=''):
        try:
            h = {'User-Agent': self.ua, 'Accept': 'application/json'}
            if referer:
                h['Referer'] = referer
            r = ur.urlopen(ur.Request(url, headers=h), timeout=15, context=CTX)
            return json.loads(r.read().decode('utf-8', 'ignore'))
        except Exception:
            return {}

    # ------------------------------------------------------------------ 工具
    def _fix(self, u):
        return (u or '').replace('&amp;', '&').strip()

    def _abs(self, u, base=None):
        u = self._fix(u)
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        if not u.startswith('http'):
            return urljoin(base or (self.host + '/'), u)
        return u

    def _clean(self, s):
        if not s:
            return ''
        s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
        s = re.sub(r'</p\s*>', '\n', s, flags=re.I)
        s = re.sub(r'<[^>]+>', '', s)
        s = (s.replace('&nbsp;', ' ')
              .replace('&amp;', '&')
              .replace('&lt;', '<')
              .replace('&gt;', '>')
              .replace('&quot;', '"')
              .replace('&#39;', "'")
              .replace('&ldquo;', '“')
              .replace('&rdquo;', '”'))
        s = re.sub(r'[ \t\r\f\v]+', ' ', s)
        s = re.sub(r'\n{2,}', '\n', s)
        return s.strip()

    # ------------------------------------------------------------- 列表解析
    def _parse_list(self, html):
        out = []
        seen = set()
        if not html:
            return out
        for m in re.finditer(r'<a[^>]+href=["\'](/v/([^"\'/]+?))\.html["\'][^>]*>',
                             html, re.I):
            vid = m.group(2)
            href = '/v/%s.html' % vid
            if not vid or href in seen:
                continue
            start = m.start()
            end = html.find('</a>', m.end())
            seg = html[start:end + 4] if end > 0 else html[start:m.end() + 800]

            img = re.search(
                r'<img[^>]*?(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                seg, re.I)
            if not img:
                continue
            pic = self._abs(img.group(1))
            if not pic:
                continue

            name = ''
            nm = re.search(r'<img[^>]*alt=["\']([^"\']*)["\']', seg, re.I)
            if nm:
                name = nm.group(1)
            if not name:
                nm = re.search(r'title=["\']([^"\']*)["\']', m.group(0), re.I)
                if nm:
                    name = nm.group(1)
            if not name and end > 0:
                nm = re.search(r'>([^<>]{1,80})</a>\s*$', seg)
                if nm:
                    name = nm.group(1)

            rm = re.search(
                r'(更新至[^<>"\']*|全集|HD中字|TC中字|第\d+集|完结|全\d+集)',
                seg)
            seen.add(href)
            out.append({
                'vod_id': vid,
                'vod_name': self._clean(name),
                'vod_pic': pic,
                'vod_remarks': rm.group(1) if rm else '',
            })
        return out

    # ------------------------------------------------------------- 首页内容
    def homeContent(self, filter=False):
        return {
            'class': [{'type_id': k, 'type_name': v}
                      for k, v in self.CATEGORIES.items()],
            'filters': {},
        }

    def homeVideoContent(self):
        return {'list': self._parse_list(self._get(self.host + '/'))[:72]}

    def categoryContent(self, tid, pg='1', filter=False, extend=None):
        try:
            page = max(1, int(str(pg)))
        except Exception:
            page = 1
        tid = str(tid or '').strip()
        if tid not in self.CATEGORIES:
            for k, v in self.CATEGORIES.items():
                if v == tid:
                    tid = k
                    break
        if tid not in self.CATEGORIES:
            return {'list': [], 'page': page, 'pagecount': page,
                    'limit': 36, 'total': 0}

        html = self._get('%s/list/%s/%s.html' % (self.host, tid, page),
                         referer=self.host + '/')
        items = self._parse_list(html)
        nxt = bool(re.search(
            r'href=["\'][^"\']*/%s/%d\.html["\']' % (re.escape(tid), page + 1),
            html or ''))
        total = 0
        tm = re.search(r'共\s*(\d+)\s*[部条]', html or '')
        if tm:
            total = int(tm.group(1))
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if (nxt or len(items) >= 20) else page,
            'limit': 36,
            'total': total,
        }

    # ------------------------------------------------------------- 详情内容
    def _parse_intro(self, html):
        """按优先级抽取剧情简介"""
        # 1) 常见容器 class
        patterns = [
            r'<div[^>]*class=["\'][^"\']*(?:detail-content|vod-content|vod-detail|'
            r'content-desc|introduction|desc)[^"\']*["\'][^>]*>(.*?)</div>',
            r'<span[^>]*class=["\'][^"\']*(?:detail-content|introduction|desc)'
            r'[^"\']*["\'][^>]*>(.*?)</span>',
            r'<p[^>]*class=["\'][^"\']*(?:detail-content|introduction|desc)'
            r'[^"\']*["\'][^>]*>(.*?)</p>',
            r'<div[^>]*id=["\'](?:desc|content|intro|introduction)["\'][^>]*>(.*?)</div>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I | re.S)
            if m:
                c = self._clean(m.group(1))
                if c:
                    return c

        # 2) “简介 / 剧情介绍”关键字后面的一段
        for pat in [
            r'(?:剧情简介|内容简介|简介|剧情介绍|剧情)[：:]?\s*(?:</?[^>]+>\s*)*([^<]{5,})',
            r'(?:剧情简介|内容简介|简介|剧情介绍|剧情)[：:]?\s*<[^>]+>\s*([^<]{5,})',
        ]:
            m = re.search(pat, html, re.S)
            if m:
                c = self._clean(m.group(1))
                if c:
                    return c

        # 3) meta description 兜底
        m = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.I)
        if m:
            return self._clean(m.group(1))
        m = re.search(
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']',
            html, re.I)
        if m:
            return self._clean(m.group(1))
        return ''

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids).strip()
        vod = {
            'vod_id': vid, 'vod_name': '', 'vod_pic': '', 'vod_remarks': '',
            'vod_year': '', 'vod_area': '', 'vod_director': '', 'vod_actor': '',
            'vod_content': '', 'vod_play_from': '', 'vod_play_url': '',
        }
        if not vid:
            return {'list': [vod]}

        page_url = '%s/v/%s.html' % (self.host, vid)
        html = self._get(page_url, referer=self.host + '/')
        if not html:
            return {'list': [vod]}

        # 片名
        hm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if hm:
            vod['vod_name'] = self._clean(hm.group(1))
        if not vod['vod_name']:
            tm = re.search(r'<title>([^<>]+?)\s*(?:在线观看|全集|-\s*|\|)', html, re.I)
            if tm:
                vod['vod_name'] = self._clean(tm.group(1))

        # 海报
        pm = re.search(
            r'<div[^>]*class=["\'][^"\']*(?:detail-pic|vod-pic|poster|pic)'
            r'[^"\']*["\'][^>]*>(.*?)</div>', html, re.I | re.S)
        if pm:
            im = re.search(
                r'<img[^>]*?(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                pm.group(1), re.I)
            if im:
                vod['vod_pic'] = self._abs(im.group(1))
        if not vod['vod_pic']:
            im = re.search(
                r'<img[^>]*?(?:data-original|data-src|src)=["\']([^"\']+)["\']',
                html, re.I)
            if im:
                vod['vod_pic'] = self._abs(im.group(1))

        # 导演 / 主演
        m = re.search(r'<dt>\s*导演\s*</dt>\s*<dd>(.*?)</dd>', html, re.S)
        if m:
            vod['vod_director'] = self._clean(m.group(1))
        m = re.search(r'<dt>\s*主演\s*</dt>\s*<dd>(.*?)</dd>', html, re.S)
        if m:
            vod['vod_actor'] = self._clean(m.group(1))

        # 地区 / 年份
        m = re.search(r'<dt>\s*地区\s*/\s*年份\s*</dt>\s*<dd>(.*?)</dd>', html, re.S)
        if m:
            parts = [x.strip() for x in self._clean(m.group(1)).split('/')]
            if len(parts) >= 1:
                vod['vod_area'] = parts[0]
            if len(parts) >= 2:
                vod['vod_year'] = parts[1]

        # 状态
        m = re.search(r'<dt>\s*状态\s*</dt>\s*<dd>(.*?)</dd>', html, re.S)
        if m:
            vod['vod_remarks'] = self._clean(m.group(1))
        if not vod['vod_remarks']:
            m = re.search(r'(更新至[^<>"\']*|全集|完结|HD中字)', html)
            if m:
                vod['vod_remarks'] = m.group(1)

        # 简介（重点补全）
        vod['vod_content'] = self._parse_intro(html)

        # 播放列表
        line_map = {}
        seen = set()
        for href, name in re.findall(
                r'href=["\'](/p/[^"\']*)["\'][^<>]*>([^<>]+)</a>', html):
            m = re.match(r'/p/%s/(\d+)/(\d+)\.html' % re.escape(vid), href)
            if not m or href in seen:
                continue
            seen.add(href)
            ln = m.group(1)
            ep = m.group(2)
            epn = self._clean(name)
            if not epn or epn in ('立即播放', '播放', '点击播放'):
                epn = '第%02d集' % int(ep)
            line_map.setdefault(ln, []).append((int(ep), epn, href))

        froms, urls = [], []
        for ln in sorted(line_map.keys(), key=lambda x: int(x)):
            eps = sorted(line_map[ln], key=lambda x: x[0])
            froms.append('线路%s' % ln)
            urls.append('#'.join('%s$%s' % (e[1], e[2]) for e in eps))
        if froms:
            vod['vod_play_from'] = '$$$'.join(froms)
            vod['vod_play_url'] = '$$$'.join(urls)

        return {'list': [vod]}

    # ------------------------------------------------------------- 搜索
    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = max(1, int(str(pg)))
        except Exception:
            page = 1
        k = str(key or '').strip()
        if not k:
            return {'list': [], 'page': page}
        q = quote(k)
        items = self._parse_list(
            self._get('%s/?s=%s&page=%d' % (self.host, q, page),
                      referer=self.host + '/'))
        if not items:
            items = self._parse_list(
                self._get('%s/search/%s/%s.html' % (self.host, q, page),
                          referer=self.host + '/'))
        if not items:
            items = self._parse_list(
                self._get('%s/search.php?wd=%s&page=%d' % (self.host, q, page),
                          referer=self.host + '/'))
        return {'list': items, 'page': page}

    # ------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        h = {'User-Agent': self.ua}
        pid = str(id or '').strip()
        if not pid:
            return {'parse': 0, 'url': '', 'header': h}
        if not pid.startswith('/p/'):
            return {'parse': 0, 'url': self._abs(pid), 'header': h}

        page = self.host + pid
        html = self._get(page, referer=self.host + '/')
        m = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html or '', re.I)
        if not m:
            return {'parse': 1, 'url': page, 'header': h}

        src = self._fix(m.group(1))
        if not src.startswith('http'):
            src = 'https:' + src if src.startswith('//') else self.host + src

        vm = re.search(r'[?&]v=([^&]+)', src)
        if vm and 'proxy/' not in src:
            d = self._jget('%s/proxy/%s' % (self.proxy, vm.group(1)))
            u = self._fix(str(d.get('url', '') or ''))
            if u:
                return {'parse': 0, 'url': u, 'header': h}
            return {'parse': 1, 'url': src, 'header': h}

        um = re.search(r'[?&]url=([^&]+)', src)
        if um:
            return {'parse': 0, 'url': unquote(self._fix(um.group(1))),
                    'header': h}

        return {'parse': 1, 'url': src, 'header': h}

    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return (any(u.endswith(x) for x in
                    ['.m3u8', '.mp4', '.ts', '.flv', '.mkv'])
                or u.endswith('/'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def destroy(self):
        pass
