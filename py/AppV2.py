# -*- coding: utf-8 -*-
# by @嗷呜
# 基于原作者 @嗷呜 版本修改，仅可用于个人学习用途
# 已修复：播放异常、解析失败、签名错误、返回格式问题

from base.spider import Spider
from urllib.parse import urlparse, urlencode
import re, sys, time, json, hashlib, datetime, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    headers = {'User-Agent': 'okhttp/4.12.0',}
    api = ''
    apisignkey = ''
    datasignkey = ''

    def init(self, extend=""):
        ext = extend.rstrip()
        if ext.startswith('http'):
            self.api = ext.rstrip('/')
        else:
            try:
                arr = json.loads(ext)
                self.api = arr['api'].rstrip('/')
                self.apisignkey = arr.get('apisignkey', '')
                self.datasignkey = arr.get('datasignkey', '6QQNUsP3PkD2ajJCPCY8')
            except:
                self.api = ext

    def homeContent(self, filter):
        try:
            filters = {}
            classes = []
            if self.api.endswith('v1.vod'):
                path = '/types'
                if self.apisignkey and self.datasignkey:
                    path = self.datasign(path)
                data = self.fetch(f"{self.api}{path}", headers=self.headers, verify=False).json()
                data = data.get('data', [])
            else:
                data = self.fetch(f"{self.api}/nav?token=", headers=self.headers, verify=False).json()
            
            data_list = data.get('list', data.get('data', []))
            keys = ["class", "area", "lang", "year", "letter", "by", "sort"]
            
            for item in data_list:
                classes.append({
                    "type_name": item.get("type_name", ""),
                    "type_id": item.get("type_id", "")
                })
                type_ext = item.get("type_extend", "{}")
                if isinstance(type_ext, str):
                    try:
                        type_ext = json.loads(type_ext)
                    except:
                        type_ext = {}
                
                has_filter = False
                for key in keys:
                    if key in type_ext and type_ext[key].strip():
                        has_filter = True
                        break
                if has_filter:
                    filters[str(item["type_id"])] = []
                    for dk in type_ext:
                        if dk in keys and type_ext[dk].strip():
                            vals = [{"n": v.strip(), "v": v.strip()} for v in type_ext[dk].split(",") if v.strip()]
                            filters[str(item["type_id"])].append({"key": dk, "name": dk, "value": vals})
            
            return {"class": classes, "filters": filters}
        except:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        try:
            videos = []
            if self.api.endswith('v1.vod'):
                path = '/vodPhbAll'
                if self.apisignkey and self.datasignkey:
                    keytime = self.keytime()
                    path = self.datasign(f'?apikey={self.apikey()}&keytime={keytime}', keytime)
                res = self.fetch(f"{self.api}{path}", headers=self.headers, verify=False).json()
                data = res.get('data', {})
                for item in data.get('list', []):
                    videos.extend(item.get('vod_list', []))
            else:
                res = self.fetch(f"{self.api}/index_video?token=", headers=self.headers, verify=False).json()
                data = res.get('list', res.get('data', []))
                for item in data:
                    videos.extend(item.get('vlist', []))
            return {'list': videos}
        except:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if self.api.endswith('v1.vod'):
                path = f"?type={tid}&class={extend.get('class', '')}&lang={extend.get('lang', '')}&area={extend.get('area', '')}&year={extend.get('year', '')}&by=&page={pg}&limit=12"
                if self.apisignkey and self.datasignkey:
                    keytime = self.keytime()
                    path = self.datasign(f'{path}&apikey={self.apikey()}&keytime={keytime}', keytime)
                res = self.fetch(f"{self.api}{path}", headers=self.headers, verify=False).json()
                data = res.get('data', {})
            else:
                params = {
                    'tid': tid, 'class': extend.get('class', ''), 'area': extend.get('area', ''),
                    'lang': extend.get('lang', ''), 'year': extend.get('year', ''), 'limit': '18', 'pg': pg
                }
                res = self.fetch(f"{self.api}/video", params=params, headers=self.headers, verify=False).json()
                data = res.get('data', res)
            
            if 'list' not in data:
                data = {'list': data, 'page': pg, 'pagecount': 999, 'limit': 12, 'total': 9999}
            return data
        except:
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 12, 'total': 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            if self.api.endswith('v1.vod'):
                path = f"?page={pg}&limit=12&wd={key}"
                if self.apisignkey and self.datasignkey:
                    keytime = self.keytime()
                    path = self.datasign(f'{path}&apikey={self.apikey()}&keytime={keytime}', keytime)
                url = f"{self.api}{path}"
            else:
                url = f"{self.api}/search?text={key}&pg={pg}"
            
            res = self.fetch(url, headers=self.headers, verify=False).json()
            data2 = res.get('list', res.get('data', []))
            if isinstance(data2, dict):
                data2 = data2.get('list', [])
            
            return {'list': data2, 'page': pg, 'pagecount': 999, 'limit': 12, 'total': 9999}
        except:
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 12, 'total': 0}

    def detailContent(self, ids):
        try:
            if self.api.endswith('v1.vod'):
                path = f'/detail?vod_id={ids[0]}&rel_limit=5'
                if self.apisignkey and self.datasignkey:
                    keytime = self.keytime()
                    path = self.datasign(f'{path}&apikey={self.apikey()}&keytime={keytime}', keytime)
                res = self.fetch(f"{self.api}{path}", headers=self.headers, verify=False).json()
            else:
                res = self.fetch(f"{self.api}/video_detail?id={ids[0]}", headers=self.headers, verify=False).json()
            
            data = res.get('data', {})
            if 'vod_info' in data:
                data = data['vod_info']
            
            show = ''
            vod_play_url = ''

            # 播放组1
            if 'vod_url_with_player' in data:
                for i in data['vod_url_with_player']:
                    name = i.get('name', '默认线路')
                    show += name + '$$$'
                    parse = i.get('parse_api', '')
                    url_raw = i.get('url', '')
                    if parse and parse.startswith('http') and url_raw:
                        tmp = '#'.join([f"{u}@{parse}" for u in url_raw.split('#')])
                    else:
                        tmp = url_raw
                    vod_play_url += tmp + '$$$'

            # 播放组2
            if 'vod_play_list' in data:
                for i in data['vod_play_list']:
                    pinfo = i.get('player_info', {})
                    sname = pinfo.get('show', '播放') + f"({i.get('from','')})"
                    show += sname + '$$$'
                    parse = pinfo.get('parse', '')
                    parse2 = pinfo.get('parse2', '')
                    jx_list = []
                    if parse and parse.startswith('http'): jx_list.append(parse)
                    if parse2 and parse2.startswith('http') and parse2 != parse: jx_list.append(parse2)
                    jx_str = ','.join(jx_list)
                    urls = ''
                    for j in i.get('urls', []):
                        n = j.get('name', '')
                        u = j.get('url', '')
                        if jx_str:
                            urls += f"{n}${u}@{jx_str}#"
                        else:
                            urls += f"{n}${u}#"
                    vod_play_url += urls.rstrip('#') + '$$$'

            data['vod_play_from'] = show.rstrip('$$$')
            data['vod_play_url'] = vod_play_url.rstrip('$$$')
            return {'list': [data]}
        except:
            return {'list': []}

    # ====================== 核心修复：playerContent 播放正常 ======================
    def playerContent(self, flag, id, vipFlags):
        try:
            video_pattern = re.compile(r'https?://.*\.(m3u8|mp4|flv|mp3)', re.I)
            parse = 0
            url = ''
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
            
            # 带解析器的格式：播放地址@解析接口
            if '@' in id:
                raw, jx_addr = id.split('@', 1)
                # 支持多解析器
                jx_list = jx_addr.split(',') if ',' in jx_addr else [jx_addr]
                
                for jx in jx_list:
                    try:
                        res = self.fetch(f"{jx}{raw}", headers=self.headers, timeout=8, verify=False)
                        if res.status_code != 200:
                            continue
                        # 自动识别 JSON / 文本 解析
                        try:
                            jdata = res.json()
                            play_url = jdata.get('url') or jdata.get('play') or jdata.get('m3u8')
                        except:
                            play_url = re.search(r'https?://[^\s"]+', res.text).group() if re.search(r'https?://[^\s"]+', res.text) else ''
                        
                        if play_url and play_url.startswith('http'):
                            url = play_url
                            if jdata.get('ua'):
                                ua = jdata.get('ua')
                            break
                    except:
                        continue
                
                # 解析失败，直接用原始地址
                if not url:
                    url = raw
                    parse = 0 if video_pattern.match(raw) else 1
            else:
                # 无解析器，直接播放
                url = id
                parse = 0 if video_pattern.match(id) else 1

            # 屏蔽无效前缀
            if url.startswith(('NBY', 'unknown', 'test')):
                return {'parse': 0, 'url': '', 'header': {'User-Agent': ua}}

            return {
                'parse': parse,
                'url': url,
                'playUrl': '',
                'header': {'User-Agent': ua}
            }
        except:
            return {'parse': 0, 'url': '', 'header': {'User-Agent': ua}}

    def keytime(self):
        return str(int(datetime.datetime.now().timestamp()))

    def md5(self, s):
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    def apikey(self):
        now = datetime.datetime.now()
        y = str(now.year)
        h = f"{now.hour:02d}"
        m = f"{now.minute:02d}"
        sign_str = f"{y}:{h}:{y}:{m}:{self.apisignkey}"
        return self.md5(sign_str)

    def datasign(self, url='', timestamp=''):
        parsed = urlparse(url)
        q = self._parse_query(parsed.query)
        ts = timestamp or str(int(time.time()))
        q['timestamp'] = ts
        qs = sorted(q.items())
        sign = self.md5('&'.join(f"{k}={v}" for k, v in qs) + self.datasignkey)
        q['datasign'] = sign
        return parsed._replace(query=urlencode(q)).geturl()

    def _parse_query(self, qs):
        res = {}
        if not qs: return res
        for p in qs.split('&'):
            if '=' not in p: continue
            k, v = p.split('=', 1)
            if v: res[k] = v
        return res

    def getName(self):
        return "影视爬虫"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass
