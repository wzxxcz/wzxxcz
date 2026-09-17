# -*- coding: utf-8 -*-
"""
趣看影视APP爬虫 UI9 Python标准
适配UI9规范，支持extend后台修改域名
依赖：pycryptodome,urllib3
UI9配置JSON:
{
  "key": "qukan_py",
  "name": "趣看影视",
  "type": 3,
  "api": "./py/qukan.py",
  "searchable": 1,
  "quickSearch": 1,
  "filterable": 0
}
"""
import re
import urllib.parse
import json
import time
import base64
import hashlib
import urllib3
from urllib.parse import quote

# 依赖容错
try:
    import requests
except Exception:
    requests = None

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
except Exception:
    RSA = None
    PKCS1_v1_5 = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# UI9父类兜底
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    # 默认扩展配置，后台extend JSON覆盖
    DEFAULT_EXT = {
        "host": "http://qkys.qukanwh.com",
        "ua_app": "okhttp/4.12.0"
    }

    # ---------- 加密常量 ----------
    PUB_KEY_B64 = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCoYt0BP77U+DM08BiI/QbSRIfxijXo85BTPqIM1Ow8BNwhLETzRIZ+dEwdWDbydG/PspgBAfRpGaYVdJYtvaC2JnoO8+Ik6qMWojfEJxSFLa0Pb0A892tun4gsxoEMjcreZ+YGyaBxAfqX0BSMfdrOgIYaZQjYrw9TRLlUT31QoQIDAQAB"
    APP_SIGN_SHA1 = "09a8dc51639a31801af5f6418caebfabc695eb24"
    DEVICE_ID = "2d590b9842d064a1"
    PRIV_KEY_B64 = """MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCquQQ5r6+yJI8CDFkXRp8vUsdD45ov8EP12ooLs56ca2DQXaSNGS9910bAPVA9chkp0mKIvKqjAsHz5Tl9EeNPblarGEeJUIxpxZtiSqNTpvtiD/TjhpzuHYic7RAfQ/h7p/ypE8ymU42pYjsB5t26Mv6XgkLV+jzrSf73HlCuS0iMyLmt6zz3Mw9izM13EpB8iFLtfbbYymycKTx4RAmPQLwhNGex/AlUIYxXP4R2yyaa4W6mEtc6aME2QuzJFxPgP3HJ9NBx/LWVn4skxWjZ7zg+VRQRHnjyVaSLu3Z5gN5ITWCyE32qaHJa6WBahZj5jWhRyAG1bQ+xKJa8lBL5AgMBAAECggEAUwv9SjJ0PSwbhNuM2w23kcWquROWhYtTA91zGY4esehqB/IFgb2mpIh8Gje5OKqwIu/8jpd4SiOlRYdUF8sD0DfUYRZGdj2AkFNX6tBz8tVfo6wvbB6naA1lzzBij1L5JO3qsjS3cJFkb+kg2yP66AC2Z+0tpfk8eRhdtshAZwfcd1DEGt1uAvYL1eaUK9HRvpt9lPeGcHERDl2hBd4uyaF0K1O+zF9y59nYbTySWPxRZq3sFEE85xRMlstD7YZi7W2gKvMFRD4/FKmrZ3m7aKJRITtyKOyyPcYmepNv3Qv7kk59Pg38n2WWQ0Ra/bCH3E48YNCnQvZMpitkTfJhoQKBgQDbnROOYTP8OTJ6f/qhoGjxeO3x1VOaOp8l0x7b0SCfoqNGS0Cyiqj72BmJtPMPqSTjn6MmNzqbg1KOdhXyzNozs+i5ccW1M56j96mr5I/Z0FpE3oyIHNfDDBlf9M8YQqEF9oYxniYYft9oapO7cRQkHER6qpvnHTavwlv4m78CXwKBgQDHAjs2YlpKDdI1lcbZJCc7TwtH+Pd2bUki8YXafWNcPhITQHbOZjr310eK1QJC6GJncjkOqbX7yv3ivvTO35FZTQhuA1xEG1P00FG8bE0tHYPIwQHi9y0eA5cieMdo8E6XYria1mw/3fqSQEsfZyJlR32JQIoGAipM8iO1X2nZpwKBgDkMFIhnt5lNQk+P7wsNIDWZtDWdtJnboHuy29E+Abt2A/O+mI/IdRz2hau/1WO8DFkUnszOi+rZshhPlGP90rCbi1igtTrcrdjp/KkqNjPea5R4OwkgdOu1uOG0NheXNzzVTQaWjk7Opjn5dWa7eP/oV+GFb/oZHJuLYVizHGsBAoGADA7rjZEKDYCm4w5PPSr+oY5ZjaPdQrS+gLqHtMRyN82fBMGcMUdqfUfzEstzVqCEDeaS5HuOBlK3bXzKkppjUTjksN3NQmcxgBz7RuJ9DqXCLXDcb2cwuafYCYOt+YLOEEgwDVm+t2P44dG5e46hO+fICH/7nP+WlpD5buz4GfMCgYB57r3g/6hi9WUDnfc7ZAzWMqR0EhJVYKYy+KFEtdIPzhkkIHq5RASe88E9kzoGoZFdb3tIjvGZWcHerirrqWkMsuQtP/Qi0zjieid5tAPj+r4kbiCVTw0E0jnmPBzGInQi7lpeTTKnG1fbyS5lBS+WmHfIuzpECgCkxhaT+LJJkg=="""

    def getName(self):
        return "趣看影视"

    def init(self, extend=""):
        # 加载后台扩展配置
        self.ext = dict(self.DEFAULT_EXT)
        if isinstance(extend, dict):
            self.ext.update(extend)
        elif isinstance(extend, str) and extend.strip():
            try:
                cfg = json.loads(extend)
                if isinstance(cfg, dict):
                    self.ext.update(cfg)
            except Exception:
                pass

        self.host = self.ext["host"].rstrip("/")
        self.session = requests.Session() if requests else None
        self.userid = ""
        self.token = ""

        # 请求头
        self.base_headers = {
            'User-Agent': self.ext["ua_app"],
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/json;charset=UTF-8",
            'Cache-Control': "no-cache",
            'deviceId': self.DEVICE_ID,
            'client': "app",
            'deviceType': "Android"
        }
        if self.session:
            self.session.headers.update(self.base_headers)

        # 初始化访客信息获取token
        self._init_visitor()

    def _init_visitor(self):
        if not self.session:
            return
        try:
            url = f"{self.host}/api/v1/app/user/visitorInfo"
            resp = self.session.get(url, headers=self.base_headers, timeout=12, verify=False)
            js = resp.json()
            self.userid = js['data']['id']
            self.token = js['data']['token']
        except Exception as e:
            print("访客初始化失败", e)

    # ==================== RSA加密解密 ====================
    def rsa_encrypt(self, data: str) -> str:
        if not RSA:
            raise RuntimeError("缺失pycryptodome")
        key = RSA.import_key(base64.b64decode(self.PUB_KEY_B64))
        cipher = PKCS1_v1_5.new(key)
        encrypted = cipher.encrypt(data.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')

    def rsa_decrypt(self, encrypted_b64: str) -> str:
        if not RSA:
            raise RuntimeError("缺失pycryptodome")
        key = RSA.import_key(base64.b64decode(self.PRIV_KEY_B64))
        cipher = PKCS1_v1_5.new(key)
        encrypted_bytes = base64.b64decode(encrypted_b64)
        block_size = 256
        decrypted_parts = []
        for i in range(0, len(encrypted_bytes), block_size):
            block = encrypted_bytes[i:i+block_size]
            raw = cipher.decrypt(block, b'')
            if raw is None:
                raise Exception("RSA解密失败")
            decrypted_parts.append(raw)
        return b''.join(decrypted_parts).decode('utf-8')

    def build_params_string(self, episode_id="", episode_index="", vid="", player_id="", type_id="", user_id=""):
        return (f"episodeId{episode_id}"
                f"episodeIndex{episode_index}"
                f"id{vid}"
                f"playerId{player_id}"
                f"source0"
                f"typeId{type_id}"
                f"userId{user_id}")

    def generate_sign(self, timestamp: str, params_str: str, device_id: str) -> str:
        raw = f"SaltLSFBTimestamp{timestamp}Params{params_str}ClientappDeviceId{device_id}"
        b64 = base64.b64encode(raw.encode('utf-8')).decode('utf-8')
        md5 = hashlib.md5(b64.encode('utf-8')).hexdigest().upper()
        return md5

    def build_encrypted_req(self, body_dict: dict, type_id="M15"):
        body_json = json.dumps(body_dict, separators=(',', ':'))
        params_str = self.build_params_string(
            episode_id=body_dict.get("episodeId", ""),
            episode_index=body_dict.get("episodeIndex", ""),
            vid=str(body_dict["id"]),
            player_id=body_dict.get("playerId", ""),
            type_id=type_id,
            user_id=str(self.userid)
        )
        timestamp = str(int(time.time()))
        encrypted_key = self.rsa_encrypt(body_json)
        snjm = self.rsa_encrypt("113")
        appsign = self.rsa_encrypt(self.APP_SIGN_SHA1)
        sign = self.generate_sign(timestamp, params_str, self.DEVICE_ID)

        headers = {
            "snjm": snjm,
            "appsign": appsign,
            "timestamp": timestamp,
            "sign": sign,
            "deviceId": self.DEVICE_ID,
            "token": self.token,
            "client": "app",
            "deviceType": "Android",
            "Content-Type": "application/json;charset=UTF-8",
            "Cache-Control": "no-cache",
            "User-Agent": self.ext["ua_app"]
        }
        payload = {"key": encrypted_key}
        return headers, payload

    # ==================== UI9通用工具 ====================
    def _ensure_runtime(self):
        if requests is None:
            raise RuntimeError("缺失requests依赖")
        if RSA is None:
            raise RuntimeError("缺失pycryptodome依赖")

    def _request_json(self, url, method="GET", headers=None, data=None):
        self._ensure_runtime()
        try:
            if method.upper() == "POST":
                resp = self.session.post(url, headers=headers, data=json.dumps(data), timeout=12, verify=False)
            else:
                resp = self.session.get(url, headers=headers, timeout=12, verify=False)
            return resp.json()
        except Exception as e:
            print(f"请求异常 {url}: {e}")
            return {}

    @staticmethod
    def _safe_json(text, default=None):
        try:
            return json.loads(text)
        except Exception:
            return default if default is not None else {}

    def _video_item(self, item):
        if not isinstance(item, dict):
            return {}
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": item.get("name", ""),
            "vod_pic": item.get("cover", ""),
            "vod_remarks": item.get("area", "")
        }

    def isVideoFormat(self, url):
        return bool(re.search(r"(?i)\.(m3u8|mp4|mkv|ts|flv)(\?|$)", str(url)))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param=''):
        return [404, "text/plain", "NotFound"]

    # ==================== UI9标准入口方法 ====================
    def homeContent(self, filter):
        # 获取分类
        url = f"{self.host}/api/v1/app/screen/screenType"
        data = self._request_json(url, method="POST")
        class_list = []
        for item in data.get("data", []):
            class_list.append({
                "type_id": str(item["id"]),
                "type_name": item["name"]
            })
        return {"class": class_list, "filters": {}}

    def homeVideoContent(self):
        url = f"{self.host}/api/v1/app/recommend/recommendList"
        data = self._request_json(url, method="POST")
        all_videos = []
        for rec in data.get("data", []):
            sub_url = f"{self.host}/api/v1/app/recommend/recommendSubList"
            sub_body = {"condition": rec['id'], "pageNum":1, "pageSize":6}
            sub_data = self._request_json(sub_url, method="POST", data=sub_body)
            for video in sub_data.get("data", {}).get("records", []):
                all_videos.append(self._video_item(video))
        return {"list": all_videos}

    def categoryContent(self, tid, pg, filter, extend):
        payload = {
            "condition": {
                "classify": "",
                "region": "",
                "sreecnTypeEnum": "NEWEST",
                "typeId": tid,
                "year": ""
            },
            "pageNum": int(pg),
            "pageSize": 40
        }
        url = f"{self.host}/api/v1/app/screen/screenMovie"
        res = self._request_json(url, method="POST", data=payload)
        records = res.get("data", {}).get("records", [])
        video_list = [self._video_item(i) for i in records]
        return {
            "list": video_list,
            "page": int(pg),
            "pagecount": 99,
            "limit": 40,
            "total": 9999
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        payload = {
            "condition": {"value": key},
            "pageNum": int(pg),
            "pageSize": 40
        }
        url = f"{self.host}/api/v1/app/search/searchMovie"
        res = self._request_json(url, method="POST", data=payload)
        records = res.get("data", {}).get("records", [])
        video_list = [self._video_item(i) for i in records]
        return {
            "list": video_list,
            "page": int(pg),
            "pagecount": 99,
            "limit": 40,
            "total": 9999
        }

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0]
        type_id = "M15"
        body = {
            "id": int(vid),
            "source": 0,
            "typeId": type_id,
            "userId": int(self.userid),
            "episodeId": "",
            "episodeIndex": "",
            "playerId": ""
        }
        headers, payload = self.build_encrypted_req(body, type_id)
        url = f"{self.host}/api/v1/app/play/movieDetails"
        resp_raw = self._request_json(url, method="POST", headers=headers, data=payload)
        enc_data = resp_raw.get("data")
        if not enc_data:
            return result
        dec_str = self.rsa_decrypt(enc_data)
        data = json.loads(dec_str)

        currentplayerid = data['playerId']
        play_urls = []
        show_names = []

        # 当前线路剧集
        ep_urls = []
        for ep in data['episodeList']:
            ep_urls.append(f"{ep['episode']}${vid}@{currentplayerid}@{ep['id']}@episode")
        play_urls.append('#'.join(ep_urls))

        # 线路名称
        for pl in data['moviePlayerList']:
            if pl['id'] == currentplayerid:
                show_names.append(pl['moviePlayerName'])

        # 其他虚拟线路
        for pl in data['moviePlayerList']:
            pid = pl['id']
            etotal = pl.get('episodeTotal')
            if pid == currentplayerid or etotal is None:
                continue
            tmp_ep = []
            for k in range(1, etotal + 1):
                tmp_ep.append(f"第{k}集${k}@{pid}@{vid}@virtual")
            play_urls.append('#'.join(tmp_ep))
            if pl['moviePlayerName'] not in show_names:
                show_names.append(pl['moviePlayerName'])

        # 获取简介
        desc_body = {"id": int(vid), "typeId": type_id}
        desc_url = f"{self.host}/api/v1/app/play/movieDesc"
        desc_res = self._request_json(desc_url, method="POST", data=desc_body)
        desc_data = desc_res.get("data", {})

        vod_info = {
            'vod_id': str(desc_data.get('id')),
            'vod_name': desc_data.get('name', ''),
            'vod_pic': desc_data.get('cover', ''),
            'vod_content': desc_data.get('introduce', ''),
            'vod_year': desc_data.get('year', ''),
            'vod_area': desc_data.get('area', ''),
            'vod_remarks': '',
            'vod_score': desc_data.get('score', ''),
            'type_name': desc_data.get('classify', ''),
            'vod_director': desc_data.get('director', ''),
            'vod_actor': desc_data.get('star', ''),
            'vod_play_from': '$$$'.join(show_names),
            'vod_play_url': '$$$'.join(play_urls)
        }
        result["list"].append(vod_info)
        return result

    def playerContent(self, flag, id, vipFlags):
        param, playerid, param2, mode = id.split('@')
        type_id = "M15"
        if mode == 'virtual':
            payload = {
                "episodeIndex": str(int(param)-1),
                "id": int(param2),
                "playerId": playerid,
                "source": 0,
                "typeId": type_id,
                "userId": int(self.userid),
                "episodeId": ""
            }
        else:
            payload = {
                "episodeId": param2,
                "id": int(param),
                "playerId": playerid,
                "source": 0,
                "typeId": type_id,
                "userId": int(self.userid),
                "episodeIndex": ""
            }
        headers, req_payload = self.build_encrypted_req(payload, type_id)
        url = f"{self.host}/api/v1/app/play/movieDetails"
        resp_raw = self._request_json(url, method="POST", headers=headers, data=req_payload)
        enc_data = resp_raw.get("data")
        if not enc_data:
            return {"parse":0, "url":""}
        dec_str = self.rsa_decrypt(enc_data)
        play_data = json.loads(dec_str)
        parse_url = play_data['url']

        # 调用解析接口
        ana_url = f"{self.host}/api/v1/app/play/analysisMovieUrl?playerUrl={quote(parse_url,safe='')}&playerId={playerid}"
        ana_res = self._request_json(ana_url, method="GET")
        final_url = ana_res.get("data", "")

        return {
            'jx': '0',
            'parse': '0',
            'url': final_url,
            'header': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
            }
        }


if __name__ == '__main__':
    sp = Spider()
    sp.init()
