# -*- coding: utf-8 -*-
# 【对照版·无限制】所有日志长度相关的截断/限额均已移除，仅用于排查
"""
繁花剧场（com.dzhong.fhjc 2.28.1）— 影视+ Python 源

写法完全对齐可正常工作的同类源（dyx.py）：
  · 不自定义 __init__（不调用任何基类初始化）
  · 不继承基类失败时再退回到普通 object
  · 所有状态用类属性或 init 内赋值
  · 每个对外方法都返回合法结构，任何情况都不返回 None
    （尤其 localProxy 必须恒返回 4 元组，Java 侧会 asList().get(0)）
"""
import base64
import binascii
import importlib
import json
import random
import re
import time

try:
    import requests
except Exception:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def __init__(self):
            pass


# ─────────────────────────── 常量 ───────────────────────────
_HOSTS = ["https://flowerapi.kydca.cn",
          "https://flowerapi.kydcb.cn",
          "https://flowerapi.kydbg.cn"]
_KEY = b"di@$z^o$#f@$^u@j"
_IV = b"dzf@$^u@juc^@$#$"
_ST = "l1t5u51n1wk1yfor1ncrypt"
_UA = "okhttp/4.12.0"
_PKG = "com.dzhong.fhjc"

_C_HOME = "1126"
_C_SEARCH = "1201"
_C_CATALOG = "1301"
_C_PLAY = "1303"

_RSA_N = int(
    "a79da6ea653778eca2db99bf9a2832c33ac84ac65a14fa102a55380eef4db97a0f27267adca473563b527b3b215c33ea5b17da458bf0aa3569e5532886ffd52c7b960674116596386f172ef8870a9c1d3c8fb243c8eefab7d49db75921d97ac57b87d466677115c3018226d2750f4d1f7fff5c3f99b853fe23ddb7cd1e44c82fbf64169e4620f0a26d81a11d0b82635e15be336cc98f7c661bf1fbcca52a5c6630426ca0ae121b6d50b3ac5be84606200bedd1cae7160417be0577c3fbf44610fd00a0a48d93bda1a7767fccee86a4aac3caaf8ab594c586731d43065b777c133276c18fcbb79a13cf5841967d22801682a3d7786b926a732110d1dff0bbbf1b", 16)
_RSA_D = int(
    "6083e5fe284435ec44a6a0b47466db3c11980d7e83967a9b5e54edcfa3ba24a8051bad0ba80b45a28ccc24cb5a9d4603976a77b3fe2d9944e2723b5d25c7208fd9a5fc974f0128ebdc040476f50385fb4bc90e83fbaaa851bc2b08cd59316a81566d533f9826c4ba221f388d8cfc3f9378d7a8ddb27d32582f7cd6fe548494a3fe94f256944cdeb9142a8973a3e83422d81bc69a03ae4bfbba2e18cdda45552b1a08eb6c2b7b2d1fbff88d1f9c81caac871d4c001052a4e64e0fe075d46063048774b32a9011583e333cd2993877696b29d0e9ae72fadacadd8c3b0549160f5551ea125367ac6cb73af5594836603ddd32646703b2f2a20bbf75d3abbbef8449", 16)
_RSA_E = 65537

_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]
_INV = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV[_v] = _i
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xt(a):
    a <<= 1
    return (a ^ 0x1b) & 0xff if a & 0x100 else a


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xt(a)
        b >>= 1
    return r & 0xff


def _expand(key):
    w = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return [bytes(b for word in w[r * 4:r * 4 + 4] for b in word) for r in range(11)]


def _shift(s, inv=False):
    for r in range(1, 4):
        row = [s[r + 4 * c] for c in range(4)]
        row = row[-r:] + row[:-r] if inv else row[r:] + row[:r]
        for c in range(4):
            s[r + 4 * c] = row[c]


def _mix(s, inv=False):
    m = [14, 11, 13, 9] if inv else [2, 3, 1, 1]
    for c in range(4):
        col = s[c * 4:c * 4 + 4]
        s[c * 4:c * 4 + 4] = [
            _mul(col[0], m[0]) ^ _mul(col[1], m[1]) ^ _mul(col[2], m[2]) ^ _mul(col[3], m[3]),
            _mul(col[0], m[3]) ^ _mul(col[1], m[0]) ^ _mul(col[2], m[1]) ^ _mul(col[3], m[2]),
            _mul(col[0], m[2]) ^ _mul(col[1], m[3]) ^ _mul(col[2], m[0]) ^ _mul(col[3], m[1]),
            _mul(col[0], m[1]) ^ _mul(col[1], m[2]) ^ _mul(col[2], m[3]) ^ _mul(col[3], m[0]),
        ]


def _blk(block, rks, enc=True):
    s = list(block)
    box = _SBOX if enc else _INV
    if enc:
        for i in range(16):
            s[i] ^= rks[0][i]
        for rnd in range(1, 11):
            s = [box[b] for b in s]
            _shift(s)
            if rnd != 10:
                _mix(s)
            for i in range(16):
                s[i] ^= rks[rnd][i]
    else:
        for i in range(16):
            s[i] ^= rks[10][i]
        for rnd in range(9, -1, -1):
            _shift(s, True)
            s = [box[b] for b in s]
            for i in range(16):
                s[i] ^= rks[rnd][i]
            if rnd != 0:
                _mix(s, True)
    return bytes(s)


def _pure_cbc(key, iv, data, enc=True):
    rks = _expand(key)
    out = bytearray()
    prev = iv
    if enc:
        for i in range(0, len(data), 16):
            b = bytes(x ^ y for x, y in zip(data[i:i + 16], prev))
            e = _blk(b, rks, True)
            out += e
            prev = e
    else:
        for i in range(0, len(data), 16):
            d = _blk(data[i:i + 16], rks, False)
            out += bytes(x ^ y for x, y in zip(d, prev))
            prev = data[i:i + 16]
    return bytes(out)


def _enc(text):
    raw = text.encode("utf-8")
    n = 16 - len(raw) % 16
    raw += bytes([n]) * n
    for mod in ("Crypto.Cipher.AES", "Cryptodome.Cipher.AES"):
        try:
            AES = importlib.import_module(mod)
            return AES.new(_KEY, AES.MODE_CBC, _IV).encrypt(raw).hex()
        except Exception:
            continue
    return _pure_cbc(_KEY, _IV, raw, True).hex()


def _dec(hexstr):
    try:
        raw = binascii.unhexlify(re.sub(r"\s+", "", str(hexstr)))
    except Exception:
        return ""
    outs = []
    for mod in ("Crypto.Cipher.AES", "Cryptodome.Cipher.AES"):
        try:
            AES = importlib.import_module(mod)
            outs.append(AES.new(_KEY, AES.MODE_CBC, _IV).decrypt(raw))
            break
        except Exception:
            continue
    if not outs:
        outs.append(_pure_cbc(_KEY, _IV, raw, False))
    for d in outs:
        if d and 1 <= d[-1] <= 16:
            t = d[:-d[-1]].decode("utf-8", "replace")
            if t.lstrip().startswith(("{", "[")):
                return t
        t = d.rstrip(b"\x00").decode("utf-8", "replace")
        if t.lstrip().startswith(("{", "[")):
            return t
    return ""


def _rsa(cipher_b64):
    """付费集地址：RSA/ECB/OAEPPadding 解密（私钥 n/d 来自 APK，已内嵌）。"""
    try:
        data = base64.b64decode(re.sub(r"\s+", "", str(cipher_b64)))
    except Exception:
        return ""
    # 1) pycryptodome / Cryptodome（用 n/d 直接构造，不依赖 base64 私钥串）
    for mod in ("Crypto", "Cryptodome"):
        try:
            oaep = importlib.import_module(mod + ".Cipher.PKCS1_OAEP")
            rsam = importlib.import_module(mod + ".PublicKey.RSA")
            key = rsam.RSA.construct((_RSA_N, _RSA_E, _RSA_D))
        except Exception:
            continue
        for nm in (".Hash.SHA1", ".Hash.SHA256"):
            try:
                h = importlib.import_module(mod + nm)
                return oaep.new(key, hashAlgo=h).decrypt(data).decode("utf-8", "replace")
            except Exception:
                continue
    # 2) 纯 Python 兜底
    return _rsa_pure(data, (_RSA_N.bit_length() + 7) // 8)


def _mgf1(seed, mlen, sha):
    out = b""
    c = 0
    while len(out) < mlen:
        out += sha(seed + c.to_bytes(4, "big")).digest()
        c += 1
    return out[:mlen]


def _rsa_pure(data, k):
    import hashlib
    if not _RSA_N or not k or len(data) != k:
        return ""
    c = int.from_bytes(data, "big")
    if c >= _RSA_N:
        return ""
    raw = pow(c, _RSA_D, _RSA_N).to_bytes(k, "big")
    for sha in (hashlib.sha1, hashlib.sha256):
        hlen = sha(b"").digest_size
        if raw[0] != 0:
            continue
        m_seed, m_db = raw[1:1 + hlen], raw[1 + hlen:]
        seed = bytes(a ^ b for a, b in zip(m_seed, _mgf1(m_db, hlen, sha)))
        db = bytes(a ^ b for a, b in zip(m_db, _mgf1(seed, k - hlen - 1, sha)))
        if db[:hlen] != sha(b"").digest():
            continue
        rest = db[hlen:]
        idx = rest.find(b"\x01")
        if idx < 0 or any(b != 0 for b in rest[:idx]):
            continue
        try:
            return rest[idx + 1:].decode("utf-8", "replace")
        except Exception:
            continue
    return ""


def _rsa(cipher_b64):
    """付费集地址：RSA/ECB/OAEPPadding 解密（n/d 来自 APK，已内嵌为常量）。"""
    try:
        data = base64.b64decode(re.sub(r"\s+", "", str(cipher_b64)))
    except Exception:
        return ""
    # 1) pycryptodome / Cryptodome：用 n/e/d 直接构造密钥
    for mod in ("Crypto", "Cryptodome"):
        try:
            oaep = importlib.import_module(mod + ".Cipher.PKCS1_OAEP")
            rsam = importlib.import_module(mod + ".PublicKey.RSA")
            key = rsam.RSA.construct((_RSA_N, _RSA_E, _RSA_D))
        except Exception:
            continue
        for nm in (".Hash.SHA1", ".Hash.SHA256"):
            try:
                h = importlib.import_module(mod + nm)
                return oaep.new(key, hashAlgo=h).decrypt(data).decode("utf-8", "replace")
            except Exception:
                continue
    # 2) 纯 Python 兜底
    return _rsa_pure(data, (_RSA_N.bit_length() + 7) // 8)


class Spider(BaseSpider):
    """影视+ 源。不定义 __init__，全部状态在 init() 里赋值。"""

    def getName(self):
        return "繁花剧场"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = _HOSTS[0]
        self.timeout = 15
        self.err = ""
        self._home = None
        self._home_ts = 0
        # 体积红线：影视+ 会把每次返回 dump 进 logcat（SpiderDebug.log），
        # 总量一大就会被 libbase::SplitByLogdChunks abort 掉进程（实测两次）。
        # 下面这些数字都是按这条红线倒推的，别随意放大。
        self.page_size = 12       # 每页条目
        self.paging = True
        # 详情页：线路 = 清晰度（干净三条），token 只放集序号
        self.episode_chunk = 60      # 保留给 ext 微调用
        self.max_episodes = 400      # 单剧集数上限
        # 可选清晰度（影视+ 显示成可切换的"线路"）。
        # 服务端只在请求带 supportHD=1 时才下发这三档。
        self.qualities = [("1080p", "1080p"), ("720p", "720p"), ("540p", "540p")]
        self._ch = {}          # vid -> [chapterId,...] 序号反查缓存
        self.pub = {
            "pname": _PKG, "p": 37, "h": 2, "version": "11022801",
            "channelCode": "OFHAZ1000007", "mchid": "OFHAZ1000007",
            "nchid": "OFHAZ1000007",
            "utdid": "9df6799f5cd44ff565dfbf8fd69702fb",
            "utdidTmp": "A20260927231655300MUIAn1",
            # userId 留空 = 游客态：实测服务端接受，且不绑定任何账号，
            # 因此这份源可以直接分享（用真人的 userId 反而会报 code=9 用户不存在）
            "userId": "",
            "os": "android", "osv": 33, "brand": "Xiaomi", "model": "M2104K10AC",
            "manu": "Xiaomi", "bm": 1, "launch": "", "launchNum": 1,
            "dayLaunchNum": 1, "visitor": 0, "supportAd": 1, "origin_push": 2,
            "installTime": 1790522148473, "token": "", "session1": "", "session2": "",
        }
        self.sess = None
        if requests is not None:
            try:
                self.sess = requests.Session()
                self.sess.trust_env = False
                self.sess.verify = False
                import urllib3
                urllib3.disable_warnings()
            except Exception as e:
                self.err = str(e)
                try:
                    self.sess = requests.Session()
                except Exception:
                    self.sess = None
        ext = (extend or "").strip()
        if ext:
            try:
                cfg = json.loads(ext)
                if isinstance(cfg, dict):
                    if cfg.get("host"):
                        self.host = str(cfg["host"]).rstrip("/")
                    for k in ("utdid", "utdidTmp", "userId", "channelCode", "version"):
                        if k in cfg:
                            self.pub[k] = str(cfg[k] or "")
            except Exception:
                if ext.startswith("http"):
                    self.host = ext.rstrip("/")
        return None

    def destroy(self):
        try:
            self.sess.close()
        except Exception:
            pass

    def liveContent(self, url):
        return ""

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4)(\?|$)", url or "", re.I))

    def manualVideoCheck(self):
        return False

    # ─────────────── 协议 ───────────────
    def _post(self, call, biz=None):
        if self.sess is None:
            raise RuntimeError("requests 不可用")
        body = _enc(json.dumps(biz, ensure_ascii=False, separators=(",", ":"))
                    if biz else "{}")
        pub = dict(self.pub)
        pub["tstp"] = int(time.time() * 1000)
        hdrs = {"User-Agent": _UA, "Accept": "*/*", "Accept-Encoding": "identity",
                "Content-Type": "application/json; charset=utf-8",
                "datas": _enc(json.dumps(pub, ensure_ascii=False, separators=(",", ":"))),
                "st": _ST,
                "st1": base64.b64encode(
                    bytes(random.getrandbits(8) for _ in range(12))).decode("ascii")}
        last = ""
        for host in [self.host] + [h for h in _HOSTS if h != self.host]:
            try:
                r = self.sess.post("%s/app-video-portal/portal/client/%s"
                                   % (host.rstrip("/"), call),
                                   data=body.encode("utf-8"), headers=hdrs,
                                   timeout=self.timeout)
                j = json.loads((r.text or "").strip() or "{}")
                code = str(j.get("code", "")).strip()
                if code in ("0", "200"):
                    raw = j.get("data")
                    if isinstance(raw, str) and len(raw) > 32:
                        t = _dec(raw)
                        if t:
                            try:
                                j["decoded"] = json.loads(t)
                            except Exception:
                                j["decoded"] = t
                    return j
                last = "code=%s %s" % (code, j.get("msg"))
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
        raise RuntimeError("call %s 失败: %s" % (call, last))

    @staticmethod
    def _txt(o, *keys):
        if not isinstance(o, dict):
            return ""
        for k in keys:
            v = o.get(k)
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)):
                return str(v)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _books(self, j):
        d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
        if not isinstance(d, dict):
            return []
        w = d.get("words")
        if isinstance(w, list):
            out = []
            for x in w:
                if isinstance(x, dict):
                    bi = x.get("bookInfo")
                    out.append(bi if isinstance(bi, dict) else x)
            return out
        rd = d.get("recomDataResponse")
        if isinstance(rd, dict) and isinstance(rd.get("books"), list):
            return [b for b in rd["books"] if isinstance(b, dict)]
        if isinstance(d.get("chapterList"), list):
            return [b for b in d["chapterList"] if isinstance(b, dict)]
        for k in ("books", "list", "items"):
            if isinstance(d.get(k), list):
                return [b for b in d[k] if isinstance(b, dict)]
        return []

    def _vod(self, it):
        bi = it.get("bookInfo") if isinstance(it.get("bookInfo"), dict) else it
        vid = self._txt(bi, "bookId", "id")
        name = self._txt(bi, "bookName", "name", "title")
        if not vid or not name:
            return None
        total = self._txt(bi, "totalChapterNum")
        # 体积红线：影视+ 会把每次返回 dump 进 logcat，单条超过 4068 字节
        # 时 libbase::SplitByLogdChunks 会 abort 整个进程（已实测两次）。
        # 单条目约 380 字节，12 条就会超线，所以：去掉简介、去掉封面
        # 的 ?t= 缓存参数、备注截断。
        pic = self._txt(bi, "img", "coverWap", "cover", "coverUrl")
        if "?" in pic:
            pic = pic.split("?", 1)[0]
        return {
            "vod_id": vid,
            "vod_name": self._cut(name, 30),
            "vod_pic": pic,
            "vod_remarks": self._cut(("共%s集" % total) if total else
                                     self._txt(it, "copywriting"), 16),
            "vod_year": self._txt(bi, "status"),
            "vod_area": "",
            "vod_content": "",
        }

    @staticmethod
    def _cut(s, n):
        """截断长文本：日志 dump 安全。"""
        s = str(s or "")
        return s if len(s) <= n else s[:n]

    def _notice(self):
        return {"vod_id": "__n__", "vod_name": "【提示】%s" % (self.err or "无数据")[:30],
                "vod_pic": "", "vod_remarks": "点开查看",
                "vod_year": "", "vod_area": "",
                "vod_content": "源提示：%s" % (self.err or ""),
                "vod_play_from": "提示", "vod_play_url": "查看$__n__"}

    # ─────────────── 内容 ───────────────
    def homeContent(self, filter):
        """首页分类 = 题材分类（「精选·古装」「热播·恋爱」这种）。

        影视+ 的分类只能是一串 type_id，没有二级结构，而服务端的标签是
        按频道下发的，所以用 "频道|标签" 组合出题材分类：点进去直接就是
        该频道下该题材的内容，不需要再手动筛一次。

        格式要点（影视+ 的 Result / Class / Filter bean）：
            顶层  filters: { "<type_id>": [ {key,name,init,value:[{n,v}]} ] }
            键必须【直接是 type_id】—— app 用 getFilters().get(class.getTypeId())
            取值，加 "category:" 之类前缀会导致标签栏不显示。
        """
        out = {"class": [], "filters": {}}
        meta = self._meta()
        chans = (meta.get("channels") or []) if isinstance(meta, dict) else []
        tags = (meta.get("tags") or []) if isinstance(meta, dict) else []
        if not chans:
            chans = [{"type_id": c, "type_name": n} for c, n in
                     (("1#75", "精选"), ("1#77", "排行榜"), ("1#76", "新剧"),
                      ("1#80", "热播"), ("1#79", "会员专区"))]

        if tags:
            # 分类栏：只用频道（精选 / 排行榜 / 新剧 / 热播 / 会员专区）
            # 筛选栏：题材（推荐/古装/恋爱/…），挂在每个频道下。
            # 这样分类名干净，也不用把"频道·题材"拼成上百个分类 ——
            # 每个分类名都会被 dump 进 logcat，拼起来体量翻好几倍。
            out["class"] = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                            for c in chans]
            opts = [{"n": t["name"], "v": t["tag"]} for t in tags if t.get("tag")]
            if opts:
                for c in out["class"]:
                    out["filters"][c["type_id"]] = [
                        {"key": "tag", "name": "题材", "init": "", "value": opts}]
        else:
            out["class"] = chans
        return out

    def _meta(self):
        """缓存频道表 + 标签表（来自 1127 接口）。"""
        if isinstance(getattr(self, "_meta_cache", None), dict) and self._meta_cache:
            return self._meta_cache
        meta = {"channels": [], "tags": []}
        try:
            j = self._post("1127", {"channelId": "1#75", "pageFlag": 1})
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            for c in (d.get("channelList") or []):
                if not isinstance(c, dict):
                    continue
                nm = self._txt(c, "channelName")
                cid = self._txt(c, "channelId")
                if nm and cid:
                    meta["channels"].append({"type_id": cid, "type_name": nm})
            for t in (d.get("tagList") or []):
                if not isinstance(t, dict):
                    continue
                nm = self._txt(t, "name")
                tg = self._txt(t, "tag")
                if nm and tg:
                    meta["tags"].append({"name": nm, "tag": tg})
        except Exception as e:
            self.err = str(e)
        self._meta_cache = meta
        return meta

    def homeVideoContent(self):
        """首页推荐（1127 + pageFlag 游标，可续翻）。"""
        out = []
        try:
            j = self._post("1127", {"channelId": "1#72", "pageFlag": 1})
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            out = [v for v in (self._vod(x) for x in self._col_items(d)) if v]
        except Exception as e:
            self.err = str(e)
        return out[:self.page_size]

    def categoryContent(self, tid, pg, filter, extend):
        """分类浏览：接口 1127，pageFlag 做游标（实测每 +1 换一批 22 条）。

        tid    = "1#75"（channelId）
        extend = {"tag": "444,616,1102"}（标签筛选，可为空/JSON 字符串/字典）
        """
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        out = {"list": [], "page": page, "pagecount": page, "limit": 20, "total": 0}
        ch, _, tag = str(tid or "").partition("|")
        ch = ch.strip() or "1#75"
        # 从 extend 里取标签（影视+ 会以 JSON 字符串或 dict 传入）
        if not tag.strip():
            ex = extend
            if isinstance(ex, str) and ex.strip():
                try:
                    ex = json.loads(ex)
                except Exception:
                    ex = None
            if isinstance(ex, dict):
                tag = self._txt(ex, "tag")
        params = {"channelId": ch, "pageFlag": page}
        if tag.strip():
            params["tag"] = tag.strip()
        try:
            j = self._post("1127", params)
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            its = self._col_items(d)
            out["list"] = [v for v in (self._vod(x) for x in its) if v][:self.page_size]
            out["limit"] = self.page_size
            more = str(d.get("hasMore", "0")).strip() in ("1", "true", "True")
            out["pagecount"] = page + 1 if more else page
            if more:
                out["total"] = (page + 1) * self.page_size
            else:
                out["total"] = (page - 1) * self.page_size + len(out["list"])
        except Exception as e:
            self.err = str(e)
        if not out["list"]:
            if page == 1:
                out["list"] = [self._notice()]
            else:
                out["pagecount"] = page          # 到底了
        return out

    @staticmethod
    def _col_items(d):
        """1127 的条目在 columnList[].items[] 里。"""
        out = []
        if not isinstance(d, dict):
            return out
        cols = d.get("columnList")
        if isinstance(cols, list):
            for c in cols:
                if isinstance(c, dict) and isinstance(c.get("items"), list):
                    out += [x for x in c["items"] if isinstance(x, dict)]
        if not out:
            for k in ("books", "list", "items"):
                v = d.get(k)
                if isinstance(v, list):
                    out += [x for x in v if isinstance(x, dict)]
        # 1127 的条目用 title/id/desc 而非 bookName/bookId
        for x in out:
            if "bookId" not in x and x.get("id"):
                x.setdefault("bookId", x.get("id"))
            if "bookName" not in x and x.get("title"):
                x.setdefault("bookName", x.get("title"))
            if "introduction" not in x and x.get("desc"):
                x.setdefault("introduction", x.get("desc"))
        return out

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        out = {"list": [], "page": page, "pagecount": page, "limit": 20, "total": 0}
        if not key:
            return out
        try:
            j = self._post(_C_SEARCH, {"keyword": str(key), "page": page, "pageSize": 20})
            out["list"] = [v for v in (self._vod(x) for x in self._books(j)) if v]
        except Exception as e:
            self.err = str(e)
        if not out["list"]:
            out["list"] = [self._notice()]
        return out

    def detailContent(self, array):
        vid = ""
        try:
            if isinstance(array, (list, tuple)) and array:
                vid = array[0]
                if isinstance(vid, dict):
                    vid = vid.get("vod_id") or vid.get("id") or ""
                vid = str(vid)
            elif array is not None:
                vid = str(array)
                if vid.startswith("["):
                    try:
                        a = json.loads(vid)
                        vid = str(a[0]) if a else ""
                    except Exception:
                        pass
        except Exception:
            vid = ""
        if vid == "__n__":
            return {"list": [self._notice()]}
        vod = {"vod_id": vid, "vod_name": "繁花剧场", "vod_pic": "",
               "vod_content": "", "vod_play_from": "", "vod_play_url": ""}
        eps = []
        try:
            j = self._post(_C_CATALOG, {"bookId": vid})
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            bi = d.get("bookInfo") if isinstance(d.get("bookInfo"), dict) else d
            vod["vod_name"] = self._txt(bi, "bookName", "name") or vod["vod_name"]
            vod["vod_pic"] = self._txt(bi, "coverWap", "cover", "img")
            vod["vod_content"] = self._txt(bi, "introduction", "desc")
            total = self._txt(bi, "totalChapterNum")
            vod["vod_remarks"] = ("共%s集" % total) if total else ""
            vod["vod_area"] = self._cut(self._txt(bi, "roleName"), 20)
            cl = d.get("chapterList") if isinstance(d.get("chapterList"), list) else []
            cids = []
            for i, c in enumerate(cl, 1):
                cid = self._txt(c, "chapterId", "id")
                if cid:
                    cids.append(cid)
            if cids:
                self._set_chapters(vid, cids)
                eps = list(range(1, len(cids) + 1))
        except Exception as e:
            self.err = str(e)
        if not eps:
            eps = [1]
        # 线路 = 清晰度（干净的三条：1080p / 720p / 540p），
        # 每条带该清晰度下的完整剧集列表，选集后按所选线路播放。
        #
        # 体积红线：影视+ 会把返回值 dump 进 logcat（SpiderDebug.log），
        # 总量一大就会被 libbase::SplitByLogdChunks abort 掉进程（实测两次）。
        # 所以 token 只放"集序号"（约 4 字节/集），vid 只在线路名里出现一次：
        # 180 集 × 3 清晰度 ≈ 2.2KB，安全。
        limit = max(1, int(self.max_episodes))
        if len(eps) > limit:
            eps = eps[:limit]
        urls = "#".join(str(i) for i in eps)
        # 线路名只写清晰度（净名给用户看）；剧 id 记在实例上供播放时取用。
        self.current_vid = vid
        froms = [q[0] for q in self.qualities]
        vod["vod_play_from"] = "$$$".join(froms)
        vod["vod_play_url"] = "$$$".join([urls] * len(froms))
        return {"list": [vod]}

    def _set_chapters(self, vid, cids):
        """缓存 集序号 -> chapterId（播放时反查，避免 URL 里重复长 id）。"""
        try:
            if not isinstance(getattr(self, "_ch", None), dict):
                self._ch = {}
            self._ch[vid] = list(cids)
        except Exception:
            pass

    def _cache_chapters(self, vid, cl):
        """兼容入口：接受 chapterList 或 chapterId 列表。"""
        try:
            cids = []
            for c in cl:
                if isinstance(c, dict):
                    v = self._txt(c, "chapterId", "id")
                    if v:
                        cids.append(v)
                elif isinstance(c, (str, int)):
                    cids.append(str(c))
            self._set_chapters(vid, cids)
        except Exception:
            pass

    def _chapter_id(self, vid, idx):
        """按序号取 chapterId；缓存没有就现查一次。"""
        try:
            m = getattr(self, "_ch", None)
            if isinstance(m, dict):
                arr = m.get(vid)
                if isinstance(arr, list) and 1 <= idx <= len(arr) and arr[idx - 1]:
                    return arr[idx - 1]
        except Exception:
            pass
        try:
            j = self._post(_C_CATALOG, {"bookId": vid})
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            cl = d.get("chapterList") if isinstance(d.get("chapterList"), list) else []
            if not cl:
                return ""
            self._cache_chapters(vid, cl)
            arr = (self._ch or {}).get(vid) or []
            if 1 <= idx <= len(arr):
                return arr[idx - 1]
        except Exception as e:
            self.err = str(e)
        return ""

    def playerContent(self, flag, id, vipFlags):
        """flag = 线路名（就是清晰度，如 "1080p"）
        id   = 集序号（详情页缓存的剧 id 用来反查 chapterId）
        """
        result = {"parse": 0, "playUrl": "", "url": "",
                  "header": {"User-Agent": _UA}, "format": ""}
        try:
            raw = str(id or "").strip()
            if raw.startswith("http"):
                result["url"] = raw
                return result
            qkey, fvid = self._parse_flag(flag)
            vid = cid = ""
            if "@" in raw:                      # 兼容旧式 "清晰度@vid|集"
                qkey2, _, raw = raw.partition("@")
                qkey = qkey or qkey2
            if "|" in raw:                      # 兼容 "vid|集"
                vid, _, cid = raw.partition("|")
                vid, cid = vid.strip(), cid.strip()
            else:                               # 纯集序号
                cid = raw
                vid = fvid
            if not vid:
                vid = str(getattr(self, "current_vid", "") or "")
            if not vid:
                return result
            # cid 是集序号时换成真实 chapterId
            if cid.isdigit():
                real = self._chapter_id(vid, int(cid))
                if real:
                    cid = real
            biz = {"bookId": vid, "chapterId": cid or "1"}
            # 关键：带上 supportHD=1 服务端才会下发 540p/720p/1080p 三档
            if qkey:
                biz["supportHD"] = 1
            j = self._post(_C_PLAY, biz)
            d = j.get("decoded") if isinstance(j.get("decoded"), dict) else j
            ci = d.get("chapterInfo") if isinstance(d.get("chapterInfo"), dict) else {}
            vo = ci.get("videoUrlVo") if isinstance(ci.get("videoUrlVo"), dict) else {}
            if not vo and isinstance(d.get("videoUrlVo"), dict):
                vo = d["videoUrlVo"]
            infos = vo.get("videoInfos")
            if isinstance(infos, list):
                picked = self._pick_quality(infos, qkey)
                if picked:
                    result["url"] = picked
                    return result
            for k in ("url", "videoUrl", "playUrl"):
                u = self._txt(ci, k)
                if u.startswith("http"):
                    result["url"] = u
                    return result
        except Exception as e:
            self.err = str(e)
        return result

    def _quality_of(self, flag):
        """从线路名里取清晰度，识别不出来返回空（由服务端给默认档）。"""
        return self._parse_flag(flag)[0]

    @staticmethod
    def _parse_flag(flag):
        """线路名 "1080p#2@<vid>" -> ("1080p", "<vid>")。"""
        f = str(flag or "")
        vid = ""
        if "@" in f:
            f, _, vid = f.partition("@")
        q = ""
        for cand in ("1080p", "720p", "540p", "480p", "360p"):
            if cand in f:
                q = cand
                break
        return q, vid.strip()

    @staticmethod
    def _pick_quality(infos, qkey):
        """从 videoInfos 里挑出目标清晰度（付费集是 RSA 密文，需要解密）。"""
        want = qkey or "1080p"
        order = [want] + [q for q in ("1080p", "720p", "540p") if q != want]
        for target in order:
            for it in infos:
                if not isinstance(it, dict):
                    continue
                if str(it.get("definition") or "").strip() != target:
                    continue
                u = str(it.get("url") or "")
                if not u:
                    continue
                if str(it.get("encryptUrl", "")) == "1" or not u.startswith("http"):
                    u = _rsa(u)
                if u.startswith("http"):
                    return u
        # 完全没匹配到就退第一个能用的
        for it in infos:
            if not isinstance(it, dict):
                continue
            u = str(it.get("url") or "")
            if not u:
                continue
            if str(it.get("encryptUrl", "")) == "1" or not u.startswith("http"):
                u = _rsa(u)
            if u.startswith("http"):
                return u
        return ""

    def action(self, action):
        cmd = str(action or "").strip()
        if cmd in ("status", "ping", "version"):
            return {"ok": True, "name": self.getName(), "host": self.host,
                    "err": self.err, "utdid": self.pub.get("utdid", ""),
                    "userId": self.pub.get("userId", "")}
        if cmd.startswith("api:"):
            call = cmd.split(":", 1)[1].strip()
            try:
                return {"ok": True, "call": call, "data": self._post(call)}
            except Exception as e:
                return {"ok": False, "call": call, "error": str(e)}
        return {}

    # ─────────────── 代理（恒返回 4 元组） ───────────────
    def localProxy(self, param):
        try:
            s = ""
            if isinstance(param, dict):
                s = param.get("url") or param.get("Url") or ""
            elif param:
                s = str(param)
            s = str(s).strip()
            if "url=" in s[:24]:
                s = s.split("url=", 1)[1].split("&", 1)[0]
            try:
                from urllib.parse import unquote
                s = unquote(s)
            except Exception:
                pass
            url = s
            if not url.startswith("http"):
                for pad in (0, 1, 2, 3):
                    try:
                        d = base64.b64decode(url + "=" * pad, validate=False).decode("utf-8")
                        if d.startswith("http"):
                            url = d
                            break
                    except Exception:
                        pass
            if not url.startswith("http"):
                return [500, "text/plain", "bad param", ""]
            typ = str(param.get("type") or "").lower() if isinstance(param, dict) else ""
            hdrs = {"User-Agent": _UA, "Accept": "*/*"}
            r = self.sess.get(url, headers=hdrs, timeout=self.timeout,
                              allow_redirects=True)
            if r.status_code not in (200, 206):
                return [r.status_code, "text/plain", "upstream fail", ""]
            low = url.lower().split("?", 1)[0]
            if typ == "m3u8" or low.endswith(".m3u8"):
                return [200, "application/vnd.apple.mpegurl",
                        r.content.decode("utf-8", "ignore"), ""]
            if low.endswith(".key"):
                return [200, "application/octet-stream", r.content, ""]
            return [r.status_code, r.headers.get("Content-Type") or "video/mp4",
                    r.content, ""]
        except Exception as e:
            return [500, "text/plain", "proxy error: %s" % e, ""]


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    s = Spider()
    s.init("")
    print("getName :", s.getName())
    h = s.homeContent(True)
    print("分类    :", [c["type_name"] for c in h["class"]])
    print("首页    :", len(h["list"]), "条")
    r = s.searchContent("总裁", False, "1")
    print("搜索    :", len(r["list"]), "条")
    if r["list"] and not r["list"][0]["vod_id"].startswith("__"):
        d = s.detailContent([r["list"][0]["vod_id"]])
        eps = d["list"][0]["vod_play_url"].split("#")
        print("详情    :", d["list"][0]["vod_name"], len(eps), "集")
        for i in (0, len(eps) - 1):
            nm, _, pid = eps[i].partition("$")
            u = s.playerContent("", pid, "[]").get("url") or ""
            print("  %-8s -> %s" % (nm, u[-56:] if u else "(空)"))
    print("localProxy:", s.localProxy({}))
