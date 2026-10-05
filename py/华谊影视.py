# -*- coding: utf-8 -*-
# 华谊影视 TVBox spider — 协议逆向完整版（修复简介/演员/容错）
import json
import re
import sys
import time
import base64
import string
import random
import hashlib
import urllib.request
import urllib.parse

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import pad, unpad

try:
    from base.spider import Spider as _Base
except Exception:
    class _Base:
        pass


PUB1_B64 = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCr8SzZhjYy+rsya1K09t8d2K50pWFoBkgUqMpKOiW+3IEVKd4eTdvg9RSOjQ82kypL6R9BnsmrS1V8s4PVDwjQbUtYhTPPC9Hz16qY7rpD6m0d2vr09/UpWQ5uOy9PR0QTrsioveZ+DIe9jc3C+zBCu/kZSY/R8stwJoiitki3gwIDAQAB'
NATIVE_K = b'ed5fdsgucxumegqa'
SAFE = b'OC1A06E197EF10CF3F6058CA7A803B5E'
PW_SAFE = b'11GK2we32144LO&hilUITB)FMd1khdaF'
CERT_MD5 = '089C68CF7E7F6A5A29790CC656EB7126'
CERT_SHA1 = '7E1141ECF197A3A7FD9A41900F8C638A12BA102F'
PKG = 'com.lxf.sncgtzxyx'
VC = '6001'
HOST = 'http://43.240.158.154:18004'
UA = 'okhttp/3.12.1'

_e = base64.b64encode(AES.new(PW_SAFE, AES.MODE_ECB).encrypt(pad(
    (CERT_MD5 + '######' + CERT_SHA1 + '~~~~~~' + PKG + '>>>+++' + VC).encode(), 16))).decode()
_e2 = base64.b64encode(_e.encode()).decode()
SAFECODE = (_e2[:16] + _e2[-16:]).upper()


# ============================================================
# Protobuf 小工具
# ============================================================

def _varint(n):
    b = b''
    while True:
        x = n & 0x7f
        n >>= 7
        if n:
            b += bytes([x | 0x80])
        else:
            return b + bytes([x])


def _f(num, wire, payload):
    t = _varint((num << 3) | wire)
    if wire == 2:
        return t + _varint(len(payload)) + payload
    return t + payload


def _pb(buf):
    """极简 protobuf 解析器，返回 [(field_num, wire_type, value)]"""
    out = []
    i = 0
    n = len(buf)
    while i < n:
        b = buf[i]
        fn, wt = b >> 3, b & 7
        i += 1
        if wt == 0:
            v = 0
            sh = 0
            while i < n:
                x = buf[i]
                i += 1
                v |= (x & 0x7f) << sh
                sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, v))
        elif wt == 2:
            ln = 0
            sh = 0
            while i < n:
                x = buf[i]
                i += 1
                ln |= (x & 0x7f) << sh
                sh += 7
                if not x & 0x80:
                    break
            out.append((fn, wt, buf[i:i + ln]))
            i += ln
        elif wt == 5:
            out.append((fn, wt, buf[i:i + 4]))
            i += 4
        elif wt == 1:
            out.append((fn, wt, buf[i:i + 8]))
            i += 8
        else:
            i += 1
    return out


def _rnd(k):
    CH = string.ascii_letters + string.digits
    return ''.join(random.sample(list(CH), k - 1)) + '='


# ============================================================
# 简介/字段提取辅助
# ============================================================

def _clean_text(s):
    """去 HTML 标签、空白归一"""
    if not s:
        return ''
    s = re.sub(r'<[^>]+>', '', s)
    s = s.replace('&nbsp;', ' ').replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _cn_ratio(s):
    if not s:
        return 0.0
    cn = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
    return cn / len(s)


def _looks_like_content(s):
    """判断是否是简介文本（不是 URL/JSON/集名列表）"""
    if not s or len(s) < 20 or len(s) > 4000:
        return False
    if s.startswith('http') or s.startswith('{') or s.startswith('['):
        return False
    if s.count('$') > 3 or s.count('#') > 3:
        return False
    if _cn_ratio(s) < 0.35:
        return False
    return True


# ============================================================
# Spider
# ============================================================

class Spider(_Base):

    HOST_NAME = '华谊影视'
    _cur_id = ''

    def getName(self):
        return '华谊影视'

    def init(self, extend=''):
        self.udid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16].upper()
        self._rsa1 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB1_B64)))
        self._rsa2 = None
        self._token = ''
        # 容错：登录/握手失败不阻塞整个 spider
        try:
            self._login()
        except Exception:
            self._token = ''
        try:
            self._zone()
        except Exception:
            pass
        # 若握手失败，用 rsa1 兜底（协议兼容，服务端仍可能接受）
        if self._rsa2 is None:
            self._rsa2 = self._rsa1

    # -------- HTTP --------
    def _http(self, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        return urllib.request.urlopen(req, timeout=25).read()

    # -------- 登录 --------
    def _login(self):
        try:
            body = json.dumps({
                'username': 'tv_%s' % self.udid[:10].lower(),
                'password': hashlib.md5(('tv' + self.udid).encode()).hexdigest(),
                'udid': self.udid,
            }).encode()
            try:
                self._http(HOST + '/api/ex/v3/user/register', body, {
                    'User-Agent': UA, 'Content-Type': 'application/json'})
            except Exception:
                pass
            d = self._http(HOST + '/api/ex/v3/user/login', body, {
                'User-Agent': UA, 'Content-Type': 'application/json'})
            data = json.loads(d).get('data') or {}
            self._token = (data.get('token')
                           or (data.get('user') or {}).get('token') or '')
        except Exception:
            self._token = ''

    # -------- 握手：获取动态 RSA 公钥 --------
    def _zone(self):
        ts = int(time.time() * 1000)
        rnd = _rnd(16)
        sign = base64.b64encode(self._rsa1.encrypt((str(ts) + rnd).encode())).decode()
        body = (_f(1, 0, _varint(ts)) + _f(2, 2, sign.encode()) +
                _f(3, 2, rnd.encode()) + _f(4, 2, rnd.encode()) +
                _f(5, 2, rnd.encode()))
        P = {
            'plat': 'android', 'vOs': '16', '_vOsCode': '36', 'vApp': '6001',
            'vName': '6.0.0.1', 'pkg': PKG,
            'appName': '%E5%8D%8E%E8%B0%8A%E5%BD%B1%E8%A7%86',
            'udid': self.udid, 'uuid': self.udid, 'chid': '10000',
            'androidID': self.udid, 'net': '1', 'young': 0, 'tenantId': '',
            'v': 1, 'device': 0, 'lang': 'zh', 'country': 'CN', 'cpu': 'arm64-v8a',
        }
        d = self._http(HOST + '/api/v5/find/app/zone', body, {
            'User-Agent': UA, 'Content-Type': 'application/x-protobuf',
            'Accept': 'application/x-protobuf', 'Cache-Control': 'no-cache',
            'publicParams': json.dumps(P, separators=(',', ':'))})
        if not d:
            return
        top = _pb(d)
        inner_list = [v for fn, wt, v in top if fn == 3 and wt == 2]
        if not inner_list:
            return
        strs = {fn: v for fn, wt, v in _pb(inner_list[0]) if wt == 2}
        if all(k in strs for k in (2, 3, 4, 5)):
            self._rsa2 = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(
                strs[2] + strs[3] + strs[4] + strs[5])))

    # -------- 请求头 --------
    def _hdr(self):
        rsa = self._rsa2 or self._rsa1
        ts = int(time.time() * 1000)
        rnd = _rnd(16)
        sig = base64.b64encode(rsa.encrypt(
            (str(ts) + rnd + '6001').encode())).decode()
        ao = base64.b64encode(AES.new(SAFE, AES.MODE_ECB).encrypt(
            pad((str(ts) + rnd).encode(), 16))).decode()
        J = {
            'country': 'CN', 'vName': '6.0.0.1', 'cpuId': '', 'young': 0,
            'facturer': 'OnePlus', 'pkg': PKG, 'uuid': self.udid,
            'resolution': '1080x2256', 'mac': '02%3A00%3A00%3A00%3A00%3A00',
            'sig': sig, 'abid': '3884', 'model': 'PJX110', 'plat': 'android',
            'udid': self.udid, 'dpi': '480', 'net': '1', 'lang': 'zh',
            'random_str': rnd, 'brand': 'OnePlus', 'timestamp': ts,
            'density': '3.0', 'appName': '%E5%8D%8E%E8%B0%8A%E5%BD%B1%E8%A7%86',
            'cpu': 'arm64-v8a', 'chid': '10000',
            'carrier': '%E8%81%94%E9%80%9A',
            'sig2': ao[:8], 'v': 1, 'sig3': ao[8:], 'tenantId': '',
            '_vOsCode': '36', 'vOs': '16', 'vApp': '6001', 'device': 0,
            'androidID': self.udid,
        }
        blob = json.dumps(J, separators=(',', ':'), ensure_ascii=False).encode()
        pd_hex = AES.new(NATIVE_K, AES.MODE_CBC, NATIVE_K).encrypt(
            pad(blob, 16)).hex()
        h = {
            'User-Agent': UA, 'Accept': 'application/json',
            'Cache-Control': 'no-cache',
            'publicParams': json.dumps({'paramsData': pd_hex},
                                       separators=(',', ':')),
        }
        if self._token:
            h['token'] = self._token
        return h

    # -------- 业务参数加密 --------
    def _secure(self, mapkv):
        ts = int(time.time() * 1000)
        rnd8 = _rnd(8)
        plain = (mapkv + str(ts)).encode()
        ct = AES.new(SAFECODE.encode(), AES.MODE_ECB).encrypt(pad(plain, 16))
        b64 = base64.b64encode(ct).decode()
        return (_f(1, 2, (rnd8 + b64[:12]).encode()) +
                _f(2, 2, b64[12:].encode()) +
                _f(3, 2, _rnd(20).encode()) +
                _f(4, 0, _varint(ts)) +
                _f(5, 2, rnd8.encode()))

    # ============================================================
    # 首页分类
    # ============================================================
    def homeContent(self, f):
        cats = []
        try:
            d = self._http(HOST + '/api/v3/drama/getCategory?orderBy=type_id',
                           None, {'User-Agent': UA, 'Accept': 'application/json'})
            for c in (json.loads(d).get('data') or []):
                if str(c.get('id')) != '29':
                    cats.append({'type_id': str(c['id']),
                                 'type_name': c.get('name', '')})
        except Exception:
            pass
        if not cats:
            cats = [
                {'type_id': '21', 'type_name': '电影'},
                {'type_id': '22', 'type_name': '剧集'},
                {'type_id': '25', 'type_name': '动漫'},
                {'type_id': '26', 'type_name': '综艺'},
                {'type_id': '27', 'type_name': '短剧'},
                {'type_id': '28', 'type_name': '漫剧'},
            ]
        # history 去重追加
        if not any(c['type_id'] == 'history' for c in cats):
            cats.append({'type_id': 'history', 'type_name': '最近在看'})
        return {'class': cats}

    def homeVideoContent(self):
        try:
            return {'list': self._list('page=1&pagesize=24')}
        except Exception:
            return {'list': []}

    # ============================================================
    # 列表
    # ============================================================
    def _list(self, qs):
        out = []
        try:
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            d = self._http(HOST + '/api/proto/v5/drama/category',
                           self._secure(qs), hh)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return out
            data_list = [v for fn, wt, v in top if fn == 3 and wt == 2]
            if not data_list:
                return out
            data = data_list[0]
            for fn, wt, v in _pb(data):
                if fn != 1 or wt != 2:
                    continue
                info = {'vod_id': '', 'vod_name': '', 'vod_pic': '',
                        'vod_remarks': ''}
                for f2, w2, v2 in _pb(v):
                    if f2 == 3 and w2 == 0:
                        info['vod_id'] = str(v2)
                    elif f2 == 5 and w2 == 2:
                        info['vod_name'] = v2.decode('utf-8', 'replace')
                    elif f2 == 2 and w2 == 2:
                        cands = [v3.decode('utf-8', 'replace')
                                 for f3, w3, v3 in _pb(v2)
                                 if w3 == 2 and v3.startswith(b'http')]
                        if cands:
                            info['vod_pic'] = next(
                                (u for u in cands if u.startswith('https')),
                                cands[0])
                    elif f2 == 13 and w2 == 2:
                        info['vod_remarks'] = v2.decode('utf-8', 'replace')
                if info['vod_id']:
                    out.append(info)
        except Exception:
            pass
        return out

    def categoryContent(self, tid, pg, f, ext):
        pg = int(pg or 1)
        if tid == 'history':
            return {'list': self._history_list(), 'page': 1,
                    'pagecount': 1, 'limit': 40, 'total': 40}
        qs = 'page=%d&pagesize=24&typeId1=%s' % (pg, tid)
        return {'list': self._list(qs), 'page': pg,
                'pagecount': 999, 'limit': 24, 'total': 99999}

    def _history_list(self):
        out = []
        try:
            d = self._http(HOST + '/api/ex/v3/user/history?username=fzcrym',
                           None, {'User-Agent': UA, 'Accept': 'application/json'})
            for it in (json.loads(d).get('data') or []):
                vid = it.get('videoId', '')
                if '|' in vid:
                    frm, url = vid.split('|', 1)
                    out.append({
                        'vod_id': 'h$%s$%s' % (frm, url),
                        'vod_name': it.get('videoName', ''),
                        'vod_pic': it.get('videoCover', ''),
                        'vod_remarks': '%s·第%s集' % (frm, it.get('videoPart', '')),
                    })
        except Exception:
            pass
        return out

    # ============================================================
    # 详情（重点：简介 / 演员 / 导演）
    # ============================================================
    def _pick_first_text(self, field_map, fn_candidates, validator=None,
                         max_len=100):
        """
        从 field_map 里按候选字段号顺序取第一个合法文本
        - validator: 可选，签名 validator(text) -> bool
        - max_len: 单值最大长度（避免抓到拼接串）
        """
        for f in fn_candidates:
            vals = field_map.get(f)
            if not vals:
                continue
            for raw in vals:
                try:
                    txt = _clean_text(raw.decode('utf-8', 'replace'))
                except Exception:
                    continue
                if not txt or len(txt) > max_len:
                    continue
                if validator and not validator(txt):
                    continue
                return txt
        return ''

    def _extract_content(self, dd, field_map):
        """
        简介三层回退（重点）：
          1. 已知简介字段号（f6 优先，多个变体依次尝试）
          2. 字段号区间扫描（含中文字符比过滤）
          3. 全局兜底：扫描所有 wt==2 长中文串
        """
        # --- 1. 已知字段号（按命中概率排序）---
        content_fns = (6, 7, 8, 13, 14, 15, 24, 27, 28, 30, 32, 35, 20)
        for f in content_fns:
            vals = field_map.get(f)
            if not vals:
                continue
            for raw in vals:
                try:
                    txt = raw.decode('utf-8', 'replace')
                except Exception:
                    continue
                txt = _clean_text(txt)
                if _looks_like_content(txt):
                    return txt

        # --- 2. 字段号区间扫描（错位前的合法字段）---
        for fn, wt, v in dd:
            if fn == 0 or fn > 100:
                break
            if wt != 2 or not isinstance(v, (bytes, bytearray)):
                continue
            try:
                txt = _clean_text(v.decode('utf-8', 'replace'))
            except Exception:
                continue
            if _looks_like_content(txt) and _cn_ratio(txt) > 0.55:
                # 排除集名列表特征
                if re.search(r'第\d+集', txt) and txt.count('第') > 3:
                    continue
                return txt

        # --- 3. 全局兜底：扫描所有长中文串，取最长的一个 ---
        candidates = []
        for fn, wt, v in dd:
            if wt != 2 or not isinstance(v, (bytes, bytearray)):
                continue
            try:
                txt = _clean_text(v.decode('utf-8', 'replace'))
            except Exception:
                continue
            if _looks_like_content(txt) and _cn_ratio(txt) > 0.55:
                if re.search(r'第\d+集', txt) and txt.count('第') > 3:
                    continue
                candidates.append((len(txt), txt))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]

        return ''

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        out = {'vod_id': ids[0]}
        self._cur_id = ids[0]

        # 历史播放
        if ids[0].startswith('h$'):
            parts = ids[0].split('$', 2)
            if len(parts) == 3:
                _, frm, url = parts
                return {'list': [dict(out, vod_name='继续观看',
                                      vod_play_from=frm,
                                      vod_play_url='正片$%s' % url,
                                      vod_pic='',
                                      vod_content='播放历史·线路:' + frm)]}
            return {'list': [dict(out, vod_name='继续观看',
                                  vod_play_from='历史',
                                  vod_play_url='播放$http://',
                                  vod_pic='', vod_content='')]}

        try:
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            d = self._http(HOST + '/api/proto/v5/drama/getDetail',
                           self._secure('id=' + ids[0]), hh)
            top = _pb(d)
            data_list = [v for fn, wt, v in top if fn == 3 and wt == 2]
            if not data_list:
                raise ValueError('no data field')
            data = data_list[0]
            dd = _pb(data)

            # ---- 先收集所有字段（错位前），再筛选 ----
            field_map = {}
            for fn, wt, v in dd:
                if fn == 0 or fn > 100:
                    break
                if wt != 2 or not isinstance(v, (bytes, bytearray)):
                    continue
                field_map.setdefault(fn, []).append(v)

            # ---- 标题 ----
            name = self._pick_first_text(
                field_map, (9, 5, 8, 10, 11), max_len=100)
            if name:
                out['vod_name'] = name

            # ---- 地区 ----
            area = self._pick_first_text(
                field_map, (1, 3, 4), max_len=30)
            if area:
                out['vod_area'] = area

            # ---- 导演 ----
            director = self._pick_first_text(
                field_map, (12, 11, 22), max_len=200)
            if director:
                out['vod_director'] = director

            # ---- 演员 ----
            actor = self._pick_first_text(
                field_map, (16, 25, 17, 26, 18, 27), max_len=500)
            if actor:
                out['vod_actor'] = actor.lstrip(' ,;，；')
            else:
                # 演员兜底：从错位后的干净中文串提取（原逻辑升级版）
                for fn, wt, v in dd:
                    if wt != 2:
                        continue
                    try:
                        txt = v.decode('utf-8', 'replace')
                    except Exception:
                        continue
                    if _cn_ratio(txt) < 0.7:
                        continue
                    # 用逗号/顿号分割人名，常见格式：张三,李四,王五
                    parts = re.split(r'[,，、;；/]', txt)
                    names = [p.strip() for p in parts
                             if 2 <= len(p.strip()) <= 20
                             and re.match(r'^[\u4e00-\u9fa5·]+$', p.strip())]
                    if len(names) >= 2:
                        out['vod_actor'] = ','.join(names[:10])
                        break

            # ---- 封面 ----
            for f in (2, 4):
                vals = field_map.get(f)
                if not vals:
                    continue
                for raw in vals:
                    sub = _pb(raw)
                    cands = [v3.decode('utf-8', 'replace')
                             for f3, w3, v3 in sub
                             if w3 == 2 and v3.startswith(b'http')]
                    if cands:
                        out['vod_pic'] = next(
                            (u for u in cands if u.startswith('https')),
                            cands[0])
                        break
                if out.get('vod_pic'):
                    break

            # ---- 简介（重点）----
            content = self._extract_content(dd, field_map)
            if content:
                out['vod_content'] = content

            # ---- 分集（原始 0xEA01 tag 扫描）----
            eps = []
            pos = 0
            n = len(data)
            while True:
                j = data.find(b'\xea\x01', pos)
                if j < 0:
                    break
                k = j + 2
                ln = 0
                sh = 0
                while k < n and data[k] & 0x80:
                    ln |= (data[k] & 0x7f) << sh
                    sh += 7
                    k += 1
                if k >= n:
                    break
                ln |= (data[k] & 0x7f) << sh
                k += 1
                if ln <= 0 or k + ln > n:
                    pos = j + 1
                    continue
                entry = data[k:k + ln]
                pos = k + ln
                title = pth = src = src_cn = ''
                for f3_, w3_, v3_ in _pb(entry):
                    if w3_ != 2:
                        continue
                    if f3_ == 2:
                        title = v3_.decode('utf-8', 'replace')
                    elif f3_ == 3 and not title:
                        title = v3_.decode('utf-8', 'replace')
                    elif f3_ == 4:
                        pth = v3_.decode('utf-8', 'replace')
                    elif f3_ == 9:
                        src = v3_.decode('utf-8', 'replace')
                    elif f3_ == 10:
                        src_cn = v3_.decode('utf-8', 'replace')
                if not pth:
                    continue
                mm = re.match(r'^第?0*(\d{1,4})[集话期](?:完结)?$', title)
                if mm:
                    title = mm.group(1)
                eps.append((title, pth, src, src_cn))

            lines = {}
            order = []
            for title, pth, src, src_cn in eps:
                line = src_cn or src or '正片'
                if line not in lines:
                    lines[line] = []
                    order.append(line)
                if re.match(
                        r'(?i).*\.(mp4|m3u8|flv|mkv|avi|ts|mov|mpd|m4a|wmv)(\?.*)?$',
                        pth):
                    ep_url = pth
                else:
                    ep_url = base64.b64encode(json.dumps(
                        {'vodPlayFrom': src, 'playUrl': pth},
                        separators=(',', ':')).encode()).decode()
                lines[line].append('%s$%s' % (title or '正片', ep_url))

            # 集名归一化
            for ln_name in lines:
                norm = []
                for it in lines[ln_name]:
                    t, u = it.split('$', 1)
                    mm = re.match(r'^第?0*(\d{1,4})[集话期]$', t)
                    norm.append('%s$%s' % (mm.group(1) if mm else t, u))
                lines[ln_name] = norm

            # 线路排序
            def _rank(nm):
                if '超高清' in nm:
                    return 0
                if '蓝光' in nm:
                    return 1
                return 2

            order.sort(key=lambda x: (_rank(x), x))
            if order:
                out['vod_play_from'] = '$$$'.join(order)
                out['vod_play_url'] = '$$$'.join(
                    '#'.join(lines[l]) for l in order)
            else:
                out['vod_play_from'] = '华谊'
                out['vod_play_url'] = '暂无片源$http://'

        except Exception:
            out.setdefault('vod_name', ids[0])
            out.setdefault('vod_content', '')
            out.setdefault('vod_play_from', '华谊')
            out.setdefault('vod_play_url', '播放$http://')

        # 最终字段兜底，避免播放器渲染空
        out.setdefault('vod_name', ids[0])
        out.setdefault('vod_content', '')
        out.setdefault('vod_pic', '')
        out.setdefault('vod_actor', '')
        out.setdefault('vod_director', '')
        out.setdefault('vod_area', '')
        out.setdefault('vod_year', '')
        out.setdefault('vod_remarks', '')
        out.setdefault('vod_play_from', '华谊')
        out.setdefault('vod_play_url', '播放$http://')
        return {'list': [out]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg=1):
        try:
            # searchKeys 参数不 URL 编码（编码后返回空）
            qs = 'page=%s&pagesize=24&searchKeys=%s' % (pg or 1, key)
            hh = self._hdr()
            hh['Content-Type'] = 'application/x-protobuf'
            hh['Accept'] = 'application/x-protobuf'
            d = self._http(HOST + '/api/proto/v5/drama/search',
                           self._secure(qs), hh)
            top = _pb(d)
            code = [v for fn, wt, v in top if fn == 1 and wt == 0]
            if (code[0] if code else 0) != 200:
                return {'list': [], 'page': int(pg or 1)}
            data_list = [v for fn, wt, v in top if fn == 3 and wt == 2]
            if not data_list:
                return {'list': [], 'page': int(pg or 1)}
            data = data_list[0]
            out = []
            for fn, wt, v in _pb(data):
                if fn != 1 or wt != 2:
                    continue
                info = {'vod_id': '', 'vod_name': '', 'vod_pic': '',
                        'vod_remarks': ''}
                for f2, w2, v2 in _pb(v):
                    if f2 == 3 and w2 == 0:
                        info['vod_id'] = str(v2)
                    elif f2 == 5 and w2 == 2:
                        info['vod_name'] = v2.decode('utf-8', 'replace')
                    elif f2 == 2 and w2 == 2:
                        cands = [v3.decode('utf-8', 'replace')
                                 for f3, w3, v3 in _pb(v2)
                                 if w3 == 2 and v3.startswith(b'http')]
                        if cands:
                            info['vod_pic'] = next(
                                (u for u in cands if u.startswith('https')),
                                cands[0])
                    elif f2 == 13 and w2 == 2:
                        info['vod_remarks'] = v2.decode('utf-8', 'replace')
                if info['vod_id'] and info['vod_name']:
                    out.append(info)
            return {'list': out, 'page': int(pg or 1)}
        except Exception:
            return {'list': [], 'page': 1}

    # ============================================================
    # 播放
    # ============================================================
    def playerContent(self, flag, id, vipFlags):
        url = id
        try:
            if id and not id.startswith('http') and not id.startswith('h$'):
                jm = json.loads(base64.b64decode(id))
                pf, pu = jm.get('vodPlayFrom', ''), jm.get('playUrl', '')
                hh = self._hdr()
                hh['Content-Type'] = 'application/x-protobuf'
                hh['Accept'] = 'application/x-protobuf'
                qs = 'vodPlayFrom=%s&playUrl=%s' % (
                    urllib.parse.quote(pf),
                    urllib.parse.quote(pu, safe=''))
                d = self._http(HOST + '/api/proto/v5/videoUsableUrl',
                               self._secure(qs), hh)
                top = _pb(d)
                code = [v for fn, wt, v in top if fn == 1 and wt == 0]
                if (code[0] if code else 0) == 200:
                    data_list = [v for fn, wt, v in top if fn == 3 and wt == 2]
                    if data_list:
                        mm = re.search(rb'https?://[\x21-\x7e]+', data_list[0])
                        if mm:
                            url = mm.group(0).decode('utf-8', 'replace')
            elif not url.startswith('http'):
                url = 'http://'
        except Exception:
            pass

        # 补 Referer，部分 CDN 需要
        headers = {'User-Agent': UA}
        try:
            p = urllib.parse.urlparse(url)
            if p.scheme and p.netloc:
                headers['Referer'] = '%s://%s/' % (p.scheme, p.netloc)
        except Exception:
            pass

        return {'parse': 0, 'playUrl': '', 'url': url, 'header': headers}

    def isVideoFormat(self, url):
        return True

    def isTextFormat(self, url):
        return False

    def destroy(self):
        self._token = ''
        self._rsa2 = None
