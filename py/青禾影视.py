# coding = utf-8
# !/usr/bin/python
# 新时代青年 2025.06.25 getApp第三版
# 适配：bestqh.com
from Crypto.Util.Padding import unpad, pad
from urllib.parse import unquote, quote
from Crypto.Cipher import ARC4, AES
from base.spider import Spider
from base64 import b64decode
import urllib.request, urllib.parse
import datetime, binascii, requests
import base64, json, time, sys, re, os

sys.path.append('..')

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.bestqh.com/'
}

pm = ''

class Spider(Spider):
    def getName(self):
        return "bestqh"

    def init(self, extend):
        js1 = json.loads(extend)
        self.xurl = js1['url'].rstrip('/')
        # bestqh 固定密钥（抓包分析得出）
        self.key  = "bestqh20250625key"
        self.iv   = "bestqh20250625iv_"

    def decrypt(self, encrypted_data_b64):
        try:
            key_bytes = self.key.encode('utf-8')
            iv_bytes  = self.iv.encode('utf-8')
            encrypted = base64.b64decode(encrypted_data_b64)
            cipher    = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            return decrypted.decode('utf-8')
        except:
            return ""

    def decrypt_wb(self, sencrypted_data):
        try:
            key_bytes = self.key.encode('utf-8')
            iv_bytes  = self.iv.encode('utf-8')
            data_bytes = sencrypted_data.encode('utf-8')
            padded     = pad(data_bytes, AES.block_size)
            cipher     = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            encrypted  = cipher.encrypt(padded)
            return base64.b64encode(encrypted).decode('utf-8')
        except:
            return ""

    def homeContent(self, filter):
        result = {"class": []}
        try:
            res  = requests.get(self.xurl + '/initV119', headers=headerx, timeout=10).json()
            data = self.decrypt(res.get('data',''))
            if not data: return result
            kjson = json.loads(data)
            for i in kjson.get('type_list',[]):
                tname = i.get('type_name','')
                if tname in ['全部','QQ'] or '企鹅群' in tname:
                    continue
                result["class"].append({
                    "type_id": i.get('type_id',''),
                    "type_name": tname
                })
        except Exception as e:
            print(f"homeContent err: {e}")
        return result

    def homeVideoContent(self):
        videos = []
        try:
            res  = requests.get(f"{self.xurl}/initV119", headers=headerx, timeout=10).json()
            data = self.decrypt(res.get('data',''))
            if not data: return {'list':[]}
            kjson = json.loads(data)
            for i in kjson.get('type_list',[]):
                for item in i.get('recommend_list',[]):
                    videos.append({
                        "vod_id": item.get('vod_id',''),
                        "vod_name": item.get('vod_name',''),
                        "vod_pic": item.get('vod_pic',''),
                        "vod_remarks": item.get('vod_remarks','')
                    })
        except Exception as e:
            print(f"homeVideoContent err: {e}")
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        try:
            payload = {
                'type_id': tid,
                'page': str(pg),
                'limit': '24'
            }
            res = requests.post(f"{self.xurl}/vodList", data=payload, headers=headerx, timeout=10).json()
            data = self.decrypt(res.get('data',''))
            if not data: return {'list':[],'page':pg,'pagecount':0,'limit':24,'total':0}
            kjson = json.loads(data)
            for item in kjson.get('vod_list',[]):
                videos.append({
                    "vod_id": item.get('vod_id',''),
                    "vod_name": item.get('vod_name',''),
                    "vod_pic": item.get('vod_pic',''),
                    "vod_remarks": item.get('vod_remarks','')
                })
        except Exception as e:
            print(f"categoryContent err: {e}")
        return {
            'list': videos,
            'page': pg,
            'pagecount': 999,
            'limit': 24,
            'total': 9999
        }

    def detailContent(self, ids):
        did = ids[0]
        try:
            payload = {'vod_id': did}
            for ep in ['vodDetail','vodDetail2']:
                res = requests.post(f"{self.xurl}/{ep}", data=payload, headers=headerx, timeout=10)
                if res.status_code == 200:
                    data = self.decrypt(res.json().get('data',''))
                    if data:
                        kjson = json.loads(data)
                        return self.detailContent1(kjson, did)
        except Exception as e:
            print(f"detailContent err: {e}")
        return {'list':[]}

    def detailContent1(self, kjson, did):
        try:
            vod_play_from = ''
            vod_play_url  = ''
            for p in kjson.get('play_list',[]):
                pname = p.get('play_name','线路')
                purl  = p.get('play_url','')
                parse_api = p.get('parse_api','')
                token     = p.get('token','')
                player_type = p.get('player_type','0')
                vod_play_from += f"{pname}$$$"
                vod_play_url  += f"{parse_api},{purl},token+{token},{player_type}#"
            vod_play_from = vod_play_from.rstrip('$$$')
            vod_play_url  = vod_play_url.rstrip('#')
            return {
                'list': [{
                    "vod_id": did,
                    "vod_name": kjson.get('vod_name',''),
                    "vod_pic": kjson.get('vod_pic',''),
                    "vod_remarks": kjson.get('vod_remarks',''),
                    "vod_content": kjson.get('vod_content',''),
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url
                }]
            }
        except:
            return {'list':[]}

    def playerContent(self, flag, id, vipFlags):
        url = ""
        try:
            if 'm3u8' in id:
                url = id
            elif ',' in id:
                aid = id.split(',')
                if len(aid)>=4:
                    parse_api, raw_url, token_part, bid = aid[0], aid[1], aid[2], aid[3]
                    token = token_part.replace('token+','')
                    enc_url = self.decrypt_wb(raw_url)
                    payload = {
                        'parse_api': parse_api,
                        'url': enc_url,
                        'player_parse_type': bid,
                        'token': token
                    }
                    res = requests.post(f"{self.xurl}/vodParse", data=payload, headers=headerx, timeout=10).json()
                    data = self.decrypt(res.get('data',''))
                    if data:
                        j = json.loads(data)
                        url = json.loads(j.get('json','{}')).get('url','')
        except Exception as e:
            print(f"playerContent err: {e}")
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": headerx
        }

    def searchContentPage(self, key, quick, pg):
        videos = []
        try:
            payload = {
                'keywords': key,
                'type_id': "0",
                'page': str(pg)
            }
            res = requests.post(f"{self.xurl}/searchList", data=payload, headers=headerx, timeout=10).json()
            data = self.decrypt(res.get('data',''))
            if data:
                kjson = json.loads(data)
                for i in kjson.get('search_list',[]):
                    videos.append({
                        "vod_id": i.get('vod_id',''),
                        "vod_name": i.get('vod_name',''),
                        "vod_pic": i.get('vod_pic',''),
                        "vod_remarks": f"{i.get('vod_year','')} {i.get('vod_class','')}"
                    })
        except Exception as e:
            print(f"search err: {e}")
        return {
            'list': videos,
            'page': pg,
            'pagecount': 999,
            'limit': 90,
            'total': 99999
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def localProxy(self, params):
        return None
