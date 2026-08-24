# -*- coding: utf-8 -*-
# by @嗷呜
import json
import sys
import threading
import uuid
import requests
sys.path.append('..')
from base.spider import Spider
import time
from Crypto.Hash import MD5, SHA1

class Spider(Spider):
    '''
    配置示例：
    {
        "key": "xxxx",
        "name": "xxxx",
        "type": 3,
        "api": ".所在路径/金牌.py",
        "searchable": 1,
        "quickSearch": 1,
        "filterable": 1,
        "changeable": 1,
        "ext": {
            "site": "https://www.jiabaide.cn,域名2,域名3"
        }
    },
    '''
    def init(self, extend=""):
        if extend:
            hosts=json.loads(extend)['site']
        # 尝试获取上一次可用的域名，如果没有则测速选择
        self.host = self.host_late(hosts)
        self.fallback_hosts = self._parse_hosts(hosts)
        # 记录当前可用的备用域名列表（排除当前选中的）
        self.available_fallbacks = [h for h in self.fallback_hosts if h != self.host]
        pass

    def _parse_hosts(self, url_list):
        if isinstance(url_list, str):
            return [u.strip() for u in url_list.split(',') if u.strip()]
        return url_list if url_list else []

    def getName(self):
        return "文才影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        cdata = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/get/filer/type", headers=self.getheaders())
        if not cdata:
            return {'class': [], 'filters': {}}
        cdata = cdata.json()
        
        fdata = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/v1/get/filer/list", headers=self.getheaders())
        if not fdata:
            return {'class': [], 'filters': {}}
        fdata = fdata.json()
        
        result = {}
        classes = []
        filters={}
        for k in cdata.get('data', []):
            classes.append({
                'type_name': k.get('typeName', ''),
                'type_id': str(k.get('typeId', '')),
            })
        sort_values = [{"n": "最近更新", "v": "2"},{"n": "人气高低", "v": "3"}, {"n": "评分高低", "v": "4"}]
        for tid, d in fdata.get('data', {}).items():
            current_sort_values = sort_values.copy()
            if tid == '1':
                del current_sort_values[0]
            filters[tid] = [
                {"key": "type", "name": "类型",
                 "value": [{"n": i["itemText"], "v": i["itemValue"]} for i in d.get("typeList", [])]},

                *([] if not d.get("plotList") else [{"key": "v_class", "name": "剧情",
                                                 "value": [{"n": i["itemText"], "v": i["itemText"]}
                                                           for i in d["plotList"]]}]),

                {"key": "area", "name": "地区",
                 "value": [{"n": i["itemText"], "v": i["itemText"]} for i in d.get("districtList", [])]},

                {"key": "year", "name": "年份",
                 "value": [{"n": i["itemText"], "v": i["itemText"]} for i in d.get("yearList", [])]},

                {"key": "lang", "name": "语言",
                 "value": [{"n": i["itemText"], "v": i["itemText"]} for i in d.get("languageList", [])]},

                {"key": "sort", "name": "排序", "value": current_sort_values}
            ]
        result['class'] = classes
        result['filters'] = filters
        return result

    def homeVideoContent(self):
        data1 = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/v1/home/all/list", headers=self.getheaders())
        if not data1:
            return {'list': []}
        data1 = data1.json()
        
        data2 = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/home/hotSearch", headers=self.getheaders())
        if not data2:
            data2_data = []
        else:
            data2 = data2.json()
            data2_data = data2.get('data', [])
        
        data = []
        for i in data1.get('data', {}).values():
            data.extend(i.get('list', []))
        data.extend(data2_data)
        vods = self.getvod(data)
        return {'list': vods}

    def categoryContent(self, tid, pg, filter, extend):
        params = {
          "area": extend.get('area', ''),
          "filterStatus": "1",
          "lang": extend.get('lang', ''),
          "pageNum": pg,
          "pageSize": "30",
          "sort": extend.get('sort', '1'),
          "sortBy": "1",
          "type": extend.get('type', ''),
          "type1": tid,
          "v_class": extend.get('v_class', ''),
          "year": extend.get('year', '')
        }
        data = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/video/list?{self.js(params)}", headers=self.getheaders(params))
        if not data:
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 30, 'total': 0}
        data = data.json()
        result = {}
        result['list'] = self.getvod(data.get('data', {}).get('list', []))
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        data = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/video/detail?id={ids[0]}", headers=self.getheaders({'id': ids[0]}))
        if not data:
            return {'list': []}
        data = data.json()
        
        detail_data = data.get('data', {})
        if not detail_data:
            return {'list': []}
            
        vod = self.getvod([detail_data])[0]
        vod['vod_play_from'] = '小橙子有文才'
        
        # ============================================================
        # 修复：检查 episodelist 是否存在且不为空
        # ============================================================
        episodelist = vod.get('episodelist', [])
        if episodelist and len(episodelist) > 0:
            vod['vod_play_url'] = '#'.join(
                f"{i.get('name', '第{}集'.format(idx+1)) if len(episodelist) > 1 else vod.get('vod_name', '')}${ids[0]}@@{i.get('nid', '0')}" 
                for idx, i in enumerate(episodelist)
            )
        else:
            # 如果没有剧集列表，尝试从其他字段获取播放地址
            vod['vod_play_url'] = f"{vod.get('vod_name', '')}${ids[0]}@@0"
        
        vod.pop('episodelist', None)
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        params = {
          "keyword": key,
          "pageNum": pg,
          "pageSize": "8",
          "sourceCode": "1"
        }
        data = self.fetch_with_retry(f"{self.host}/api/mw-movie/anonymous/video/searchByWord?{self.js(params)}", headers=self.getheaders(params))
        if not data:
            return {'list': [], 'page': pg}
        data = data.json()
        vods = self.getvod(data.get('data', {}).get('result', {}).get('list', []))
        return {'list': vods, 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.61 Chrome/126.0.6478.61 Not/A)Brand/8  Safari/537.36',
            'sec-ch-ua-platform': '"Windows"',
            'DNT': '1',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'Origin': self.host,
            'Referer': f'{self.host}/'
        }
        ids = id.split('@@')
        
        # 如果 ID 格式不对，直接返回空
        if len(ids) < 2:
            return {'parse': 0, 'url': '', 'header': self.header}
        
        # ============================================================
        # 修复：增强播放地址获取的健壮性，支持备用域名重试
        # ============================================================
        # 尝试的主机列表：当前主机 + 备用主机
        hosts_to_try = [self.host] + self.available_fallbacks
        
        for host in hosts_to_try:
            try:
                # 尝试 v2 接口
                pdata = self.fetch_with_retry(
                    f"{host}/api/mw-movie/anonymous/v2/video/episode/url?clientType=1&id={ids[0]}&nid={ids[1]}",
                    headers=self.getheaders({'clientType':'1','id': ids[0], 'nid': ids[1]})
                )
                if pdata:
                    pdata = pdata.json()
                    # 检查 v2 返回数据是否有效
                    if pdata and 'data' in pdata and 'list' in pdata['data'] and pdata['data']['list']:
                        for item in pdata['data']['list']:
                            url = item.get('url', '')
                            if url and url.startswith('http'):
                                # 如果使用的是备用主机，更新 self.host 以便后续使用
                                if host != self.host:
                                    self.host = host
                                return {'parse': 0, 'url': url, 'header': self.header}
                
                # 如果 v2 没有数据，尝试 v1 接口
                pdata_v1 = self.fetch_with_retry(
                    f"{host}/api/mw-movie/anonymous/v1/video/episode/url?clientType=1&id={ids[0]}&nid={ids[1]}",
                    headers=self.getheaders({'clientType':'1','id': ids[0], 'nid': ids[1]})
                )
                if pdata_v1:
                    pdata_v1 = pdata_v1.json()
                    if pdata_v1 and 'data' in pdata_v1 and 'list' in pdata_v1['data'] and pdata_v1['data']['list']:
                        for item in pdata_v1['data']['list']:
                            url = item.get('url', '')
                            if url and url.startswith('http'):
                                if host != self.host:
                                    self.host = host
                                return {'parse': 0, 'url': url, 'header': self.header}
            except Exception as e:
                # 当前主机失败，继续尝试下一个
                continue
        
        # 所有接口都没有数据，返回空
        return {'parse': 0, 'url': '', 'header': self.header}

    def fetch_with_retry(self, url, headers=None, retries=2, timeout=10):
        """带重试机制的请求方法"""
        for i in range(retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return response
            except Exception as e:
                if i == retries:
                    # 最后一次重试失败，返回 None
                    pass
                else:
                    time.sleep(0.5)
        return None

    def localProxy(self, param):
        pass

    def host_late(self, url_list):
        hosts = self._parse_hosts(url_list)
        if len(hosts) <= 1:
            return hosts[0] if hosts else ''

        results = {}
        threads = []

        def test_host(url):
            try:
                start_time = time.time()
                response = requests.head(url, timeout=2.0, allow_redirects=False)
                delay = (time.time() - start_time) * 1000
                results[url] = delay
            except Exception as e:
                results[url] = float('inf')
                
        for url in hosts:
            t = threading.Thread(target=test_host, args=(url,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        
        min_url = min(results.items(), key=lambda x: x[1])[0]
        if results[min_url] == float('inf'):
            return hosts[0] if hosts else ''
        return min_url

    def md5(self, sign_key):
        md5_hash = MD5.new()
        md5_hash.update(sign_key.encode('utf-8'))
        md5_result = md5_hash.hexdigest()
        return md5_result

    def js(self, param):
        return '&'.join(f"{k}={v}" for k, v in param.items())

    def getheaders(self, param=None):
        if param is None: param = {}
        t = str(int(time.time() * 1000))
        param['key'] = 'cb808529bae6b6be45ecfab29a4889bc'
        param['t'] = t
        sha1_hash = SHA1.new()
        sha1_hash.update(self.md5(self.js(param)).encode('utf-8'))
        sign = sha1_hash.hexdigest()
        deviceid = str(uuid.uuid4())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.61 Chrome/126.0.6478.61 Not/A)Brand/8  Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'sign': sign,
            't': t,
            'deviceid': deviceid
        }
        return headers

    def convert_field_name(self, field):
        field = field.lower()
        if field.startswith('vod') and len(field) > 3:
            field = field.replace('vod', 'vod_')
        if field.startswith('type') and len(field) > 4:
            field = field.replace('type', 'type_')
        return field

    def getvod(self, array):
        return [{self.convert_field_name(k): v for k, v in item.items()} for item in array]
