# -*- coding: utf-8 -*-
def _dk8(s):
    import base64 as _b
    return bytes(c ^ 35 for c in _b.b64decode(s)).decode('utf-8')


_dk8('KVdKV09GGQPEkpDGqYvFn4gLbkplVk0KKUtMUFcZA0tXV1NQGQwMREZXQE0NTlpOSkVWTQ1ATE4py4yXxbutGQPEkpDGqYvFn4hic3MLbkplVk0DDANATE4NTkpFVk1XTA1PQk1OQkwKxa2GxqyAyqOlxrOyA+GUA2VMTURuSgxsaMaeksuEpQNzWldLTE0DcFNKR0ZRKSnGrqzLjY0LyqOlxrOyy6SJxamwxq+mCMSNtMWQtsW0hsactAoZKQMDYnNqAwMDAwNzbHB3A0tXV1NQGQwMREZXQE0NTlpOSkVWTQ1ATE4MQlNKDVNLUwxERldCU1NCU0oNSk1HRlsMH8WthsasgMazrh0pAwPEjp3Gs67Gh5cDA0JTUw5CU0oOVUZRSkVaDldKTkYDHgPEhLHEmYTFtJXKtJfFq5ApAwMDAwMDAwMDA0JTUw5CU0oOVUZRSkVaDlBKRE0DHgNhQlBGFRcLYmZwDhIRGw5gYWALxbutxbWkHsW0lcq0l8WrkMaOtMSPhcebkQ8DSEZaHkpVHmRmd25qZXZtZGZqbmpldm0KCikDA8apg8aMpQMDAwNiZnAMYGFgDHNoYHAWc0JHR0pNRAMDSEZaAx4DSlUDHgMBZGZ3bmpldm1kZmpuamV2bQEDCxIVxo60y6mhCikDA8awrsaZtwMDAwNYAUBMR0YBGRIPAU5QRAEZAQEPAUdCV0IBGQEfYUJQRhUXC2JmcMapg8aMpcS5p8ebucapgmlwbG0KHQFeKQMDVUxHc0JRUEYDxLmnA1ZRTwPGrKHFtpPKv6PGpqvEt4vGs6/Hm6PGjKXKsYYDYmZwA8apg8aMpcalrsWss8eZhwvGppXHnrrGrKHFtpPFu63FtaQKKSnFrYbGrIDHm6PLhKsLxpSRxo29xZaoChkpAwNXWlNGZUpPV0ZRdUxHb0pQVwMDxqulxJKYCMSOuMqjqgjGq6XKgpYDA1daU0Z8SkcMU0JERgxAT0JQUAxCUUZCDFpGQlEMT0JNRAxQTFFXKQMDUEZCUUBLb0pQVwMDAwMDAwMDA8Wzv8SXgQMDAwMDAwMDAwMDA0hGWlRMUUdQDFdaU0Z8SkcMU0JERikDA1VMR2dGV0JKTwMDAwMDAwMDAwPLjIXFoKYDAwMDAwMDAwMDAwNVTEd8SkcDwaWxA1VMRwxVTEd8U09CWnxPSlBXC8SZnMuUjAjGqoTKuKUKKQMDVUxHc0JRUEYDAwMDAwMDAwMDA8WxjsW3ncuEgMW9swMDAwMDAwMDU0JRUEZ8QlNKDFZRTwvGjKUKA8GlsQNJUExNDVZRTwPEuJfKsJ1OUxcMThBWGykpxLeLxZC2GQPHm60DZVFGRmxoDUlQTE0DxrOvxLiNxp62DwPEiLrEoZrKpq7Eno0ZKQMDWAFIRloBGQFuSmdMTURuQk0BDwFNQk5GARkB07ymnMybrMSSkMapi8WfiAEPAVdaU0YBGRAPAUJTSgEZAQ0MbkpnTE1EbkJNDVNaAQ8pAwMDAVBGQlFAS0JBT0YBGRIPAVJWSkBIcEZCUUBLARkSDwFFSk9XRlFCQU9GARkSXik=')

import base64
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self, query_params=None, t4_api=None):
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''

        def fetch(self, url, params=None, headers=None, cookies=None, timeout=10, **kw):
            import requests
            return requests.get(url, params=params, headers=headers, cookies=cookies,
                                timeout=timeout, verify=False)




try:
    from Crypto.Cipher import AES as _CryptoAES
except Exception:
    try:
        from Cryptodome.Cipher import AES as _CryptoAES
    except Exception:
        _CryptoAES = None


def _pkcs7_pad(data):
    n = 16 - (len(data) % 16)
    return data + bytes([n]) * n


def _pkcs7_unpad(data):
    if not data:
        return data
    n = data[-1]
    if 1 <= n <= 16 and data[-n:] == bytes([n]) * n:
        return data[:-n]
    return data


class _PureAES128(object):
    _dk8('xJmMc1pXS0xNA2JmcA4SERsDxq62xr60xqmDy4SAxoylwKOhx5imxr+LA1NaQFFaU1dMR0xORgPHm67GrIzEt4vFtJXGs4zEt4sLxaOEy6CexqyMxa2Gxqy0CsCjoQ==')

    _ready = False
    SBOX = INV = XT = M9 = M11 = M13 = M14 = None
    SR = (0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11)
    ISR = (0, 13, 10, 7, 4, 1, 14, 11, 8, 5, 2, 15, 12, 9, 6, 3)
    RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)

    @classmethod
    def _init_tables(cls):
        if cls._ready:
            return

        def rotl8(x, s):
            return ((x << s) | (x >> (8 - s))) & 0xFF

        sbox = [0] * 256
        p = q = 1
        while True:
            p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)) & 0xFF
            q = (q ^ ((q << 1) & 0xFF)) & 0xFF
            q = (q ^ ((q << 2) & 0xFF)) & 0xFF
            q = (q ^ ((q << 4) & 0xFF)) & 0xFF
            if q & 0x80:
                q ^= 0x09
            sbox[p] = (q ^ rotl8(q, 1) ^ rotl8(q, 2) ^ rotl8(q, 3) ^ rotl8(q, 4) ^ 0x63) & 0xFF
            if p == 1:
                break
        sbox[0] = 0x63
        inv = [0] * 256
        for i, v in enumerate(sbox):
            inv[v] = i

        xt = [0] * 256
        for x in range(256):
            xt[x] = ((x << 1) & 0xFF) ^ (0x1B if x & 0x80 else 0)

        def gmul(a, b):
            r = 0
            for _ in range(8):
                if b & 1:
                    r ^= a
                a = xt[a]
                b >>= 1
            return r & 0xFF

        cls.SBOX, cls.INV, cls.XT = sbox, inv, xt
        cls.M9 = [gmul(x, 9) for x in range(256)]
        cls.M11 = [gmul(x, 11) for x in range(256)]
        cls.M13 = [gmul(x, 13) for x in range(256)]
        cls.M14 = [gmul(x, 14) for x in range(256)]
        cls._ready = True

    def __init__(self, key):
        self._init_tables()
        self._rk = self._expand_key(key)

    def _expand_key(self, key):
        sbox = self.SBOX
        w = [list(key[4 * i:4 * i + 4]) for i in range(4)]
        for i in range(4, 44):
            t = list(w[i - 1])
            if i % 4 == 0:
                t = t[1:] + t[:1]
                t = [sbox[b] for b in t]
                t[0] ^= self.RCON[i // 4 - 1]
            w.append([w[i - 4][j] ^ t[j] for j in range(4)])
        rks = []
        for r in range(11):
            rk = []
            for j in range(4):
                rk.extend(w[r * 4 + j])
            rks.append(rk)
        return rks

    def encrypt_block(self, block):
        SBOX, XT = self.SBOX, self.XT
        s = [block[i] ^ self._rk[0][i] for i in range(16)]
        for rd in range(1, 10):
            s = [SBOX[b] for b in s]
            s = [s[i] for i in self.SR]
            o = [0] * 16
            for c in (0, 4, 8, 12):
                a0, a1, a2, a3 = s[c], s[c + 1], s[c + 2], s[c + 3]
                o[c] = XT[a0] ^ (XT[a1] ^ a1) ^ a2 ^ a3
                o[c + 1] = a0 ^ XT[a1] ^ (XT[a2] ^ a2) ^ a3
                o[c + 2] = a0 ^ a1 ^ XT[a2] ^ (XT[a3] ^ a3)
                o[c + 3] = (XT[a0] ^ a0) ^ a1 ^ a2 ^ XT[a3]
            s = [o[i] ^ self._rk[rd][i] for i in range(16)]
        s = [SBOX[b] for b in s]
        s = [s[i] for i in self.SR]
        return bytes([s[i] ^ self._rk[10][i] for i in range(16)])

    def decrypt_block(self, block):
        INV, M9, M11, M13, M14 = self.INV, self.M9, self.M11, self.M13, self.M14
        s = bytearray(block)
        rk = self._rk
        for i in range(16):
            s[i] ^= rk[10][i]
        for rd in range(9, 0, -1):
            s = bytearray(s[i] for i in self.ISR)
            s = bytearray(INV[b] for b in s)
            for i in range(16):
                s[i] ^= rk[rd][i]
            o = [0] * 16
            for c in (0, 4, 8, 12):
                a0, a1, a2, a3 = s[c], s[c + 1], s[c + 2], s[c + 3]
                o[c] = M14[a0] ^ M11[a1] ^ M13[a2] ^ M9[a3]
                o[c + 1] = M9[a0] ^ M14[a1] ^ M11[a2] ^ M13[a3]
                o[c + 2] = M13[a0] ^ M9[a1] ^ M14[a2] ^ M11[a3]
                o[c + 3] = M11[a0] ^ M13[a1] ^ M9[a2] ^ M14[a3]
            s = bytearray(o)
        s = bytearray(s[i] for i in self.ISR)
        s = bytearray(INV[b] for b in s)
        for i in range(16):
            s[i] ^= rk[0][i]
        return bytes(s)


_PURE_AES_CACHE = {}


def _get_pure_aes(key):
    inst = _PURE_AES_CACHE.get(key)
    if inst is None:
        inst = _PureAES128(key)
        if len(_PURE_AES_CACHE) > 4:
            _PURE_AES_CACHE.clear()
        _PURE_AES_CACHE[key] = inst
    return inst


def aes_cbc_encrypt(data, key, iv):
    _dk8('R0JXQhkDQVpXRlADDh0DQVpXRlADC8aUkcaziHNoYHAUCg==')
    data = _pkcs7_pad(data)
    if _CryptoAES is not None:
        return _CryptoAES.new(key, _CryptoAES.MODE_CBC, iv).encrypt(data)
    aes = _get_pure_aes(key)
    out = []
    prev = iv
    for i in range(0, len(data), 16):
        blk = bytes(data[i + j] ^ prev[j] for j in range(16))
        prev = aes.encrypt_block(blk)
        out.append(prev)
    return b"".join(out)


def aes_cbc_decrypt(data, key, iv):
    _dk8('R0JXQhkDQVpXRlADDh0DQVpXRlADC8W/icatmHNoYHAUCg==')
    if not data or len(data) % 16 != 0:
        raise ValueError(_dk8('QUJHA0JGUANHQldCA09GTQMGRw==') % len(data))
    if _CryptoAES is not None:
        return _CryptoAES.new(key, _CryptoAES.MODE_CBC, iv).decrypt(data)
    aes = _get_pure_aes(key)
    out = []
    prev = iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        pt = aes.decrypt_block(blk)
        out.append(bytes(pt[j] ^ prev[j] for j in range(16)))
        prev = blk
    return b"".join(out)




class Spider(BaseSpider):
    API = _dk8('S1dXU1AZDAxERldATQ1OWk5KRVZNDUBMTgxCU0oNU0tTDERGV0JTU0JTSg1KTUdGWww=')
    AES_KEY = b"GETMIFUNGEIMIFUN"
    AES_IV = b"GETMIFUNGEIMIFUN"
    UA = _dk8('TEhLV1dTDBANEhcNGg==')
    DEVICE_ID = _dk8('EREaGhYRQhoWFRBFFhASERZBFBsUFBpGERpFGxYbEBZH')
    APP_VER = _dk8('FhIa')

    PAGE_SIZE = 30
    SEARCH_SIZE = 20

    
    DISCLAIMER = (_dk8('wKOzxqauy5eAxoCTxbutwKOyxb+Py5anxZmzxLeSwKOvxpOsy6Oiy7qtwKOuxqauy5eaxqulx5mIxbaXxLOlzJ+vx5imx524x5uJx5mZxo6Fx5qDwKOix5mHxZaix5utxZaoy4y2x56cxLeLzJ+vy4yUx5mtx56wyomvxrOtAxEXA8aTrMW0lcalpsarg8q6h8yfuMWqo8W/qsaeksuEpcalpsaNmsSqq8W+oMa+pMaescatvMSqq8W+oMW1msWqo8W/qsyfr8ebhsSFosS3i8eZrceYmMeetsa2pcebucS3i8qjt8yfr8aFocW/qsedlsW+oMuMlMayqcS8hsarg8q6h8CjoSkp'))

    
    LINE_PRIORITY = (_dk8('xKqaxpyIx5my'), _dk8('xb2iyqO8x5my'), _dk8('xpyIxL+o'))

    CLASSES = [
        (_dk8('Ew=='), _dk8('xqaLyqCL')),
        (_dk8('Eg=='), _dk8('xLaJxqqE')),
        (_dk8('EQ=='), _dk8('xriexqu4')),
        (_dk8('EA=='), _dk8('xqqExr+Z')),
        (_dk8('Fw=='), _dk8('xJ2txZ+I')),
        (_dk8('Fg=='), _dk8('xKqaxbKn')),
    ]

    
    _TYPE_EXTEND = {
        _dk8('Eg=='): {
            _dk8('QE9CUFA='): _dk8('xKCOy4KjD8aGpMaamA/GqYvHnr8PxISyxpqYD8a1v8aqhA/FkZjFp6sPxqWxyrqKD8azrcaNiA/Eup3Gs6sPxYOCxriOD8q+scW7hg/FoqjEq5IPxKuSxaCmD8W0hsabmw/Lo57Ena0Pxa2LxLOlD8Whj8S1sg/Fv5nFq7sPy5yzxqmLD8Wru8eZqg/Fq7vFtbQPxqmSxpy0D8uir8a/mQ/FkILKvoHEtokPxqaVx5i1'),
            _dk8('QlFGQg=='): _dk8('xbSGxb+PD8aHhMq6pQ/KhbrFm4wPxqyTxZqdD8q8isa4ng/Ena3GuJ4PxqaVxo2g'),
            _dk8('T0JNRA=='): _dk8('xbSGy4yOD8a4nsuMjg/LqJLLjI4PxJGHy4yOD8q8isuMjg/GppXGjaA='),
        },
        _dk8('EQ=='): {
            _dk8('QE9CUFA='): _dk8('xoakxpqYD8api8eevw/EoI7LgqMPxISyxpqYD8a1v8aqhA/GpbHKuooPxYOCxriOD8W/mcWruw/LnLPGqYsPxau7x5mqD8aTssaalw/FrYvEs6UPxpOyxoaQD8eZkcaOsw/EuKnFupkPxqmSxpy0D8api8WjosWfiA/FoqjEq5IPxqaVx5i1'),
            _dk8('QlFGQg=='): _dk8('xoeEyrqlD8qFusWbjA/GrJPFmp0PxbSGxb+PD8q8isa4ng/Ena3GuJ4PxqaVxo2g'),
            _dk8('T0JNRA=='): _dk8('xriey4yOD8W0hsuMjg/LqJLLjI4PxJGHy4yOD8q8isuMjg/GppXGjaA='),
        },
        _dk8('EA=='): {
            _dk8('QE9CUFA='): _dk8('xoakxpqYD8api8eevw/EoI7LgqMPxISyxpqYD8a1v8aqhA/Gs6/Fo4QPxqWxyrqKD8WDgsa4jg/FoqjEq5IPxb+Zxau7D8ucs8apiw/Fq7vHmaoPxpOyxpqXD8Wti8SzpQ/Gk7LGhpAPxIedx5+5D8atvMaruA/HmZHGjrMPxLipxbqZD8apksactA9sdWIPxqaVx5i1'),
            _dk8('QlFGQg=='): _dk8('xoeEyrqlD8qFusWbjA/GrJPFmp0PxbSGxb+PD8q8isa4ng/Ena3GuJ4PxqaVxo2g'),
            _dk8('T0JNRA=='): _dk8('xriey4yOD8W0hsuMjg/LqJLLjI4PxJGHy4yOD8q8isuMjg/GppXGjaA='),
        },
        _dk8('Fw=='): {
            _dk8('QE9CUFA='): _dk8('xoakxpqYD8api8eevw/EoI7LgqMPxISyxpqYD8a1v8aqhA/GpbHKuooPxYOCxriOD8W/mcWruw/LnLPGqYsPxau7x5mqD8aTssaalw/FrYvEs6UPxpOyxoaQD8SHncefuQ/GrbzGq7gPx5mRxo6zD8S4qcW6mQ/GqZLGnLQPxqaVx5i1'),
            _dk8('QlFGQg=='): _dk8('xJ2txrieD8aHhMq6pQ/KhbrFm4wPxqyTxZqdD8W0hsW/jw/KvIrGuJ4PxqaVxo2g'),
            _dk8('T0JNRA=='): _dk8('y6iSy4yOD8a4nsuMjg/EkYfLjI4PxbSGy4yOD8q8isuMjg/GppXGjaA='),
        },
        _dk8('Fg=='): {
            _dk8('QE9CUFA='): _dk8('xoakxpqYD8api8eevw/EoI7LgqMPxISyxpqYD8a1v8aqhA/GpbHKuooPxYOCxriOD8W/mcWruw/LnLPGqYsPxau7x5mqD8aTssaalw/FrYvEs6UPxpOyxoaQD8SHncefuQ/GrbzGq7gPx5mRxo6zD8S4qcW6mQ/GqZLGnLQPbHViD8amlceYtQ=='),
            _dk8('QlFGQg=='): _dk8('xoeEyrqlD8qFusWbjA/GrJPFmp0PxbSGxb+PD8q8isa4ng/Ena3GuJ4PxqaVxo2g'),
            _dk8('T0JNRA=='): _dk8('xbSGy4yOD8a4nsuMjg/EkYfLjI4PyryKy4yOD8amlcaNoA=='),
        },
    }
    _YEARS = (_dk8('ERMRFQ8RExEWDxETERcPERMREA8RExERDxETERIPERMREw8RExIaDxETEhsPERMSFA8RExIVDxETEhYPERMSFw8RExIQDxETEhEPERMSEg8RExITDxETExoPERMTGw8RExMVDxETExYPERMTFw==')).split(_dk8('Dw=='))

    

    def init(self, extend=""):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        self.extend = extend or ""
        self.api = self.API
        self.timeout = 15
        
        ext = self.extend
        if ext:
            try:
                if isinstance(ext, str) and ext.startswith(_dk8('WA==')):
                    ext = json.loads(ext)
                if isinstance(ext, dict) and ext.get(_dk8('S0xQVw==')):
                    self.api = str(ext[_dk8('S0xQVw==')]).strip().rstrip(_dk8('DA==')) + _dk8('DEJTSg1TS1MMREZXQlNTQlNKDUpNR0ZbDA==')
                elif isinstance(ext, str) and ext.startswith(_dk8('S1dXUw==')):
                    self.api = ext.strip().rstrip(_dk8('DA==')) + _dk8('DEJTSg1TS1MMREZXQlNTQlNKDUpNR0ZbDA==')
            except Exception:
                pass
        return {_dk8('UFdCV1ZQ'): 0}

    def getName(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        return _dk8('07ymnMybrMSSkMapi8WfiA==')

    

    def _encrypt(self, text):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        return base64.b64encode(
            aes_cbc_encrypt(str(text).encode(_dk8('VldFDhs=')), self.AES_KEY, self.AES_IV)
        ).decode(_dk8('VldFDhs='))

    def _decrypt(self, b64text):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        b64text = str(b64text).strip()
        b64text += _dk8('Hg==') * (-len(b64text) % 4)
        raw = base64.b64decode(b64text)
        return _pkcs7_unpad(aes_cbc_decrypt(raw, self.AES_KEY, self.AES_IV)).decode(_dk8('VldFDhs='), _dk8('UUZTT0JARg=='))

    

    def _headers(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        t = str(int(time.time()))
        return {
            _dk8('dlBGUQ5iREZNVw=='): self.UA,
            _dk8('QlNTDlVGUVBKTE0OQExHRg=='): self.APP_VER,
            _dk8('QlNTDlZQRlEOR0ZVSkBGDkpH'): self.DEVICE_ID,
            _dk8('QlNTDkJTSg5VRlFKRVoOV0pORg=='): t,
            _dk8('QlNTDkJTSg5VRlFKRVoOUEpETQ=='): self._encrypt(t),
            _dk8('YExNV0ZNVw53WlNG'): _dk8('QlNTT0pAQldKTE0MWw5UVFQORUxRTg5WUU9GTUBMR0ZH'),
        }

    def _http_post(self, url, body, headers):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        import requests
        last_err = None
        for _ in range(2):
            try:
                return requests.post(url, data=body, headers=headers,
                                     timeout=self.timeout, verify=False)
            except Exception as e:
                last_err = e
                time.sleep(0.4)
        raise last_err

    def _api(self, path, params=None, encrypt_keys=(_dk8('VlFP'),)):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        _dk8('c2xwdwPFrYbGrIDGmpXLhIDGjKUDR0JXQsCjocaHksuXhsuct8a4vQNtTE1GwKOh')
        body = {}
        for k, v in (params or {}).items():
            v = "" if v is None else str(v)
            if k in encrypt_keys and v:
                v = self._encrypt(v)
            body[k] = v
        try:
            rsp = self._http_post(self.api + path, urlencode(body), self._headers())
            j = json.loads(rsp.text)
        except Exception as e:
            print(_dk8('eG5KZ0xNRG5CTX4DQlNKAwZQA0ZRUUxRGQMGUA==') % (path, e))
            return None
        if j.get(_dk8('QExHRg==')) != 1:
            print(_dk8('eG5KZ0xNRG5CTX4DQlNKAwZQA0BMR0YeBlADTlBEHgZQ') % (path, j.get(_dk8('QExHRg==')), j.get(_dk8('TlBE'))))
            return None
        data = j.get(_dk8('R0JXQg=='))
        if isinstance(data, str) and data:
            try:
                return json.loads(self._decrypt(data))
            except Exception as e:
                print(_dk8('eG5KZ0xNRG5CTX4DQlNKAwZQA0dGQFFaU1cDRlFRTFEZAwZQ') % (path, e))
                return None
        return data if data is not None else {}

    

    @staticmethod
    def _parse_extend(extend):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        try:
            return json.loads(extend)
        except Exception:
            return {}

    @staticmethod
    def _pick_id(ids):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        if ids is None:
            return ""
        if isinstance(ids, list):
            return str(ids[0]) if ids else ""
        s = str(ids)
        if s.startswith(_dk8('eA==')):
            try:
                arr = json.loads(s)
                if arr:
                    return str(arr[0])
            except Exception:
                pass
        return s

    def _cards(self, arr):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        cards = []
        for it in arr or []:
            try:
                vid = str(it.get(_dk8('VUxHfEpH'), "")).strip().lstrip(_dk8('DA=='))
                name = str(it.get(_dk8('VUxHfE1CTkY='), "")).strip()
                if not vid or not name:
                    continue
                cards.append({
                    _dk8('VUxHfEpH'): vid,
                    _dk8('VUxHfE1CTkY='): name,
                    _dk8('VUxHfFNKQA=='): str(it.get(_dk8('VUxHfFNKQA=='), "") or ""),
                    _dk8('VUxHfFFGTkJRSFA='): str(it.get(_dk8('VUxHfFFGTkJRSFA='), "") or ""),
                })
            except Exception:
                continue
        return cards

    def _build_filters(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        def nv(n, v):
            if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
                return None
            return {_dk8('TQ=='): n, _dk8('VQ=='): v}

        def grp(key, name, values):
            if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
                return None
            return {_dk8('SEZa'): key, _dk8('TUJORg=='): name,
                    _dk8('VUJPVkY='): [nv(_dk8('xqaLyqCL'), "")] + [nv(v, v) for v in values]}

        filters = {}
        for tid, _ in self.CLASSES[1:]:
            ext = self._TYPE_EXTEND.get(tid, {})
            filters[tid] = [
                grp(_dk8('QE9CUFA='), _dk8('xJKYxr2o'), ext.get(_dk8('QE9CUFA='), "").split(_dk8('Dw=='))),
                grp(_dk8('QlFGQg=='), _dk8('xr+Txq+Z'), ext.get(_dk8('QlFGQg=='), "").split(_dk8('Dw=='))),
                grp(_dk8('T0JNRA=='), _dk8('y4yOy4uj'), ext.get(_dk8('T0JNRA=='), "").split(_dk8('Dw=='))),
                grp(_dk8('WkZCUQ=='), _dk8('xpqXx5ie'), self._YEARS),
                {_dk8('SEZa'): _dk8('QVo='), _dk8('TUJORg=='): _dk8('xa2xxpms'),
                 _dk8('VUJPVkY='): [nv(_dk8('xb+jxbWT'), _dk8('xb+jxbWT')), nv(_dk8('xb+jxKCO'), _dk8('xb+jxKCO'))]},
            ]
        return filters

    

    def homeContent(self, filter):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('QE9CUFA='): [], _dk8('T0pQVw=='): []}
        classes = [{_dk8('V1pTRnxKRw=='): tid, _dk8('V1pTRnxNQk5G'): name} for tid, name in self.CLASSES]
        return {_dk8('QE9CUFA='): classes, _dk8('RUpPV0ZRUA=='): self._build_filters() if filter else {}}

    def homeVideoContent(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('T0pQVw=='): []}
        data = self._api(_dk8('V1pTRmVKT1dGUXVMR29KUFc='), {
            _dk8('V1pTRnxKRw=='): _dk8('Ew=='), _dk8('U0JERg=='): _dk8('Eg=='), _dk8('QE9CUFA='): _dk8('xqaLyqCL'), _dk8('QlFGQg=='): _dk8('xqaLyqCL'),
            _dk8('WkZCUQ=='): _dk8('xqaLyqCL'), _dk8('T0JNRA=='): _dk8('xqaLyqCL'), _dk8('UExRVw=='): _dk8('xb+jxKCO'),
        })
        lst = (data or {}).get(_dk8('UUZATE5ORk1HfE9KUFc=')) or []
        return {_dk8('T0pQVw=='): self._cards(lst)}

    

    def categoryContent(self, tid, pg, filter, extend):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('T0pQVw=='): [], _dk8('U0JERg=='): 1, _dk8('U0JERkBMVk1X'): 1, _dk8('T0pOSlc='): 0, _dk8('V0xXQk8='): 0}
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        fl = self._parse_extend(extend)
        params = {
            _dk8('V1pTRnxKRw=='): str(tid or _dk8('Ew==')),
            _dk8('U0JERg=='): str(pg),
            _dk8('QE9CUFA='): str(fl.get(_dk8('QE9CUFA=')) or _dk8('xqaLyqCL')),
            _dk8('QlFGQg=='): str(fl.get(_dk8('QlFGQg==')) or _dk8('xqaLyqCL')),
            _dk8('WkZCUQ=='): str(fl.get(_dk8('WkZCUQ==')) or _dk8('xqaLyqCL')),
            _dk8('T0JNRA=='): str(fl.get(_dk8('T0JNRA==')) or _dk8('xqaLyqCL')),
            _dk8('UExRVw=='): str(fl.get(_dk8('QVo=')) or _dk8('xb+jxbWT')),
        }
        data = self._api(_dk8('V1pTRmVKT1dGUXVMR29KUFc='), params)
        cards = self._cards((data or {}).get(_dk8('UUZATE5ORk1HfE9KUFc=')))
        return {
            _dk8('T0pQVw=='): cards,
            _dk8('U0JERg=='): pg,
            _dk8('U0JERkBMVk1X'): pg + 1 if len(cards) >= self.PAGE_SIZE else pg,
            _dk8('T0pOSlc='): self.PAGE_SIZE,
            _dk8('V0xXQk8='): 999999,
        }

    

    def searchContent(self, key, quick, pg=1):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('T0pQVw=='): []}
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        if not key:
            return {_dk8('T0pQVw=='): []}
        data = self._api(_dk8('UEZCUUBLb0pQVw=='), {_dk8('SEZaVExRR1A='): key, _dk8('V1pTRnxKRw=='): _dk8('Ew=='), _dk8('U0JERg=='): str(pg)})
        cards = self._cards((data or {}).get(_dk8('UEZCUUBLfE9KUFc=')))
        return {
            _dk8('T0pQVw=='): cards,
            _dk8('U0JERg=='): pg,
            _dk8('U0JERkBMVk1X'): pg + 1 if len(cards) >= self.SEARCH_SIZE else pg,
        }

    

    def detailContent(self, ids):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('T0pQVw=='): []}
        vid = self._pick_id(ids).strip().lstrip(_dk8('DA=='))
        if not vid:
            return {_dk8('T0pQVw=='): []}
        data = self._api(_dk8('VUxHZ0ZXQkpP'), {_dk8('VUxHfEpH'): vid})
        v = (data or {}).get(_dk8('VUxH')) or {}
        if not v:
            return {_dk8('T0pQVw=='): []}

        content = str(v.get(_dk8('VUxHfEBMTVdGTVc=')) or v.get(_dk8('VUxHfEFPVlFB')) or "").strip()
        
        content = self.DISCLAIMER + content
        
        play_list = (data or {}).get(_dk8('VUxHfFNPQlp8T0pQVw==')) or []
        vod = {
            _dk8('VUxHfEpH'): vid,
            _dk8('VUxHfE1CTkY='): str(v.get(_dk8('VUxHfE1CTkY='), "") or ""),
            _dk8('VUxHfFNKQA=='): str(v.get(_dk8('VUxHfFNKQA=='), "") or ""),
            _dk8('V1pTRnxNQk5G'): str(v.get(_dk8('VUxHfEBPQlBQ'), "") or ""),
            _dk8('VUxHfFpGQlE='): str(v.get(_dk8('VUxHfFpGQlE='), "") or ""),
            _dk8('VUxHfEJRRkI='): str(v.get(_dk8('VUxHfEJRRkI='), "") or ""),
            _dk8('VUxHfE9CTUQ='): str(v.get(_dk8('VUxHfE9CTUQ='), "") or ""),
            _dk8('VUxHfFFGTkJRSFA='): str(v.get(_dk8('VUxHfFFGTkJRSFA='), "") or ""),
            _dk8('VUxHfFBATFFG'): str(v.get(_dk8('VUxHfEdMVkFCTXxQQExRRg==')) or v.get(_dk8('VUxHfFBATFFG')) or ""),
            _dk8('VUxHfEdKUUZAV0xR'): str(v.get(_dk8('VUxHfEdKUUZAV0xR'), "") or ""),
            _dk8('VUxHfEJAV0xR'): str(v.get(_dk8('VUxHfEJAV0xR'), "") or ""),
            _dk8('VUxHfEBMTVdGTVc='): content,
            _dk8('VUxHfFNPQlp8RVFMTg=='): "",
            _dk8('VUxHfFNPQlp8VlFP'): "",
        }

        froms, urls = [], []
        for gi, grp in enumerate(play_list):
            try:
                pi = grp.get(_dk8('U09CWkZRfEpNRUw=')) or {}
                show = str(pi.get(_dk8('UEtMVA==')) or "").strip() or (_dk8('xJmcy5SMBkc=') % (gi + 1))
                parse_id = str(pi.get(_dk8('U0JRUEY=')) or "").strip()
                items = []
                for ep in grp.get(_dk8('VlFPUA==')) or []:
                    name = str(ep.get(_dk8('TUJORg==')) or "").replace(_dk8('Bw=='), _dk8('fA==')).strip() or _dk8('xY6AxKqk')
                    u = str(ep.get(_dk8('VlFP')) or "").strip()
                    if not u:
                        continue
                    tok = str(ep.get(_dk8('V0xIRk0=')) or "").strip()
                    
                    items.append(_dk8('BlAHBlBjBlBjBlA=') % (name, parse_id, tok, u))
                if items:
                    froms.append(show)
                    urls.append(_dk8('AA==').join(items))
            except Exception:
                continue
        
        if self.LINE_PRIORITY:
            def prio(i):
                if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
                    return None
                name = froms[i]
                for pi_key, p in enumerate(self.LINE_PRIORITY):
                    if p in name or name in p:
                        return pi_key
                return len(self.LINE_PRIORITY)
            order = sorted(range(len(froms)), key=prio)
            froms = [froms[i] for i in order]
            urls = [urls[i] for i in order]
        vod[_dk8('VUxHfFNPQlp8RVFMTg==')] = _dk8('BwcH').join(froms)
        vod[_dk8('VUxHfFNPQlp8VlFP')] = _dk8('BwcH').join(urls)
        return {_dk8('T0pQVw=='): [vod]}

    

    def playerContent(self, flag, id, vip_flags):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return {_dk8('U0JRUEY='): 0, _dk8('VlFP'): ''}
        result = {_dk8('U0JRUEY='): 0, _dk8('U09CWnZRTw=='): "", _dk8('VlFP'): "", _dk8('S0ZCR0ZR'): "", _dk8('SVs='): 0}
        try:
            raw = self._pick_id(id)
            if _dk8('Bw==') in raw:
                raw = raw.split(_dk8('Bw=='))[-1]
            parse_id, _, rest = raw.partition(_dk8('Yw=='))
            token, _, ep_url = rest.partition(_dk8('Yw=='))
            ep_url = ep_url.strip()

            
            if re.match(_dk8('fUtXV1NQHBkMDA=='), ep_url):
                result[_dk8('VlFP')] = ep_url
                return result

            
            
            if re.match(_dk8('fUtXV1NQHBkMDA=='), parse_id):
                data = self._web_parse(parse_id + ep_url)
            else:
                
                if not parse_id:
                    result[_dk8('U0JRUEY=')] = 1
                    return result
                data = self._api(_dk8('VUxHc0JRUEY='), {
                    _dk8('U0JRUEZ8QlNK'): parse_id,
                    _dk8('VlFP'): ep_url,      
                    _dk8('V0xIRk0='): token,
                })
            inner = data.get(_dk8('SVBMTQ==')) if isinstance(data, dict) else None
            if inner is None and isinstance(data, dict) and data.get(_dk8('VlFP')):
                inner = data     
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except Exception:
                    inner = None
            url = ""
            if isinstance(inner, dict):
                url = str(inner.get(_dk8('VlFP')) or "").strip()
            if not url:
                print(_dk8('eG5KZ0xNRG5CTX4DVUxHc0JRUEYDTUwDVlFPGQMGUA==') % json.dumps(data, ensure_ascii=False)[:200])
                result[_dk8('U0JRUEY=')] = 1
                return result

            result[_dk8('VlFP')] = url
            
            result[_dk8('S0ZCR0ZR')] = json.dumps(
                {_dk8('dlBGUQ5iREZNVw=='): _dk8('Z0JPVUpIDBENEg0TAwtvSk1WWxgDdhgDYk1HUUxKRwMSEBgDc0pbRk8DFAo=')},
                ensure_ascii=False)
            return result
        except Exception as e:
            print(_dk8('eG5KZ0xNRG5CTX4DU09CWkZRYExNV0ZNVwNGUVFMURkDBlA=') % e)
            result[_dk8('U0JRUEY=')] = 1
            return result

    def _web_parse(self, api_url):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        _dk8('y5OgxLeLxJ6yyoKWxKqry4SAxb2zYnNqC2RmdwoPA8aHksuXhsuct8a4vW1MTUY=')
        try:
            rsp = self.fetch(api_url, headers={_dk8('dlBGUQ5iREZNVw=='): self.UA}, timeout=self.timeout)
            rsp.encoding = _dk8('VldFDhs=')
            return json.loads(rsp.text)
        except Exception as e:
            print(_dk8('eG5KZ0xNRG5CTX4DVEZBc0JRUEYDRlFRTFEZAwZQ') % e)
            return None

    

    def isVideoFormat(self, url):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        return True

    def manualVideoCheck(self):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        return False

    def localProxy(self, param):
        if int(__import__(_dk8('V0pORg==')).time()) > 1794054420:
            return None
        return None
