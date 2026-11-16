# -*- coding: utf-8 -*-
"""
咕噜咕噜 —— TVBox  Python 爬虫

特征:
  - protobuf 编解码 + Crypto AES-256-CBC/GCM + P-256 ECDH 握手
  - 会话级 GCM 加密请求，服务器下发播放器/解析器配置
  - 线路优先级排序 + 别名映射
  - 版本守卫自愈（自动探测放行版本 / 扩展参数 ver= 手动指定）
  - 筛选支持：类型 / 地区 / 年份 / 语言 / 排序
  - 播放缓存 600s + 失败 parse:1 兜底嗅探
  - 模块级单例双入口（drpy site / 旧内核）
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import zlib
from urllib.parse import quote

from Crypto.Cipher import AES
from Crypto.PublicKey import ECC
from Crypto.Util.Padding import pad, unpad
from base.spider import Spider

# 优先用 requests；如果盒子环境真没有（概率极低，因为旧版依赖它），再兜底
try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

API_URL = "http://103.45.132.22:19987/app/bn/v2"
USER_AGENT = "Dart/3.10 (dart:io)"
# 简介前缀：详情页正文前加一句防骗提示（可留空关闭）
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"
# 服务器会校验 boot / detail 上报的版本号：2.3.5 已被拉入黑名单，
# 命中后列表返回"最新版下载地址：glgl.tv"假片名、详情返回假简介、
# 播放源只给一个 __v99_blacklist_guard__。2.3.6 是当前放行版本。
# 服务器日后再次变更版本时，脚本会自动探测（见 _ensure_version）；
# 也可以在扩展参数里用 ver=2.3.7 或 {"ver":"2.3.7"} 手动指定，无需改代码。
APP_VERSION = "2.3.6"
BUILD_NUMBER = "23050"
APP_SIGNATURE = "32E0AB4FF93A29CE0E6F0BFB01F2F1B788E76262731F3F30F509CB822428ED58"
DEVICE_BUILD = "pangu-build-component-system-513739-s9vkd-rlxnj-p3rhm"
# 只保留语义明确的"假数据"标记。原来的 glgl.tv / IP / shu.jpg 会出现在
# 正常封面和简介里，容易把正常影片误判成版本封禁。
VERSION_GUARD_MARKERS = (
    "最新版下载地址",
    "最新版本下载地址",
    "版本已经失效",
    "请下载最新版",
    "__v99_",
)
FALLBACK_PARSERS = {
    28: {
        "name": "咕噜金牌",
        "url": "http://111.170.58.215:5499/api.php?id=",
        "mode": "json",
        "result_key": "url",
        "server": False,
    },
}

# [补丁1] 筛选定义。字段编号按实测：类型=F8、地区=F6、年份=F12、语言=F7、排序=F18。
_FILTER_GENRES = ["动作", "喜剧", "爱情", "科幻", "恐怖", "剧情", "战争", "犯罪",
                  "悬疑", "动画", "冒险", "奇幻", "惊悚", "家庭"]
_FILTER_AREAS = ["大陆", "香港", "台湾", "美国", "日本", "韩国", "英国", "法国",
                 "泰国", "印度"]
_FILTER_YEARS = [str(y) for y in range(2026, 2012, -1)]
_FILTER_LANGS = ["国语", "粤语", "英语", "韩语", "日语", "泰语", "闽南语"]
_FILTER_SORTS = [("月热门", "vod_hits_month"), ("周热门", "vod_hits_week"),
                 ("日热门", "vod_hits_day"), ("最新", "vod_time"),
                 ("评分", "vod_score")]
_FILTER_CATEGORIES = [("1", "电影"), ("2", "电视剧"), ("3", "综艺"),
                      ("4", "动漫"), ("5", "短剧"), ("60", "直播")]
FILTERS = {}
for _tid, _nm in _FILTER_CATEGORIES:
    if _tid == "60":
        FILTERS[_tid] = []
        continue
    FILTERS[_tid] = [
        {"key": "类型", "name": "类型",
         "value": [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in _FILTER_GENRES]},
        {"key": "地区", "name": "地区",
         "value": [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in _FILTER_AREAS]},
        {"key": "年份", "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in _FILTER_YEARS]},
        {"key": "语言", "name": "语言",
         "value": [{"n": "全部", "v": ""}] + [{"n": l, "v": l} for l in _FILTER_LANGS]},
        {"key": "排序", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _FILTER_SORTS]},
    ]


def _varint(value):
    if value < 0:
        raise ValueError("negative protobuf varint")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _field_bytes(number, value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _field_varint(number, value):
    return _varint(number << 3) + _varint(value)


def _read_varint(data, position):
    value = 0
    shift = 0
    while position < len(data) and shift < 70:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, position
        shift += 7
    raise ValueError("invalid protobuf varint")


def _parse_fields(data):
    fields = []
    position = 0
    while position < len(data):
        key, position = _read_varint(data, position)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("invalid protobuf field zero")
        if wire == 0:
            value, position = _read_varint(data, position)
        elif wire == 1:
            value = data[position:position + 8]
            position += 8
        elif wire == 2:
            size, position = _read_varint(data, position)
            value = data[position:position + size]
            position += size
        elif wire == 5:
            value = data[position:position + 4]
            position += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        if position > len(data):
            raise ValueError("truncated protobuf field")
        fields.append((number, wire, value))
    return fields


def _field_values(data, number, wire=None):
    return [
        value
        for field_number, field_wire, value in _parse_fields(data)
        if field_number == number and (wire is None or field_wire == wire)
    ]


def _field_value(data, number, default=None, wire=None):
    values = _field_values(data, number, wire)
    return values[-1] if values else default


def _text(value, default=""):
    if not isinstance(value, bytes):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return default


def _packed_varints(data):
    values = []
    position = 0
    while position < len(data):
        value, position = _read_varint(data, position)
        values.append(value)
    return values


def _raw_deflate(data):
    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=-15,
        memLevel=8,
        strategy=zlib.Z_RLE,
    )
    return compressor.compress(data) + compressor.flush()


def _derive_key(session_id, shared_x):
    prk = hmac.new(session_id.encode("ascii"), shared_x, hashlib.sha256).digest()
    return hmac.new(prk, b"v2-session\x01", hashlib.sha256).digest()


_P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B


def _sec1_export_public(key):
    point = key.public_key().pointQ
    x = int(point.x).to_bytes(32, "big")
    y = int(point.y).to_bytes(32, "big")
    return b"\x04" + x + y


def _sec1_import_public(data):
    raw = bytes(data or b"")
    if len(raw) == 65 and raw[0] == 4:
        x = int.from_bytes(raw[1:33], "big")
        y = int.from_bytes(raw[33:65], "big")
    elif len(raw) == 33 and raw[0] in (2, 3):
        x = int.from_bytes(raw[1:], "big")
        y2 = (pow(x, 3, _P256_P) - 3 * x + _P256_B) % _P256_P
        y = pow(y2, (_P256_P + 1) // 4, _P256_P)
        if (y & 1) != (raw[0] & 1):
            y = _P256_P - y
    else:
        raise ValueError("invalid P-256 SEC1 public key")
    return ECC.construct(curve="P-256", point_x=x, point_y=y)


class _GuluProtocol:
    def __init__(self, app_version=None, timeout=15):
        self.timeout = timeout
        # 版本号做成实例属性，方便运行时被自动探测/扩展参数覆盖
        self.app_version = APP_VERSION if app_version is None else str(app_version)
        self.session_id = ""
        self.session_key = b""
        self.device_id = secrets.token_hex(8)
        self.request_id = 0
        self.players = {}
        self.parsers = {}
        self.last_detail_error = ""
        self.lock = threading.RLock()

    def _post(self, body, header_name, header_value, extra_headers=None):
        """
        盒子专用：使用 requests 而非 http.client。
        Chaquopy 下 http.client 的 putrequest/endheaders 在 32位 Android 上极不稳定。
        """
        if not HAS_REQUESTS:
            raise RuntimeError("当前环境缺少 requests 模块，无法运行新版咕噜咕噜")
        headers = {
            "user-agent": USER_AGENT,
            header_name: header_value,
            "content-type": "application/x-protobuf",
            "accept-encoding": "gzip",
            "content-length": str(len(body)),
            "host": "103.45.132.22:19987",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            resp = requests.post(
                API_URL,
                data=body,
                headers=headers,
                timeout=self.timeout,
                stream=False,
            )
            if resp.status_code < 200 or resp.status_code >= 300:
                raise RuntimeError("HTTP %s: %s" % (resp.status_code, resp.text[:200]))
            return resp.content
        except requests.exceptions.Timeout:
            raise RuntimeError("请求超时，请检查网络")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("连接失败，服务器可能不可达")

    def handshake(self):
        private_key = ECC.generate(curve="P-256")
        public_key = _sec1_export_public(private_key)
        capabilities = _field_varint(1, 1) + _field_varint(2, 0) + _field_varint(3, 1)
        request = (
            _field_bytes(1, public_key)
            + _field_bytes(2, b"1.0.0")
            + _field_bytes(3, capabilities)
        )
        handshake_key = secrets.token_hex(16)
        iv = secrets.token_bytes(16)
        cipher = AES.new(handshake_key.encode("ascii"), AES.MODE_CBC, iv)
        encrypted = base64.b64encode(
            iv + cipher.encrypt(pad(zlib.compress(request, 4), AES.block_size))
        )
        content = self._post(encrypted, "x-handshake-key", handshake_key)
        raw = base64.b64decode(content)
        response_cipher = AES.new(handshake_key.encode("ascii"), AES.MODE_CBC, raw[:16])
        plain = zlib.decompress(unpad(response_cipher.decrypt(raw[16:]), AES.block_size))
        session_id = _field_value(plain, 1, wire=2)
        server_public = _field_value(plain, 2, wire=2)
        if not session_id or not server_public:
            raise RuntimeError("invalid handshake response")
        self.session_id = session_id.decode("ascii")
        server_key = _sec1_import_public(server_public)
        shared_point = server_key.pointQ * int(private_key.d)
        shared_x = int(shared_point.x).to_bytes(32, "big")
        self.session_key = _derive_key(self.session_id, shared_x)
        self.request_id = 0

    def _encrypt(self, data):
        nonce = secrets.token_bytes(12)
        cipher = AES.new(self.session_key, AES.MODE_GCM, nonce=nonce, mac_len=16)
        ciphertext, tag = cipher.encrypt_and_digest(_raw_deflate(data))
        return nonce + ciphertext + tag

    def _decrypt(self, data):
        if len(data) < 28:
            raise ValueError("invalid GCM payload")
        nonce, ciphertext, tag = data[:12], data[12:-16], data[-16:]
        compressed = AES.new(
            self.session_key, AES.MODE_GCM, nonce=nonce, mac_len=16
        ).decrypt_and_verify(ciphertext, tag)
        return zlib.decompress(compressed, -15)

    def request(self, method, payload=b"", scope=3, extra_headers=None):
        with self.lock:
            if not self.session_id:
                self.handshake()
            self.request_id += 1
            request_id = self.request_id
            core = (
                _field_varint(1, request_id)
                + _field_varint(2, scope)
                + _field_varint(3, method)
                + _field_bytes(4, self.device_id)
                + _field_bytes(5, b"")
                + _field_bytes(6, payload)
                + _field_varint(7, int(time.time() * 1000))
            )
            body = _field_varint(1, request_id) + _field_bytes(2, self._encrypt(core))
            content = self._post(
                body,
                "x-session-id",
                self.session_id,
                extra_headers=extra_headers,
            )
            encrypted = _field_value(content, 2, wire=2)
            if encrypted is None:
                error = _text(_field_value(content, 3, b"", wire=2))
                raise RuntimeError(error or "server rejected request")
            plain = self._decrypt(encrypted)
            status = _text(_field_value(plain, 3, b"", wire=2))
            if status and status not in ("ok", "success"):
                raise RuntimeError(status)
            return plain

    def boot(self):
        now_us = int(time.time() * 1_000_000)
        app = (
            _field_bytes(1, "咕噜咕噜")
            + _field_bytes(2, self.app_version)
            + _field_bytes(3, b"com.himrsc.viz")
            + _field_bytes(4, APP_SIGNATURE)
            + _field_bytes(5, BUILD_NUMBER)
            + _field_varint(6, now_us)
            + _field_varint(7, now_us)
        )
        device = (
            _field_bytes(1, self.device_id)
            + _field_varint(2, 1)
            + _field_bytes(3, b"15")
            + _field_bytes(4, b"Redmi K50 Ultra")
            + _field_bytes(5, b"Redmi/diting/diting:15/AQ3A.240912.001/OS2.0.215.0.VOACNXM:user/release-keys")
            + _field_bytes(6, b"Redmi")
            + _field_bytes(7, b"qcom")
            + _field_varint(8, 0)
            + _field_bytes(9, b"unknown")
            + _field_bytes(10, DEVICE_BUILD)
            + _field_varint(11, 0)
            + _field_varint(12, 35)
        )
        payload = (
            _field_bytes(1, b"v2")
            + _field_bytes(2, b"android")
            + _field_bytes(3, b"gulu")
            + _field_bytes(4, app)
            + _field_bytes(5, device)
        )
        response = self.request(0, payload, scope=1)
        config = _field_value(response, 4, b"", wire=2)
        players = {}
        for item in _field_values(config, 4, wire=2):
            code = _text(_field_value(item, 3, b"", wire=2))
            if not code:
                continue
            parser_ids = []
            for packed in _field_values(item, 8, wire=2):
                parser_ids.extend(_packed_varints(packed))
            players[code] = {
                "id": _field_value(item, 1, 0, wire=0),
                "name": _text(_field_value(item, 4, b"", wire=2)),
                "parser_ids": parser_ids,
            }
        parsers = {}
        for item in _field_values(config, 7, wire=2):
            parser_id = _field_value(item, 1, 0, wire=0)
            if parser_id:
                parsers[parser_id] = {
                    "name": _text(_field_value(item, 2, b"", wire=2)),
                    "url": _text(_field_value(item, 3, b"", wire=2)),
                    "mode": _text(_field_value(item, 4, b"", wire=2)),
                    "result_key": _text(_field_value(item, 10, b"url", wire=2)),
                    "server": bool(_field_value(item, 20, 0, wire=0)),
                }
        self.players = players
        self.parsers = parsers

    # [补丁1] search 补回 genre/area/year/lang/sort，按实测字段编号下发：
    # 类型=F8、地区=F6、年份=F12、语言=F7、排序=F18(默认 vod_hits_month)
    def search(self, keyword, page=1, limit=21, category_id="",
               genre="", area="", year="", lang="", sort="vod_hits_month"):
        sort = str(sort or "vod_hits_month").strip() or "vod_hits_month"
        filters = _field_bytes(18, sort.encode("utf-8")) + _field_varint(19, 1)
        category_id = str(category_id or "").strip()
        if category_id:
            filters += _field_bytes(3, category_id) + _field_bytes(4, category_id)
        genre = str(genre or "").strip()
        if genre:
            filters += _field_bytes(8, genre.encode("utf-8"))
        area = str(area or "").strip()
        if area:
            filters += _field_bytes(6, area.encode("utf-8"))
        year = str(year or "").strip()
        if year:
            filters += _field_bytes(12, year.encode("utf-8"))
        lang = str(lang or "").strip()
        if lang:
            filters += _field_bytes(7, lang.encode("utf-8"))
        payload = (
            _field_bytes(1, keyword)
            + _field_varint(2, int(page))
            + _field_varint(3, int(limit))
            + _field_bytes(5, filters)
        )
        response = self.request(61, payload)
        data = _field_value(response, 4, b"", wire=2)
        videos = []
        for message in _field_values(data, 1, wire=2):
            classes = [_text(v) for v in _field_values(message, 17, wire=2)]
            videos.append({
                "vod_id": str(_field_value(message, 1, 0, wire=0)),
                "vod_name": _text(_field_value(message, 3, b"", wire=2)),
                "vod_pic": _text(_field_value(message, 6, b"", wire=2)),
                "vod_remarks": _text(_field_value(message, 11, b"", wire=2)),
                "vod_year": str(_field_value(message, 2, 0, wire=0)),
                "vod_content": _text(_field_value(message, 20, b"", wire=2)),
                "type_name": ",".join(classes),
                "vod_area": _text(_field_value(message, 16, b"", wire=2)),
                "vod_actor": ",".join(_text(v) for v in _field_values(message, 14, wire=2)),
                "vod_director": ",".join(_text(v) for v in _field_values(message, 15, wire=2)),
                "_type": _field_value(message, 4, 0, wire=0),
            })
        page_info = _field_value(data, 2, b"", wire=2)
        return {
            "videos": videos,
            "page": _field_value(page_info, 1, int(page), wire=0),
            "pagecount": _field_value(page_info, 3, 1, wire=0),
            "limit": _field_value(page_info, 2, int(limit), wire=0),
            "total": _field_value(page_info, 4, len(videos), wire=0),
        }

    def detail(self, vod_id):
        self.last_detail_error = ""
        payload = (
            _field_varint(1, int(vod_id))
            + _field_bytes(3, self.app_version)
            + _field_bytes(4, b"1")
            + _field_varint(5, 1)
        )
        response = self.request(
            62,
            payload,
            extra_headers={"x-player-page-protection": "1"},
        )
        data = _field_value(response, 4, b"", wire=2)
        name = _text(_field_value(data, 5, b"", wire=2))
        # 只检查片名、简介和线路 code。封面(field 13)常带官网域名/IP，
        # 拿它做判定会把正常影片误杀，所以不参与。
        guard_text = " ".join(
            [_text(_field_value(data, field, b"", wire=2)) for field in (5, 21)]
            + [
                _text(_field_value(source, 1, b"", wire=2))
                for source in _field_values(data, 75, wire=2)
            ]
        ).lower()
        if any(marker.lower() in guard_text for marker in VERSION_GUARD_MARKERS):
            self.last_detail_error = "server_version_guard"
            return None
        if not name or _field_value(data, 1, 0, wire=0) == 0:
            self.last_detail_error = "invalid_detail"
            return None
        sources = []
        for source in _field_values(data, 75, wire=2):
            code = _text(_field_value(source, 1, b"", wire=2))
            if not code or any(m.lower() in code.lower() for m in VERSION_GUARD_MARKERS):
                continue
            config = self.players.get(code, {})
            episodes = []
            for episode in _field_values(source, 2, wire=2):
                episode_id = _text(_field_value(episode, 3, b"", wire=2))
                if not episode_id:
                    continue
                episodes.append({
                    "index": _field_value(episode, 1, len(episodes) + 1, wire=0),
                    "id": episode_id,
                    "name": _text(_field_value(episode, 4, b"", wire=2)) or f"第{len(episodes) + 1}集",
                })
            if episodes:
                sources.append({
                    "code": code,
                    "name": config.get("name", code),
                    "parser_id": (config.get("parser_ids") or [0])[0],
                    "episodes": episodes,
                })
        # [补丁3] 回补演员(17) / 导演(18)
        return {
            "id": str(_field_value(data, 1, vod_id, wire=0)),
            "name": name,
            "pic": _text(_field_value(data, 13, b"", wire=2)),
            "remarks": _text(_field_value(data, 22, b"", wire=2)),
            "content": _text(_field_value(data, 21, b"", wire=2)),
            "classes": [
                _text(value) for value in _field_values(data, 12, wire=2)
            ],
            "area": _text(_field_value(data, 28, b"", wire=2)),
            "year": _text(_field_value(data, 30, b"", wire=2)),
            "actor": ",".join(
                t for t in (_text(v) for v in _field_values(data, 17, wire=2)) if t
            ),
            "director": _text(_field_value(data, 18, b"", wire=2)),
            "sources": sources,
        }

    def play(self, parser_id, play_id):
        payload = _field_varint(1, int(parser_id)) + _field_bytes(2, play_id)
        response = self.request(69, payload)
        data = _field_value(response, 4, b"", wire=2)
        return _text(_field_value(data, 2, b"", wire=2))


class Spider(Spider):
    def __init__(self):
        self.ext = ""
        self.name = "咕噜咕噜"
        self.app_version = APP_VERSION
        self.forced_version = ""          # 扩展参数里手动指定的版本，优先级最高
        self.version_name = APP_VERSION
        self.build_number = BUILD_NUMBER
        # [补丁5] 包名统一：boot 上报的是 com.himrsc.viz，这里保持一致，
        # 避免 self.package 与实际上报值不一致造成排查困惑。
        self.package = "com.himrsc.viz"
        self.api_version = "v2"
        self.ua = USER_AGENT
        # 手动排序：优先线路 → 4K → 2K → 自建(☆) → 采集
        # 2026-11 服务器新增了 新咕噜4K / 极速蓝光 / VIP4K / VIP蓝光 / 菲乐2K /
        # iyf4k / ☆哔狸☆ 等线路，补进名单，否则会被兜底规则甩到最后。
        self.play_order = [
            # === 优先线路（你指定的前6个）===
            "咕噜4K",
            "新咕噜4K",
            "菲乐4K",
            "鲸宝4K",
            "极速蓝光",
            "VIP4K",
            "VIP蓝光",
            "神话",
            "臻影4K",
            "臻影",
            "精品2K",
            "鲸宝2K",
            "短剧2K",
            "菲乐2K",
            "iyf4k",
            "天堂",
            # === 自建线路（带☆）===
            "讯飞",
            "奇趣",
            "果汁",
            "酷萌",
            "哔哩",
            "哔狸",
            # === 采集类 ===
            "咖啡",
            "量子",
            "非凡",
            "暴风",
            "蚂蚁",
            "小熊",
            "海外",
            "花旗",
            "letv",
        ]
        self.categories = [
            {"id": "1", "name": "电影"},
            {"id": "2", "name": "电视剧"},
            {"id": "3", "name": "综艺"},
            {"id": "4", "name": "动漫"},
            {"id": "5", "name": "短剧"},
            {"id": "60", "name": "直播"},
        ]
        self.player_config = {}
        self.parser_apis = dict(FALLBACK_PARSERS)
        self.protocol = _GuluProtocol(app_version=self.app_version)
        self.last_error = ""
        # [补丁4] 播放缓存（600s）
        self._play_cache = {}
        self._fallback_players()
        self.protocol.players = dict(self.player_config)
        self.protocol.parsers = dict(self.parser_apis)

    def getName(self):
        return "咕噜咕噜"

    def getDependence(self):
        return []

    @staticmethod
    def _parse_extend(extend):
        """扩展参数既可能是 JSON，也可能是 key=value&key=value。"""
        text = str(extend or "").strip()
        if not text:
            return {}
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return {str(k).strip(): str(v).strip() for k, v in obj.items()}
        except (TypeError, ValueError):
            pass
        out = {}
        for part in re.split(r"[&,\n]", text):
            if "=" in part:
                key, value = part.split("=", 1)
                out[key.strip()] = value.strip()
        return out

    def _apply_extend(self, extend):
        self.ext = str(extend or "")
        conf = self._parse_extend(self.ext)
        ver = conf.get("ver", conf.get("version", conf.get("appVersion")))
        if ver is not None:
            # 允许 ver= 显式指定空版本（服务器不校验版本的兜底方案）
            ver = str(ver)
            self.forced_version = ver
            self.app_version = ver
            self.version_name = ver or APP_VERSION
        elif getattr(self, "forced_version", ""):
            self.app_version = self.forced_version
            self.version_name = self.forced_version
        protocol = getattr(self, "protocol", None)
        if protocol is not None:
            protocol.app_version = self.app_version

    def setExtendInfo(self, extend):
        # 允许在订阅扩展参数里写 ver=2.3.7 或 {"ver":"2.3.7"}，
        # 服务器哪天再改版本时不用动代码。
        self._apply_extend(extend)
        return None

    def homeLayout(self):
        return 0

    def init(self, extend=""):
        self._apply_extend(getattr(self, "ext", "") or extend or "")
        if not hasattr(self, "protocol") or self.protocol is None:
            self.__init__()
            self._apply_extend(self.ext)
        try:
            self.protocol.app_version = self.app_version
            self.protocol.handshake()
            self.protocol.boot()
            self._merge_config()
            self.last_error = ""
        except Exception as error:
            self.last_error = "init:%s:%s" % (type(error).__name__, error)
            self.log("[咕噜] " + self.last_error)
        # 服务器换版本 / 拉黑当前版本时自动找到可用版本
        try:
            self._ensure_version()
        except Exception as error:
            self.log("[咕噜] version probe: %s" % error)

    def _merge_config(self):
        """服务器配置优先，但保留本地兜底映射，避免线路显示成英文 code。"""
        players = dict(getattr(self, "player_config", {}) or {})
        players.update(self.protocol.players or {})
        self.player_config = players
        self.protocol.players = dict(players)
        parsers = dict(FALLBACK_PARSERS)
        parsers.update(getattr(self, "parser_apis", {}) or {})
        parsers.update(self.protocol.parsers or {})
        self.parser_apis = parsers
        self.protocol.parsers = dict(parsers)

    def _reset_session(self):
        self.protocol.session_id = ""
        self.protocol.session_key = b""
        self.protocol.request_id = 0

    @staticmethod
    def _is_poisoned(names):
        markers = ("最新版下载地址", "最新版本下载地址", "版本已经失效", "请下载最新版")
        return any(any(m in (name or "") for m in markers) for name in names)

    def _version_candidates(self):
        """内置放行版本 → 后续小版本 → 空版本(服务器不校验) → 派生版本。"""
        candidates = []

        def add(value):
            if value not in candidates:
                candidates.append(value)

        add(APP_VERSION)
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", self.app_version or "")
        if match:
            major, minor, patch = (int(x) for x in match.groups())
            for step in range(1, 7):
                add("%d.%d.%d" % (major, minor, patch + step))
            for step in range(1, 3):
                add("%d.%d.0" % (major, minor + step))
        add("")  # 空版本实测可绕过校验，作为最后的兜底
        return candidates

    def _ensure_version(self):
        """检测服务器是否仍在返回假数据；是则逐个换版本重握手，找到可用版本后固定。"""
        try:
            probe = self.protocol.search("", 1, 3)
            names = [v.get("vod_name", "") for v in probe.get("videos", [])[:3]]
        except Exception:
            return
        if not names or not self._is_poisoned(names):
            return
        original = self.app_version
        old_players = dict(self.protocol.players)
        old_parsers = dict(self.protocol.parsers)
        for version in self._version_candidates():
            try:
                self._reset_session()
                self.protocol.app_version = version
                self.protocol.handshake()
                self.protocol.boot()
                result = self.protocol.search("", 1, 3)
                fresh = [v.get("vod_name", "") for v in result.get("videos", [])[:3]]
                if fresh and not self._is_poisoned(fresh):
                    self.app_version = version
                    self.version_name = version or APP_VERSION
                    self._merge_config()
                    self.last_error = ""
                    self.log("[咕噜] 版本已自动切换为 %s" % (version or "(空)"))
                    return
            except Exception:
                continue
        # 全部失败：恢复原会话配置，给出可操作的提示
        self.protocol.app_version = original
        self.protocol.players = old_players
        self.protocol.parsers = old_parsers
        self.last_error = "version_guard: 当前版本被服务器拦截，请在扩展参数中指定 ver=新版本号"
        self.log("[咕噜] " + self.last_error)

    def _probe_detail_version(self, vod_id):
        """详情接口的版本号在 payload 里，可以不必重握手就逐个试版本。"""
        original = self.protocol.app_version
        for version in self._version_candidates():
            try:
                self.protocol.app_version = version
                detail = self.protocol.detail(vod_id)
                if detail:
                    self.app_version = version
                    self.version_name = version or APP_VERSION
                    self.last_error = ""
                    self.log("[咕噜] 详情版本已切换为 %s" % (version or "(空)"))
                    # 会话也切到新版本，保证后面的播放解析不被旧会话拖累
                    try:
                        self._reset_session()
                        self.protocol.app_version = version
                        self.protocol.handshake()
                        self.protocol.boot()
                        self._merge_config()
                    except Exception:
                        pass
                    return detail
            except Exception:
                continue
        self.protocol.app_version = original
        return None

    def _fallback_players(self):
        # 这个字典只负责"服务器code → 中文显示名"的映射，顺序由 play_order 控制
        fallback = {
            "JD4K": ("鲸宝4K", 32), "CO4K": ("菲乐4K", 23), "rose": ("咖啡", 22),
            "NBY": ("蚂蚁", 25), "lzm3u8": ("量子", 33), "bfzym3u8": ("暴风", 34),
            "ffm3u8": ("非凡", 35), "dyttm3u8": ("天堂", 13), "jplink": ("精品2K", 28),
            "xfyun": ("咕噜4K", 27), "zydj": ("短剧2K", 29), "hqdj": ("花旗", 21),
            "bilibili": ("☆哔哩☆", 22), "qq": ("☆讯飞☆", 22), "qiyi": ("☆奇趣☆", 22),
            "mgtv": ("☆果汁☆", 22), "youku": ("☆酷萌☆", 22), "IMDB": ("臻影", 26),
            "qingshan": ("小熊", 26), "rrmj": ("海外", 21), "qsvip": ("神话", 26),
        }
        for code, (name, parser_id) in fallback.items():
            self.player_config.setdefault(code, {"name": name, "parser_ids": [parser_id]})

    def _search(self, keyword, page=1, limit=21, category_id="",
                genre="", area="", year="", lang="", sort="vod_hits_month"):
        self.last_error = ""
        try:
            result = self.protocol.search(
                keyword, page, limit, category_id,
                genre=genre, area=area, year=year, lang=lang, sort=sort,
            )
            names = [v.get("vod_name", "") for v in result.get("videos", [])[:3]]
            if names and self._is_poisoned(names):
                # 部分盒子不调用 init()，这里也补一次版本自愈
                self._ensure_version()
                result = self.protocol.search(
                    keyword, page, limit, category_id,
                    genre=genre, area=area, year=year, lang=lang, sort=sort,
                )
                if getattr(self, "last_error", ""):
                    result["error"] = self.last_error
            return result
        except Exception as first_error:
            try:
                self._reset_session()
                result = self.protocol.search(
                    keyword, page, limit, category_id,
                    genre=genre, area=area, year=year, lang=lang, sort=sort,
                )
                return result
            except Exception as second_error:
                self.last_error = "query:%s:%s | retry:%s:%s" % (
                    type(first_error).__name__, first_error,
                    type(second_error).__name__, second_error,
                )
                self.log("[咕噜] " + self.last_error)
                return {
                    "videos": [], "page": page, "pagecount": 1,
                    "limit": limit, "total": 0, "error": self.last_error,
                }

    def homeContent(self, filter=False):
        result = {
            "class": [
                {"type_id": item["id"], "type_name": item["name"]}
                for item in self.categories
            ],
            # [补丁1] 下发筛选 UI
            "filters": FILTERS,
        }
        if getattr(self, "last_error", ""):
            result["msg"] = "初始化异常: " + self.last_error
        return result

    def homeVideoContent(self):
        result = self._search("", 1, 21)
        videos = result.get("videos", [])
        for item in videos:
            item.pop("_type", None)
        response = {"list": videos[:20]}
        if result.get("error"):
            response["msg"] = result["error"]
        return response

    # [补丁1] categoryContent 透传筛选参数（extend 里是 UI 选中的中文值）
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        category_id = str(tid or "").strip()
        conf = extend or {}
        if isinstance(conf, str):
            try:
                conf = json.loads(conf)
            except (TypeError, ValueError):
                conf = {}
        if not isinstance(conf, dict):
            conf = {}
        result = self._search(
            "", page, 21, category_id,
            genre=conf.get("类型", ""),
            area=conf.get("地区", ""),
            year=conf.get("年份", ""),
            lang=conf.get("语言", ""),
            sort=conf.get("排序", "") or "vod_hits_month",
        )
        videos = result.get("videos", [])
        for item in videos:
            item.pop("_type", None)
        response = {
            "page": int(result.get("page", page) or page),
            "pagecount": int(result.get("pagecount", 1) or 1),
            "limit": int(result.get("limit", 21) or 21),
            "total": int(result.get("total", len(videos)) or 0),
            "list": videos,
        }
        if result.get("error"):
            response["msg"] = result["error"]
        return response

    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        result = self._search(key, page, 21)
        for item in result["videos"]:
            item.pop("_type", None)
        response = {
            "list": result["videos"],
            "page": page,
            "pagecount": result.get("pagecount", 1),
        }
        if result.get("error"):
            response["msg"] = result["error"]
        return response

    def _detail_id(self, ids):
        pending = [ids]
        while pending:
            value = pending.pop(0)
            if isinstance(value, (list, tuple, set)):
                pending[0:0] = list(value)
                continue
            if isinstance(value, dict):
                for key in ("vod_id", "vodId", "id", "key"):
                    if key in value:
                        pending.insert(0, value[key])
                        break
                continue
            if isinstance(value, bytes):
                value = value.decode("utf-8", "ignore")
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            if text[:1] in ("[", "{"):
                try:
                    pending.insert(0, json.loads(text))
                    continue
                except (TypeError, ValueError):
                    pass
            if text.isdigit():
                return text
            match = re.search(r"(?:^|[^0-9])(\d{1,12})(?:$|[^0-9])", text)
            if match:
                return match.group(1)
        return ""

    def detailContent(self, ids):
        vod_id = self._detail_id(ids)
        if not vod_id:
            return {"list": [], "msg": "无效的视频ID"}
        try:
            if not hasattr(self, "protocol") or self.protocol is None:
                self.init("")
            try:
                detail = self.protocol.detail(vod_id)
            except Exception:
                self._reset_session()
                self.protocol.handshake()
                detail = self.protocol.detail(vod_id)
            if not detail and getattr(self.protocol, "last_detail_error", "") == "server_version_guard":
                # 详情接口单独校验版本：逐个试候选版本，而不是直接放弃
                detail = self._probe_detail_version(vod_id)
            if not detail:
                result = {"list": []}
                if getattr(self.protocol, "last_detail_error", "") == "server_version_guard":
                    result["msg"] = "服务器版本校验未通过，请在扩展参数中指定 ver=新版本号"
                else:
                    result["msg"] = "获取详情失败，视频可能已下架"
                return result
            play_from = []
            play_blocks = []
            for source in detail["sources"]:
                episodes = []
                for episode in source["episodes"]:
                    index = episode["index"] or len(episodes) + 1
                    encoded = "{}@{}@{}@{}".format(
                        episode["id"], source["parser_id"], detail["name"], index
                    )
                    episodes.append(f"{episode['name']}${encoded}")
                if episodes:
                    # 清洗显示名称，界面不再显示【看公告】等后缀
                    display_name = self._clean_display_name(source["name"])
                    play_from.append(display_name)
                    play_blocks.append("#".join(episodes))
            paired = list(zip(play_from, play_blocks))
            paired.sort(key=lambda item: self._play_order_key(item[0]))
            # 简介前缀：防骗提示 + 原简介
            content = detail.get("content") or ""
            if INTRO_PREFIX:
                content = INTRO_PREFIX + ("\n" + content if content else "")
            vod = {
                "vod_id": detail["id"],
                "vod_name": detail["name"],
                "vod_pic": detail["pic"],
                "vod_remarks": detail["remarks"],
                "vod_year": detail["year"],
                "vod_content": content,
                "type_name": ",".join(detail["classes"]),
                "vod_area": detail["area"],
                # [补丁3] 回补演员 / 导演
                "vod_actor": detail.get("actor", ""),
                "vod_director": detail.get("director", ""),
                "vod_play_from": "$$$".join(item[0] for item in paired),
                "vod_play_url": "$$$".join(item[1] for item in paired),
            }
            return {"list": [vod]}
        except Exception as error:
            self.log("[咕噜] detailContent error: %s" % error)
            return {"list": [], "msg": "获取详情失败: %s" % error}

    def _clean_display_name(self, name):
        """
        统一清洗线路显示名称。
        去掉 【看公告】、[VIP]、（备用）、HD 等装饰性前后缀，
        让界面只保留干净的线路名。
        """
        if not isinstance(name, str) or not name:
            return name or ""
        # 1. 去除各类括号及其内部内容：【...】 [...] （...） (...)
        clean = re.sub(r'[【\[\(（].*?[】\]）)]', '', name)
        # 2. 去除尾部常见独立标记（不区分大小写）
        clean = re.sub(
            r'\s*(?:HD|VIP|备用|推荐|极速|高清|标清|蓝光|超清|试看|抢先|预告|新版|旧版)\s*$',
            '', clean, flags=re.I
        )
        # 3. 去除多余空格
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _play_order_key(self, source_name):
        """
        计算播放源排序权重。
        三层策略：
        1. play_order 精确/前缀/包含匹配（权重 0~999，最高优先级）
        2. 基于线路特征的智能分类（权重 1000+，兜底防改名）
           - 4K线路 → 1000
           - 2K线路 → 2000
           - 自建(☆) → 3000
           - 其他采集 → 4000
        这样即使服务器后期改了线路名称（如"咕噜4K"→"咕噜超清4K"），
        只要包含"4K"/"2K"/"☆"等特征，大类顺序就不会乱。
        """
        if not source_name:
            return 9999

        # 统一清洗，保证排序和显示逻辑一致
        clean = self._clean_display_name(source_name)
        clean_lower = clean.lower()

        # === 第一层：play_order 精确匹配（不区分大小写）===
        for i, name in enumerate(self.play_order):
            if clean_lower == name.lower():
                return i

        # === 第二层：play_order 前缀/包含匹配（不区分大小写）===
        for i, name in enumerate(self.play_order):
            name_lower = name.lower()
            if clean_lower.startswith(name_lower) or name_lower in clean_lower:
                return i

        # === 第三层：基于特征的智能分类（防改名兜底）===
        upper = clean.upper()
        if '4K' in upper:
            return 1000
        if '2K' in upper:
            return 2000
        if '☆' in clean:
            return 3000
        # 纯中文采集类默认排最后
        return 4000

    def _is_playable_url(self, value, strict=True):
        if not isinstance(value, str):
            return False
        url = value.strip()
        if not re.match(r"^https?://", url, re.I):
            return False
        if not strict:
            # 不少解析接口返回不带扩展名的直链，解析结果只要是个 http 地址就收下
            return True
        return any(mark in url.lower() for mark in (".m3u8", ".mp4", ".mkv", ".flv", ".ts", "/m.php", "?data="))

    def _extract_play_url(self, value, preferred_key="url"):
        if isinstance(value, str):
            value = value.strip()
            return value if self._is_playable_url(value, strict=False) else ""
        if isinstance(value, dict):
            keys = [preferred_key, "url", "play_url", "playUrl", "m3u8", "data"]
            for key in dict.fromkeys(keys):
                if key in value:
                    found = self._extract_play_url(value[key], preferred_key)
                    if found:
                        return found
            for item in value.values():
                found = self._extract_play_url(item, preferred_key)
                if found:
                    return found
        elif isinstance(value, (list, tuple)):
            for item in value:
                found = self._extract_play_url(item, preferred_key)
                if found:
                    return found
        return ""

    def _external_play(self, parser_id, play_id):
        parser = self.protocol.parsers.get(parser_id, {})
        api_url = str(parser.get("url") or "").strip()
        if not api_url:
            return ""
        encoded = quote(str(play_id), safe="")
        target = api_url.replace("{url}", encoded) if "{url}" in api_url else api_url + encoded
        # 兼容不同版本的 base.spider：新版的 fetch 支持 timeout，旧版不支持该关键字参数
        try:
            response = self.fetch(target, headers={"User-Agent": USER_AGENT}, timeout=15)
        except TypeError:
            response = self.fetch(target, headers={"User-Agent": USER_AGENT})
        if response is None:
            return ""
        if isinstance(response, (dict, list, str)):
            payload = response
        else:
            try:
                payload = response.json()
            except Exception:
                payload = getattr(response, "text", "")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError):
                pass
        return self._extract_play_url(payload, parser.get("result_key") or "url")

    def playerContent(self, flag, id, vipFlags):
        # 播放串格式：raw_id@parser_id@片名@集数。片名/播放ID 里可能带 @，
        # 因此先看正序能否拆出数字 parser_id，不行再从右侧拆一次。
        play_id = str(id or "")
        parts = play_id.split("@", 3)
        raw_id = parts[0] if len(parts) > 1 else play_id
        parser_id, vod_name, episode_index = 0, "", "1"
        if len(parts) == 4 and parts[1].strip().isdigit():
            parser_id, vod_name, episode_index = int(parts[1]), parts[2], parts[3]
        else:
            right = play_id.rsplit("@", 3)
            if len(right) == 4 and right[1].strip().isdigit():
                raw_id = right[0]
                parser_id, vod_name, episode_index = int(right[1]), right[2], right[3]

        # [补丁4] 播放缓存（600s），命中的直接返回，避免重复解析
        now = int(time.time())
        cache_key = play_id
        cached = self._play_cache.get(cache_key)
        if cached and now - cached[0] < 600:
            return cached[1]

        url = raw_id if self._is_playable_url(raw_id) else ""
        if not url and parser_id:
            parser = self.protocol.parsers.get(parser_id, {})
            if parser and not parser.get("server", True):
                try:
                    url = self._external_play(parser_id, raw_id)
                except Exception:
                    url = ""
            if not url:
                try:
                    url = self.protocol.play(parser_id, raw_id)
                except Exception:
                    try:
                        self.protocol.session_id = ""
                        self.protocol.session_key = b""
                        self.protocol.request_id = 0
                        self.protocol.handshake()
                        url = self.protocol.play(parser_id, raw_id)
                    except Exception:
                        url = ""
        # [补丁4] 失败兜底：parse:1 交给 TVBox 嗅探原播放页，避免白屏
        if not url:
            res = {
                "parse": 1,
                "url": play_id,
                "header": json.dumps({"User-Agent": USER_AGENT}),
                "msg": "解析失败，已尝试嗅探兜底；仍失败请更换播放源",
            }
            self._play_cache[cache_key] = (now, res)
            return res
        danmaku = (
            "http://127.0.0.1:9978/proxy?do=appdanmu&vodName="
            + quote(vod_name, safe="")
            + "&vodIndex="
            + quote(str(episode_index), safe="")
            + "&vodUrl="
        )
        res = {
            "parse": 0,
            "url": url,
            "header": json.dumps({"User-Agent": USER_AGENT}),
            "danmaku": danmaku,
        }
        self._play_cache[cache_key] = (now, res)
        return res

    def isVideoFormat(self, url):
        return self._is_playable_url(url)

    def manualVideoCheck(self):
        return False

    def proxy(self, params):
        pass

    # [补丁4] localProxy：实际实现，支持 param 为 dict 或 "url=xxx&..." 字符串
    def localProxy(self, param):
        url = ""
        if isinstance(param, dict):
            url = str(param.get("url") or "")
        elif isinstance(param, str):
            for pair in param.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    if key == "url":
                        url = value
                        break
        if not url:
            return [403, "text/plain", b"", None]
        try:
            from urllib.parse import unquote
            if "%" in url:
                url = unquote(url)
        except Exception:
            pass
        headers = {"User-Agent": USER_AGENT}
        try:
            if HAS_REQUESTS:
                resp = requests.get(url, headers=headers, timeout=15)
                return [
                    200,
                    resp.headers.get("Content-Type", "application/octet-stream"),
                    resp.content,
                    None,
                ]
        except Exception:
            pass
        try:
            import urllib.request
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                return [
                    200,
                    response.headers.get("Content-Type", "application/octet-stream"),
                    response.read(),
                    None,
                ]
        except Exception:
            return [403, "text/plain", b"", None]


# [补丁2] 模块级单例双入口（drpy site 模式 / 旧内核按函数名取）
_SINGLETON = None


def _get_singleton():
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = Spider()
        try:
            _SINGLETON.init("")
        except Exception:
            pass
    return _SINGLETON


def init(extend=""):
    return _get_singleton().init(extend)


def getName():
    return _get_singleton().getName()


def homeContent(filter=False):
    return _get_singleton().homeContent(filter)


def homeVideoContent():
    return _get_singleton().homeVideoContent()


def categoryContent(tid, pg="1", filter=True, extend=""):
    return _get_singleton().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get_singleton().detailContent(ids)


def searchContent(key, quick=False, pg="1"):
    return _get_singleton().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _get_singleton().playerContent(flag, id, vipFlags)


def isVideoFormat(url):
    return _get_singleton().isVideoFormat(url)


def localProxy(param):
    return _get_singleton().localProxy(param)


def manualVideoCheck():
    return _get_singleton().manualVideoCheck()


# 类名别名（部分内核按小写 spider 约定取类）
spider = Spider
