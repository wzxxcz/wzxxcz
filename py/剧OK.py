# -*- coding: utf-8 -*-
def _dk8(s):
    import base64 as _b
    return bytes(c ^ 35 for c in _b.b64decode(s)).decode('utf-8')




import json
import re
import sys
import os
from urllib.parse import quote, unquote, urlencode

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self, query_params=None, t4_api=None):
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''

        def fetch(self, url, params=None, headers=None, cookies=None, timeout=10, **kw):
            import requests
            return requests.get(url, params=params, headers=headers, cookies=cookies,
                                timeout=timeout, verify=False)

try:
    import requests
except ImportError:
    requests = None


class Spider(BaseSpider):
    HOST = _dk8('S1dXU1AZDAxJVkxIEA1XTFM=')
    UA = (_dk8('bkxZSk9PQgwWDRMDC29KTVZbGANiTUdRTEpHAxIQGANzSltGTwMUCgNiU1NPRnRGQWhKVwwWEBQNEBUDC2hrd25vDwNPSkhGA2RGQEhMCgNgS1FMTkYMEhEXDRMNEw0TA25MQUpPRgNwQkVCUUoMFhAUDRAV'))

    
    DISCLAIMER = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

    PAGE_SIZE = 30

    SITE_NAMES = {
        _dk8('UkpaSg=='): _dk8('xKuSxoaky6qZ'), _dk8('UlI='): _dk8('y6ady42My4SlyoGy'), _dk8('WkxWSFY='): _dk8('x5+7yqaU'), _dk8('Sk5ETA=='): _dk8('y6mxxb2/d3U='),
        _dk8('TkRXVQ=='): _dk8('y6mxxb2/d3U='), _dk8('T0ZQS0o='): _dk8('x5qzy4Sl'), _dk8('QUpPSkFKT0o='): _dk8('xrC3xrCK'), _dk8('QUpPSkFKT0oS'): _dk8('xrC3xrCK'),
        _dk8('R0xWWkpN'): _dk8('xam1yryQ'), _dk8('QE1XVQ=='): _dk8('xoeNy4Sl'), _dk8('UExLVg=='): _dk8('xbO/xKiz'), _dk8('U1NXVQ=='): _dk8('c3PLhKXKgbI='), _dk8('EhoTFg=='): _dk8('EhoTFsS3lsaeksSesg=='),
    }
    SITE_SORT = [_dk8('UkpaSg=='), _dk8('UlI='), _dk8('WkxWSFY='), _dk8('Sk5ETA=='), _dk8('TkRXVQ=='), _dk8('T0ZQS0o='),
                 _dk8('QUpPSkFKT0o='), _dk8('QUpPSkFKT0oS'), _dk8('UExLVg=='), _dk8('R0xWWkpN'), _dk8('QE1XVQ=='), _dk8('U1NXVQ=='), _dk8('EhoTFg==')]

    T_MOVIE = [_dk8('xrW/xqqE'), _dk8('xKuSxaCm'), _dk8('xqmLx56/'), _dk8('xaKzxaO1'), _dk8('xISyxpqY'), _dk8('xqqExaCm'), _dk8('xKmMxJ6J'), _dk8('xoakxpqY'), _dk8('xau7x5mq'), _dk8('xaGPxLWy'),
               _dk8('xqmLxLeY'), _dk8('xbWky6qZ'), _dk8('xJmJxp62'), _dk8('x5+Dy42T'), _dk8('xY6vy6u9'), _dk8('xqyHy4Cm'), _dk8('xq2lxqyR'), _dk8('xaCpxaG5'), _dk8('x5+FxLOl'), _dk8('xqaVx5i1')]
    T_TV = [_dk8('y4ujxaCm'), _dk8('xqqExaCm'), _dk8('x5+FxLOl'), _dk8('xrW/xqqE'), _dk8('xaGPxLWy'), _dk8('yqCexpuh'), _dk8('xqKVxqCs'), _dk8('xqyHy4Cm'), _dk8('xqW4x5mo'), _dk8('y46Fxq+J'),
            _dk8('xq2lxqyR'), _dk8('xqmSxpy0'), _dk8('xIa9y4y+'), _dk8('y5Ouxau7'), _dk8('yr6xxbuG'), _dk8('xo2VxpmO'), _dk8('xqmLx56/'), _dk8('xaCmxbqM'), _dk8('xY6Fx52D'), _dk8('xISyxpqY'), _dk8('xqaVx5i1')]
    T_VA = [_dk8('y6eSxqyAxISj'), _dk8('xL+8x5mZxISj'), _dk8('xbO9xI+y'), _dk8('yqOqxISj'), _dk8('xqaIxq6F'), _dk8('y42cy5Or'), _dk8('xaCmxae8'), _dk8('xLe8xZeY'), _dk8('xbq5x5+5'), _dk8('yryQx5qz'),
            _dk8('y6Kvxr+Z'), _dk8('xJ2tyoC8'), _dk8('xbSVxpO5'), _dk8('xZubxaus'), _dk8('xpOyxqec'), _dk8('x56wy6GR'), _dk8('xJmJxo29'), _dk8('xISyxba6'), _dk8('xbiRy6qZ'), _dk8('xY6vy6u9'),
            _dk8('y5eBxJis'), _dk8('xZKey56F'), _dk8('xbGOxamG'), _dk8('xqaVx5i1')]
    T_AN = [_dk8('xKCOy4Kj'), _dk8('xISyxpqY'), _dk8('xJ2txpOyxoaQ'), _dk8('yo63xpqY'), _dk8('xJisxqab'), _dk8('xqmSxpy0'), _dk8('xpOyxqec'), _dk8('xqWxyrqK'), _dk8('xbO9xI+y'), _dk8('xa2LxLOl'),
            _dk8('xaKoxKuS'), _dk8('xZGYxaer'), _dk8('xpqYxaCQ'), _dk8('xYOCxriO'), _dk8('xqmLxKqK'), _dk8('xb+Zxau7'), _dk8('x5mRxo6z'), _dk8('xqecxY6v'), _dk8('y5yzxqmL'), _dk8('xaGPxLWy'),
            _dk8('xaOJxKqK'), _dk8('xau7x5mq'), _dk8('xLipxbqZ'), _dk8('yr6xxbuG'), _dk8('xIiGy4y+'), _dk8('xIi9xamj'), _dk8('xqmLx56/'), _dk8('xIedx5+5'), _dk8('xqyoxaCm'),
            _dk8('xL+8x5mZxKqr'), _dk8('xLeWxp6SxKqr'), _dk8('bHVixKqr'), _dk8('d3XEqqs='), _dk8('xbWTxLaJxqmLxLeY'), _dk8('xo2vxJiwxqmLxLeY')]
    A_MOVIE = [_dk8('xoeEyrql'), _dk8('yoW6xZuM'), _dk8('xqyTxZqd'), _dk8('xZCTxrie'), _dk8('xJ2txrie'), _dk8('yryKxrie'), _dk8('xbSGxb+P'), _dk8('xZC2xrie'), _dk8('y6iSxrie'), _dk8('xp2Uxrie'), _dk8('xq6TxpmF'), _dk8('xqaVx5i1')]
    A_TV = [_dk8('xoeEyrql'), _dk8('yoW6xZuM'), _dk8('xqyTxZqd'), _dk8('xZCTxrie'), _dk8('xbSGxb+P'), _dk8('yryKxrie'), _dk8('xJ2txrie'), _dk8('y6iSxrie'), _dk8('xbWTxqmDxr6C')]
    A_VA = [_dk8('xoeEyrql'), _dk8('yoW6xZuM'), _dk8('xqyTxZqd'), _dk8('xbSGxb+P'), _dk8('xY+ExJ2t')]
    A_AN = [_dk8('xoeEyrql'), _dk8('xbSGxb+P'), _dk8('xJ2txrie')]
    YEARS = [_dk8('ERMRFQ=='), _dk8('ERMRFg=='), _dk8('ERMRFw=='), _dk8('ERMREA=='), _dk8('ERMREQ=='), _dk8('ERMREg=='), _dk8('ERMREw=='),
             _dk8('ERMSGg=='), _dk8('ERMSGw=='), _dk8('ERMSFA=='), _dk8('ERMSFQ=='), _dk8('ERMSFg==')]
    SORTS = [(_dk8('xa+qxb+jxbWT'), _dk8('UUJNSE9CV0ZQVw==')), (_dk8('xa+qxKCOxpmF'), _dk8('UUJNSEtMVw==')), (_dk8('xa+qy4ynxqul'), _dk8('UUJNSFNMSk1X'))]

    def init(self, extend=""):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        self.extend = extend or ""
        self.timeout = 15
        self._cache = {}        
        self._session = None    
        self._pending = {}      
        return {_dk8('UFdCV1ZQ'): 0}

    def getName(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return _dk8('07ymnMybrMaqhGxo')

    
    def _headers(self, ref=None):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        h = {
            _dk8('dlBGUQ5iREZNVw=='): self.UA,
            _dk8('YkBARlNX'): (_dk8('V0ZbVwxLV05PD0JTU09KQEJXSkxNDFtLV05PCFtOTw9CU1NPSkBCV0pMTQxbTk8YUh4TDRoPSk5CREYMQlVKRQ9KTkJERgxURkFTDwkMCRhSHhMNGw==')),
            _dk8('YkBARlNXDm9CTURWQkRG'): _dk8('WUsOYG0PWUsYUh4TDRo='),
        }
        if ref:
            h[_dk8('cUZFRlFGUQ==')] = ref
        return h

    def _sess(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        if self._session is not None:
            return self._session
        if requests is None:
            self._session = False
            return self._session
        try:
            s = requests.Session()
            s.verify = False
            s.headers.update({_dk8('dlBGUQ5iREZNVw=='): self.UA})
            
            try:
                s.get(self.HOST + _dk8('DA=='), timeout=self.timeout, headers=self._headers())
            except Exception:
                pass
            self._session = s
        except Exception:
            self._session = False
        return self._session

    def _get(self, url, ref=None):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        if url in self._cache:
            return self._cache[url]
        ref = ref or (self.HOST + _dk8('DA=='))
        text = ""
        s = self._sess()
        if s:
            try:
                text = s.get(url, headers=self._headers(ref), timeout=self.timeout).text or ""
            except Exception:
                text = ""
        else:
            try:
                rsp = self.fetch(url, headers=self._headers(ref), timeout=self.timeout)
                text = getattr(rsp, _dk8('V0ZbVw=='), "") or ""
            except Exception:
                text = ""
        
        if text and _dk8('VEpNR0xUDU9MQEJXSkxNDUtRRkU=') in text[:400]:
            try:
                if s:
                    text = s.get(url, headers=self._headers(ref), timeout=self.timeout).text or ""
            except Exception:
                pass
        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[url] = text
        return text

    def _get_json(self, url, ref=None):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        try:
            return json.loads(self._get(url, ref))
        except Exception:
            return None

    
    @staticmethod
    def _txt(s):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        if s is None:
            return ""
        if isinstance(s, list):
            s = _dk8('wKOi').join(str(x) for x in s)
        return str(s).strip()

    @staticmethod
    def _unesc(s):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        if not s:
            return ''
        t = s.replace(_dk8('f1YTExEV'), _dk8('BQ==')).replace(_dk8('fww='), _dk8('DA=='))
        try:
            import html as _h
            t = _h.unescape(t)
        except Exception:
            q = chr(34)
            t = t.replace(_dk8('BQ==') + _dk8('UlZMVxg='), q).replace(_dk8('BQ==') + _dk8('ABAaGA=='), chr(39))
            t = t.replace(_dk8('BQ==') + _dk8('T1cY'), _dk8('Hw==')).replace(_dk8('BQ==') + _dk8('RFcY'), _dk8('HQ=='))
        return t

    def _pic(self, u):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        u = self._txt(u)
        if not u:
            return ""
        if u.startswith(_dk8('DAw=')):
            return _dk8('S1dXU1AZ') + u
        return u

    @staticmethod
    def _strip_tags(s):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return re.sub(_dk8('H3h9HX4IHQ=='), "", s or "").strip()

    def _card(self, m, cat=_dk8('Eg==')):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        vid = self._txt(m.get(_dk8('Skc=')))
        if not vid:
            return None
        cat = self._txt(cat) or _dk8('Eg==')
        c = m.get(_dk8('TkxVSkZAQldGRExRWg==')) or []
        remark = _dk8('DA==').join(self._txt(x) for x in c[:2]) if c else self._txt(m.get(_dk8('U1ZBR0JXRg==')))[:10]
        return {
            _dk8('VUxHfEpH'): _dk8('BlAHBlA=') % (cat, vid),
            _dk8('VUxHfE1CTkY='): self._txt(m.get(_dk8('V0pXT0Y='))),
            _dk8('VUxHfFNKQA=='): self._pic(m.get(_dk8('QEdNQExVRlE=')) or m.get(_dk8('QExVRlE='))),
            _dk8('VUxHfFFGTkJRSFA='): remark,
        }

    def _filters(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        def grp(key, name, vals):
            if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
                return None
            return {_dk8('SEZa'): key, _dk8('TUJORg=='): name,
                    _dk8('VUJPVkY='): [{_dk8('TQ=='): _dk8('xqaLyqCL'), _dk8('VQ=='): ""}] + [{_dk8('TQ=='): v, _dk8('VQ=='): v} for v in vals]}

        def year_grp():
            if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
                return None
            return grp(_dk8('WkZCUQ=='), _dk8('xpqXx5ie'), self.YEARS)

        sort_grp = {_dk8('SEZa'): _dk8('QVo='), _dk8('TUJORg=='): _dk8('xa2xxpms'),
                    _dk8('VUJPVkY='): [{_dk8('TQ=='): n, _dk8('VQ=='): v} for n, v in self.SORTS]}
        return {
            _dk8('Eg=='): [grp(_dk8('QE9CUFA='), _dk8('xJKYxr2o'), self.T_MOVIE), grp(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), self.A_MOVIE), year_grp(), sort_grp],
            _dk8('EQ=='): [grp(_dk8('QE9CUFA='), _dk8('xJKYxr2o'), self.T_TV), grp(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), self.A_TV), year_grp(), sort_grp],
            _dk8('EA=='): [grp(_dk8('QE9CUFA='), _dk8('xJKYxr2o'), self.T_VA), grp(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), self.A_VA), year_grp(), sort_grp],
            _dk8('Fw=='): [grp(_dk8('QE9CUFA='), _dk8('xJKYxr2o'), self.T_AN), grp(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), self.A_AN), year_grp(), sort_grp],
        }

    
    def homeContent(self, filter):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('QE9CUFA='): [], _dk8('T0pQVw=='): []}
        classes = [
            {_dk8('V1pTRnxKRw=='): _dk8('Eg=='), _dk8('V1pTRnxNQk5G'): _dk8('xLeWxp6S')},
            {_dk8('V1pTRnxKRw=='): _dk8('EQ=='), _dk8('V1pTRnxNQk5G'): _dk8('xLeWy4SlxqqE')},
            {_dk8('V1pTRnxKRw=='): _dk8('EA=='), _dk8('V1pTRnxNQk5G'): _dk8('xJify6qZ')},
            {_dk8('V1pTRnxKRw=='): _dk8('Fw=='), _dk8('V1pTRnxNQk5G'): _dk8('xqmLxZ+I')},
        ]
        return {_dk8('QE9CUFA='): classes, _dk8('RUpPV0ZRUA=='): self._filters() if filter else {}}

    def homeVideoContent(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('T0pQVw=='): []}
        html = self._get(self.HOST + _dk8('DA=='))
        return {_dk8('T0pQVw=='): self._cards_from_html(html)}

    def _cards_from_html(self, html):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        out, seen = [], set()
        if not html:
            return out
        pat = re.compile(
            _dk8('H0J4fR1+CUBPQlBQHgFVSkdGTA5AQlFHeH0BfgkBeH0dfglLUUZFHgEMR0ZXQkpPDAt/RwgKDAt4Yg55Qg5ZEw4afggKAQsNCRwKHwxCHQ=='), re.S)
        t_pat = re.compile(_dk8('H0sQeH0dfgkdC3h9H34ICh8MSxAd'))
        p_pat = re.compile(_dk8('H0pORHh9HX4IUFFAHgELeH0BfggKAQ=='))
        r_pat = re.compile(_dk8('QE9CUFAeAUJBUExPVldGeH0BfgkBeH0dfgkdC3h9H35YEg8RE14KHw=='))
        for _cat, ent, seg in pat.findall(html):
            if ent in seen:
                continue
            seen.add(ent)
            tm, pm, rm = t_pat.search(seg), p_pat.search(seg), r_pat.search(seg)
            out.append({
                _dk8('VUxHfEpH'): _dk8('BlAHBlA=') % (_cat, ent),
                _dk8('VUxHfE1CTkY='): self._unesc(tm.group(1).strip()) if tm else ent,
                _dk8('VUxHfFNKQA=='): self._pic(pm.group(1)) if pm else "",
                _dk8('VUxHfFFGTkJRSFA='): self._unesc(rm.group(1).strip()) if rm else "",
            })
        return out[:30]

    
    def categoryContent(self, tid, pg, filter, extend):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('T0pQVw=='): [], _dk8('U0JERg=='): 1, _dk8('U0JERkBMVk1X'): 1, _dk8('T0pOSlc='): 0, _dk8('V0xXQk8='): 0}
        pg = max(1, int(pg or 1))
        try:
            fl = json.loads(extend) if isinstance(extend, str) and extend.strip() else (extend or {})
        except Exception:
            fl = {}
        params = {_dk8('QEJXakc='): str(tid), _dk8('U0JERg=='): str(pg), _dk8('UEpZRg=='): str(self.PAGE_SIZE)}
        for fkey, pkey in ((_dk8('QE9CUFA='), _dk8('V1pTRg==')), (_dk8('QlFGQg=='), _dk8('QlFGQg==')), (_dk8('WkZCUQ=='), _dk8('WkZCUQ==')), (_dk8('QVo='), _dk8('UExRVw=='))):
            v = self._txt(fl.get(fkey))
            if v and v != _dk8('xqaLyqCL'):
                params[pkey] = v
        data = self._get_json(self.HOST + _dk8('DEJTSgxFSk9XRlEc') + urlencode(params)) or {}
        movies = data.get(_dk8('TkxVSkZQ')) or []
        total = int(data.get(_dk8('V0xXQk8=')) or 0)
        lst = [c for c in (self._card(m, tid) for m in movies) if c]
        if total:
            pagecount = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        else:
            pagecount = pg + 1 if len(lst) >= self.PAGE_SIZE else pg
        return {_dk8('T0pQVw=='): lst, _dk8('U0JERg=='): pg, _dk8('U0JERkBMVk1X'): pagecount,
                _dk8('T0pOSlc='): self.PAGE_SIZE, _dk8('V0xXQk8='): total or 999999}

    
    def searchContent(self, key, quick, pg=1):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('T0pQVw=='): []}
        pg = max(1, int(pg or 1))
        url = _dk8('BlAMQlNKDFBGQlFASxxSHgZQBVNCREYeBkc=') % (self.HOST, quote(key), pg)
        data = self._get_json(url) or {}
        lst = []
        for it in data.get(_dk8('UUZQVk9XUA==')) or []:
            if it.get(_dk8('SlBmW1dGUU1CTw==')):
                play = self._txt(it.get(_dk8('VUxHfFNPQlp8VlFP')))
                if _dk8('Bw==') in play:
                    play = play.split(_dk8('Bw=='), 1)[1]
                if not play:
                    continue
                name = self._strip_tags(self._txt(it.get(_dk8('VUxHfE1CTkY='))))
                ext_id = _dk8('RltXBwZQBwZQBwZQ') % (
                    quote(self._txt(it.get(_dk8('UExWUUBGaEZa'))) or _dk8('QUU='), safe=""),
                    quote(name, safe=""),
                    quote(play.strip(), safe=""))
                lst.append({
                    _dk8('VUxHfEpH'): ext_id,
                    _dk8('VUxHfE1CTkY='): name,
                    _dk8('VUxHfFNKQA=='): self._pic(it.get(_dk8('VUxHfFNKQA=='))),
                    _dk8('VUxHfFFGTkJRSFA='): self._txt(it.get(_dk8('VUxHfFFGTkJRSFA='))),
                })
            else:
                cat = self._txt(it.get(_dk8('QEJXfEpH'))) or _dk8('Eg==')
                ent = self._txt(it.get(_dk8('Rk18Skc='))) or self._txt(it.get(_dk8('Skc=')))
                if not ent:
                    continue
                name = self._strip_tags(self._txt(it.get(_dk8('V0pXT0Y=')) or it.get(_dk8('V0pXT0Z3W1c='))))
                sites = it.get(_dk8('VUpTcEpXRg==')) or []
                remark = self._txt(it.get(_dk8('WkZCUQ==')))
                if sites:
                    remark = (self.SITE_NAMES.get(sites[0], sites[0]) + _dk8('4ZQ=') + remark) if remark else \
                             self.SITE_NAMES.get(sites[0], sites[0])
                lst.append({
                    _dk8('VUxHfEpH'): _dk8('BlAHBlA=') % (cat, ent),
                    _dk8('VUxHfE1CTkY='): name,
                    _dk8('VUxHfFNKQA=='): self._pic(it.get(_dk8('QExVRlE='))),
                    _dk8('VUxHfFFGTkJRSFA='): remark,
                })
        return {_dk8('T0pQVw=='): lst, _dk8('U0JERg=='): pg}

    
    CLOUD_NAMES = {_dk8('R1pXVw=='): _dk8('x5myxbGO4ZRnxJmc'), _dk8('QUU='): _dk8('x5myxbGO4ZRhxJmc')}

    def _cloud_eps(self, title):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        
        key = _dk8('QE9MVkcZ') + title
        if key in self._pending:
            return self._pending[key]
        out = []
        if title:
            q = quote(title, safe="")
            for src in (_dk8('R1pXVw=='), _dk8('QUU=')):
                try:
                    d = self._get_json(_dk8('BlAMQlNKDFBGQlFASxxSHgZQBVBMVlFARh4GUA==') % (self.HOST, q, src)) or {}
                except Exception:
                    d = {}
                for it in d.get(_dk8('UUZQVk9XUA==')) or []:
                    if not it.get(_dk8('SlBmW1dGUU1CTw==')):
                        continue
                    nm = self._strip_tags(self._txt(it.get(_dk8('VUxHfE1CTkY='))))
                    if nm != title:
                        continue
                    eps = []
                    for seg in self._txt(it.get(_dk8('VUxHfFNPQlp8VlFP'))).split(_dk8('AA==')):
                        if _dk8('Bw==') not in seg:
                            continue
                        en, eu = seg.split(_dk8('Bw=='), 1)
                        eu = self._unesc(eu).strip()
                        if eu:
                            eps.append((self._txt(en) or _dk8('a2c='), eu))
                    if eps:
                        out.append((src, eps))
                        break
        if len(self._pending) > 24:
            self._pending.clear()
        self._pending[key] = out
        return out

    def detailContent(self, ids):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('T0pQVw=='): []}
        raw = self._txt(ids[0] if isinstance(ids, (list, tuple)) else ids)
        parts = raw.split(_dk8('Bw=='))
        if parts[0] == _dk8('RltX') and len(parts) >= 4:
            return self._detail_external(parts[1], parts[2], parts[3])
        if len(parts) >= 2:
            cat, ent = parts[0], parts[1]
        else:
            cat, ent = _dk8('Eg=='), raw
        data = self._detail_api(cat, ent)
        if not data:
            return {_dk8('T0pQVw=='): []}
        pd = data.get(_dk8('U09CWk9KTUhQR0ZXQkpP')) or {}
        sites = [s for s in self.SITE_SORT if s in pd] + [s for s in pd if s not in self.SITE_SORT]
        vod = {
            _dk8('VUxHfEpH'): _dk8('BlAHBlA=') % (cat, ent),
            _dk8('VUxHfE1CTkY='): self._txt(data.get(_dk8('V0pXT0Y='))),
            _dk8('VUxHfFNKQA=='): self._pic(data.get(_dk8('QEdNQExVRlE=')) or data.get(_dk8('QExVRlE='))),
            _dk8('V1pTRnxNQk5G'): _dk8('DA==').join(self._txt(x) for x in (data.get(_dk8('TkxVSkZAQldGRExRWg==')) or [])[:3]),
            _dk8('VUxHfFpGQlE='): self._txt(data.get(_dk8('U1ZBR0JXRg==')))[:4],
            _dk8('VUxHfEJRRkI='): _dk8('DA==').join(self._txt(x) for x in (data.get(_dk8('QlFGQg==')) or [])[:2]),
            _dk8('VUxHfFFGTkJRSFA='): "",
            _dk8('VUxHfFBATFFG'): self._txt(data.get(_dk8('R0xWQUJNUEBMUUY=')) or ""),
            _dk8('VUxHfEdKUUZAV0xR'): _dk8('DA==').join(self._txt(x) for x in (data.get(_dk8('R0pRRkBXTFE=')) or [])[:5]),
            _dk8('VUxHfEJAV0xR'): _dk8('DA==').join(self._txt(x) for x in (data.get(_dk8('QkBXTFE=')) or [])[:12]),
        }
        
        vod[_dk8('VUxHfEBMTVdGTVc=')] = self.DISCLAIMER + self._txt(data.get(_dk8('R0ZQQFFKU1dKTE0=')))
        cache = self._pending.get(ent) or {}
        names, urls = [], []

        
        for s in sites:
            eps = cache.get(s)
            names.append(self.SITE_NAMES.get(s, s))
            if not eps and cat != _dk8('Eg=='):
                
                eps = self._site_episodes(self._get(
                    self.HOST + self._play_path(cat, ent, s, 1),
                    ref=_dk8('BlAMR0ZXQkpPDAZQDAZQ') % (self.HOST, cat, ent)), s)
                if eps:
                    self._pending.setdefault(ent, {})[s] = eps
            if eps:
                urls.append(_dk8('AA==').join(_dk8('xI+PBhMRR8q4pQcGUA==') % (it[_dk8('TVZO')], self._play_path(cat, ent, s, it[_dk8('TVZO')]))
                                     for it in eps))
            else:
                
                urls.append(_dk8('xI+PEsq4pQcGUA==') % self._play_path(cat, ent, s, 1))

        
        try:
            clouds = self._cloud_eps(vod.get(_dk8('VUxHfE1CTkY=')) or "")
        except Exception:
            clouds = []
        for src, eps in clouds:
            names.append(self.CLOUD_NAMES.get(src, src))
            urls.append(_dk8('AA==').join(_dk8('BlAHBlA=') % (en, eu) for en, eu in eps))
        vod[_dk8('VUxHfFNPQlp8RVFMTg==')] = _dk8('BwcH').join(names)
        vod[_dk8('VUxHfFNPQlp8VlFP')] = _dk8('BwcH').join(urls)
        return {_dk8('T0pQVw=='): [vod]}

    def _detail_api(self, cat, ent):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        d = self._get_json(_dk8('BlAMQlNKDEdGV0JKTxxAQlceBlAFSkceBlA=') % (self.HOST, quote(cat), quote(ent)))
        return (d or {}).get(_dk8('R0JXQg==')) or {}

    
    
    
    def _resolve_play(self, play_url, ent, site, name):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        s = self._sess()
        if not s:
            return None
        body = json.dumps({_dk8('U09CWnZRTw=='): play_url, _dk8('UFdCV3VMR2pH'): ent,
                           _dk8('UFdCV3BMVlFARg=='): site, _dk8('UFdCV3VMR21CTkY='): name or ent})
        try:
            r = s.post(self.HOST + _dk8('DEJTSgxTT0JaRlEMUUZQTE9VRg=='), data=body.encode(_dk8('VldFDhs=')),
                       timeout=self.timeout,
                       headers={_dk8('cUZFRlFGUQ=='): self.HOST + _dk8('DA=='), _dk8('bFFKREpN'): self.HOST,
                                _dk8('ew5zT0JaRlEOcUZSVkZQVw=='): _dk8('Eg=='),
                                _dk8('YExNV0ZNVw53WlNG'): _dk8('QlNTT0pAQldKTE0MSVBMTQ=='),
                                _dk8('YkBARlNX'): _dk8('QlNTT0pAQldKTE0MSVBMTQ=='),
                                _dk8('dlBGUQ5iREZNVw=='): self.UA})
            j = r.json()
        except Exception:
            return None
        if not isinstance(j, dict) or not j.get(_dk8('UFZAQEZQUA==')) or j.get(_dk8('TkxHRg==')) != _dk8('R0pRRkBX'):
            return None
        u = self._txt(j.get(_dk8('VlFP')))
        if not u or _dk8('RlFRTFE=') in u.lower():
            return None
        if u.startswith(_dk8('DA==')):
            u = self.HOST + u
        if j.get(_dk8('VlBGc1FMW1o=')):
            u = _dk8('BlAMQlNKDFNPQlpGUQxTUUxbWhxWUU8eBlA=') % (self.HOST, quote(u, safe=""))
        return u

    @staticmethod
    def _play_path(cat, ent, site, ep):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return _dk8('DFNPQloMBlAMBlAMBlAcUB4GUA==') % (cat, ent, ep, site)

    def _detail_external(self, src_q, name_q, url_q):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        src = unquote(src_q)
        name = unquote(name_q)
        url = unquote(url_q)
        vod = {
            _dk8('VUxHfEpH'): _dk8('RltXBwZQBwZQBwZQ') % (src_q, name_q, url_q),
            _dk8('VUxHfE1CTkY='): name or src,
            _dk8('VUxHfFNKQA=='): "",
            _dk8('V1pTRnxNQk5G'): "", _dk8('VUxHfFpGQlE='): "", _dk8('VUxHfEJRRkI='): "", _dk8('VUxHfFFGTkJRSFA='): _dk8('xLiXy5y9xJmcy5SM'),
            _dk8('VUxHfFBATFFG'): "", _dk8('VUxHfEdKUUZAV0xR'): "", _dk8('VUxHfEJAV0xR'): "",
            _dk8('VUxHfFNPQlp8RVFMTg=='): _dk8('x5myxbGOxLiXy5y9'),
            _dk8('VUxHfFNPQlp8VlFP'): _dk8('a2cHBlA=') % url,
        }
        
        vod[_dk8('VUxHfEBMTVdGTVc=')] = self.DISCLAIMER
        return {_dk8('T0pQVw=='): [vod]}

    
    def playerContent(self, flag, vid, vip_flags):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return {_dk8('U0JRUEY='): 0, _dk8('VlFP'): ''}
        url = self._txt(vid).strip()
        hdr = json.dumps({_dk8('dlBGUQ5iREZNVw=='): self.UA}, ensure_ascii=False)
        if url.startswith(_dk8('S1dXUw==')):
            return {_dk8('U0JRUEY='): 0, _dk8('SVs='): 0, _dk8('VlFP'): url, _dk8('S0ZCR0ZR'): hdr}
        m = re.match(_dk8('fQxTT0JaDAt/RwgKDAt4Yg55Qg5ZEw4afggKDAt/RwgKfxxQHgt4Yg55Qg5ZEw4afggKBw=='), url)
        if not m:
            return {_dk8('U0JRUEY='): 1, _dk8('SVs='): 0, _dk8('VlFP'): url, _dk8('S0ZCR0ZR'): hdr}
        cat, ent, ep, site = m.groups()
        html = self._get(self.HOST + url, ref=_dk8('BlAMR0ZXQkpPDAZQDAZQ') % (self.HOST, cat, ent))
        eps = self._site_episodes(html, site)
        if eps:
            self._pending.setdefault(ent, {})[site] = eps
        try:
            epn = int(ep)
        except Exception:
            epn = 1
        link = ""
        for it in eps:
            if int(it.get(_dk8('TVZO'), 0)) == epn and it.get(_dk8('VlFP')):
                link = self._unesc(self._txt(it[_dk8('VlFP')])).strip()
                break
        if not link:
            
            pd = self._detail_api(cat, ent).get(_dk8('U09CWk9KTUhQR0ZXQkpP')) or {}
            link = self._txt((pd.get(site) or {}).get(_dk8('R0ZFQlZPV3xWUU8='))).strip()
        if link.startswith(_dk8('DAw=')):
            link = _dk8('S1dXU1AZ') + link
        
        direct = self._resolve_play(link, ent, site, "") if link else None
        if direct:
            return {_dk8('U0JRUEY='): 0, _dk8('SVs='): 0, _dk8('VlFP'): direct, _dk8('S0ZCR0ZR'): hdr}
        return {_dk8('U0JRUEY='): 1, _dk8('SVs='): 0, _dk8('VlFP'): link, _dk8('S0ZCR0ZR'): hdr}

    
    def _dig_json_after(self, html, key):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        i = html.find(key)
        if i < 0:
            return None
        j = html.find(_dk8('WA=='), i)
        if j < 0:
            return None
        
        depth, k = 0, j
        n = len(html)
        while k < n:
            c = html[k]
            if c == _dk8('WA=='):
                depth += 1
            elif c == _dk8('Xg=='):
                depth -= 1
                if depth == 0:
                    break
            k += 1
        t = html[j:k + 1].replace(_dk8('f1YTExEV'), _dk8('BQ==')).replace(_dk8('fww='), _dk8('DA=='))
        cnt = 0
        while _dk8('fwE=') in t and cnt < 10:
            t = t.replace(_dk8('fwE='), _dk8('AQ=='))
            cnt += 1
        try:
            return json.loads(t)
        except Exception:
            return None

    def _site_episodes(self, html, site):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        eps = []
        if not html:
            return eps
        obj = self._dig_json_after(html, _dk8('Qk9PRlNKR0ZXQkpP'))
        if obj:
            arr = obj.get(site)
            if arr is None and (site + _dk8('Eg==')) in obj:
                arr = obj.get(site + _dk8('Eg=='))
            for it in arr or []:
                try:
                    num = int(self._txt(it.get(_dk8('U09CWk9KTUh8TVZO'))))
                except Exception:
                    num = len(eps) + 1
                u = self._txt(it.get(_dk8('VlFP')))
                if u:
                    eps.append({_dk8('TVZO'): num, _dk8('VlFP'): u})
        if not eps:
            
            nums = re.findall(_dk8('DFNPQloMf0cIDHhiDnlCDlkTDhp+CAwLf0cICn8cUB4GUA==') % re.escape(site), html)
            for i in range(1, max([int(x) for x in nums] or [0]) + 1):
                eps.append({_dk8('TVZO'): i, _dk8('VlFP'): ""})
        eps.sort(key=lambda x: x[_dk8('TVZO')])
        return eps

    
    def isVideoFormat(self, url):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return True

    def manualVideoCheck(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return False

    def localProxy(self, param):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791612540:
            return None
        return None
