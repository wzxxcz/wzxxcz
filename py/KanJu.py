# -*- coding: utf-8 -*-
def _dk8(s):
    import base64 as _b
    return bytes(c ^ 35 for c in _b.b64decode(s)).decode('utf-8')


_dk8('KVdKV09GGQPEv6jGqoRiailLTFBXGQNLV1dTUBkMDEhCTUlWEhQNQExODCnLjJfFu60ZA2VMTURuSgxsaMaeksuEpQNzWldLTE0DcFNKR0ZRzJ+raGJtaXYNYmoDxISixb+qYnNqA+GUA2tuYmAOcGtiERYVy4yUxZKhxI6dxrOuA+GUA04QVhvEuJfKsJ3Ego/LhIDMn6opxq28xLOlGQPEiLrEoZrHm5lxRkJAVwNwc2LMn6/LjJTFkqHKv6PFs5nGm4XEjp3Gs67Gh5fMn6vEjbTFkLbFrLPGrLXLpInGqq7EiIwDTkxVSkYOQEJRRw5RVk1XSk5GA0BLVk1IzJ+qGSkDAwMDAwNQSkQDHgNrbmJgDnBrYhEWFQtQRkBRRlcPAwFuZndrbGd/TVNCV0scUlZGUVp/TcW0lcq0l8WrkE5Qf01NTE1ARgEKKQMDAwMDA8aHlxkDWw5CSg5OTFVKRg5XSk5GUFdCTlMDDANbDkJKDk5MVUpGDk1MTUBGAwwDWw5CSg5OTFVKRg5QSkRNQldWUUYpxa2GxqyAGSkDAwMDAwPKhbXKgpYDDFUSDEVGRkcMS0xORikDAwMDAwPGq6XEkpgDDFUSDEFRTFRQRgxAQldCT0xEHEpNV0ZNVx5PQldGUFd8QEJXQk9MRAVISk1HHk5MVUpGBURGTVFGHgVCUUZCHgVaRkJRHgVTQkRGHgVPSk5KVx4pAwMDAwMDxbO/xJeBAwxVEgxBUUxUUEYMQEJXQk9MRBxSHsamkMq3jcuMrgVTQkRGHgVPSk5KVx4pAwMDAwMDy4yFxaCmAwxVEgxAQldCT0xEDFhKR14DAwPKuKXFtpMDDFUSDEBCV0JPTEQMWEpHXgxGU0pQTEdGUBxMRUVQRlceEwVPSk5KVx4WExMpAwMDAwMDxbGOxbedAwxVEgxTT0JaQUJASAxRRlBMT1VGDFjKuKVXTEhGTV4cVUpGVB5ATE5TQkBXAwPBpbEDT0pNRnxMU1dKTE1QA8alpsaziANOEFYbA8S4l8qwnSkDAwMDAwMDAwMDA8SGi8arm8SZnMuUjAtRRlBMT1VGGQwMW1tbCsq/owNzbHB3AwxVEgxTT0JaQUJASAxRRlBMT1VGDk9KTUYDWAFXSkBIRlcBGQ0NDV4Dx5mvxY+Cxa6ByrCdKcS3i8WQthkDx5utA2VRRkZsaA1JUExNA8azr8S4jcaetsyfr8SIusShmsqmrsSejQNYAUhGWgEZAWhCTWlWAQ8BTUJORgEZAdO8ppzMm6zEv6jGqoRiagEPAVdaU0YBGRAPAUJTSgEZAQ0MaEJNaVYNU1oBXinFuJfFtZMZAxETERUOExoOERYp')

import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import quote

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self, query_params=None, t4_api=None):
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''


class Spider(BaseSpider):
    HOST = _dk8('S1dXU1AZDAxIQk1JVhIUDUBMTg==')
    SECRET = _dk8('FhYURxNGF0JGGhEaRRcQG0dCFUFHGxcXEhEQFBdGFRMbFUEbQkUTGkEQRUZHFhdBRRERFRMSRxZBRRtAFhdCEw==')
    UA = (_dk8('bkxZSk9PQgwWDRMDC29KTVZbGANiTUdRTEpHAxIQGANzSltGTwMUCgNiU1NPRnRGQWhKVwwWEBQNEBUDC2hrd25vDwNPSkhGA2RGQEhMCgNgS1FMTkYMEhEXDRMNEw0TA25MQUpPRgNwQkVCUUoMFhAUDRAV'))
    
    CLIENT_HEADERS = {
        _dk8('Ww5CSg5OTFVKRg5AT0pGTVcOTUJORg=='): _dk8('R0pCTVpKTURXSkJNV0JNRA5FUUxNV0ZNRw=='),
        _dk8('Ww5CSg5OTFVKRg5AT0pGTVcOVUZRUEpMTQ=='): _dk8('Eg0TDRM='),
        _dk8('Ww5CSg5OTFVKRg5BVkpPRw5VRlFQSkxN'): _dk8('R0pCTVpKTURXSkJNV0JNRA5VERMRFQ0TGg0RFw0XDhdFFRAWEEIUEkAQFg4XRRUQFhBCFBJAEBYOF0UVEBYQQhQSQBAW'),
        _dk8('Ww5CSg5OTFVKRg5TUUxXTEBMTw5VRlFQSkxN'): _dk8('ERMRFQ4TFA4TFg1PSkFRQlFaDlURDVNPQlpBQkBIDlUS'),
    }
    
    DISCLAIMER = (_dk8('wKOzxqauy5eAxoCTxbutwKOyxb+Py5anxZmzxLeSwKOvxpOsy6Oiy7qtwKOuxqauy5eaxqulx5mIxbaXxLOlzJ+vx5imx524x5uJx5mZxo6Fx5qDwKOix5mHxZaix5utxZaoy4y2x56cxLeLzJ+vy4yUx5mtx56wyomvxrOtAxEXA8aTrMW0lcalpsarg8q6h8yfuMWqo8W/qsaeksuEpcalpsaNmsSqq8W+oMa+pMaescatvMSqq8W+oMW1msWqo8W/qsyfr8ebhsSFosS3i8eZrceYmMeetsa2pcebucS3i8qjt8yfr8aFocW/qsedlsW+oMuMlMayqcS8hsarg8q6h8CjoSkp'))

    
    KINDS = {
        _dk8('Eg=='): _dk8('TkxVSkY='),        
        _dk8('EQ=='): _dk8('UEZRSkZQ'),       
        _dk8('EA=='): _dk8('Qk1KTkY='),        
        _dk8('Fw=='): _dk8('VUJRSkZXWg=='),      
        _dk8('Fg=='): _dk8('R0xAVk5GTVdCUVo='),  
    }
    SHORT_DRAMA_TID = _dk8('FQ==')

    def init(self, extend=""):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        self.extend = extend or ""
        self.timeout = 20
        self._cache = {}
        self._session_cookie = ""
        try:
            import urllib3
            urllib3.disable_warnings()
        except Exception:
            pass
        return {_dk8('UFdCV1ZQ'): 0}

    def getName(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        return _dk8('07ymnMybrMS/qMaqhGJq')

    

    def _sign_headers(self, method, path):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        ts = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        msg = _dk8('KQ==').join([method, path, ts, nonce])
        sig = hmac.new(self.SECRET.encode(_dk8('VldFDhs=')), msg.encode(_dk8('VldFDhs=')),
                       hashlib.sha256).hexdigest()
        return {
            _dk8('Ww5CSg5OTFVKRg5XSk5GUFdCTlM='): ts,
            _dk8('Ww5CSg5OTFVKRg5NTE1ARg=='): nonce,
            _dk8('Ww5CSg5OTFVKRg5QSkRNQldWUUY='): sig,
        }

    def _headers(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        h = {
            _dk8('dlBGUQ5iREZNVw=='): self.UA,
            _dk8('YkBARlNX'): _dk8('QlNTT0pAQldKTE0MSVBMTQ=='),
            _dk8('bFFKREpN'): self.HOST,
            _dk8('cUZFRlFGUQ=='): self.HOST + _dk8('DA=='),
        }
        h.update(self.CLIENT_HEADERS)
        return h

    def _qs(self, params):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xo60xqaby56PUlZGUVrHm5HMn6/Go5/Et4vEup3Gq6XGrJTEn7XEg6LMn6vHm63Ejp3Gs67HnL7Fr6LHm6PLpJfMn6o=')
        arr = []
        for k, v in params.items():
            if v is None or v == "":
                continue
            arr.append(_dk8('BlAeBlA=') % (k, quote(str(v), safe="")))
        return _dk8('BQ==').join(arr)

    def _ensure_session(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xqu4xpiZxZubxo2Bx5+5y4y+zJ+rc2xwdwMMVRIMVlBGUVAMQk1MTVpOTFZQA8ebqMassgNCSnxOTFVKRnxQRlBQSkxNA0BMTEhKRsyfqg==')
        if self._session_cookie:
            return self._session_cookie
        try:
            import requests
            hdrs = self._headers()
            hdrs.update(self._sign_headers(_dk8('c2xwdw=='), _dk8('DFUSDFZQRlFQDEJNTE1aTkxWUA==')))
            rsp = requests.post(self.HOST + _dk8('DFUSDFZQRlFQDEJNTE1aTkxWUA=='), json={},
                                headers=hdrs, timeout=self.timeout, verify=False)
            raw_sc = rsp.headers.get(_dk8('cEZXDmBMTEhKRg==')) or ""
            for sc in raw_sc.split(_dk8('KQ==')):
                if _dk8('Qkp8TkxVSkZ8UEZQUEpMTR4=') in sc and _dk8('bkJbDmJERh4T') not in sc and _dk8('Vk5QfA==') in sc:
                    self._session_cookie = sc.split(_dk8('GA=='))[0]
                    break
        except Exception:
            self._session_cookie = ""
        if not self._session_cookie:
            try:
                import urllib.request
                import ssl
                hdrs = self._headers()
                hdrs.update(self._sign_headers(_dk8('c2xwdw=='), _dk8('DFUSDFZQRlFQDEJNTE1aTkxWUA==')))
                hdrs[_dk8('YExNV0ZNVw53WlNG')] = _dk8('QlNTT0pAQldKTE0MSVBMTQ==')
                req = urllib.request.Request(
                    self.HOST + _dk8('DFUSDFZQRlFQDEJNTE1aTkxWUA=='),
                    data=b"{}", method=_dk8('c2xwdw=='), headers=hdrs)
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                    for sc in (r.headers.get_all(_dk8('cEZXDmBMTEhKRg==')) or []):
                        if _dk8('Qkp8TkxVSkZ8UEZQUEpMTR4=') in sc and _dk8('bkJbDmJERh4T') not in sc and _dk8('Vk5QfA==') in sc:
                            self._session_cookie = sc.split(_dk8('GA=='))[0]
                            break
            except Exception:
                self._session_cookie = ""
        return self._session_cookie

    def _api(self, method, path, body=None):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('y5OgxLeLxL+oxqqEYmrEhKLFv6pic2rMn6/LnLfGuL1HSkBXzJ+4xoeSy5eGy5y3xri9xIqZR0pAVw==')
        url = self.HOST + path
        headers = self._headers()
        headers.update(self._sign_headers(method, path))
        data = None
        if body is not None:
            data = json.dumps(body).encode(_dk8('VldFDhs='))
            headers[_dk8('YExNV0ZNVw53WlNG')] = _dk8('QlNTT0pAQldKTE0MSVBMTQ==')
        
        if _dk8('DFUSDFZQRlFQDE5G') in path or _dk8('DFUSDFNPQlpBQkBIDFFGUExPVUY=') in path:
            ck = self._ensure_session()
            if ck:
                headers[_dk8('YExMSEpG')] = ck
        text = ""
        try:
            import requests
            rsp = requests.request(method, url, data=data, headers=headers,
                                   timeout=self.timeout, verify=False)
            text = rsp.text or ""
        except Exception:
            try:
                import urllib.request
                import urllib.error
                import ssl
                req = urllib.request.Request(url, data=data, method=method,
                                             headers=headers)
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=self.timeout,
                                            context=ctx) as r:
                    text = r.read().decode(_dk8('VldFDhs='), _dk8('SkRNTFFG'))
            except Exception:
                text = ""
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _cached_api(self, path):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        if path in self._cache:
            return self._cache[path]
        data = self._api(_dk8('ZGZ3'), path)
        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[path] = data
        return data

    

    @staticmethod
    def _parse_extend(extend):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        try:
            obj = json.loads(extend)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _pick_first_id(ids):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        if ids is None:
            return ""
        if isinstance(ids, list):
            return str(ids[0]) if ids else ""
        s = str(ids)
        if s.startswith(_dk8('eA==')):
            try:
                arr = json.loads(s)
                if arr and len(arr):
                    return str(arr[0])
            except Exception:
                pass
        return s

    @staticmethod
    def _cards(data):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('QVFMVFBGDEVGRkcDxbaTxa6NA8GlsQPFg6TGpKVVTEfGq7TLgos=')
        lst = []
        seen = set()
        raw = []
        if isinstance(data, dict):
            raw = data.get(_dk8('QEJRR1A=')) or []
            if not raw and data.get(_dk8('TEFJRkBX')) == _dk8('UEtMUVd8R1FCTkINRUZGRw=='):
                raw = data.get(_dk8('SldGTlA=')) or []
        for c in raw:
            if not isinstance(c, dict):
                continue
            vid = str(c.get(_dk8('Skc=')) or "").strip().lstrip(_dk8('DA=='))
            title = str(c.get(_dk8('V0pXT0Y=')) or "").strip()
            if not vid or not title or vid in seen:
                continue
            seen.add(vid)
            lst.append({
                _dk8('VUxHfEpH'): vid,
                _dk8('VUxHfE1CTkY='): title,
                _dk8('VUxHfFNKQA=='): str(c.get(_dk8('U0xQV0ZRfFZRTw==')) or ""),
                _dk8('VUxHfFFGTkJRSFA='): str(c.get(_dk8('UUZOQlFIUA==')) or ""),
            })
        return lst

    @staticmethod
    def _is_video_url(u):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xquHxbWOxbuMxrOFxbGOxbedxLiXyrCdwKOhxZCLxaeszJ+5xo27xbWadQx5xLmnbnMXx5+Jy4CmxauzAw1JU0RdV1NPVQPGuJ3EqqR2cW/Mn68pAwMDAwMDAwPHm67LoJ7Fr6rFqorGkrbGs67LnKTFmIfMn7jGrInFrbHKuofEgo3GjbnFu4zKvrrFo6LGuJ3EqqTGvLzGs67EuafGsK7Gmbc=')
        u = str(u or "").strip()
        if not u.startswith(_dk8('S1dXUw==')):
            return False
        low = u.lower()
        
        if _dk8('REpORBMNQUJKR1YNQExO') in low:
            return False
        
        return True

    @staticmethod
    def _find_play_url(obj):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('yqOxxp6xxaqdxrCuxpm3yqSvxI+Px5ujx5uJy4SlyoGyxLiXyrCdzJ+ry6SJxqmLxa2xyrqHxridxKqkzJ+q')
        if isinstance(obj, str):
            return obj if Spider._is_video_url(obj) else ""
        if isinstance(obj, dict):
            for v in obj.values():
                r = Spider._find_play_url(v)
                if r:
                    return r
        if isinstance(obj, list):
            for v in obj:
                r = Spider._find_play_url(v)
                if r:
                    return r
        return ""

    

    def _build_filters(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        def nv(n, v):
            if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
                return None
            return {_dk8('TQ=='): n, _dk8('VQ=='): v}

        def fg(key, name, values):
            if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
                return None
            return {_dk8('SEZa'): key, _dk8('TUJORg=='): name, _dk8('VUJPVkY='): values}

        def tags(*args):
            if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
                return None
            arr = [nv(_dk8('xqaLyqCL'), "")]
            for a in args:
                arr.append(nv(a, a))
            return arr

        areas = tags(_dk8('x5uOxriexoeEyrql'), _dk8('x5uOxrieyoW6xZuM'), _dk8('x5uOxriexqyTxZqd'), _dk8('xJ2txrie'), _dk8('yryKxrie'), _dk8('xbSGxb+P'),
                     _dk8('y6iSxrie'), _dk8('xZC2xrie'), _dk8('xp2Uxrie'), _dk8('xZCTxrie'), _dk8('xq6TxpmF'), _dk8('xqmDxaicxoeE'), _dk8('xqaVxo2g'))
        years = tags(*[str(y) for y in range(2026, 2011, -1)])

        g_movie = tags(_dk8('xqqExaCm'), _dk8('xqmLx56/'), _dk8('xrW/xqqE'), _dk8('xKuSxaCm'), _dk8('xISyxpqY'), _dk8('xqmLxLeY'), _dk8('xaGPxLWy'),
                       _dk8('xaCpxaG5'), _dk8('xKmMxJ6J'), _dk8('xaKzxaO1'), _dk8('xqWxyrqK'), _dk8('xau7x5mq'), _dk8('xoakxpqY'), _dk8('xqyHy4Cm'),
                       _dk8('xY6Fx52D'), _dk8('xq2lxqyR'), _dk8('x5+Dy42T'), _dk8('xKKdyrmd'))
        g_tv = tags(_dk8('xqqExaCm'), _dk8('xrW/xqqE'), _dk8('xKuSxaCm'), _dk8('xaGPxLWy'), _dk8('xKmMxJ6J'), _dk8('xqmLx56/'), _dk8('xISyxpqY'),
                    _dk8('xoakxpqY'), _dk8('xqyHy4Cm'), _dk8('xY6Fx52D'), _dk8('xau7x5mq'), _dk8('yqCexpuh'), _dk8('xo2VxpmO'), _dk8('xq2lxqyR'))
        g_simple = tags(_dk8('xqqExaCm'), _dk8('xrW/xqqE'), _dk8('xKuSxaCm'), _dk8('xqmLx56/'), _dk8('xISyxpqY'), _dk8('xqWxyrqK'), _dk8('xoakxpqY'))

        common = [fg(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), areas), fg(_dk8('WkZCUQ=='), _dk8('xpqXx5ie'), years)]
        return {
            _dk8('Eg=='): [fg(_dk8('REZNUUY='), _dk8('xJKYxr2o'), g_movie)] + common,
            _dk8('EQ=='): [fg(_dk8('REZNUUY='), _dk8('xJKYxr2o'), g_tv)] + common,
            _dk8('EA=='): [fg(_dk8('REZNUUY='), _dk8('xJKYxr2o'), g_simple)] + common,
            _dk8('Fw=='): [fg(_dk8('REZNUUY='), _dk8('xJKYxr2o'), g_simple)] + common,
            _dk8('Fg=='): common,
            _dk8('FQ=='): [],
        }

    

    def homeContent(self, filter):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('QE9CUFA='): [], _dk8('T0pQVw=='): []}
        classes = [
            {_dk8('V1pTRnxKRw=='): _dk8('Eg=='), _dk8('V1pTRnxNQk5G'): _dk8('xLeWxp6S')},
            {_dk8('V1pTRnxKRw=='): _dk8('EQ=='), _dk8('V1pTRnxNQk5G'): _dk8('xLeWy4SlxqqE')},
            {_dk8('V1pTRnxKRw=='): _dk8('EA=='), _dk8('V1pTRnxNQk5G'): _dk8('xqmLxZ+I')},
            {_dk8('V1pTRnxKRw=='): _dk8('Fw=='), _dk8('V1pTRnxNQk5G'): _dk8('xJify6qZ')},
            {_dk8('V1pTRnxKRw=='): _dk8('Fg=='), _dk8('V1pTRnxNQk5G'): _dk8('xJmJxp62xKqk')},
            {_dk8('V1pTRnxKRw=='): _dk8('FQ=='), _dk8('V1pTRnxNQk5G'): _dk8('xLyOxqqE')},
        ]
        return {_dk8('QE9CUFA='): classes, _dk8('RUpPV0ZRUA=='): self._build_filters() if filter else {}}

    def homeVideoContent(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('T0pQVw=='): []}
        try:
            data = self._cached_api(_dk8('DFUSDEVGRkcMS0xORg=='))
            lst = []
            seen = set()
            for sec in (data.get(_dk8('UEZAV0pMTVA=')) or []):
                for c in (sec.get(_dk8('QEJRR1A=')) or []):
                    vid = str(c.get(_dk8('Skc=')) or "").strip().lstrip(_dk8('DA=='))
                    title = str(c.get(_dk8('V0pXT0Y=')) or "").strip()
                    if not vid or not title or vid in seen:
                        continue
                    seen.add(vid)
                    lst.append({
                        _dk8('VUxHfEpH'): vid,
                        _dk8('VUxHfE1CTkY='): title,
                        _dk8('VUxHfFNKQA=='): str(c.get(_dk8('U0xQV0ZRfFZRTw==')) or ""),
                        _dk8('VUxHfFFGTkJRSFA='): str(c.get(_dk8('UUZOQlFIUA==')) or ""),
                    })
            return {_dk8('T0pQVw=='): lst}
        except Exception as e:
            print(_dk8('eGhCTWlWfgNLTE5GdUpHRkxgTE1XRk1XA0ZRUUxRGQ=='), e)
            return {_dk8('T0pQVw=='): []}

    

    def categoryContent(self, tid, pg, filter, extend):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('T0pQVw=='): [], _dk8('U0JERg=='): 1, _dk8('U0JERkBMVk1X'): 1, _dk8('T0pOSlc='): 0, _dk8('V0xXQk8='): 0}
        try:
            pg = max(1, int(pg or 1))
            fl = self._parse_extend(extend)

            
            if str(tid) == self.SHORT_DRAMA_TID:
                data = self._cached_api(_dk8('DFUSDFBLTFFXDkdRQk5CDEVGRkc='))
                lst = self._cards(data)
                return {_dk8('T0pQVw=='): lst, _dk8('U0JERg=='): 1, _dk8('U0JERkBMVk1X'): 1,
                        _dk8('T0pOSlc='): max(len(lst), 1), _dk8('V0xXQk8='): len(lst)}

            kind = self.KINDS.get(str(tid), _dk8('TkxVSkY='))
            params = {_dk8('Sk1XRk1X'): _dk8('T0JXRlBXfEBCV0JPTEQ='), _dk8('SEpNRw=='): kind,
                      _dk8('U0JERg=='): pg, _dk8('T0pOSlc='): 24}
            for k in (_dk8('REZNUUY='), _dk8('QlFGQg=='), _dk8('WkZCUQ==')):
                v = str(fl.get(k, "") or "").strip()
                if v and v != _dk8('xqaLyqCL'):
                    params[k] = v
            data = self._cached_api(_dk8('DFUSDEFRTFRQRgxAQldCT0xEHA==') + self._qs(params))
            lst = self._cards(data)
            pag = data.get(_dk8('U0JESk1CV0pMTQ==')) or {}
            has_more = bool(pag.get(_dk8('S0JQfE5MUUY=')))
            total = int(pag.get(_dk8('V0xXQk8=')) or 0) or 999999
            return {_dk8('T0pQVw=='): lst, _dk8('U0JERg=='): pg,
                    _dk8('U0JERkBMVk1X'): pg + 1 if has_more else pg,
                    _dk8('T0pOSlc='): 24, _dk8('V0xXQk8='): total}
        except Exception as e:
            print(_dk8('eGhCTWlWfgNAQldGRExRWmBMTVdGTVcDRlFRTFEZ'), e)
            return {_dk8('T0pQVw=='): [], _dk8('U0JERg=='): max(1, int(pg or 1)), _dk8('U0JERkBMVk1X'): 1,
                    _dk8('T0pOSlc='): 24, _dk8('V0xXQk8='): 0}

    

    def searchContent(self, key, quick, pg=1):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('T0pQVw=='): []}
        try:
            key = (key or "").strip()
            if not key:
                return {_dk8('T0pQVw=='): []}
            pg = max(1, int(pg or 1))
            params = {_dk8('Ug=='): key, _dk8('U0JERg=='): pg, _dk8('T0pOSlc='): 24}
            data = self._api(_dk8('ZGZ3'), _dk8('DFUSDEFRTFRQRgxAQldCT0xEHA==') + self._qs(params))
            lst = self._cards(data)
            return {_dk8('T0pQVw=='): lst, _dk8('U0JERg=='): pg,
                    _dk8('U0JERkBMVk1X'): pg + 1 if len(lst) >= 24 else pg,
                    _dk8('T0pOSlc='): 24, _dk8('V0xXQk8='): 999999}
        except Exception as e:
            print(_dk8('eGhCTWlWfgNQRkJRQEtgTE1XRk1XA0ZRUUxRGQ=='), e)
            return {_dk8('T0pQVw=='): []}

    def searchContentPage(self, key, quick, pg):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        return self.searchContent(key, quick, pg)

    

    def _fetch_episodes(self, vid, d):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xqy1xqaLyrilzJ+rxpuFV0xIRk3Mn6rAo6HLjIXFoKbEn5lXTEhGTcW0lcuToMq4pcW2k8arpcqClsWthsasgMuChsamiw==')
        eps = d.get(_dk8('RlNKUExHRlA=')) or []
        if eps and eps[0].get(_dk8('V0xIRk0=')):
            return eps
        pag = d.get(_dk8('RlNKUExHRnxTQkRKTUJXSkxN')) or {}
        total = int(pag.get(_dk8('V0xXQk98QExWTVc=')) or d.get(_dk8('RlNKUExHRnxATFZNVw==')) or len(eps))
        if total <= 0:
            return eps
        data = self._api(_dk8('ZGZ3'), _dk8('DFUSDEBCV0JPTEQMBlAMRlNKUExHRlAcBlA=') % (
            quote(vid, safe=""), self._qs({_dk8('TEVFUEZX'): 0, _dk8('T0pOSlc='): 500})))
        eps2 = data.get(_dk8('RlNKUExHRlA=')) or []
        return eps2 if eps2 else eps

    def _list_lines(self, first_token):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xqu0xqSZy4yGxKqkxLmnxqaLyqCLxJmcy5SMxrOuzJ+rx5uuxZWry5eaxIaLxqubzJ+vx5imxL+oUUZQTE9VRkfEhovGq5vFg6TLjZPMn6rAo6EpAwMDAwMDAwPLnLfGuL0DeE9CQUZPDw0NDX7Mn6/En7DGjrs=')
        key = _dk8('T0pNRlAZ') + first_token
        if key in self._cache:
            return self._cache[key]
        lines = self._resolve(first_token, use_cache=True)
        names, seen = [], set()
        for l in lines:
            label = str(l.get(_dk8('T0JBRk8=')) or "").strip()
            if label and label not in seen:
                seen.add(label)
                names.append(label)
        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[key] = names
        return names

    def detailContent(self, ids):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('T0pQVw=='): []}
        try:
            vid = self._pick_first_id(ids).strip().lstrip(_dk8('DA=='))
            if not vid:
                return {_dk8('T0pQVw=='): []}
            d = self._api(_dk8('ZGZ3'), _dk8('DFUSDEBCV0JPTEQM') + quote(vid, safe=""))
            if not d or not d.get(_dk8('Skc=')):
                return {_dk8('T0pQVw=='): []}

            eps = self._fetch_episodes(vid, d)
            play_tokens = []
            for i, e in enumerate(eps):
                token = str(e.get(_dk8('V0xIRk0=')) or "").strip()
                if not token:
                    continue
                name = str(e.get(_dk8('V0pXT0Y=')) or e.get(_dk8('R0pQU09CWnxNQk5G')) or
                           (_dk8('xI+PBkfKuKU=') % (i + 1))).replace(_dk8('Bw=='), _dk8('fA==')).replace(_dk8('AA=='), _dk8('fA=='))
                play_tokens.append((name, token))
            if not play_tokens:
                return {_dk8('T0pQVw=='): []}

            
            eps_str = _dk8('AA==').join(_dk8('BlAHBlA=') % (n, t) for n, t in play_tokens)
            play_from = self._list_lines(play_tokens[0][1])
            if not play_from:
                play_from = [_dk8('07ymnMybrMS/qMaqhGJq')]
            play_url = [eps_str] * len(play_from)

            genres = d.get(_dk8('REZNUUZQ')) or []
            vod = {
                _dk8('VUxHfEpH'): vid,
                _dk8('VUxHfE1CTkY='): str(d.get(_dk8('V0pXT0Y=')) or ""),
                _dk8('VUxHfFNKQA=='): str(d.get(_dk8('U0xQV0ZRfFZRTw==')) or ""),
                _dk8('V1pTRnxNQk5G'): _dk8('DA==').join([str(g) for g in genres[:4]]),
                _dk8('VUxHfFpGQlE='): str(d.get(_dk8('WkZCUQ==')) or ""),
                _dk8('VUxHfEJRRkI='): str(d.get(_dk8('QlFGQg==')) or ""),
                _dk8('VUxHfE9CTURWQkRG'): str(d.get(_dk8('T0JNRFZCREY=')) or ""),
                _dk8('VUxHfFFGTkJRSFA='): str(d.get(_dk8('UUZOQlFIUA==')) or ""),
                _dk8('VUxHfEdKUUZAV0xR'): _dk8('wKOi').join([str(a) for a in (d.get(_dk8('R0pRRkBXTFFQ')) or [])]),
                _dk8('VUxHfEJAV0xR'): _dk8('wKOi').join([str(a) for a in (d.get(_dk8('QkBXTFFQ')) or [])[:12]]),
                _dk8('VUxHfEBMTVdGTVc='): self.DISCLAIMER + str(d.get(_dk8('R0ZQQFFKU1dKTE0=')) or ""),
                _dk8('VUxHfFNPQlp8RVFMTg=='): _dk8('BwcH').join(play_from),
                _dk8('VUxHfFNPQlp8VlFP'): _dk8('BwcH').join(play_url),
            }
            return {_dk8('T0pQVw=='): [vod]}
        except Exception as e:
            print(_dk8('eGhCTWlWfgNHRldCSk9gTE1XRk1XA0ZRUUxRGQ=='), e)
            return {_dk8('T0pQVw=='): []}

    

    def _resolve(self, token, use_cache=True):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('y4SAxb2zxbyzyrilxJmcy5SMxqu0y4KLwKOhxIaLxqubx5uZx5ujxY+CxaOEzJ+vxbGOxbedxbSVxpymyoKYxqy1xbWTxLmn')
        token = (token or "").strip()
        if not token:
            return []
        key = _dk8('UUZQTE9VRhk=') + token
        if use_cache and key in self._cache:
            return self._cache[key]
        data = self._api(_dk8('ZGZ3'), _dk8('DFUSDFNPQlpBQkBIDFFGUExPVUYMBlAcVUpGVB5ATE5TQkBX')
                         % quote(token, safe=""))
        lines = data.get(_dk8('T0pNRnxMU1dKTE1Q')) or []
        if use_cache:
            if len(self._cache) > 24:
                self._cache.clear()
            self._cache[key] = lines
        return lines

    def _pick_line_url(self, lines, flag=""):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        _dk8('xa+qxJmcy5SMxrOuC0VPQkQKyqOqxJmcy5SMxa6BxLiXyrCdzJ+4xoeSy5eGy6SJxqmLxri9yqOjxqaVx5i1xJmcy5SMwKOhKQMDAwMDAwMDxZCLxaeszJ+5xqyJxZWry5eax5ujx5uJxIaLxqubzJ+vxauzxqm8xq6Qy5y3xri9')
        fl = (flag or "").replace(_dk8('07ymnMybrA=='), "").strip()
        target = None
        if fl:
            for l in lines:
                label = str(l.get(_dk8('T0JBRk8=')) or "").strip()
                pid = str(l.get(_dk8('U1FMVUpHRlF8Skc=')) or "").strip()
                if fl == label or fl == pid:
                    target = l
                    break
        candidates = []
        if target is not None:
            candidates.append(target)
        for l in lines:
            if l is not target:
                candidates.append(l)
        for l in candidates:
            u = str(l.get(_dk8('VlFP')) or "").strip()
            if l.get(_dk8('UUZQTE9VRkc=')) and self._is_video_url(u):
                return u
            if u.startswith(_dk8('UUZQTE9VRhkMDA==')):
                ticket = u[10:].strip()
                rd = self._api(_dk8('c2xwdw=='), _dk8('DFUSDFNPQlpBQkBIDFFGUExPVUYOT0pNRhxVSkZUHkBMTlNCQFc='),
                               {_dk8('V0pASEZX'): ticket})
                line = rd.get(_dk8('T0pNRg==')) or {}
                url = str(line.get(_dk8('VlFP')) or "").strip()
                if line.get(_dk8('UUZQTE9VRkc=')) and self._is_video_url(url):
                    return url
                url = self._find_play_url(rd)
                if url:
                    return url
        return ""

    def playerContent(self, flag, vid, vip_flags):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return {_dk8('U0JRUEY='): 0, _dk8('VlFP'): ''}
        result = {_dk8('U0JRUEY='): 0, _dk8('U09CWnZRTw=='): "", _dk8('VlFP'): "", _dk8('S0ZCR0ZR'): ""}
        try:
            token = self._pick_first_id(vid)
            if _dk8('Bw==') in token:
                token = token.split(_dk8('Bw=='))[-1]
            token = token.strip().lstrip(_dk8('DA=='))
            if not token:
                return result

            
            lines = self._resolve(token, use_cache=False)
            url = self._pick_line_url(lines, flag)
            result[_dk8('VlFP')] = (url or "").strip()
            result[_dk8('S0ZCR0ZR')] = json.dumps(
                {_dk8('dlBGUQ5iREZNVw=='): self.UA, _dk8('cUZFRlFGUQ=='): self.HOST + _dk8('DA==')},
                ensure_ascii=False)
            return result
        except Exception as e:
            print(_dk8('eGhCTWlWfgNTT0JaRlFgTE1XRk1XA0ZRUUxRGQ=='), e)
            return result

    

    def isVideoFormat(self, url):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        u = (url or "").lower()
        return any(x in u for x in (_dk8('DU4QVhs='), _dk8('DU5TFw=='), _dk8('DUVPVQ=='), _dk8('DVdQ')))

    def manualVideoCheck(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        return False

    def localProxy(self, param):
        if int(__import__(_dk8('V0pORg==')).time()) > 1791635220:
            return None
        return None
