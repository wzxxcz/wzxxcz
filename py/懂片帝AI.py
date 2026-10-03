# -*- coding: utf-8 -*-
"""
懂片帝 TVBox Spider
站点: https://dongpian20.com/ (懂片帝 / 懂片帝AI, React SPA)
形态: API 站, 全部走 JSON 接口, 无需登录(匿名可调), 无需 Cookie
"""
import re
import json
import base64
import time
import secrets
import hashlib
import hmac
import html as _html
import urllib.request
import urllib.parse
import urllib.error


class Spider:
    # 图片直连模式，避免本地代理卡死
    DIRECT_MODE = True

    _BASE = 'https://dongpian20.com'
    _SIGN_SECRET = '8b9a908a05eac640e1ee06f52acaa741bfe4ba9e004eeffdbeb635e532e06666'
    _CLIENT_HEADERS = {
        'x-ai-movie-client-name': 'movie-search-frontend',
        'x-ai-movie-client-version': '1.0.0',
        'x-ai-movie-build-version': 'dongpiandi-v2026.09.30.1-dbb1f9857565-web',
        'x-ai-movie-protocol-version': '2026-07-05.library-v2.playback-v1',
    }
    _UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    _PAGE_LIMIT = 20

    _KINDS = [
        ('series', '电视剧'), ('movie', '电影'), ('short_drama', '短剧'),
        ('anime', '动漫'), ('variety', '综艺'), ('documentary', '纪录片'),
    ]
    _GENRES = {
        'movie': ['剧情', '喜剧', '动作', '爱情', '科幻', '悬疑', '惊悚', '恐怖',
                  '犯罪', '奇幻', '冒险', '战争', '家庭', '古装', '武侠'],
        'series': ['剧情', '爱情', '悬疑', '犯罪', '喜剧', '古装', '动作', '奇幻',
                   '都市', '韩剧', '美剧', '日剧', '欧美剧', '国产剧'],
        'anime': ['国产动漫', '日韩动漫', '日本动漫', '动作', '奇幻', '冒险', '剧情',
                  '喜剧', '热血', '科幻', '恋爱', '悬疑'],
        'variety': ['综艺', '真人秀', '大陆综艺', '国产综艺', '日韩综艺', '欧美综艺',
                    '音乐', '脱口秀', '晚会', '游戏', '美食'],
        'short_drama': ['剧情', '爱情', '古装', '悬疑', '喜剧', '都市'],
        'documentary': ['纪录片', '历史', '自然', '人文', '科技'],
    }
    _AREAS = {
        'movie': ['中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国',
                  '英国', '法国', '印度'],
        'series': ['中国大陆', '美国', '韩国', '日本', '英国', '泰国', '中国台湾'],
        'anime': ['中国大陆', '日本', '美国'],
        'variety': ['中国大陆', '韩国', '美国'],
        'short_drama': ['中国大陆'],
        'documentary': ['中国大陆', '美国', '英国', '日本'],
    }
    _YEARS = [str(y) for y in range(2026, 2014, -1)]
    _SORTS = [('全部', ''), ('热门趋势', 'trending')]

    def __init__(self):
        self._proxy = None

    # ================= 签名与请求 =================
    def _sign_headers(self, method, path):
        ts = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        msg = '{0}\n{1}\n{2}\n{3}'.format(method.upper(), path, ts, nonce)
        sig = hmac.new(self._SIGN_SECRET.encode('utf-8'), msg.encode('utf-8'),
                       hashlib.sha256).hexdigest()
        h = dict(self._CLIENT_HEADERS)
        h['x-ai-movie-timestamp'] = ts
        h['x-ai-movie-nonce'] = nonce
        h['x-ai-movie-signature'] = sig
        return h

    def _api(self, method, path, body=None):
        headers = {
            'User-Agent': self._UA,
            'Referer': self._BASE + '/',
            'Accept': 'application/json',
        }
        headers.update(self._sign_headers(method, path))
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        handlers = []
        if self._proxy:
            handlers.append(urllib.request.ProxyHandler(
                {'http': self._proxy, 'https': self._proxy}))
        opener = urllib.request.build_opener(*handlers)
        for _ in range(2):
            try:
                req = urllib.request.Request(self._BASE + path, data=data,
                                             headers=headers, method=method.upper())
                with opener.open(req, timeout=15) as resp:
                    raw = resp.read()
                return json.loads(raw.decode('utf-8', 'ignore'))
            except Exception:
                pass
        return None

    def _get(self, path):
        return self._api('GET', path)

    # ================= 小工具 =================
    def _clean(self, s):
        if not s:
            return ''
        s = _html.unescape(s)
        s = re.sub(r'<[^>]+>', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    def _safe_title(self, s):
        return (s or '').replace('$', '').replace('#', '').strip()

    def _norm_id(self, ids):
        v = ids
        if isinstance(v, dict):
            v = v.get('id') or v.get('vid') or ''
        if isinstance(v, (list, tuple)):
            v = v[0] if v else ''
        if isinstance(v, str):
            s = v.strip()
            if s.startswith('[') or s.startswith('{'):
                try:
                    d = json.loads(s)
                    if isinstance(d, dict):
                        s = d.get('id') or d.get('vid') or ''
                    elif isinstance(d, list) and d:
                        s = str(d[0])
                except Exception:
                    pass
            v = s
        v = str(v or '').strip()
        if v.startswith('/v1/catalog/'):
            return v
        if v.startswith('av_'):
            return '/v1/catalog/' + v
        return v

    def _card(self, c):
        vid = c.get('detail_url') or ''
        title = c.get('title') or ''
        if not vid or not title:
            return None
        pic = c.get('poster_url') or ''
        remark = c.get('remarks') or ''
        if not remark:
            remark = str(c.get('year') or '')
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._pic(pic),
            'vod_remarks': remark,
        }

    def _filters(self, kind):
        def _opts(vals):
            return [{'n': '全部', 'v': ''}] + [{'n': v, 'v': v} for v in vals]

        def _sorts():
            return [{'n': n, 'v': v} for n, v in self._SORTS]

        return [
            {'key': 'genre', 'name': '类型',
             'value': _opts(self._GENRES.get(kind, self._GENRES['movie']))},
            {'key': 'area', 'name': '地区',
             'value': _opts(self._AREAS.get(kind, self._AREAS['movie']))},
            {'key': 'year', 'name': '年份', 'value': _opts(self._YEARS)},
            {'key': 'sort', 'name': '排序', 'value': _sorts()},
        ]

    # ================= 播放线路解析 =================
    def _resolve_lines(self, token):
        """
        根据 token 解析播放线路，返回线路列表。
        过滤掉需要登录的线路，只保留 resolved=true 且 url 可用的线路。
        """
        if not token:
            return []
        path = '/v1/playback/resolve/{0}?view=compact'.format(
            urllib.parse.quote(str(token), safe=''))
        d = self._get(path)
        if not isinstance(d, dict):
            return []

        out, seen = [], set()
        for l in d.get('line_options') or []:
            if not isinstance(l, dict):
                continue
            # 跳过需要登录的线路
            if l.get('resolve_required'):
                continue
            # 跳过未成功解析的线路
            if not l.get('resolved'):
                continue
            url_kind = l.get('url_kind') or ''
            if url_kind not in ('m3u8', 'mp4'):
                continue
            url = (l.get('url') or '').strip()
            if not url.startswith('http'):
                continue
            name = self._safe_title(l.get('label') or l.get('play_from') or '线路')
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({
                'name': name,
                'play_from': l.get('play_from') or '',
                'url': url,
            })
        return out

    # ================= 简介提取 =================
    def _extract_desc(self, d):
        if not isinstance(d, dict):
            return ''
        raw = ''
        for key in ('description', 'desc', 'summary', 'intro',
                    'content', 'overview', 'plot', 'synopsis'):
            v = d.get(key)
            if isinstance(v, str) and v.strip():
                raw = v.strip()
                break
        if not raw:
            parts = []
            for k in ('title', 'year', 'area'):
                v = d.get(k)
                if v:
                    parts.append(str(v))
            genres = d.get('genres')
            if isinstance(genres, list):
                parts.append('/'.join(str(g) for g in genres if g))
            return ' '.join(parts).strip()
        text = _html.unescape(raw)
        text = re.sub(r'<[^>]+>', '', text)
        text = (text.replace('&nbsp;', ' ').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'")
                    .replace('&lt;', '<').replace('&gt;', '>'))
        for sw in ['详情', '立即播放', '报错', '收藏', '扫一扫',
                   '排序', '播放地址', '第01集', '第1集']:
            if sw in text:
                text = text.split(sw)[0]
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:3000]

    # ================= 封面/本地代理 =================
    def _proxy_base(self):
        try:
            fn = getattr(self, 'getProxyUrl', None)
            if callable(fn):
                b = fn() or ''
                if b:
                    return b
        except Exception:
            pass
        return ''

    def _pic(self, url):
        if not url:
            return ''
        if url.startswith('data:'):
            return ''
        if self.DIRECT_MODE:
            return url
        b64 = base64.urlsafe_b64encode(url.encode('utf-8')).decode().rstrip('=')
        base = self._proxy_base()
        if base:
            sep = '&' if '?' in base else '?'
            return base + sep + 'key=img/' + b64
        return 'http://127.0.0.1:9978/proxy?do=local&key=img/' + b64

    _IMG_PLACEHOLDER = base64.b64decode(
        'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

    def _proxy_target(self, param):
        p = param
        if isinstance(p, bytes):
            p = p.decode('utf-8', 'ignore')
        if isinstance(p, str):
            s = p.strip()
            d = None
            try:
                d = json.loads(s)
            except Exception:
                d = None
            if isinstance(d, dict):
                p = d
            else:
                if '?' in s:
                    s = s.split('?', 1)[1]
                p = dict(urllib.parse.parse_qsl(s))
        if not isinstance(p, dict):
            return '', ''
        kind, raw = '', ''
        k = str(p.get('key') or '')
        if k.startswith('img/'):
            kind, raw = 'img', k[4:]
        elif k.startswith('hls/'):
            kind, raw = 'hls', k[4:]
        elif p.get('type') == 'hls' and p.get('url'):
            kind, raw = 'hls', str(p.get('url'))
        if not raw:
            return '', ''
        try:
            target = base64.urlsafe_b64decode(
                raw + '=' * (-len(raw) % 4)).decode('utf-8')
        except Exception:
            return '', ''
        return kind, target

    def _serve_image(self, url):
        try:
            h = {'User-Agent': self._UA}
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                ct = (r.headers.get('Content-Type') or 'image/jpeg').split(';')[0].strip()
            if data:
                return [200, ct or 'image/jpeg', data, {}]
        except Exception:
            pass
        return [200, 'image/gif', self._IMG_PLACEHOLDER, {}]

    def _serve_hls(self, url):
        try:
            h = {'User-Agent': self._UA, 'Referer': self._BASE + '/'}
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=20) as r:
                text = r.read().decode('utf-8', 'ignore')
            base = url.rsplit('/', 1)[0] + '/'
            out = []
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith('#'):
                    s = urllib.parse.urljoin(base, s)
                elif s.startswith('#') and 'URI="' in s:
                    s = re.sub(r'URI="([^"]+)"',
                               lambda m: 'URI="{0}"'.format(
                                   urllib.parse.urljoin(base, m.group(1))), s)
                out.append(s)
            return [200, 'application/vnd.apple.mpegurl',
                    '\n'.join(out).encode('utf-8'), {}]
        except Exception:
            return [502, 'text/plain', b'fetch failed', {}]

    # ================= 14 壳方法 =================
    def getName(self):
        return '懂片帝'

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower().split('?')[0]
        return u.endswith(('.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov'))

    def manualVideoCheck(self):
        return False

    def init(self, extend):
        self._proxy = None
        try:
            s = (extend or '').strip() if isinstance(extend, str) else ''
            if s.startswith('{'):
                d = json.loads(s)
                p = d.get('proxy') or ''
                if p:
                    self._proxy = p if '://' in p else 'http://' + p
            elif s and '://' in s:
                self._proxy = s
        except Exception:
            self._proxy = None
        return None

    def destroy(self):
        return None

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': n} for k, n in self._KINDS]
        filters = {k: self._filters(k) for k, _ in self._KINDS}
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            d = self._get('/v1/browse/catalog?' + urllib.parse.urlencode(
                {'kind': 'movie', 'sort': 'trending', 'window': 'day',
                 'page': 1, 'limit': 12}))
            cards = (d or {}).get('cards') or []
            items = [c for c in (self._card(x) for x in cards) if c]
            return {'list': items}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        kind = (tid or 'movie').strip() or 'movie'
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        ext = extend or {}
        if isinstance(ext, str):
            try:
                ext = json.loads(ext) if ext.strip() else {}
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}
        params = {'kind': kind, 'page': pg, 'limit': self._PAGE_LIMIT}
        for k in ('genre', 'area', 'year', 'sort'):
            v = ext.get(k)
            if v:
                params[k] = v
        d = self._get('/v1/browse/catalog?' + urllib.parse.urlencode(params))
        if not isinstance(d, dict):
            return {'list': [], 'page': pg, 'pagecount': 999999,
                    'limit': self._PAGE_LIMIT, 'total': 999999}
        cards = d.get('cards') or []
        items = [c for c in (self._card(x) for x in cards) if c]
        pag = d.get('pagination') or {}
        total = pag.get('total') or 0
        try:
            pagecount = max(1, -(-int(total) // self._PAGE_LIMIT))
        except Exception:
            pagecount = 999999
        return {'list': items, 'page': pg, 'pagecount': pagecount,
                'limit': self._PAGE_LIMIT, 'total': total or 999999}

    def detailContent(self, ids):
        vid = self._norm_id(ids)
        if not vid:
            return {'list': []}
        d = self._get(vid)
        if not isinstance(d, dict):
            return {'list': []}

        episodes = []
        if isinstance(d.get('episodes'), list):
            episodes = d['episodes']
        else:
            offset, guard = 0, 0
            while guard < 5:
                e = self._get(vid + '/episodes?' + urllib.parse.urlencode(
                    {'offset': offset, 'limit': 48}))
                if not isinstance(e, dict):
                    break
                eps = e.get('episodes') or []
                episodes.extend(eps)
                pag = e.get('episode_pagination') or {}
                if not pag.get('has_more'):
                    break
                offset += pag.get('returned_count') or len(eps) or 48
                guard += 1

        lines = []
        if episodes:
            tok = (episodes[0] or {}).get('token') or ''
            lines = self._resolve_lines(tok)

        ep_items = []
        for ep in episodes:
            if not isinstance(ep, dict):
                continue
            t = self._safe_title(ep.get('title') or ep.get('display_name') or '正片')
            tok = ep.get('token') or ''
            if t and tok:
                ep_items.append('{0}${1}'.format(t, tok))

        vod_content = self._extract_desc(d)

        vod = {
            'vod_id': vid,
            'vod_name': d.get('title') or '',
            'vod_pic': self._pic(d.get('poster_url') or ''),
            'vod_year': str(d.get('year') or ''),
            'vod_area': d.get('area') or '',
            'vod_remarks': d.get('remarks') or d.get('update_status') or '',
            'vod_actor': ' '.join(d.get('actors') or []),
            'vod_director': ' '.join(d.get('directors') or []),
            'vod_content': vod_content,
        }
        genres = d.get('genres')
        if isinstance(genres, list) and genres:
            vod['type_name'] = '/'.join(str(g) for g in genres if g)

        if lines and ep_items:
            vod['vod_play_from'] = '$$$'.join(l['name'] for l in lines)
            vod['vod_play_url'] = '$$$'.join('#'.join(ep_items) for _ in lines)
        else:
            vod['vod_play_from'] = ''
            vod['vod_play_url'] = ''
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        try:
            if str(pg) != '1':
                return {'list': []}
        except Exception:
            pass
        key = (key or '').strip()
        if not key:
            return {'list': []}
        d = self._get('/v1/suggest?' + urllib.parse.urlencode(
            {'q': key, 'limit': 20}))
        if not isinstance(d, dict):
            return {'list': []}
        vids = []
        for s in d.get('suggestions') or []:
            if not isinstance(s, dict) or s.get('type') != 'title':
                continue
            t = (s.get('target') or {}).get('variant_id') or ''
            if t and t not in vids:
                vids.append(t)
        items = []
        for t in vids[:12]:
            dd = self._get('/v1/catalog/' + urllib.parse.quote(t, safe=''))
            if not isinstance(dd, dict) or not dd.get('title'):
                continue
            remark = dd.get('remarks') or ''
            if not remark:
                remark = '{0} {1}'.format(dd.get('year') or '',
                                         dd.get('area') or '').strip()
            items.append({
                'vod_id': '/v1/catalog/' + t,
                'vod_name': dd.get('title') or '',
                'vod_pic': self._pic(dd.get('poster_url') or ''),
                'vod_remarks': remark,
            })
        return {'list': items}

    # ================= 播放解析（核心修复） =================
    def playerContent(self, flag, id, vipFlags):
        token = (id or '').strip()
        header = {
            'User-Agent': self._UA,
            'Referer': self._BASE + '/',
            'Origin': self._BASE,
            'Cookie': '',
        }

        if not token:
            return {'parse': 0, 'playUrl': '', 'url': '',
                    'header': header, 'msg': '空 id'}

        # 如果 id 本身就是直链
        if token.startswith('http') and ('.m3u8' in token or '.mp4' in token):
            return {'parse': 1, 'playUrl': token, 'url': token, 'header': header}

        # 剥离 "集名$token" 前缀
        if '$' in token:
            token = token.split('$')[-1]

        # 解析线路
        lines = self._resolve_lines(token)
        if not lines:
            return {'parse': 1, 'playUrl': '', 'url': '',
                    'header': header, 'msg': '未找到可播放线路'}

        # 优先匹配当前 flag 对应的线路
        # 注意：flag 是线路显示名称，play_from 是内部标识，需要同时匹配
        pick = None
        for l in lines:
            if l['name'] == flag or l['play_from'] == flag:
                pick = l
                break
        if pick is None:
            pick = lines[0]

        url = pick['url']

        # 对于 m3u8，先尝试 HEAD 请求验证链接是否可直接访问
        if '.m3u8' in url:
            try:
                req = urllib.request.Request(url, method='HEAD', headers=header)
                with urllib.request.urlopen(req, timeout=8) as r:
                    if r.status == 200:
                        return {'parse': 0, 'playUrl': url, 'url': url, 'header': header}
            except Exception:
                pass
            # HEAD 失败，走嗅探模式
            return {'parse': 1, 'playUrl': url, 'url': url, 'header': header}

        # 非 m3u8 链接
        return {'parse': 0, 'playUrl': url, 'url': url, 'header': header}

    def localProxy(self, param):
        kind, target = self._proxy_target(param)
        if not target:
            return [404, 'text/plain', b'bad param', {}]
        if kind == 'img':
            return self._serve_image(target)
        return self._serve_hls(target)

    def action(self, action):
        return None
