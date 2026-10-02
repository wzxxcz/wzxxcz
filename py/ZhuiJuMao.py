# -*- coding: utf-8 -*-
def _dk8(s):
    import base64 as _b
    return bytes(c ^ 35 for c in _b.b64decode(s)).decode('utf-8')


_dk8('KVdKV09GGQPLnJ7GqoTEr4gpS0xQVxkDS1dXUxkMDBIWFw0QFQ0SFRANEhYaGRIWFBspy4yXxbutGQNlTE1EbkoDDANsaMaeksuEpQNzWldLTE0DcFNKR0ZRzJ+ry5yexqqExK+Iy4SlyoGyA0BADUVGSlRCTUQNQlNTA8aurMuNjcaMmsWthsyfqinEt4vFkLYZA8ebrQNlUUZGbGgNSVBMTQPGs6/EuI3GnrbMn6/EiLrEoZrKpq7Eno0pAwMDAwMDWAFIRloBGQF5S1ZKaVZuQkwBDwFNQk5GARkB07ymnMybrMucnsaqhMSviAEPAVdaU0YBGRAPAUJTSgEZAQ0MeUtWSmlWbkJMDVNaAQ8pAwMDAwMDAwFQRkJRQEtCQU9GARkSDwFSVkpASHBGQlFASwEZEg8BRUpPV0ZRQkFPRgEZEl4pKcWthsasgMaurMuNjcyfq8qjpcazssukicWpsMavpgNrYnEDCAPLnLPLgq/FtJXEjbTFkLbFtIbGnLTMn6oZKQMDc2xwdwNYQUJQRl4MQlNKDVNLUwxERldCU1NCU0oNSk1HRlsMWEJTSl4pAwPLjJTFkqHGh5cZKQMDAwMDA0JTUw5VRlFQSkxNDkBMR0YDAwMDAwMZAxYSESkDAwMDAwNCU1MOVkoOTkxHRgMDAwMDAwMDAwMDGQNHQlFIKQMDAwMDA0JTUw5WUEZRDkdGVUpARg5KRwMDAwMZAx8QEceerktGWx0pAwMDAwMDQlNTDkJTSg5VRlFKRVoOV0pORgMDAxkDHxITx56uxbSVyrSXxauQHSkDAwMDAwNCU1MOQlNKDlVGUUpFWg5QSkRNAwMDGQNBQlBGFRcLYmZwDhIRGw5gYWAOc2hgcBQLxbSVyrSXxauQDwNIRloeSlUeR0JMTkJHQkxOQllLVkpJVgoKKQMDQlNKGQNKTUpXdRISGgMMA1daU0ZlSk9XRlF1TEdvSlBXAwwDUEZCUUBLb0pQVwMMA1VMR2dGV0JKTwMMA1VMR3NCUVBGAwwDR0JNTlZvSlBXKQMDxrCuxpm3GQNYAUdCV0IBGQMBH0FCUEYVFwtiZnAOEhEbDmBhYA5zaGBwFAtJUExNCgodAQ8DAUBMR0YBGQMSXikDA8WxjsW3nRkDR0ZXQkpPDVVMR3xTT0JafE9KUFd4fg1WUU9QeH4NU0JRUEZ8QlNKfFZRTwMDZGZ3A8azrcuct8a4vcS/vMaNvQNOEFYbKSnHnb7LlrUZA8SZjANzWldLTE0DYmZwzJ+rxrOvxLiNxp62A0JGUEBBQA1TWsyfqsyfr8W0g8q/owNTWkBRWlNXTEdMTkYp')

import json
import re
import os
import ssl
import gzip
import time
import base64
import random
import sys
from urllib.parse import urlencode, quote

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self, query_params=None, t4_api=None):
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''

        def fetch(self, url, params=None, headers=None, cookies=None, timeout=10, **kwargs):
            import requests
            return requests.get(url, params=params, headers=headers,
                                cookies=cookies, timeout=timeout, verify=False)


_AES = None
try:
    import aescbc as _aescbc
    _AES = _aescbc.AES
except Exception:
    try:
        from Crypto.Cipher import AES as _PCryptoAES
        from Crypto.Util.Padding import pad as _pc_pad, unpad as _pc_unpad

        class _PCAdapter(object):
            def __init__(self, key):
                self._key = key

            def encrypt_cbc(self, data, iv):
                return _PCryptoAES.new(self._key, _PCryptoAES.MODE_CBC, iv).encrypt(_pc_pad(data, 16))

            def decrypt_cbc(self, data, iv):
                return _pc_unpad(_PCryptoAES.new(self._key, _PCryptoAES.MODE_CBC, iv).decrypt(data), 16)

        _AES = _PCAdapter
    except Exception:
        _AES = None


class Spider(BaseSpider):

    
    BASE_DEFAULT = _dk8('S1dXUxkMDBIWFw0QFQ0SFRANEhYaGRIWFBs=')
    BASE_URL_API = _dk8('S1dXU1AZDAxZSU4OEhATERAbEBYTGg1ATFANQlMORFZCTURZS0xWDU5aUkBPTFZHDUBMTgxZSU5XVQ1XW1c=')
    AES_KEY = b"daomadaomazhuiju"

    UA_API = _dk8('TEhLV1dTDBANEhcNGg==')
    UA_PLAY = (_dk8('bkxZSk9PQgwWDRMDC29KTVZbGANiTUdRTEpHAxIQGANzSltGTwMUCgNiU1NPRnRGQWhKVwwWEBQNEBUDC2hrd25vDwNPSkhGA2RGQEhMCgNgS1FMTkYMEhEXDRMNEw0TA25MQUpPRgNwQkVCUUoMFhAUDRAV'))

    
    CLASS_IDS = [1, 2, 3, 4, 5, 7, 10, 8]
    SORTS = [(_dk8('xb+jxbWT'), _dk8('xb+jxbWT')), (_dk8('xb+jxKCO'), _dk8('xb+jxKCO')), (_dk8('y4ynxqul'), _dk8('y4ynxqul'))]
    
    FILTER_LABELS = [(_dk8('QE9CUFA='), _dk8('xJKYxr2o')), (_dk8('QlFGQg=='), _dk8('xr+Txq+Z')), (_dk8('WkZCUQ=='), _dk8('xpqXx5ie'))]

    
    DROP_LINE_KEYWORDS = (_dk8('y5yexqqExK+I'),)     
    DROP_LINE_FROM = (_dk8('RFlVSlM='),)          

    
    DISCLAIMER = (_dk8('wKOzxqauy5eAxoCTxbutwKOyxb+Py5anxZmzxLeSwKOvxpOsy6Oiy7qtwKOuxqauy5eaxqulx5mIxbaXxLOlzJ+vx5imx524x5uJx5mZxo6Fx5qDwKOix5mHxZaix5utxZaoy4y2x56cxLeLzJ+vy4yUx5mtx56wyomvxrOtAxEXA8aTrMW0lcalpsarg8q6h8yfuMWqo8W/qsaeksuEpcalpsaNmsSqq8W+oMa+pMaescatvMSqq8W+oMW1msWqo8W/qsyfr8ebhsSFosS3i8eZrceYmMeetsa2pcebucS3i8qjt8yfr8aFocW/qsedlsW+oMuMlMayqcS8hsarg8q6h8CjoSkp'))

    def __init__(self, query_params=None, t4_api=None):
        try:
            BaseSpider.__init__(self, query_params, t4_api)
        except Exception:
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''
        self.base = self.BASE_DEFAULT
        self.timeout = 12
        self._device = ''.join(random.choice(_dk8('ExIREBcWFRQbGkJBQEdGRQ==')) for _ in range(32))
        self._aes = _AES(self.AES_KEY) if _AES else None
        self._init_cache = None
        self._init_ts = 0
        self._detail_cache = {}
        self._last_detail = None
        self._last_detail_ts = 0
        self._base_tried = False
        self._ctx = ssl._create_unverified_context()

    

    def init(self, extend=""):
        self.extend = extend or ""
        
        if self.extend:
            ext = self.extend.strip()
            try:
                obj = json.loads(ext)
                if isinstance(obj, dict) and obj.get(_dk8('QUJQRg==')):
                    self.base = str(obj[_dk8('QUJQRg==')]).rstrip(_dk8('DA=='))
            except Exception:
                if ext.startswith(_dk8('S1dXUw==')):
                    self.base = ext.rstrip(_dk8('DA=='))
        return {_dk8('UFdCV1ZQ'): 0}

    def getName(self):
        return _dk8('07ymnMybrMucnsaqhMSviA==')

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(k in u for k in (_dk8('DU4QVhs='), _dk8('DU5TFw=='), _dk8('DUVPVQ=='), _dk8('DU5IVQ=='), _dk8('DVdQ')))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass

    

    def _sign(self, ts):
        _dk8('QlNTDkJTSg5VRlFKRVoOUEpETQMeA0FCUEYVFwtiZnAOYGFgDnNoYHAUC1BXUQtXUAoPA0hGWh5KVR5HQkxOQkdCTE5CWUtWSklWCgo=')
        if not self._aes:
            return ""
        raw = self._aes.encrypt_cbc(str(ts).encode(_dk8('VldFDhs=')), self.AES_KEY)
        return base64.b64encode(raw).decode(_dk8('QlBASko='))

    def _decrypt(self, b64):
        if not self._aes or not b64:
            return None
        raw = base64.b64decode(b64)
        data = self._aes.decrypt_cbc(raw, self.AES_KEY)
        return data.decode(_dk8('VldFDhs='), _dk8('SkRNTFFG'))

    

    def _headers_api(self, ts):
        return {
            _dk8('dlBGUQ5iREZNVw=='): self.UA_API,
            _dk8('YExNV0ZNVw53WlNG'): _dk8('QlNTT0pAQldKTE0MWw5UVFQORUxRTg5WUU9GTUBMR0ZHGANAS0JRUEZXHnZ3ZQ4b'),
            _dk8('YkBARlNXDmZNQExHSk1E'): _dk8('RFlKUw=='),
            _dk8('QlNTDlVGUVBKTE0OQExHRg=='): _dk8('FhIR'),
            _dk8('QlNTDlZKDk5MR0Y='): _dk8('R0JRSA=='),
            _dk8('QlNTDlZQRlEOR0ZVSkBGDkpH'): self._device,
            _dk8('QlNTDkJTSg5VRlFKRVoOV0pORg=='): ts,
            _dk8('QlNTDkJTSg5VRlFKRVoOUEpETQ=='): self._sign(ts),
        }

    def _http_get(self, url, headers=None, timeout=None):
        _dk8('y5y3xri9xbWkxb+PzJ+4UUZSVkZQV1ADx5+7xqarzJ+vVlFPT0pBA8amv8aZtg==')
        hdrs = headers or {_dk8('dlBGUQ5iREZNVw=='): self.UA_PLAY}
        t = timeout or self.timeout
        try:
            import requests
            r = requests.get(url, headers=hdrs, timeout=t, verify=False)
            r.encoding = _dk8('VldFDhs=')
            return r.text or ""
        except Exception:
            try:
                import urllib.request
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=t, context=self._ctx) as resp:
                    raw = resp.read()
                    if resp.headers.get(_dk8('YExNV0ZNVw5mTUBMR0pNRA==')) == _dk8('RFlKUw=='):
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    return raw.decode(_dk8('VldFDhs='), _dk8('SkRNTFFG'))
            except Exception:
                return ""

    def _http_post(self, url, data):
        body = urlencode(data or {}).encode(_dk8('VldFDhs='))
        hdrs = self._headers_api(str(int(time.time())))
        try:
            import requests
            r = requests.post(url, data=data, headers=hdrs, timeout=self.timeout, verify=False)
            r.encoding = _dk8('VldFDhs=')
            return r.text or ""
        except Exception:
            try:
                import urllib.request
                req = urllib.request.Request(url, data=body, headers=hdrs, method=_dk8('c2xwdw=='))
                with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                    raw = resp.read()
                    if resp.headers.get(_dk8('YExNV0ZNVw5mTUBMR0pNRA==')) == _dk8('RFlKUw=='):
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    return raw.decode(_dk8('VldFDhs='), _dk8('SkRNTFFG'))
            except Exception:
                return ""

    def _refresh_base(self):
        _dk8('xa2GxqyAxry8xrOux5+5xqy7zJ+vx5itxo27xbWayqauxJ6Nxa2GxqyAxqy1xb+jxbWTxr+Txr6j')
        if self._base_tried:
            return
        self._base_tried = True
        try:
            txt = (self._http_get(self.BASE_URL_API, timeout=8) or "").strip()
            m = re.search(_dk8('S1dXU1AcGQwMeH9Ufw1/Dn4ICxl/RwgKHA=='), txt)
            if m:
                self.base = m.group(0).rstrip(_dk8('DA=='))
        except Exception:
            pass

    def _call(self, api, data=None):
        _dk8('y5OgxLeLA0RGV0JTU0JTSgPFrYbGrIDGmpXLhIDGjKUDR0JXQgPGjrTFjZbMn6/Gh5LLl4bLnLfGuL0DbUxNRg==')
        url = _dk8('BlAMQlNKDVNLUwxERldCU1NCU0oNSk1HRlsMBlA=') % (self.base, api)
        txt = self._http_post(url, data or {})
        if not txt:
            if not self._base_tried:
                self._refresh_base()
                txt = self._http_post(_dk8('BlAMQlNKDVNLUwxERldCU1NCU0oNSk1HRlsMBlA=') % (self.base, api), data or {})
            if not txt:
                return None
        try:
            obj = json.loads(txt)
        except Exception:
            return None
        payload = obj.get(_dk8('R0JXQg=='))
        if not payload:
            return None
        dec = self._decrypt(payload)
        if not dec:
            return None
        try:
            return json.loads(dec)
        except Exception:
            return None

    

    @staticmethod
    def _clean(txt):
        if not txt:
            return ""
        s = str(txt)
        s = re.sub(_dk8('H3h9HX4IHQ=='), "", s)
        s = (s.replace(_dk8('BU1BUFMY'), _dk8('Aw==')).replace(_dk8('BUJOUxg='), _dk8('BQ==')).replace(_dk8('BQAQGhg='), _dk8('BA=='))
              .replace(_dk8('BVJWTFcY'), _dk8('AQ==')).replace(_dk8('BU9XGA=='), _dk8('Hw==')).replace(_dk8('BURXGA=='), _dk8('HQ==')))
        s = re.sub(_dk8('xLeSeH3Mn6/Ao6F+WBMPERNeC8SRncqjqgocxa2Ly66zeMyfr8CjoX4c'), "", s)
        return s.strip()

    @staticmethod
    def _name(txt):
        _dk8('yrilxrOux5uuy6CexrOIAwcDxrGvAwA=')
        s = str(txt or "").strip()
        return s.replace(_dk8('Bw=='), _dk8('fA==')).replace(_dk8('AA=='), _dk8('fA==')) or _dk8('xY6AxKqk')

    @staticmethod
    def _pic(url):
        u = (url or "").strip()
        if u.startswith(_dk8('DAw=')):
            u = _dk8('S1dXUxk=') + u
        return u

    def _init_data(self):
        now = time.time()
        if self._init_cache and now - self._init_ts < 600:
            return self._init_cache
        d = self._call(_dk8('Sk1KV3USEho='), {})
        if isinstance(d, dict) and d:
            self._init_cache = d
            self._init_ts = now
            return d
        return self._init_cache or {}

    def _filters(self):
        data = self._init_data()
        types = data.get(_dk8('V1pTRnxPSlBX')) or []
        out = {}
        for t in types:
            tid = str(t.get(_dk8('V1pTRnxKRw==')))
            ext = t.get(_dk8('V1pTRnxGW1dGTUc='))
            if isinstance(ext, str) and ext.strip():
                try:
                    ext = json.loads(ext)
                except Exception:
                    ext = {}
            if not isinstance(ext, dict):
                ext = {}
            groups = []
            for key, label in self.FILTER_LABELS:
                raw = ext.get(key)
                if not raw:
                    continue
                vals = [v for v in str(raw).split(_dk8('Dw==')) if v.strip()]
                if not vals:
                    continue
                groups.append({
                    _dk8('SEZa'): key, _dk8('TUJORg=='): label,
                    _dk8('VUJPVkY='): [{_dk8('TQ=='): _dk8('xqaLyqCL'), _dk8('VQ=='): ""}] + [{_dk8('TQ=='): v.strip(), _dk8('VQ=='): v.strip()} for v in vals],
                })
            groups.append({
                _dk8('SEZa'): _dk8('UExRVw=='), _dk8('TUJORg=='): _dk8('xa2xxpms'),
                _dk8('VUJPVkY='): [{_dk8('TQ=='): n, _dk8('VQ=='): v} for n, v in self.SORTS],
            })
            out[tid] = groups
        return out

    @staticmethod
    def _card(v):
        return {
            _dk8('VUxHfEpH'): str(v.get(_dk8('VUxHfEpH')) or ""),
            _dk8('VUxHfE1CTkY='): Spider._clean(v.get(_dk8('VUxHfE1CTkY='))),
            _dk8('VUxHfFNKQA=='): Spider._pic(v.get(_dk8('VUxHfFNKQA=='))),
            _dk8('VUxHfFFGTkJRSFA='): Spider._clean(v.get(_dk8('VUxHfFFGTkJRSFA='))),
            _dk8('VUxHfFpGQlE='): str(v.get(_dk8('VUxHfFpGQlE=')) or ""),
            _dk8('VUxHfEJRRkI='): str(v.get(_dk8('VUxHfEJRRkI=')) or ""),
            _dk8('VUxHfEJAV0xR'): Spider._clean(v.get(_dk8('VUxHfEJAV0xR'))),
        }

    

    def _is_bad_line(self, name, first_from, urls):
        _dk8('xquHxbWOxbuMxrOFx5uZxbSDxbarxJmcy5SMzJ+rxbGOx5uux5mlDMuMtsS/qMaOu8WDmsyfqg==')
        nm = str(name or "")
        for kw in self.DROP_LINE_KEYWORDS:
            if kw and kw in nm:
                return True
        ff = str(first_from or "")
        for f in self.DROP_LINE_FROM:
            if f and f in ff:
                return True
        return False

    def _lines(self, d):
        _dk8('y5y3xri9y5ykxZiHAwgDxq2YyqSuxrOtxLmnxJmcy5SMxqu0y4KLGQN4C8SZnMuUjMazrg8DeFZRT8qCmg8DDQ0NfgoPAw0NDX4=')
        if not d:
            return []
        out = []
        seen = set()
        for idx, pl in enumerate(d.get(_dk8('VUxHfFNPQlp8T0pQVw==')) or []):
            if not isinstance(pl, dict):
                continue
            info = pl.get(_dk8('U09CWkZRfEpNRUw=')) or {}
            name = self._clean(info.get(_dk8('UEtMVA=='))) or (_dk8('xJmcy5SMBkc=') % (idx + 1))
            urls = [u for u in (pl.get(_dk8('VlFPUA==')) or []) if isinstance(u, dict)]
            if not urls:
                continue
            if self._is_bad_line(name, str(urls[0].get(_dk8('RVFMTg==')) or ""), urls):
                continue
            if name in seen:            
                continue
            seen.add(name)
            out.append((name, urls))
        return out

    def _build_lines(self, d):
        _dk8('xb2nxpiZA1VMR3xTT0JafEVRTE4DDANVTEd8U09CWnxWUU/Mn6vEl4HGn7bHm60DfE9KTUZQA8ebo8ukl8yfqg==')
        pf = []
        pu = []
        for i, (name, urls) in enumerate(self._lines(d)):
            pf.append(name)
            eps = []
            for pos, u in enumerate(urls):
                eps.append(_dk8('BlAHBkdjBkdjBlA=') % (self._name(u.get(_dk8('TUJORg=='))), i, pos,
                                            u.get(_dk8('RVFMTg==')) or ""))
            pu.append(_dk8('AA==').join(eps))
        return pf, pu

    

    def homeContent(self, filter):
        data = self._init_data()
        types = data.get(_dk8('V1pTRnxPSlBX')) or []
        name_map = dict((int(t.get(_dk8('V1pTRnxKRw==')) or 0), t.get(_dk8('V1pTRnxNQk5G')) or "") for t in types)
        classes = [{_dk8('V1pTRnxKRw=='): str(i), _dk8('V1pTRnxNQk5G'): name_map.get(i) or str(i)} for i in self.CLASS_IDS]
        if not classes:
            classes = [{_dk8('V1pTRnxKRw=='): _dk8('Eg=='), _dk8('V1pTRnxNQk5G'): _dk8('xLeWy4SlxqqE')}]
        return {_dk8('QE9CUFA='): classes, _dk8('RUpPV0ZRUA=='): self._filters() if filter else {}}

    def homeVideoContent(self):
        data = self._init_data()
        lst = data.get(_dk8('UUZATE5ORk1HfE9KUFc=')) or data.get(_dk8('QUJNTUZRfE9KUFc=')) or []
        if not lst:
            r = self._call(_dk8('V1pTRmVKT1dGUXVMR29KUFc='), self._cat_params(_dk8('Eg=='), 1, {})) or {}
            lst = r.get(_dk8('UUZATE5ORk1HfE9KUFc=')) or []
        return {_dk8('T0pQVw=='): [self._card(v) for v in lst]}

    

    @staticmethod
    def _cat_params(tid, pg, fl):
        def pick(k):
            v = str(fl.get(k, "") or "").strip()
            return v if v else _dk8('xqaLyqCL')
        return {
            _dk8('V1pTRnxKRw=='): str(tid),
            _dk8('U0JERg=='): int(pg),
            _dk8('UExRVw=='): fl.get(_dk8('UExRVw==')) or _dk8('xb+jxbWT'),
            _dk8('QE9CUFA='): pick(_dk8('QE9CUFA=')),
            _dk8('QlFGQg=='): pick(_dk8('QlFGQg==')),
            _dk8('WkZCUQ=='): pick(_dk8('WkZCUQ==')),
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(1, int(pg or 1))
        except Exception:
            pg = 1
        fl = extend
        if isinstance(fl, str):
            try:
                fl = json.loads(fl or _dk8('WF4='))
            except Exception:
                fl = {}
        if not isinstance(fl, dict):
            fl = {}
        r = self._call(_dk8('V1pTRmVKT1dGUXVMR29KUFc='), self._cat_params(tid, pg, fl))
        lst = (r or {}).get(_dk8('UUZATE5ORk1HfE9KUFc=')) or []
        items = [self._card(v) for v in lst]
        return {
            _dk8('T0pQVw=='): items,
            _dk8('U0JERg=='): pg,
            _dk8('U0JERkBMVk1X'): pg + 1 if len(items) >= 30 else pg,
            _dk8('T0pOSlc='): 30,
            _dk8('V0xXQk8='): 999999,
        }

    

    def searchContent(self, key, quick, pg=1):
        try:
            pg = max(1, int(pg or 1))
        except Exception:
            pg = 1
        key = (key or "").strip()
        if not key:
            return {_dk8('T0pQVw=='): []}
        r = self._call(_dk8('UEZCUUBLb0pQVw=='), {_dk8('SEZaVExRR1A='): key, _dk8('V1pTRnxKRw=='): 0, _dk8('U0JERg=='): pg})
        lst = (r or {}).get(_dk8('UEZCUUBLfE9KUFc=')) or []
        items = [self._card(v) for v in lst]
        return {
            _dk8('T0pQVw=='): items,
            _dk8('U0JERg=='): pg,
            _dk8('U0JERkBMVk1X'): pg + 1 if len(items) >= 20 else pg,
            _dk8('T0pOSlc='): 20,
            _dk8('V0xXQk8='): 999999,
        }

    

    def detailContent(self, ids):
        vid = ""
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        elif isinstance(ids, str) and ids.strip().startswith(_dk8('eA==')):
            try:
                arr = json.loads(ids)
                vid = str(arr[0]) if arr else ""
            except Exception:
                vid = ids.strip()
        else:
            vid = str(ids or "")
        vid = vid.split(_dk8('Yw=='))[0].lstrip(_dk8('DA==')).strip()
        if not vid:
            return {_dk8('T0pQVw=='): []}

        d = self._call(_dk8('VUxHZ0ZXQkpP'), {_dk8('VUxHfEpH'): vid})
        if not d:
            return {_dk8('T0pQVw=='): []}
        self._detail_cache[vid] = (time.time(), d)
        self._last_detail = d
        self._last_detail_ts = time.time()
        if len(self._detail_cache) > 12:
            self._detail_cache.clear()

        vod = d.get(_dk8('VUxH')) or {}
        
        play_from, play_url = self._build_lines(d)

        content = self._clean(vod.get(_dk8('VUxHfEBMTVdGTVc=')) or vod.get(_dk8('VUxHfEFPVlFB')))
        
        if self.DISCLAIMER:
            content = self.DISCLAIMER + (content or "")

        out = {
            _dk8('VUxHfEpH'): vid,
            _dk8('VUxHfE1CTkY='): self._clean(vod.get(_dk8('VUxHfE1CTkY='))),
            _dk8('VUxHfFNKQA=='): self._pic(vod.get(_dk8('VUxHfFNKQA==')) or vod.get(_dk8('VUxHfFNKQHxQT0pHRg=='))),
            _dk8('V1pTRnxNQk5G'): self._clean(vod.get(_dk8('VUxHfEBPQlBQ'))),
            _dk8('VUxHfFpGQlE='): str(vod.get(_dk8('VUxHfFpGQlE=')) or ""),
            _dk8('VUxHfEJRRkI='): str(vod.get(_dk8('VUxHfEJRRkI=')) or ""),
            _dk8('VUxHfE9CTUQ='): str(vod.get(_dk8('VUxHfE9CTUQ=')) or ""),
            _dk8('VUxHfFFGTkJRSFA='): self._clean(vod.get(_dk8('VUxHfFFGTkJRSFA='))),
            _dk8('VUxHfFBATFFG'): str(vod.get(_dk8('VUxHfFBATFFG')) or ""),
            _dk8('VUxHfEdKUUZAV0xR'): self._clean(vod.get(_dk8('VUxHfEdKUUZAV0xR'))),
            _dk8('VUxHfEJAV0xR'): self._clean(vod.get(_dk8('VUxHfEJAV0xR'))),
            _dk8('VUxHfEBMTVdGTVc='): content,
            _dk8('VUxHfFNPQlp8RVFMTg=='): _dk8('BwcH').join(play_from),
            _dk8('VUxHfFNPQlp8VlFP'): _dk8('BwcH').join(play_url),
        }
        return {_dk8('T0pQVw=='): [out]}

    

    def _detail(self):
        _dk8('xqy1xp6wxqquy4yFxaCmzJ+rx5+7xqarxb+jy5yyx5ujxY+CA0dGV0JKT2BMTVdGTVfMn6/GppXFj4LEn7DGjrvMn6o=')
        if self._last_detail and time.time() - self._last_detail_ts < 300:
            return self._last_detail
        best = None
        best_ts = 0
        for ts, val in self._detail_cache.values():
            if time.time() - ts < 300 and ts > best_ts:
                best, best_ts = val, ts
        return best

    def _get_ep(self, vid):
        _dk8('VUpHA8aegcaFoQMDxJmcy5SMx5uoxYOkY8q4pcebqMWDpGNFUUxOAw4dAwtWUU8PA1NCUVBGfEJTSnxWUU8PA0VRTE4KKQMDAwMDAwMDxJmcy5SMx5uoxYOkxryZx5mty5ykxZiHAwgDxq2YyqSuxrOtxLmnxJmcy5SMyoKZxpmszJ+rx5utA0dGV0JKT2BMTVdGTVcDy52wxqSZx5ujy6SXzJ+q')
        parts = str(vid or "").split(_dk8('Yw=='))
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            return "", "", ""
        line_idx, pos = int(parts[0]), int(parts[1])
        src = parts[2] if len(parts) >= 3 else ""
        d = self._detail()
        if not d:
            return "", "", ""
        lines = self._lines(d)
        if line_idx >= len(lines):
            return "", "", ""
        urls = lines[line_idx][1]
        if pos >= len(urls):
            return "", "", ""
        u = urls[pos]
        return str(u.get(_dk8('VlFP')) or ""), str(u.get(_dk8('U0JRUEZ8QlNKfFZRTw==')) or ""), str(u.get(_dk8('RVFMTg==')) or src)

    @staticmethod
    def _valid_play_url(u):
        _dk8('y5ykxZiHy4SAxb2zxa2GxqyAxY+Dy5eaDMuUkMuej8qClsSOqsW0g8W2q8SYsMW9vw==')
        if not u:
            return False
        s = u.strip()
        if not s.lower().startswith((_dk8('S1dXUxkMDA=='), _dk8('S1dXU1AZDAw='))):
            return False
        low = s.lower()
        if _dk8('DU4QVhs=') in low or _dk8('DU5TFw==') in low or _dk8('DUVPVQ==') in low or _dk8('DU5IVQ==') in low:
            return True
        
        tail = s.split(_dk8('GQwM'), 1)[-1].split(_dk8('HA=='), 1)[0]
        return (_dk8('DA==') in tail.strip(_dk8('DA=='))) and len(tail.split(_dk8('DA=='), 1)[-1]) > 0

    def _resolve_once(self, raw_url, parse_url):
        _dk8('xq62xY+Cy4SAxb2zzJ+5y4SAxb2zxa2GxqyAx5+7xqarzJ+vxLiXyrCdxqa/xpm2')
        play = ""
        if parse_url:
            txt = self._http_get(parse_url, headers={_dk8('dlBGUQ5iREZNVw=='): self.UA_PLAY}, timeout=self.timeout)
            if txt:
                try:
                    j = json.loads(txt)
                    play = str(j.get(_dk8('VlFP')) or "")
                except Exception:
                    m = re.search(_dk8('S1dXU1AcGQwMeH0BfwR/f39QfggLHBl/DU4QVhtffw1OUxcKeH0BfwR/UH4J'), txt)
                    if m:
                        play = m.group(0)
            play = play.replace(_dk8('fww='), _dk8('DA==')).strip()
        if not self._valid_play_url(play) and self._is_direct_m3u8(raw_url):
            play = raw_url.strip()
        return play if self._valid_play_url(play) else ""

    @staticmethod
    def _is_direct_m3u8(url):
        u = (url or "").lower()
        return u.startswith(_dk8('S1dXUw==')) and any(k in u for k in (_dk8('DU4QVhs='), _dk8('DU5TFw=='), _dk8('DUVPVQ=='), _dk8('DU5IVQ==')))

    def playerContent(self, flag, vid, vip_flags):
        raw_url, parse_url, src = self._get_ep(vid)
        if not raw_url and not parse_url:
            return {_dk8('U0JRUEY='): 1, _dk8('SVs='): 0, _dk8('VlFP'): "", _dk8('S0ZCR0ZR'): ""}

        
        play = self._resolve_once(raw_url, parse_url)

        
        if not play:
            d = self._detail()
            if d:
                parts = str(vid or "").split(_dk8('Yw=='))
                if len(parts) >= 2 and parts[1].isdigit():
                    pos = int(parts[1])
                    for _name, urls in self._lines(d):
                        if pos >= len(urls):
                            continue
                        alt = urls[pos]
                        if str(alt.get(_dk8('VlFP')) or "") == raw_url:
                            continue
                        play = self._resolve_once(str(alt.get(_dk8('VlFP')) or ""),
                                                  str(alt.get(_dk8('U0JRUEZ8QlNKfFZRTw==')) or ""))
                        if play:
                            break

        if not play:
            return {_dk8('U0JRUEY='): 1, _dk8('SVs='): 0, _dk8('VlFP'): raw_url or parse_url, _dk8('S0ZCR0ZR'): ""}

        referer = _dk8('S1dXU1AZDAxUVFQNR1pXVw5XVUENQExODA==')
        try:
            host = re.match(_dk8('C0tXV1NQHBkMDHh9DH4ICg=='), play).group(1)
            referer = host + _dk8('DA==')
        except Exception:
            pass
        header = json.dumps({
            _dk8('dlBGUQ5iREZNVw=='): self.UA_PLAY,
            _dk8('cUZFRlFGUQ=='): referer,
        }, ensure_ascii=False)
        return {_dk8('U0JRUEY='): 0, _dk8('SVs='): 0, _dk8('VlFP'): play, _dk8('S0ZCR0ZR'): header}



if __name__ == _dk8('fHxOQkpNfHw='):
    s = Spider()
    print(s.init(""))
    print(_dk8('TUJORhk='), s.getName())
    h = s.homeContent(True)
    print(_dk8('QE9CUFBGUBk='), h[_dk8('QE9CUFA=')])
    hv = s.homeVideoContent()
    print(_dk8('S0xORhk='), len(hv[_dk8('T0pQVw==')]), hv[_dk8('T0pQVw==')][0][_dk8('VUxHfE1CTkY=')] if hv[_dk8('T0pQVw==')] else "")
    c = s.categoryContent(_dk8('Eg=='), _dk8('Eg=='), True, json.dumps({_dk8('QE9CUFA='): _dk8('xqyHy4Cm'), _dk8('UExRVw=='): _dk8('xb+jxbWT')}))
    print(_dk8('QEJXGQ=='), len(c[_dk8('T0pQVw==')]), c[_dk8('T0pQVw==')][0][_dk8('VUxHfE1CTkY=')] if c[_dk8('T0pQVw==')] else "")
    sc = s.searchContent(_dk8('xpmlx566xpqX'), "", 1)
    print(_dk8('UEZCUUBLGQ=='), len(sc[_dk8('T0pQVw==')]), sc[_dk8('T0pQVw==')][0][_dk8('VUxHfE1CTkY=')] if sc[_dk8('T0pQVw==')] else "")
    if sc[_dk8('T0pQVw==')]:
        d = s.detailContent([sc[_dk8('T0pQVw==')][0][_dk8('VUxHfEpH')]])[_dk8('T0pQVw==')][0]
        print(_dk8('R0ZXQkpPGQ=='), d[_dk8('VUxHfE1CTkY=')], _dk8('Xw=='), d[_dk8('VUxHfFNPQlp8RVFMTg==')])
        first = d[_dk8('VUxHfFNPQlp8VlFP')].split(_dk8('BwcH'))[0].split(_dk8('AA=='))[0].split(_dk8('Bw=='), 1)[1]
        p = s.playerContent(d[_dk8('VUxHfFNPQlp8RVFMTg==')].split(_dk8('BwcH'))[0], first, "")
        print(_dk8('U09CWhk='), p[_dk8('VlFP')][:120])
