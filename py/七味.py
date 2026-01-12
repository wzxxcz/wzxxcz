import sys
import json
import re
from urllib.parse import quote, unquote, urlparse
import requests
from lxml import etree
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "七味"

    def init(self, extend=""):
        self.hosts = [
            'https://www.pcmp4.com',
            'https://www.qwnull.com',
            'https://www.qwmkv.com',
            'https://www.qwfilm.com',
            'https://www.qnmp4.com',
            'https://www.qnnull.com',
            'https://www.qnhot.com'
        ]
        self.currentHostIndex = 0
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.timeout = 5000
    
    def getCurrentHost(self):
        return self.hosts[self.currentHostIndex]
    
    def nextHost(self):
        self.currentHostIndex = (self.currentHostIndex + 1) % len(self.hosts)
        return self.getCurrentHost()
    
    def _parse_dom(self, response):
        try:
            return etree.HTML(getattr(response, 'content', response.text))
        except:
            return None
    
    def _normalize_url(self, url):
        if not url:
            return url
        return 'https:' + url if url.startswith('//') else self.getCurrentHost() + url if url.startswith('/') else url
    
    def fetch(self, url, headers=None, timeout=None):
        for _ in range(2):
            try:
                response = requests.get(url, headers=headers or self.headers, timeout=timeout or self.timeout)
                response.encoding = response.apparent_encoding
                return response
            except:
                url = url.replace(self.getCurrentHost(), self.nextHost())
        return None
    
    def homeContent(self, filter):
        result = {
            'class': [
                {'type_name': '电影', 'type_id': '1'},
                {'type_name': '剧集', 'type_id': '2'},
                {'type_name': '综艺', 'type_id': '3'},
                {'type_name': '动漫', 'type_id': '4'},
                {'type_name': '短剧', 'type_id': '30'}
            ]
        }
        return result
    
    def homeVideoContent(self):
        result = []
        try:
            response = self.fetch(self.getCurrentHost(), headers=self.headers)
            html = self._parse_dom(response)
            if not html:
                return {'list': result}
            for item in html.xpath('//ul[contains(@class, "content-list")]/li')[:30]:
                a_tag = item.xpath('.//div[@class="li-img"]/a')[0]
                href = a_tag.get('href', '')
                title = a_tag.get('title', '')
                if title and href:
                    img = str(a_tag.xpath('.//img/@src')[0]) if a_tag.xpath('.//img/@src') else ''
                    desc = str(item.xpath('.//div[@class="tag"]/text()')[0]).strip() if item.xpath('.//div[@class="tag"]/text()') else ''
                    vod_id = re.search(r'/mv/(\d+)\.html', href).group(1) if re.search(r'/mv/(\d+)\.html', href) else ''
                    result.append({
                        'vod_id': vod_id,
                        'vod_name': title,
                        'vod_pic': self._normalize_url(img),
                        'vod_remarks': desc
                    })
        except:
            pass
        return {'list': result}
    
    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 999999}
        try:
            url = self._normalize_url(f'/vt/{tid}.html?page={pg}')
            html = self._parse_dom(self.fetch(url, headers=self.headers))
            if not html:
                return result
            for item in html.xpath('//ul[contains(@class, "content-list")]/li')[:30]:
                try:
                    a_tag = item.xpath('.//div[@class="li-img"]/a')[0]
                    href = a_tag.get('href', '')
                    title = a_tag.get('title', '')
                    if title and href:
                        img = str(a_tag.xpath('.//img/@src')[0]) if a_tag.xpath('.//img/@src') else ''
                        desc = str(item.xpath('.//div[@class="tag"]/text()')[0]).strip() if item.xpath('.//div[@class="tag"]/text()') else ''
                        vod_id = re.search(r'/mv/(\d+)\.html', href).group(1) if re.search(r'/mv/(\d+)\.html', href) else ''
                        result['list'].append({
                            'vod_id': vod_id,
                            'vod_name': title,
                            'vod_pic': self._normalize_url(img),
                            'vod_remarks': desc
                        })
                except:
                    continue
        except:
            pass
        return result
    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        try:
            input_param = str(ids[0]).strip()
            video_id = re.search(r'/mv/(\d+)\.html', input_param).group(1) if re.search(r'/mv/(\d+)\.html', input_param) else input_param
            input_url = f'{self.getCurrentHost()}/mv/{video_id}.html'
            if not video_id:
                raise Exception('无效的视频ID')
            response = self.fetch(input_url, headers=self.headers)
            if not response or not response.text:
                raise Exception('页面内容为空')
            html = response.text
            root = self._parse_dom(response)
            if root is None:
                raise Exception('页面解析失败')
            VOD = {k: '' for k in ['vod_name', 'type_name', 'vod_pic', 'vod_content', 'vod_remarks', 'vod_year', 'vod_area', 'vod_actor', 'vod_director', 'vod_play_from', 'vod_play_url']}
            h1_text = ''.join(map(str, root.xpath('.//div[@class="main-ui-meta"]/h1//text()'))).strip()
            year_match = re.search(r'\((\d{4})\)', h1_text)
            if year_match:
                VOD['vod_year'], VOD['vod_name'] = year_match.group(1), re.sub(r'\s*\(\d{4}\)', '', h1_text).strip()
            else:
                VOD['vod_name'] = h1_text
            VOD['vod_pic'] = str(root.xpath('.//div[@class="img"]/img/@src')[0]) if root.xpath('.//div[@class="img"]/img/@src') else ''
            for div in root.xpath('.//div[@class="main-ui-meta"]/div'):
                text = ''.join(map(str, div.xpath('.//text()'))).strip()
                a_text = '/'.join(map(str, div.xpath('.//a/text()')))
                if '导演：' in text: VOD['vod_director'] = a_text
                elif '主演：' in text: VOD['vod_actor'] = a_text
                elif '类型：' in text: VOD['type_name'] = a_text
                elif '地区：' in text: VOD['vod_area'] = a_text
            VOD['vod_remarks'] = ''.join(map(str, root.xpath('.//div[@class="otherbox"]//text()'))).strip()
            VOD['vod_content'] = ''.join(map(str, root.xpath('.//div[@class="movie-introduce"]//p[@class="zkjj_a"]//text()'))).strip()
            play_from, play_url = [], []
            line_items = root.xpath('//div[@class="hd right"]/ul[@class="py-tabs"]/li')
            episode_containers = root.xpath('//div[@class="bd"]/ul[contains(@class, "player")]')
            for i, (line_item, container) in enumerate(zip(line_items, episode_containers)):
                line_name = re.sub(r'\d+', '', ''.join(map(str, line_item.xpath('.//text()'))).strip().split('\n')[0]).strip().replace(' ', '')
                if not line_name:
                    continue
                play_from.append(line_name)
                episode_list = []
                for j, ep_item in enumerate(container.xpath('.//a')):
                    try:
                        ep_title = ''.join(map(str, ep_item.xpath('.//text()'))).strip()
                        href = ep_item.get('href', '')
                        line_num = re.search(r'/py/(\d+)-(\d+)-(\d+)\.html', href).group(2) if re.search(r'/py/(\d+)-(\d+)-(\d+)\.html', href) else None
                        if line_num:
                            episode_list.append(f"{ep_title}${video_id}|{line_num}|{j}")
                    except:
                        continue
                play_url.append('#'.join(episode_list) if episode_list else f"正片${video_id}|{i+1}|0")
            magnet_links = list(set(re.findall(r'magnet:\?[^&"\'\s]+', html) or []))
            if magnet_links:
                play_from.append('磁力下载')
                play_url.append('#'.join([f"磁力{i+1}${link}" for i, link in enumerate(magnet_links)]))
            pan_regex = r'https?:\/\/(?:pan\.baidu\.com|pan\.quark\.cn|drive\.uc\.cn|cloud\.189\.cn|yun\.139\.com|alipan\.com|pan\.aliyun\.com|115\.com|115cdn\.com)\/[^"\'>\s]+'
            pan_links = list(set(re.findall(pan_regex, html) or []))
            cleaned_pan_links = []
            for link in pan_links:
                link = link.replace('&amp;', '&')
                if '>' in link:
                    link = link.split('>')[0]
                if self._isValidPanUrl(link):
                    cleaned_pan_links.append(link)
            pan_links = list(set(cleaned_pan_links))
            if pan_links:
                pan_types = {'pan.baidu.com': '百度', 'pan.quark.cn': '夸克', 'drive.uc.cn': 'UC', 'cloud.189.cn': '天翼', 'yun.139.com': '移动', 'alipan.com': '阿里', 'pan.aliyun.com': '阿里', '115.com': '115', '115cdn.com': '115'}
                pan_links_by_type = {}
                for link in pan_links:
                    for domain, pan_type in pan_types.items():
                        if domain in link:
                            pan_links_by_type.setdefault(pan_type, []).append(link)
                            break
                for pan_type, links in pan_links_by_type.items():
                    play_from.append(f"{pan_type}网盘")
                    play_url.append('#'.join([f"{pan_type}网盘{i+1}$push://{link}" for i, link in enumerate(links)]))
            if not play_from:
                play_from, play_url = ['默认线路'], [f"正片${video_id}|0|0"]
            
            VOD['vod_play_from'] = '$$$'.join(play_from)
            VOD['vod_play_url'] = '$$$'.join(play_url)
            VOD['vod_id'] = video_id
            
            return {'list': [VOD]}
        except Exception as e:
            return {'list': [{
                "vod_name": '加载失败',
                "type_name": "",
                "vod_pic": "",
                "vod_content": f'加载失败: {str(e)}',
                "vod_remarks": '请检查网络连接或配置是否正确',
                "vod_play_from": '默认线路',
                "vod_play_url": '正片$$0|0|0',
                "vod_id": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_year": "",
                "vod_area": ""
            }]}
    
    def searchContent(self, key, quick, pg):
        results = []
        try:
            keyword = key.lower().strip()
            if not keyword:
                return {'list': results}
            root = self._parse_dom(self.fetch(self.getCurrentHost(), headers=self.headers))
            if not root:
                return {'list': results}
            home_data = root.xpath('//ul[contains(@class, "content-list")]/li | //ul[contains(@class, "content-list-nth")]/li')
            seen_titles = set()
            for item in home_data:
                try:
                    a_tag = item.xpath('.//div[@class="li-img"]/a')[0]
                    href = a_tag.get('href', '')
                    if not href.startswith('/mv/'):
                        continue
                    title = a_tag.get('title', '').strip()
                    if not title or title in seen_titles:
                        continue
                    if keyword not in title.lower():
                        continue
                    seen_titles.add(title)
                    img = str(a_tag.xpath('.//img/@src')[0]) if a_tag.xpath('.//img/@src') else ''
                    desc = item.xpath('.//div[@class="tag"]/text()')[0].strip() if item.xpath('.//div[@class="tag"]/text()') else ''
                    vod_id = re.search(r'/mv/(\d+)\.html', href).group(1) if re.search(r'/mv/(\d+)\.html', href) else ''
                    results.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": self._normalize_url(img),
                        "vod_remarks": desc
                    })
                except IndexError:
                    continue
        except:
            pass
        return {'list': results}
    
    def _getDefaultHeaders(self):
        return {**self.headers, "Referer": self.getCurrentHost()}
    def _isValidPanUrl(self, url):
        pan_domains = ['pan.baidu.com', 'pan.baiduimg.com', 'pan.quark.cn', 'drive.uc.cn',
                      'cloud.189.cn', 'yun.139.com', 'alipan.com', 'pan.aliyun.com',
                      '115.com', '115cdn.com']
        return bool(url) and '</' not in url and '/>' not in url and any(domain in url for domain in pan_domains)
    def playerContent(self, flag, id, vipFlags):
        if id.startswith(('magnet:', 'push://')):
            return {"parse": 0, "url": id}
        try:
            ids = id.split('|')
            if len(ids) == 3:
                videoId, lineIndex, episodeIndex = ids
                playUrl = f"{self.getCurrentHost()}/py/{videoId}-{int(lineIndex)+1}-{int(episodeIndex)+1}.html"
                return {"parse": 1, "url": playUrl, "header": self._getDefaultHeaders()}
        except:
            pass
        
        return {"parse": 1, "url": id, "header": self._getDefaultHeaders()}

    def isVideoFormat(self, url):
        return False

    def localProxy(self, url):
        return False

    def manualVideoCheck(self, url):
        return False


