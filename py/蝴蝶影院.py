# -*- coding: utf-8 -*-
import base64 as _UTrfp
import zlib as _QWxzwm
_TEvqxd = 1486990715
_QWqvb = 2136337060
def _SHqcju(d, k):
    return bytes(c ^ k for c in d)
_JYykg = lambda d, k: _SHqcju(_UTrfp.b64decode(d), k).decode('utf-8')
_GVicj = lambda d, k: _SHqcju(_UTrfp.b64decode(d), k)[::-1].decode('utf-8')
_GCdn = lambda d, k: _SHqcju(bytes.fromhex(d), k).decode('utf-8')
_JQuhhg = lambda d, k: _QWxzwm.decompress(_SHqcju(_UTrfp.b64decode(d), k)).decode('utf-8')
def _JVyref(n):
    try:
        d = _BPfny[n]
        k = (((_TEvqxd ^ (n * 2654435761)) >> (n & 7)) & 255) ^ (((n << 3) ^ _QWqvb) & 255)
        if k == 0:
            k = 158
        return (_JYykg, _GVicj, _GCdn, _JQuhhg)[(n ^ _QWqvb) & 3](d, k)
    except Exception:
        return ''
_BPfny = ['N0JpOmJuiw==', 'XXMteHQsf1Qh', '7f5d485b5e5e531d071c02121a7e5b5c474a0912735c56405d5b561b127342425e57655750795b461d0701051c0104', b'Dj\xcf\xd4\xbcN"\x01\xc1\xe6G\xf6}\x14O\xac\xc9\xd3\n\x16&D\x9ad\xb4', 'DQ8NDA==', b'\t\xd2\x0b{\xecS&\xca(', b'\x1c\xae\xe7W\xbb\xf56\x92\xa6\x92\x91\xa7\xff\xdbk\xb9\x95W0I\xeb\xe4\xcb\x13\x1f\xc4,\xc1\x9b\x11,]\xca\xd3\xd3\xac\xbc5\x95\xa3+f\xae\xb5\xc4K\xb5', 'GbtKTyhNSExnYWhYY8Q=', 'YXhzSHt2eXA=', 'rKi/rJKpors=', 'befda3e5a8', '5kStrJuengWe9g==', 'ZW8=', 'u7uppKuXrKe+', '89909ba08c9c908d9a', 'vB7vD4tNC48IicHEy8rHjg==', 'PDsgKyA4ISMgLis=', 'g56FkpSDmJWulZ6H', '116243134b47', '702klpeXopei', 'lYa7iqerk+6+oq+3q7yNoaC6q6C67qu8vKG89A==', '1drS0dLOz5Q=', '2e3d00311c1028552a121001551007071a074f555006', '40EQbbPuUtcWztPSttJXV+pVVLDSVrDK07axUbQpmZsOlJHh', 'qOb37qn37/eo4OA=', b'\x15\xedQ\xd5+r\xdeu\xff\xf9eI\xe7(\x91\x9a\xeb\x0f', 'e6e4e5e3', 'HrxNZWZmEWYR', 'VFZUVA==', 'ChwAHQ==', 'a8a4dfa0', 'BqRNzHp+fuF+Eg==', 'iZCboJaMmpGb', 'd0ceXlUf', b'3\x8c[\xc9\xa1\x91,&\xa3_', b'-t\x86>+:GoE\x89\xd22\n\xea\xd2\x9a', '6/L5wu3x/OTC++/y8A==', '7Ne2wuO2', '52505159', 'rQ+G09XV8dXx', b'\x08\x1c\x12\x97NU<\x0e\xcb0\x90\x86|\xf3\xb3X)\x9f\xf1hrY\xa0\x88\xe3\x92\x83(\xabZ!\xb6\x97k\xf3YH\xbe8', b'!#\x14\x1at\xeen\x10\x92\xee\x84*\x057\x03\x92B\xd3\x0f\xeaT\x01\xe3\xd9\xd4\x92ir\xed\x19\xd0\xb1f\x97\xe1Q\xed', '80f5de8dd5d98dedc5', b'\xf1\xf3h6u\x05\xf7C\xe3\xda\x1b\xe3[\x12\xd6', '2IbAjQ==', 'Dj9jNjpiMRpv', '545457', 'UPIDBeIpKCqaKXw=', 'AQ==', 'k4SFgISJ', 'a9f4e4abf3db', 'I4EIdo10kBcSltQUEnYSl5fqlBfqDnZdWwjwXMk=', 'npydlA==', '29ja2A==', '75696d7e', 'dNYnxSNFwA0MCoMOKQ==', '18bAwg==', 'TWYMTWAA', 'ebe9f8968cdec9ddd9c9dfd8df481034492924808cd9dec0c0c5ce492930491639844a2527492604440b0fcbd6c5dc85', '0nAhXILfY+Yn/yKFgmDl4P/ih4BghRj4+oesqsATovE=', b"\xac\x8f\xf1'\xd5z!\x0e\n\xe1\x97\xd7Z\x1e\x12:\xaa\x7f\x85O3", 'u7O/sA==', '26', 'mzmY0pQ4MF74fC197uPBheVJ', '7+3w5+ax7/fv', 'nZqAhQ==', 'e788aae4bea9', 'QeNMb1RqI24tx/eWAXQCMLUxu+0RoKS1X+ufjFMfo3fKsPi5e31PvOxRVF8JMDu/jiHmKJr/kwwzn3gcMcNmA0LW10fzZtHgZGnV4cSJ2YTeB84A3kD3eCTW3ERXAnHgu60EH6x2y8uf9/o/QAJBQaeKovQvsvxdgORdi+HJipzs5+Ofqss8g62N+jaVRonyUtfQ/Urr9w0FpdkElSZDAJbyJMFjt1OZ1CV+q9b8gM4Gzs9NesL6plEQxIwl6vCYUKtHEqVcUBtOrLnw2jXRlBQPo+QJeXpMsvcmW5nw/jfTKGgDdnIiSINBFfbHfDfrc6GLo+aflvvL/6hhA653yx1nm+gEqwDSgM5xPoyeOAFeGdFPtRhyL3FBjiOlYpp+VrVZVIuPDQ+MDGNieOeycsAQmK2VHt7B5+1dU+sGXL50J24GArdWtvL9tiBNDcAecESZ/Alw9dJwD8vGLA0CAJawyknf+HgKMXyFzEgC+jcQyN9fqvxTiw0iuBeX8pIYSMCtbd9AT/HUDuEIMIZKNRemJtbOOKnRjcHQbePh/FQckMfSj3BNKBrZF9ZMCKrBQ0iqIl0fgHjFJV7JWakkNLeLbjfrzZNh4W3Gh/KC/kBfS9HAMoHL0agd21r8cNMcE12Ra1kkFw7WzcOTcaMXI6tLxiHSSxk8Nd9+hPaFd0bEjMvPO9vo3ZetcarVGz8ETEPE50iWXm00bbr9wZNpYB4ykk1GanLTnyZIIZ297P7KfyneT7zzE8BrKXcS23h/N/wtT8zj7uHURZlSULRkxgkKkMBY+d7927U/RfUdh+XHnpXylO5NQZjqe9HrAwBFlIbnQcihBaKqG0J7SH8z/GhdWSFpK95F9zD+ebkkP0CafXMQbYNf678+1LZxcwikk4zfAJghW8M+R6YhVydU7Frm6Lyxy2z1LZ3KDLpvgVNdEPfl0ohMZ2AS/6G3t8/DHKvwCRr4CBZOQHxQt9DXQUsgKAdZO1XpZJ6Nj1jSXX9/zVvcFJ9TkRTPCDbighSMCZxqoV6l9tImkzxn5XqPG5Ez6uTCnS6XRBf78a5K/wz4yu4elJJWYEjfob+fzR1FEVYWqlSNWCHpNg9i4tSP78NHb1Jjkp2Av1c+NCeY3E5ef+wrHcggh4TGYmZuyloFm+8z1aNM2abQYGlgYKKiIq3ns3w16epQPZgLFPSFLWZHmKbv3KwtZBTYY0i2fQZT8h2KPzbDg0d44LaJiNxxe/P2GoWfdwSFLQeqS0Axy5WyRNfOiHcuNUoP6SHTbNajSPgxHaz+fKUCTc/5meWvmXJArOQOMbWzoyws9LMFX5zRxvQ4QFqlXyDC7IhByw5kdKmgNMhaZ2d3sZwkGnHeSnM3h0j/Mw4NHMlnA05POkn56swq5ZxyXlO20SBrQ7YTIBfel2sZ1BeYoT3sZ3uIfevhIhhpNjhv9zejk3tIMra6ooptzr3qCbAc/Utx/EmRoACtrSj4YU4yMCYyrFyrstpdfl0Qa2nq7Pfr9QB0VetRI43aHaSttzc4gmfcmnQ7baZVHFHYbZZoOFLSVJETlOFY/ZXg4gXbpMnjeAqATctgk9UaXBrNxLN8+vhxBvZSbAtvPpmFTXVKfntIqq1m0HHPlGlwcYB6JdazCCKSQKvNfsE69fm5QSkaPrLbxw93sQ7cksul2okAnMo8mMs3f39g55Q2Az7l9ZRiPyxzpAgBj8l+PUYBmvOxp3wAT73bpV//o3iseU7ZJ9Le5EcnUQd8zg793RhwFJFPG2oSW8AkAGFraCRludRO7hcGoxvcra3+E5zPCYf8v10opVUs6bMdhHSb8pOO/Kzu6e9V0NNpdBWtbtGiPENJc6qiYeISgegUq2KY0igroI/uwzZxAL2ptVvuAgn5dkm5BoMBCy7ZmyiJb8GHaqxnlg2guP8rLiTvQQBOrKPxIMX+Ok7aM4rWLX/bQ7hdah0j+HtYiGyqmQ74mMIur6Rq8w==', b'\x1c\x07\xc8!\xd6\xb6\xe8"\xf7\xc4\xfc9\xab_\xa6\x19\xfe\x81LJ\x8f|\x97\xc6\x04\xd3\x1cCc\xbfd7Q\xddWd*\x11g\xd6h\x96\xf8\xf2\xdc~', 'sbOssLOssa3y9vbq6e0=', 'dbb8a8ddbdb5d08c9bdd9b88dea0b6dbb8a9dea494d08dbcde82a8dfac89dbb8b4dd88b7d0b8b9d0a1b6dbb8b5ddbdb5d08c81ddb0bedc8293dead8cdfa8bed784b4dc83bddc86a3dc8092dc8282dd959edc8198dbb8b9dc829cde8db9dc80b6de8db3d097addc8587dfac90d784b4d0978fdc82b6dc85abd192b4dda8b6180a0c18dd88b7deaf8eddbebdddb098d1a19cd784a3deb1b8dea4b1dd8589d09fbeddbebddd9681dfb1b0dea5bbdda5bfdd85aaddb6a7dfb1b0dea5bbdeae81deb1b8dea4b1d784b4dc809ddf9eb9dfac90dc82b6dc8383dc85adddadbedc80a2dfac90d1b8acd784b4dd9ebadea4b1dc868ddea5bbd0978fdda9b2dfa79dddb098d1a19cdbb8ba3232', 'PpxtakJGRxNGpQ==', 'ZWdmZA==', 'iJ6fjJ0=', '8a908c898e8b', '8FK7uri8iYiJeohA', b'~\xbc\x87\xaa\xef\x10\x04H\xe7m\xbdq\x7f\x18\xff\xb7\x1c\xb3\xa4\xd3\xb5\x1b\x16\x9bE\xdf\x01\xa8\xf2\xf9\x89n{aU\xa7\x12', 'QUQ=', 'c8b98bc7b187', '5Ue2VtIU0le0sNefnY9Bnl0=', 'eWBrUGxgYXtqYXs=', 'ISMhIw==', b'\xd2\x9f\x15/\x8e\x93q\xe9\x8f\xa9\xa5\xa1_\x0f\xd8T\x9fi\xc4G\x10\xd6\x1d\x191\xe5\xdfN\xc74\xe4!\xc8K\xd9\x19', 'Z8VkpWLMzGoi0GhQGR89QRm8', 'XltfW0Y=', 'YXQ/LSw=', b'\x11\xb3:\xffjv\xa1n\x95\xcbL\xfcR\x03\x93O1\x89\xd2p', b'3\xe4\x85n\x96\xd44\x08\xa7\xdd@\xc2;\xa7&\x92VH\x92\xdd\x83\x08\x87\xf2\x98\x0f\x81\xbb\x93\xa0', '4rTot6a1tKKYsa6joqj4par64rThsrWr+uK0', 'Lxx9KS5y', '01570b574b5157514b1b50415c50190157', 'ljSV35k1PVP1cQKG7u7MbOhF', b'g\xad*\x9f\xce\x9e\x88\xff\xd1>\xba\x0e\x07\x02\xb1\x9c\xc2&h`J*\x1f\xf5\xc1\xa0\x0f\x8f\xd9\xb9\xae\x83\x05A\t0\xf8', b'\xf4dZ\x9f\xaa`\xc9\xa9\xc7\n\x1c\xf4\x9aV\xe1\xe3\x8dZ\xea\xd2\x87\xdd\xa0\xfe;\xf11\xa8\x92\x1e\xff', '14090309', 'L418nBjeeJ8bUVdch1Wy', 'msyQ3N7W0dbH1tfK3tGAy9bbgprMmdHW3tGCmsw=', 'QFtX', '72072c7f272b7f3e1d7f2325', 'hSeGJ8wAOD/o0uoTqYUpy7Rc0cIYlBI/GmAQ/VKu8/s=', 't6CttKQ=', 'zImB15XUzJaB14LUzJWYhc6TlJWYh96C1A==', '3b4e65366e6237695f', 'UvAB4WWj5WYrKiLyKFw=', 'RUc=', b"5\x9fH^\xce\x91\n\x07\xd3\xa6E\xa3\x1c\xc3\x1e'f\xfd\xa8\xaaY", '561e140e', 'tBaf4Zqd4crMz3/NmQ==', 'CBAAEA==', 'AQEB', '7b', 'edsyBQEBMwEz', 'x7KZypKeyouoyLuH', 'Lg==', '70332e6a', 'uxnoau+LTgyPwsPP48Es', b'C\xf8\xdf\xc2\x0e\xfa\x809A\x0c3\xf6\x9f\x968\xc2\xf7\xfak!\xa1\xfc\x84l\x95}pM\xa7\xe5\xb5', '5Pr91/Hp5Pg=', '194a7e1a437019715d194a741a556d1b426c184e441a6174d71a70551750441a6c721a456b1a5b4bc9cb1a526817757dd3df16674d19525dbdbdbe18657bc6cfcfb2bd184558928fcb197469195244d6f5dfdfdfdfdfdfdfdf17406b1a6461dfd892cc8ac7d8dfd0dfd8928fcbd8dfd0dfd8d8', 'HL4fvt2YgYhSZGtAYEQ=', b'7\xcf\x89\xe9\xd7d\xec\x11}\xd57/m\xbaS\x8a\xc8', b'\x08\xe0lQ*^x\x85\xf1\xbe\xb7\xb9pt\xf3F\xc3\xd6\xd8\x83\xb7\xe9\x99\x164\xc23\x8dD\xba\x81h,OU\x07', '4c231a3754210854210a59010d55251e', b"#DZ'\xb1.GU\x15\x89\xd9Z\x8c\xf6/\xeb\xf3\xae\\]\x99\xaar\xcd\xe4j\xdf", b'u\xc6\x1c\x11\x88\xc3\xa5\xd9\xd3{\xf2)\x17\xf9\x9eJ\x9a\t8$i\xca\xac{\xa8f\xca\x152\x87\x92\x9ex\t', 'HQgdGA==', '1d010105', b'\x15\x17\xd1)9+q\x0b+\x7f\xf1#\x06\xd8\x02e[4(\xe4FT\x9d~>^\xed8\xe9g\xa2$\xde}D\xe9p\x0bL\xa8\xa2t\xee:', 'bW9ubw==', 'e2Z9amhWbWZ/', b'1\x83N8\xaf\xae&\xcc\x84=\xc1v\x93\xf1\xecUI\xe02\xc5\xeb', '2XuKaegNrYxroKGqFqNL', 'z9PT152IiJaWlomWkJeJlpOWiZaRn52fng==', 'WUVL', 'd9dbdadd', '5kStrK6snZ6faJ5V', b'\x12\x14\xd0\x8a\x1f\xbf\x9a\xe1\x9a\x97y\xa6p4\xd5\x85\xfb~\xff\x8ed\xa0TC\x19\x99\ns\x86;\x08N;', '6P302aD54+j54+LO', '869f94af82959d91829b83', 'SOq7NzAwUDBQ', 'rqyptq8=', 'uA==', b"\x1c\xda\xb8_V\xc1Wi\xe1'\x8b&G\xd2\x83\xe5\xbd7\xf9&_\x082\xbey\xbaa\xd5\xd7ol", b'\xae\x04v\xb20^\x9c\x86,>\xef\xd0\xc3v9\xe7)\x14v7\x82\x11T27\x93f', '7w147w==', 'CUQCXEVFSFU=', 'e4e6e7e3', '/12sTkjJSvw57HgMamySmTLK1a/Pq63JCqhMy85K0P82+3Y0/pQZMWj9sfpcNC6ajYK+DhJ2IsK+243XdyUsbv5USeCckLvcWHjrSsUPfRA0fRhKXnIzJGri7CgyxfvG1vnVLUVUCaLIUErVT7KpMldIqrfW/7ksal4T6r33FBlr6dJ3j3Zy1v85MXRuGSEgvPG7Glt881AT4Bo6SP2Qxmv+Xll85XrTCuD0nRmpHuKLM8iUhzsD4pY=', 'ABkSKQYaFw8pAwQa', b'\x98\x91N\xab\x90\xe3\xcf\xba\x84\xea}v\x16\x97o(i\x11\xd9\x8e\xaf\x81\xd9\xb3\xcaV\x87\xe9Z@\xfa\xe179VR\xcd\x02\x80\x89,', 'cc', 'sBLDuDz7zMjKHMnZ', 'ZWF9fmo0cj8=', 'h4SFhw==', b"\xbfD\xe7\xdb'\x8c\xb8", 'bsw93VmfuVpbOhQWGS0VTA==', 'C1daClVT', b"E\x07?\x1e\xb09\x82\xac\x9erq&F\xb7\xe7\xd5l'\xa6\xa0\x8c\xc8\xaa\xdf\xf3$\x1d\x83\xfb\x07\xbc-\xd88\xf8\x97\x8c\xa7\x07\x8b\xcb\x0f", 'e0fdb9', b"\xde'\xad\x06\xb9\xd6\xb5S\xcat\x19d\xbf", 'FhgREA0a', 'DUlUFlZcXVBP', '3f190f18472b0d0f041e', 'Hb9OzEkt6KouqShgZXYtZqY=', 'ZmlkdnY=', '7Lq/7Lq/pe3w7e36v/Hw7PXAv8L69tvq18Q=', 'b0b2b0b6', 'ethJTS/LNyy3AgII6wCM', 'mMfb1s6Yw8SY', 'ydPI0t7Y2tzN', '7a787979', 'DK5HRkRGcXR1gXS+', 'W1RRSVhPTg==']

_JVyref(67)

import json
import sys
import os
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

        def fetch(self, url, params=None, headers=None, cookies=None, timeout=10, **kw):
            import requests
            return requests.get(url, params=params, headers=headers,
                                cookies=cookies, timeout=timeout, verify=False)


class Spider(BaseSpider):
    HOST = _JVyref(132)
    API = HOST + _JVyref(24)
    UA = _JVyref(69)
    
    PLAY_UA = _JVyref(2)

    
    DISCLAIMER = (_JVyref(70))

    
    CLASSES = [
        {_JVyref(115): _JVyref(110), _JVyref(163): _JVyref(119)},
        {_JVyref(115): _JVyref(111), _JVyref(163): _JVyref(18)},
        {_JVyref(115): _JVyref(104), _JVyref(163): _JVyref(89)},
        {_JVyref(115): _JVyref(19), _JVyref(163): _JVyref(66)},
        {_JVyref(115): _JVyref(77), _JVyref(163): _JVyref(33)},
        {_JVyref(115): _JVyref(12), _JVyref(163): _JVyref(78)},
        {_JVyref(115): _JVyref(31), _JVyref(163): _JVyref(50)},
        {_JVyref(115): _JVyref(11), _JVyref(163): _JVyref(37)},
    ]
    YEARS = [_JVyref(135), _JVyref(171), _JVyref(166), _JVyref(4), _JVyref(28), _JVyref(53),
             _JVyref(81), _JVyref(38), _JVyref(52), _JVyref(26), _JVyref(134), _JVyref(146),
             _JVyref(75), _JVyref(72), _JVyref(153), _JVyref(170), _JVyref(128)]

    
    FLAG_NAMES = {
        _JVyref(152): _JVyref(91),
        _JVyref(30):     _JVyref(102),
        _JVyref(46):      _JVyref(45),
        _JVyref(140):    _JVyref(63),
        _JVyref(97):      _JVyref(1),
        _JVyref(29):     _JVyref(42),
        _JVyref(151):     _JVyref(0),
        _JVyref(94):     _JVyref(112),
        _JVyref(145): _JVyref(98),
    }
    
    WEB_FLAGS = (_JVyref(71), _JVyref(74), _JVyref(108))
    
    BM_ALIAS = {_JVyref(30): _JVyref(29)}

    def init(self, extend=""):
        self.extend = extend or ""
        self.timeout = 15
        self._cache = {}
        return {_JVyref(7): 0}

    def getName(self):
        return _JVyref(122)

    

    def _headers(self):
        return {_JVyref(162): self.UA}

    def _get(self, url):
        _JVyref(58)
        if url in self._cache:
            return self._cache[url]
        try:
            import requests
            rsp = requests.get(url, headers=self._headers(),
                               timeout=self.timeout, verify=False)
            html = rsp.text or ""
        except Exception:
            try:
                import urllib.request
                import ssl
                req = urllib.request.Request(url, headers=self._headers())
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                    raw = r.read()
                if raw[:2] == b"\x1f\x8b":
                    import gzip
                    raw = gzip.decompress(raw)
                html = raw.decode(_JVyref(85), _JVyref(160))
            except Exception as e:
                print(_JVyref(22) % e)
                return ""
        if len(self._cache) > 24:
            self._cache.clear()
        self._cache[url] = html
        return html

    def _json(self, url):
        try:
            t = self._get(url)
            j = json.loads(t)
            return j if isinstance(j, dict) else {}
        except Exception as e:
            print(_JVyref(165) % (url, e))
            return {}

    

    @staticmethod
    def _card(it):
        _JVyref(99)
        vid = str(it.get(_JVyref(103)) or "").strip().lstrip(_JVyref(113))
        if not vid:
            return None
        return {
            _JVyref(103): vid,
            _JVyref(15): str(it.get(_JVyref(15)) or "").strip(),
            _JVyref(95): it.get(_JVyref(95)) or "",
            _JVyref(138): it.get(_JVyref(138)) or "",
        }

    @staticmethod
    def _cards(items):
        out, seen = [], set()
        for it in (items or []):
            c = Spider._card(it)
            if c and c[_JVyref(103)] not in seen:
                seen.add(c[_JVyref(103)])
                out.append(c)
        return out

    

    def homeContent(self, filter):
        filters = {}
        if filter:
            year_vals = [{_JVyref(48): _JVyref(57), _JVyref(27): ""}] + [{_JVyref(48): y, _JVyref(27): y} for y in self.YEARS]
            for c in self.CLASSES:
                filters[c[_JVyref(115)]] = [
                    {_JVyref(133): _JVyref(54), _JVyref(61): _JVyref(156), _JVyref(100): year_vals},
                ]
        return {_JVyref(164): list(self.CLASSES), _JVyref(172): filters}

    def homeVideoContent(self):
        j = self._json(self.API + _JVyref(21))
        merged = []
        for g in (j.get(_JVyref(65)) or []):
            if isinstance(g, dict):
                merged += (g.get(_JVyref(65)) or [])
        return {_JVyref(65): self._cards(merged)}

    

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg or 1))
        try:
            fl = json.loads(extend) if isinstance(extend, str) and extend.strip() else (extend or {})
        except Exception:
            fl = {}
        year = str(fl.get(_JVyref(54), "") or "").strip()
        if year and year != _JVyref(57):
            
            j = self._json(_JVyref(96) % (self.API, quote(str(tid)), quote(year)))
            lst = self._cards(j.get(_JVyref(65)))
            return {_JVyref(65): lst, _JVyref(56): 1, _JVyref(169): 1,
                    _JVyref(84): max(1, len(lst)), _JVyref(55): len(lst)}
        j = self._json(_JVyref(101) % (self.API, quote(str(tid)), pg))
        lst = self._cards(j.get(_JVyref(65)))
        pagecount = int(j.get(_JVyref(169)) or 0)
        if pagecount <= 0:
            pagecount = pg if len(lst) < 21 else pg + 1
        return {_JVyref(65): lst, _JVyref(56): pg, _JVyref(169): pagecount,
                _JVyref(84): int(j.get(_JVyref(84)) or 21), _JVyref(55): int(j.get(_JVyref(55)) or 999999)}

    

    def searchContent(self, key, quick, pg=1):
        pg = max(1, int(pg or 1))
        if not key or pg > 1:
            return {_JVyref(65): []}  
        j = self._json(_JVyref(90) % (self.API, quote(str(key))))
        lst = self._cards(j.get(_JVyref(65)))
        return {_JVyref(65): lst, _JVyref(56): 1, _JVyref(169): 1,
                _JVyref(84): max(1, len(lst)), _JVyref(55): len(lst)}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    

    def _pick_first_id(self, ids):
        if isinstance(ids, list):
            return str(ids[0]) if ids else ""
        s = str(ids or "")
        if s.startswith(_JVyref(150)):
            try:
                arr = json.loads(s)
                if arr:
                    return str(arr[0])
            except Exception:
                pass
        return s

    def detailContent(self, ids):
        try:
            vid = self._pick_first_id(ids).strip().lstrip(_JVyref(113))
            if not vid:
                return {_JVyref(65): []}
            j = self._json(_JVyref(51) % (self.API, quote(vid)))
            d = j.get(_JVyref(125)) or {}
            if not d.get(_JVyref(103)):
                return {_JVyref(65): []}

            
            play_groups = str(d.get(_JVyref(148)) or "").split(_JVyref(109))
            from_names, group_urls = [], []
            for idx, flag in enumerate(str(d.get(_JVyref(36)) or "").split(_JVyref(109))):
                if not flag or flag in self.WEB_FLAGS or idx >= len(play_groups):
                    continue
                eps = []
                for ep in play_groups[idx].split(_JVyref(39)):
                    if _JVyref(62) not in ep:
                        continue
                    name, path = ep.split(_JVyref(62), 1)
                    eps.append(_JVyref(107) % (name.replace(_JVyref(62), _JVyref(139)).strip(), path.strip()))
                if eps:
                    from_names.append(self.FLAG_NAMES.get(flag, flag))
                    group_urls.append(_JVyref(39).join(eps))

            vod = {
                _JVyref(103): str(d.get(_JVyref(103))),
                _JVyref(15): str(d.get(_JVyref(15)) or "").strip(),
                _JVyref(95): d.get(_JVyref(95)) or "",
                _JVyref(163): str(d.get(_JVyref(13)) or "").replace(_JVyref(141), _JVyref(144)),
                _JVyref(155): str(d.get(_JVyref(155)) or ""),
                _JVyref(9): str(d.get(_JVyref(9)) or ""),
                _JVyref(8): str(d.get(_JVyref(8)) or ""),
                _JVyref(138): _JVyref(83) if d.get(_JVyref(32)) else (d.get(_JVyref(138)) or ""),
                _JVyref(14): str(d.get(_JVyref(14)) or ""),
                _JVyref(17): str(d.get(_JVyref(17)) or ""),
                _JVyref(129): str(d.get(_JVyref(129)) or ""),
                _JVyref(80): self.DISCLAIMER + str(d.get(_JVyref(80)) or d.get(_JVyref(79)) or "").strip(),
                _JVyref(36): _JVyref(109).join(from_names),
                _JVyref(148): _JVyref(109).join(group_urls),
            }
            return {_JVyref(65): [vod]}
        except Exception as e:
            print(_JVyref(23), e)
            return {_JVyref(65): []}

    

    def _resolve_token(self, flag, token):
        _JVyref(147)
        last = ""
        for _ in range(3):
            url = _JVyref(88) % (
                self.API, quote(flag, safe=""), quote(token, safe=""))
            j = self._json(url)
            data = j.get(_JVyref(125)) or {}
            last = str(data.get(_JVyref(117)) or "").strip()
            if not last.startswith(_JVyref(126)):
                continue
            kind = self._probe(last)
            if kind in (_JVyref(44), _JVyref(158)):
                return last
        return last

    def _probe(self, url):
        _JVyref(118)
        ua = {_JVyref(162): self.PLAY_UA}
        
        try:
            import requests
            rsp = requests.get(url, headers=ua, timeout=self.timeout,
                               verify=False, stream=True)
            ct = (rsp.headers.get(_JVyref(137)) or "").lower()
            chunk = b""
            for c in rsp.iter_content(64):
                chunk = c
                break
            rsp.close()
            if chunk.startswith(b"#EXTM3U") or b"#extm3u" in chunk.lower():
                return _JVyref(44)
            if _JVyref(161) in ct or (len(chunk) >= 8 and chunk[4:8] == b"ftyp"):
                return _JVyref(158)
            return ""
        except Exception:
            pass
        
        try:
            import urllib.request
            import ssl
            req = urllib.request.Request(url, headers=ua)
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                ct = (r.headers.get(_JVyref(137)) or "").lower()
                chunk = r.read(64)
            if chunk.startswith(b"#EXTM3U") or b"#extm3u" in chunk.lower():
                return _JVyref(44)
            if _JVyref(161) in ct or (len(chunk) >= 8 and chunk[4:8] == b"ftyp"):
                return _JVyref(158)
            return ""
        except Exception as e:
            print(_JVyref(59) % e)
            return ""

    def playerContent(self, flag, vid, vip_flags):
        result = {_JVyref(73): 0, _JVyref(131): "", _JVyref(47): "",
                  _JVyref(49): json.dumps({_JVyref(162): self.PLAY_UA}, ensure_ascii=False)}
        try:
            s = vid if isinstance(vid, str) else json.dumps(vid, ensure_ascii=False)
            path = s.rsplit(_JVyref(62), 1)[-1].strip()
            if not path:
                return result
            if path.startswith(_JVyref(126)):
                
                result[_JVyref(47)] = path
                return result
            
            api_flag = flag
            for f, name in self.FLAG_NAMES.items():
                if flag == name:
                    api_flag = f
                    break
            
            bm = self.BM_ALIAS.get(api_flag, api_flag)
            if bm != api_flag and path.startswith(api_flag + _JVyref(139)):
                path = bm + _JVyref(139) + path[len(api_flag) + 1:]
            
            play = self._resolve_token(bm, path)
            if play.startswith(_JVyref(126)):
                result[_JVyref(47)] = play
            return result
        except Exception as e:
            print(_JVyref(20), e)
            return result

    

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in (_JVyref(10), _JVyref(114), _JVyref(106), _JVyref(168),
                                    _JVyref(167), _JVyref(16), _JVyref(64)))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None
