# -*- coding: utf-8 -*-
# ============ 魔法盒子 / 魔法影视 (l98.cn) —— 最终版 ============
import sys, re, json, time, hashlib, urllib.parse
from concurrent.futures import ThreadPoolExecutor
try:
    import requests
except ImportError:
    requests = None
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            import urllib.request as _urq
            r = _urq.Request(url, headers=headers or {})
            return _urq.urlopen(r, timeout=15)

SITE      = 'http://l98.cn'
CMS_API   = 'https://api.wsyzy.net/api.php/provide/vod'
UA        = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
REFERER   = 'http://l98.cn/'
PIC_REFERER = 'http://l98.cn/'
MF_SALT   = 'mfys-api-guard-v1'
MF_CLIENT = 'web'

SEARCH_SOURCES = [
    'tvbox-py://source-616fbcbf9e',
    'tvbox-py://wencai',
    'tvbox-py://source-4eb17c91b4',
    'tvbox-py://source-0ad659640c',
    'tvbox-py://source-cb4888cc81',
    'tvbox-py://source-90e25e2716',
]
CLASSES = [
    {'type_id': '6,7,8,9,10,11,12',      'type_name': '电影'},
    {'type_id': '13,14,15,16,17,18,23',  'type_name': '电视剧'},
    {'type_id': '25,26,27,28',           'type_name': '综艺'},
    {'type_id': '29,30,31,44,45',        'type_name': '动漫'},
    {'type_id': '39',                    'type_name': '动画片'},
    {'type_id': '54,64,65,66,67,68,69,73', 'type_name': '短剧'},
    {'type_id': '62',                    'type_name': '4K电影'},
    {'type_id': '70',                    'type_name': '邵氏电影'},
    {'type_id': '71',                    'type_name': 'Netflix电影'},
    {'type_id': '72',                    'type_name': 'Netflix剧集'},
]
FILTERS = {}
VIDEO_EXTS = 'm3u8|mp4|flv|mkv|ts'

class Spider(Spider):
    def init(self, extend=''):
        self.base = SITE.rstrip('/')
        self.cms = CMS_API
        self.ua = UA
        self.ref = REFERER or (self.base + '/')
        self.pic_ref = PIC_REFERER or ''
        self._proxy = ''
        cfg = {}
        if isinstance(extend, dict):
            cfg = extend
        elif isinstance(extend, str) and extend.strip().startswith('{'):
            try:
                j = json.loads(extend)
                if isinstance(j, dict):
                    cfg = j
            except Exception:
                cfg = {}
        if cfg.get('site'):
            self.base = str(cfg['site']).rstrip('/')
        if cfg.get('cms'):
            self.cms = str(cfg['cms'])
        if cfg.get('proxy'):
            self._proxy = str(cfg['proxy'])
        self.sess = requests.Session() if requests else None
        self._src_cache = None

    def _headers(self, extra=None):
        h = {'User-Agent': self.ua, 'Referer': self.ref}
        if extra:
            h.update(extra)
        return h

    def _get(self, url, headers=None, timeout=15000):
        hd = self._headers(headers)
        try:
            if requests:
                r = requests.get(url, headers=hd, timeout=timeout / 1000.0, verify=False)
                r.encoding = 'utf-8'
                return r.text
            r = self.fetch(url, headers=hd, timeout=timeout)
            return r.text if hasattr(r, 'text') else str(r)
        except Exception:
            return ''

    def _mf_sign(self, method, pathname, ts):
        h = 2166136261
        text = MF_SALT + '|' + method.upper() + '|' + pathname + '|' + str(ts)
        for ch in text:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        if h == 0:
            return '0'
        digs = '0123456789abcdefghijklmnopqrstuvwxyz'
        out = ''
        while h:
            out = digs[h % 36] + out
            h //= 36
        return out

    def _api(self, path_qs, data=None, method=None, timeout=20):
        m = (method or ('POST' if data is not None else 'GET')).upper()
        p = urllib.parse.urlparse(path_qs)
        ts = int(time.time() * 1000)
        hd = {
            'User-Agent': self.ua,
            'Referer': self.ref,
            'Accept': 'application/json, text/plain, */*',
            'X-MF-TS': str(ts),
            'X-MF-Sign': self._mf_sign(m, p.path, ts),
            'X-MF-Client': MF_CLIENT,
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode('utf-8')
            hd['Content-Type'] = 'application/json'
        try:
            if requests:
                r = requests.request(m, self.base + path_qs, data=body, headers=hd,
                                     timeout=timeout, verify=False)
                if r.status_code == 200:
                    return r.json()
                return {}
            import urllib.request as _urq
            req = _urq.Request(self.base + path_qs, data=body, headers=hd)
            resp = _urq.urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode('utf-8', 'ignore'))
        except Exception:
            return {}

    def _cms(self, params):
        q = urllib.parse.urlencode(params)
        txt = self._get(self.cms + '/?' + q)
        if not txt:
            return {}
        try:
            return json.loads(txt)
        except Exception:
            return {}

    # ================= ★ 图片处理 =================
    def _pic(self, u):
        if not u:
            return ''
        u = str(u).strip()
        if not u:
            return ''
        if u.startswith('data:'):
            return u
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('/'):
            u = self.base.rstrip('/') + u
        elif not (u.startswith('http://') or u.startswith('https://')):
            u = self.base.rstrip('/') + '/' + u.lstrip('/')
        return re.sub(r'[\s\r\n]+', '', u)

    def _get_pic(self, v):
        if not isinstance(v, dict):
            return ''
        for k in ('vod_pic', 'vod_pic_slide', 'vod_pic_thumb',
                  'pic', 'img', 'thumbnail', 'cover', 'poster', 'vod_pic_url'):
            val = v.get(k)
            if val:
                p = self._pic(val)
                if p:
                    return p
        return ''

    def _pic_proxied(self, url):
        """★ 图片通过 wsrv.nl 公网 CDN 中转，规避壳子对特定域名的兼容问题"""
        if not url or url.startswith('data:'):
            return url
        enc = urllib.parse.quote(url, safe='')
        return 'https://wsrv.nl/?url=' + enc + '&output=jpg&q=88'
    # =============================================

    def _mk(self, v, api=''):
        vid = str(v.get('vod_id') or '')
        if api:
            vid = api + '|' + vid
        return {
            'vod_id': vid,
            'vod_name': v.get('vod_name') or '',
            'vod_pic': self._pic_proxied(self._get_pic(v)),
            'vod_remarks': v.get('vod_remarks') or '',
        }

    def _sources(self):
        if self._src_cache is None:
            j = self._api('/api/tvbox/sources', method='GET')
            self._src_cache = j.get('data') or []
        return self._src_cache

    def homeContent(self, filter=False):
        r = {'class': CLASSES[:]}
        if filter and FILTERS:
            r['filters'] = FILTERS
        r['list'] = self.homeVideoContent().get('list', [])
        return r

    def homeVideoContent(self):
        j = self._cms({'ac': 'videolist', 'pg': 1})
        items = [self._mk(v) for v in (j.get('list') or [])]
        return {'list': items}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1
        j = self._cms({'ac': 'videolist', 't': str(tid or ''), 'pg': pn})
        items = [self._mk(v) for v in (j.get('list') or [])]
        try:
            pc = int(j.get('pagecount') or pn)
        except Exception:
            pc = pn
        return {'page': pn, 'pagecount': max(pc, pn), 'limit': 20,
                'total': pc * 20 if items else 0, 'list': items}

    def detailContent(self, ids, quick='1'):
        raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids or '').strip()
        if not raw:
            return {'list': []}
        if '|' in raw:
            api, vid = raw.split('|', 1)
        else:
            api, vid = '', raw
        if api:
            for _ in range(2):
                j = self._api('/api/detail', {'api': api, 'ids': vid})
                v = j.get('data') or {}
                if isinstance(v, dict) and v.get('vod_name'):
                    return {'list': [self._detail_dict(api + '|' + vid, v)]}
                time.sleep(0.3)
            return {'list': []}
        j = self._cms({'ac': 'detail', 'ids': vid})
        lst = j.get('list') or []
        if not lst:
            return {'list': []}
        return {'list': [self._detail_dict(vid, lst[0])]}

    def _detail_dict(self, out_id, v):
        return {
            'vod_id': out_id,
            'vod_name': v.get('vod_name') or '',
            'vod_pic': self._pic_proxied(self._get_pic(v)),
            'vod_year': str(v.get('vod_year') or ''),
            'vod_area': v.get('vod_area') or '',
            'vod_class': v.get('type_name') or v.get('vod_class') or '',
            'vod_director': v.get('vod_director') or '',
            'vod_actor': v.get('vod_actor') or '',
            'vod_content': (v.get('vod_blurb') or v.get('vod_content') or '').strip(),
            'vod_remarks': v.get('vod_remarks') or '',
            'vod_play_from': v.get('vod_play_from') or '',
            'vod_play_url': v.get('vod_play_url') or '',
        }

    def searchContent(self, key, quick=False, pg='1'):
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1
        kw = str(key or '').strip()
        if not kw:
            return {'list': [], 'page': pn, 'pagecount': pn}

        def _one(api):
            for _ in range(2):
                j = self._api('/api/search', {'api': api, 'keyword': kw, 'page': pn})
                data = j.get('data') or []
                if data:
                    return [self._mk(v, api) for v in data]
                time.sleep(0.2)
            return []

        items, seen = [], set()
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                results = list(ex.map(_one, SEARCH_SOURCES))
        except Exception:
            results = [_one(a) for a in SEARCH_SOURCES]
        for res in results:
            for it in res:
                name = (it['vod_name'] or '').strip()
                vid = str(it['vod_id'] or '')
                if not vid or not name:
                    continue
                if kw not in name:
                    continue
                if re.search(r'访问新站|请访问|新站|广告|公告', name):
                    continue
                k = name + '|' + vid.split('|')[-1]
                if k in seen:
                    continue
                seen.add(k)
                it['_exact'] = 1 if name == kw else 0
                items.append(it)
        items.sort(key=lambda x: -x.get('_exact', 0))
        for it in items:
            it.pop('_exact', None)
        return {'list': items, 'page': pn, 'pagecount': pn + (1 if items else 0)}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '')
        if '$' in url:
            url = url.split('$', 1)[1]
        full = self.base + url if url.startswith('/') else url
        if not full.startswith('http'):
            return {'parse': 0, 'url': full}
        hd = {'User-Agent': self.ua, 'Referer': self.ref}
        if '.m3u8' in full or re.search(r'\.(?:mp4|flv|mkv|avi|ts|mov|m4v)(?:\?|$)', full, re.I):
            return {'parse': 0, 'url': full, 'header': hd}
        proxy = self.getProxyUrl()
        if proxy:
            return {'parse': 0, 'url': proxy + '&type=mfys&url=' + urllib.parse.quote(full, safe=''),
                    'header': hd}
        r = self._probe(full)
        if r:
            return {'parse': 0, 'url': r, 'header': hd}
        return {'parse': 0, 'url': full, 'header': hd}

    def _probe(self, url):
        try:
            txt = self._get(url, headers={'Referer': self.ref})
        except Exception:
            return ''
        if not txt:
            return ''
        s = txt.lstrip()
        if s.startswith('#EXTM3U'):
            for ln in s.splitlines():
                t = ln.strip()
                if t and not t.startswith('#'):
                    return url if t.startswith('http') else ''
            return ''
        if 'ftyp' in s[:32]:
            j = self._api('/api/tvbox/resolve/' + url.rsplit('/', 1)[-1], method='GET')
            u = str(j.get('url') or '')
            return (self.base + u) if u.startswith('/') else u
        return ''

    def getProxyUrl(self):
        if getattr(self, '_proxy', ''):
            return self._proxy
        return 'http://127.0.0.1:9978/proxy?do=py'

    def isVideoFormat(self, url):
        if not url:
            return False
        if '.m3u8' in url:
            return True
        return bool(re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, url, re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ''

    def destroy(self):
        try:
            if self.sess is not None:
                self.sess.close()
        except Exception:
            pass
        self._src_cache = None

    def progressVideo(self, speed, time_, end):
        return False

    def setVideoFlags(self, siteKey, flags):
        try:
            self._siteKey = siteKey
            self._vflags = flags
        except Exception:
            pass

    def localProxy(self, param):
        import urllib.parse as _up
        params = {}
        if isinstance(param, dict):
            for k, v in param.items():
                params[str(k)] = str(v)
        else:
            s = str(param or '')
            for prefix in ('?do=py&', 'do=py&', 'do=py?', '?do=py?'):
                if s.startswith(prefix):
                    s = s[len(prefix):]
                    break
            for kv in s.split('&'):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    params[_up.unquote(k.strip())] = _up.unquote(v.strip())

        p = params.get('url') or params.get('key') or ''
        if '%' in p:
            p = _up.unquote(p)
        tp = params.get('type', '').lower()

        if not p:
            return {'code': 403, 'content': b'', 'headers': {}}

        if tp == 'img' or re.search(r'\.(?:jpg|jpeg|png|webp|gif|bmp|avif)(?:\?|$)', p, re.I):
            hd = {
                'User-Agent': self.ua,
                'Referer': self.pic_ref or self.ref,
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
            try:
                if requests:
                    r = requests.get(p, headers=hd, timeout=15, verify=False)
                    return {'code': r.status_code, 'content': r.content,
                            'headers': {'Content-Type': r.headers.get('Content-Type', 'image/jpeg'),
                                        'Cache-Control': 'public, max-age=86400'}}
                import urllib.request as _urq
                resp = _urq.urlopen(_urq.Request(p, headers=hd), timeout=15)
                return {'code': 200, 'content': resp.read(),
                        'headers': {'Content-Type': resp.headers.get('Content-Type', 'image/jpeg'),
                                    'Cache-Control': 'public, max-age=86400'}}
            except Exception:
                return {'code': 404, 'content': b'', 'headers': {}}

        if (tp == 'mfys' or '.m3u8' in p
                or '/api/tvbox/play/' in p or '/api/tvbox/resolve/' in p):
            return self._proxy_m3u8(p)

        hd = {'User-Agent': self.ua, 'Referer': self.pic_ref or self.ref, 'Accept': '*/*'}
        try:
            if requests:
                r = requests.get(p, headers=hd, timeout=25, verify=False)
                ct = r.headers.get('Content-Type', 'application/octet-stream')
                return {'code': r.status_code, 'content': r.content,
                        'headers': {'Content-Type': ct}}
            import urllib.request as _urq
            resp = _urq.urlopen(_urq.Request(p, headers=hd), timeout=25)
            return {'code': 200, 'content': resp.read(),
                    'headers': {'Content-Type': resp.headers.get('Content-Type', 'application/octet-stream')}}
        except Exception:
            return {'code': 404, 'content': b'', 'headers': {}}

    def _proxy_m3u8(self, url):
        hd = {'User-Agent': self.ua, 'Referer': self.ref, 'Accept': '*/*'}
        try:
            if requests:
                r = requests.get(url, headers=hd, timeout=25, verify=False)
                raw = r.content
            else:
                import urllib.request as _urq
                resp = _urq.urlopen(_urq.Request(url, headers=hd), timeout=25)
                raw = resp.read()
        except Exception:
            return {'code': 404, 'content': b'', 'headers': {}}
        body = raw
        head = body.lstrip()[:64].lower()
        if not head.startswith(b'#extm3u'):
            if head.startswith(b'<!doctype') or head.startswith(b'<html'):
                return {'code': 502, 'content': b'', 'headers': {}}
            ct = 'video/mp4' if body[:8].endswith(b'ftyp') else 'application/octet-stream'
            return {'code': 200, 'content': body, 'headers': {'Content-Type': ct}}
        origin = re.match(r'https?://[^/]+', url)
        origin = origin.group(0) if origin else self.base
        out = []
        for ln in body.decode('utf-8', 'ignore').splitlines():
            s = ln.strip()
            if s.startswith('/'):
                out.append(origin + s)
            else:
                out.append(ln)
        return {'code': 200, 'content': '\n'.join(out).encode('utf-8'),
                'headers': {'Content-Type': 'application/vnd.apple.mpegurl'}}
