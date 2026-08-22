#coding=utf-8
import sys
import re
import json
import html as html_module
import requests
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site = 'https://www.qmao.net'
        self.session = requests.Session()
        self.ua = 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        self.session.headers.update({'User-Agent': self.ua})
        self.cateManual = {
            '电影': '1',
            '电视剧': '2',
            '动漫': '3',
            '短剧': '4',
        }
        self._m = chr(0x661f) + chr(0x6cb3)

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = html_module.unescape(text)
        text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
        text = ' '.join(text.split())
        return text.strip()

    def _get(self, url, headers=None):
        try:
            req_headers = {'Referer': self.site}
            if headers:
                req_headers.update(headers)
            r = self.session.get(url, timeout=15, headers=req_headers)
            r.encoding = 'utf-8'
            return r.text
        except Exception as e:
            print(f'_get error: {e}')
            return ''

    def init(self, extend=''):
        pass

    def getName(self):
        return '七猫短剧'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}, 'list': [], 'parse': 0, 'jx': 0}
        for k, v in self.cateManual.items():
            result['class'].append({'type_id': str(v), 'type_name': k})
        return result

    def _extract_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        # 使用更宽泛的正则匹配所有视频卡片
        for m in re.finditer(r'<a[^>]*href="/(?:voddetail|vodsearch)/(\d+)\.html"[^>]*>(.*?)</a>', html, re.DOTALL):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            content = m.group(2)
            
            # 标题提取 - 多种方式
            title = ''
            tm = re.search(r'title="([^"]*)"', content)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'alt="([^"]*)"', content)
                if tm:
                    title = self._clean(tm.group(1))
            if not title:
                # 从文本内容中提取
                text_content = self._clean(content)
                if text_content:
                    title = text_content[:50]
            
            # 封面提取
            pic = ''
            pm = re.search(r'src="([^"]*\.(?:jpg|jpeg|png|webp)[^"]*)"', content, re.IGNORECASE)
            if pm:
                pic = pm.group(1).strip()
                if not pic.startswith('http'):
                    if pic.startswith('//'):
                        pic = 'https:' + pic
                    else:
                        pic = self.site + pic
            
            # 备注提取（集数/状态）
            note = ''
            # 查找包含数字+集 或 完结 的文字
            nm = re.search(r'(\d+集|完结|更新至\d+集|全\d+集)', content)
            if nm:
                note = nm.group(1)
            if not note:
                nm = re.search(r'<span[^>]*class="[^"]*remarks[^"]*"[^>]*>([^<]+)</span>', content)
                if nm:
                    note = self._clean(nm.group(1))
            
            if title:
                videos.append({
                    'vod_id': vid,
                    'vod_name': title[:50],
                    'vod_pic': pic,
                    'vod_remarks': note
                })
        return videos

    def homeVideoContent(self):
        result = {'list': [], 'parse': 0, 'jx': 0}
        html = self._get(self.site)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'parse': 0, 'jx': 0}
        page = int(pg) if pg else 1
        if page > 1:
            url = f'{self.site}/vodtype/{tid}-{page}.html'
        else:
            url = f'{self.site}/vodtype/{tid}.html'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        result['page'] = page
        # 尝试获取总页数
        pagecount = page
        if html:
            pm = re.search(r'<span[^>]*class="[^"]*page[^"]*"[^>]*>.*?/(\d+)</span>', html)
            if pm:
                pagecount = int(pm.group(1))
            else:
                # 检查是否有下一页
                if '<a href="' in html and 'page/' in html:
                    pagecount = page + 1
        result['pagecount'] = max(pagecount, page)
        result['limit'] = len(result['list'])
        result['total'] = len(result['list'])
        return result

    def detailContent(self, ids):
        result = {'list': [], 'parse': 0, 'jx': 0}
        vid = ''
        if isinstance(ids, list):
            vid = ids[0] if ids else ''
        elif ids:
            vid = str(ids)
        if not vid:
            return result

        # 获取详情页HTML（包含所有线路和集数信息）
        detail_url = f'{self.site}/voddetail/{vid}.html'
        detail_html = self._get(detail_url)
        if not detail_html:
            return result

        # 标题
        title = ''
        m2 = re.search(r'<h1[^>]*>([^<]+)</h1>', detail_html)
        if m2:
            title = self._clean(m2.group(1))
        if not title:
            m2 = re.search(r'<title>([^<]+)</title>', detail_html)
            if m2:
                title = self._clean(re.sub(r'\s*[-–—].*$', '', m2.group(1)))

        # 封面
        pic = ''
        m2 = re.search(r'<div[^>]*class="[^"]*cover[^"]*"[^>]*>\s*<img[^>]*src="([^"]+)"', detail_html, re.DOTALL)
        if m2:
            pic = m2.group(1).strip()
        if not pic:
            m2 = re.search(r'<img[^>]*class="[^"]*dramaDetail_bookCover[^"]*"[^>]*src="([^"]+)"', detail_html)
            if m2:
                pic = m2.group(1).strip()
        if pic and not pic.startswith('http'):
            if pic.startswith('//'):
                pic = 'https:' + pic
            else:
                pic = self.site + pic

        # 类型
        vod_class = ''
        m2 = re.search(r'类型[：:]\s*([^<]+)', detail_html)
        if m2:
            vod_class = self._clean(m2.group(1))

        # 演员
        actor = ''
        m2 = re.search(r'主演[：:]\s*([^<]+)', detail_html)
        if m2:
            actor = self._clean(m2.group(1))
        if not actor:
            m2 = re.search(r'演员[：:]\s*([^<]+)', detail_html)
            if m2:
                actor = self._clean(m2.group(1))

        # 导演
        director = ''
        m2 = re.search(r'导演[：:]\s*([^<]+)', detail_html)
        if m2:
            director = self._clean(m2.group(1))
        if not director:
            director = self._m
        else:
            director = self._m + '、' + director

        # 简介
        content = ''
        m2 = re.search(r'<div[^>]*class="[^"]*dramaDetail_bookDesc[^"]*"[^>]*>(.*?)</div>', detail_html, re.DOTALL)
        if m2:
            content = self._clean(m2.group(1))
        if not content:
            m2 = re.search(r'简介[：:]\s*([^<]+)', detail_html)
            if m2:
                content = self._clean(m2.group(1))

        # 提取播放线路和集数
        play_from = []
        play_url_list = []

        # 查找所有播放线路
        # 方式1：通过tab按钮找线路
        tabs = re.findall(r'<span[^>]*class="[^"]*episode_tabBtn[^"]*"[^>]*data-sid="(\d+)"[^>]*data-from="([^"]*)"[^>]*>([^<]*)</span>', detail_html)
        if not tabs:
            # 方式2：通过按钮文本找线路
            tabs = re.findall(r'<button[^>]*class="[^"]*episode_tabBtn[^"]*"[^>]*>([^<]+)</button>', detail_html)
            if tabs:
                tabs = [(str(i), '', tabs[i]) for i in range(len(tabs))]
            else:
                # 方式3：通过线路标题
                tabs = re.findall(r'<div[^>]*class="[^"]*episode_tab[^"]*"[^>]*>([^<]+)</div>', detail_html)
                if tabs:
                    tabs = [(str(i), '', tabs[i]) for i in range(len(tabs))]

        # 提取所有剧集链接
        # 方式1：查找 CatalogList_linkBox 类的链接
        episodes = []
        ep_matches = re.findall(r'<a[^>]*class="[^"]*CatalogList_linkBox[^"]*"[^>]*href="(/vodplay/[^"]+)"[^>]*>(.*?)</a>', detail_html, re.DOTALL)
        if ep_matches:
            for href, content in ep_matches:
                # 提取集数
                num_match = re.search(r'(\d+)', content)
                if num_match:
                    ep_num = num_match.group(1)
                    episodes.append(f'第{ep_num}集${href}')
                else:
                    # 尝试从 href 中提取
                    href_match = re.search(r'-(\d+)-(\d+)\.html', href)
                    if href_match:
                        ep_num = href_match.group(2)
                        episodes.append(f'第{ep_num}集${href}')
                    else:
                        episodes.append(f'播放${href}')
        else:
            # 方式2：查找所有 vodplay 链接
            for em in re.finditer(r'href="(/vodplay/[^"]+)"[^>]*>([^<]*)</a>', detail_html):
                href = em.group(1)
                text = self._clean(em.group(2))
                if text and text.strip():
                    episodes.append(f'{text}${href}')
                else:
                    # 从链接中提取集数
                    num_match = re.search(r'-(\d+)-(\d+)\.html', href)
                    if num_match:
                        ep_num = num_match.group(2)
                        episodes.append(f'第{ep_num}集${href}')

        # 如果有线路和集数，组合播放源
        if tabs and episodes:
            # 使用第一个线路
            line_name = self._clean(tabs[0][2]) if len(tabs[0]) > 2 else '默认'
            if not line_name:
                line_name = tabs[0][1] if len(tabs[0]) > 1 and tabs[0][1] else '默认'
            play_from.append(line_name)
            play_url_list.append('#'.join(episodes))
        elif episodes:
            # 没有线路但集数存在
            play_from.append('默认线路')
            play_url_list.append('#'.join(episodes))

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': vod_class,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content[:500] if content else '',
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url_list)
        }
        result['list'].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            play_url = id
            # 如果传的是完整URL，直接使用
            if play_url.startswith('http'):
                final_url = play_url
            else:
                # 确保以 / 开头
                if not play_url.startswith('/'):
                    play_url = '/' + play_url
                final_url = self.site + play_url

            # 获取播放页HTML
            html = self._get(final_url)
            if not html:
                # 尝试直接返回原始URL
                result['parse'] = 1
                result['url'] = final_url
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': self.ua,
                    'Referer': self.site + '/'
                }
                return result

            # 尝试提取 player_aaaa 或类似播放器数据
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{[^<]+\})', html)
            if m:
                try:
                    pd = json.loads(m.group(1))
                    url = pd.get('url', '')
                    if url:
                        # 如果是相对路径，补全
                        if url.startswith('//'):
                            url = 'https:' + url
                        elif url.startswith('/'):
                            url = self.site + url
                        result['parse'] = 0
                        result['url'] = url
                        result['jx'] = 0
                        result['header'] = {
                            'User-Agent': self.ua,
                            'Referer': self.site + '/'
                        }
                        return result
                except:
                    pass

            # 尝试提取 iframe 中的视频链接
            m = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if m:
                iframe_url = m.group(1)
                if iframe_url.startswith('//'):
                    iframe_url = 'https:' + iframe_url
                elif iframe_url.startswith('/'):
                    iframe_url = self.site + iframe_url
                # 尝试获取iframe内容
                iframe_html = self._get(iframe_url)
                if iframe_html:
                    # 在iframe中查找m3u8或mp4
                    vm = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', iframe_html)
                    if vm:
                        result['parse'] = 0
                        result['url'] = vm.group(1)
                        result['jx'] = 0
                        result['header'] = {
                            'User-Agent': self.ua,
                            'Referer': iframe_url
                        }
                        return result

            # 直接在HTML中查找m3u8或mp4链接
            vm = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html)
            if vm:
                result['parse'] = 0
                result['url'] = vm.group(1)
                result['jx'] = 0
                result['header'] = {
                    'User-Agent': self.ua,
                    'Referer': self.site + '/'
                }
                return result

            # 如果以上都找不到，尝试使用解析接口
            m3 = re.search(r'<input[^>]*id="url"[^>]*value="([^"]+)"', html)
            if m3:
                video_url = m3.group(1)
                if video_url:
                    result['parse'] = 0
                    result['url'] = video_url
                    result['jx'] = 0
                    result['header'] = {
                        'User-Agent': self.ua,
                        'Referer': self.site + '/'
                    }
                    return result

            # 最后尝试：返回当前播放页，由外部解析器解析
            result['parse'] = 1
            result['url'] = final_url
            result['jx'] = 0
            result['header'] = {
                'User-Agent': self.ua,
                'Referer': self.site + '/'
            }

        except Exception as e:
            print(f'playerContent error: {e}')
            result = {'parse': 1, 'url': id, 'jx': 0, 'header': {}}

        if not result:
            result = {'parse': 1, 'url': '', 'jx': 0, 'header': {}}
        return result

    def searchContent(self, key, quick, pg='1'):
        result = {'list': [], 'parse': 0, 'jx': 0}
        wd = requests.utils.quote(key)
        url = f'{self.site}/vodsearch/-------------.html?wd={wd}'
        html = self._get(url)
        if html:
            result['list'] = self._extract_list(html)
        return result

    def localProxy(self, params):
        return [200, "video/MP2T", {}, ""]
