#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄豆短剧 (aihuangdou.com) Spider
Nuxt CMS | 分类卡片 + 排序筛选器 + 详情直链
分类 /ai-duanju/ 卡片 vod_id=/drama/{id}/
详情 /drama/{id}/ 有 data-preview-src m3u8 直链（yd-hls.tktjpm.cn）
搜索 /search/?q=xxx
"""
from base.spider import Spider
import json, re, base64, urllib.parse, html as HTML
import requests

try:
    from Crypto.Cipher import AES
except Exception:
    AES = None

class Spider(Spider):
    name = '黄豆短剧'
    HOST = 'https://aihuangdou.com'
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

    # 分类（ai-meinv 为"AI美女"）
    CATS = [
        ('ai-duanju', 'AI成人短剧'),
        ('ai-manju', 'AI成人漫剧'),
        ('ai-meinv', 'AI美女'),
        ('ai-mogai', 'AI魔改'),
    ]
    # 排序 tab
    SORTS = [
        {'n': '最新更新', 'v': 'new'},
        {'n': '当前热播', 'v': 'hot'},
        {'n': '高分推荐', 'v': 'score'},
        {'n': '最多收藏', 'v': 'collect'},
    ]

    def init(self, extend=''):
        self.headers = {'User-Agent': self.UA, 'Accept-Language': 'zh-CN,zh;q=0.9',
                        'Referer': self.HOST + '/'}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def getName(self):
        return '黄豆短剧'

    # ---- helpers ----

    def _get(self, url):
        for kw in ({'verify': False}, {}):
            try:
                r = self.session.get(url, timeout=15, **kw)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
        return None

    def _proxy_pic(self, pic):
        """封面走壳端本地图片代理：pic.wirqed.cn 返回加密响应（魔数 65d9ed8b，非 JPEG），
        需壳端 localProxy 解密还原，直连壳端显示不出。
        优先 getProxyUrl()（壳端本地代理），无代理则回退 127.0.0.1 默认端口。"""
        if not pic:
            return ''
        pic = pic.replace('\\u0026', '&').replace('&amp;', '&')
        if pic.startswith('//'):
            pic = 'https:' + pic
        if not pic.startswith('http'):
            pic = self.HOST + pic
        base = ''
        try:
            base = self.getProxyUrl() or ''
        except Exception:
            base = ''
        if not base:
            base = 'http://127.0.0.1:9978/proxy'
        sep = '?' if '?' not in base else '&'
        return base + sep + 'do=py&type=pic&url=' + urllib.parse.quote(pic, safe='')

    def _cards(self, html):
        """卡片提取：data-track-item-id/name + data-src(图) + data-preview-src(m3u8)"""
        result = []
        for m in re.finditer(
                r'<a class="poster-link"[^>]*href="[^"]*drama/(\d+)/"[^>]*'
                r'data-track-item-name="([^"]*)"[^>]*>'
                r'(.*?)</a>', html, re.S):
            vid, name, body = m.group(1), m.group(2), m.group(3)
            img = re.search(r'data-src="(https?://[^"]+)"', body)
            pic = img.group(1) if img else ''
            # 图片走本地代理（Content-Type 是 binary/octet-stream，壳端不识别）
            if pic:
                pic = self._proxy_pic(pic)
            result.append({
                'vod_id': '/drama/%s/' % vid,
                'vod_name': name.strip() if name else ('《%s》' % vid),
                'vod_pic': pic,
                'vod_tag': 'movie',
            })
        # 去重
        seen, uniq = set(), []
        for it in result:
            if it['vod_id'] not in seen:
                seen.add(it['vod_id'])
                uniq.append(it)
        return uniq

    def _total(self, html):
        m = re.search(r'共\s*<b>(\d+)</b>', html) or re.search(r'共\s*(\d+)\s*部', html)
        return int(m.group(1)) if m else 0

    def _pagecount(self, total, per=24):
        import math
        return max(1, math.ceil(total / per))

    # ---- 接口 ----

    def homeContent(self, filter):
        """首页：4个分类 + 排序筛选器 + 首页视频"""
        result = {'class': [], 'filters': {}, 'list': []}
        for cid, cname in self.CATS:
            result['class'].append({'type_id': cid, 'type_name': cname})
        # 每个分类挂排序筛选器
        for cid, cname in self.CATS:
            result['filters'][cid] = [
                {'key': 'sort', 'name': '排序', 'value': self.SORTS}
            ]
        # 首页视频（抓第一个分类）
        html = self._get(self.HOST + '/ai-duanju/')
        if html:
            result['list'] = self._cards(html)[:30]
        return result

    def homeVideoContent(self):
        html = self._get(self.HOST + '/ai-duanju/')
        return {'list': self._cards(html)[:30] if html else []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类/子分类列表（支持翻页 + 排序筛选）"""
        pg = int(pg) if str(pg).isdigit() else 1
        ext = {}
        if extend:
            if isinstance(extend, dict):
                ext = extend
            else:
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}
        sort = ext.get('sort', '')
        # tid 是分类 slug（ai-duanju）
        cid = str(tid).strip()
        known = [c for c, _ in self.CATS if c == cid]
        if not known:
            return {'list': [], 'page': pg, 'pagecount': 1000, 'limit': 24, 'total': 0}
        if pg > 1:
            url = '%s/%s/%d/' % (self.HOST, cid, pg)
        else:
            url = '%s/%s/' % (self.HOST, cid)
        if sort:
            url += ('&' if '?' in url else '?') + 'sort=' + sort
        html = self._get(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1000, 'limit': 24, 'total': 0}
        blocks = self._cards(html)
        total = self._total(html)
        return {
            'list': blocks,
            'page': pg,
            'pagecount': self._pagecount(total),
            'limit': len(blocks) if blocks else 24,
            'total': total,
            'type': sort,
        }

    def _playback(self, vid, ep):
        """请求黄豆 playback API 获取该集真实 m3u8 直链"""
        try:
            r = self.session.get('%s/videos/%s/episodes/%d/playback' % (self.HOST, vid, ep),
                                 headers={'User-Agent': self.UA, 'Referer': self.HOST + '/video/%s/' % vid,
                                          'Accept': 'application/json'}, timeout=10, verify=False)
            if r.status_code == 200:
                d = r.json()
                src = (d.get('data') or {}).get('src') or ''
                if src:
                    return src.replace('\\u0026', '&').replace('&amp;', '&')
        except Exception:
            pass
        return ''

    def detailContent(self, ids):
        """详情：/drama/{id}/ → 标题 + 图 + 真实 m3u8（经 playback API 逐集获取）"""
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid).strip()
        if not vid.startswith('http'):
            url = self.HOST + (vid if vid.startswith('/') else '/drama/%s/' % vid)
        else:
            url = vid
        html = self._get(url)
        if not html:
            return {'list': []}
        # 标题
        h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title = h1.group(1).strip() if h1 else ''
        if not title:
            title = re.search(r'"name"\s*:\s*"([^"]+)"', html).group(1) if re.search(r'"name"\s*:\s*"([^"]+)"', html) else ''
        # 图片（详情页第一个 data-src 即当前视频封面，走本地代理解密显示）
        img = re.search(r'data-src="(https?://[^"]+)"', html)
        pic = self._proxy_pic(img.group(1)) if img else ''
        # 集数：详情页 episode-grid 的 data-total（注意：详情页 data-preview-src 全是推荐位其它片，
        # 不能用作播放源，否则会播错片子，必须走 playback API 拿当前视频真实 m3u8）
        dm = re.search(r'drama/(\d+)', url)
        cur_id = dm.group(1) if dm else (re.search(r'(\d+)', vid).group(1) if re.search(r'(\d+)', vid) else '')
        total = 0
        eg = re.search(r'episode-grid[^>]*data-total="(\d+)"', html)
        if eg:
            total = int(eg.group(1))
        play_url = ''
        if total and cur_id:
            eps_urls = []
            for ep in range(1, total + 1):
                u = self._playback(cur_id, ep)
                if u:
                    eps_urls.append('第%02d集$%s' % (ep, u))
            if eps_urls:
                play_url = '#'.join(eps_urls)
        if not play_url:
            # 兜底：直接用当前视频播放页（壳端访问后可解析真实 m3u8）
            if cur_id:
                play_url = '第01集$%s/video/%s/' % (self.HOST, cur_id)
            else:
                play_url = ''
        vod = {
            'vod_id': '/drama/%s/' % cur_id if cur_id else vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': '',
            'vod_content': '',
            'vod_play_from': self.name,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg):
        """搜索 /search/?q=xxx"""
        pg = int(pg) if str(pg).isdigit() else 1
        url = '%s/search/?q=%s' % (self.HOST, urllib.parse.quote(key))
        if pg > 1:
            url += '&page=%d' % pg
        html = self._get(url)
        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1000, 'limit': 24, 'total': 0}
        blocks = self._cards(html)
        total = self._total(html)
        return {'list': blocks, 'page': pg,
                'pagecount': self._pagecount(total), 'limit': len(blocks) if blocks else 24,
                'total': total}

    def playerContent(self, flag, id, vipFlags):
        """播放：m3u8 直链（真直链验证）"""
        m3u8 = id.strip().replace('\\u0026', '&').replace('&amp;', '&')
        if not m3u8 or not m3u8.startswith('http'):
            return {'parse': 1, 'playUrl': '', 'url': ''}
        try:
            r = self.session.get(m3u8, headers={'User-Agent': self.UA, 'Referer': self.HOST + '/'},
                                 timeout=10, verify=False, allow_redirects=True)
            if r.status_code == 200 and '#EXTM3U' in r.text[:500]:
                return {'parse': 0, 'playUrl': '', 'url': m3u8,
                        'header': {'Referer': self.HOST + '/', 'User-Agent': self.UA}}
        except Exception:
            pass
        # 沙箱连不通 CDN 也放行（客户端正常网络可拉）
        return {'parse': 0, 'playUrl': '', 'url': m3u8,
                'header': {'Referer': self.HOST + '/', 'User-Agent': self.UA}}

    # ========== 本地代理（图片解密）==========
    def localProxy(self, param):
        if not param:
            return [404, "text/plain", "nf"]
        url = param.get("url") or ""
        if not url:
            return [404, "text/plain", "nf"]
        url = urllib.parse.unquote(url)
        try:
            r = self.session.get(url, headers={'User-Agent': self.UA, 'Referer': self.HOST + '/'},
                                 timeout=15, verify=False)
            ct = r.content
            if ct[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", ct]
            if ct[:8] == b"\x89PNG\r\n\x1a\n":
                return [200, "image/png", ct]
            if ct[:4] == b"RIFF" and ct[8:12] == b"WEBP":
                return [200, "image/webp", ct]
            if ct[:3] == b"GIF":
                return [200, "image/gif", ct]
            if AES and len(ct) % 16 == 0:
                key = bytes(int(c) for c in "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48".split("_"))
                iv = bytes(int(c) for c in "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49".split("_"))
                dec = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
                if dec[:3] == b"\xff\xd8\xff":
                    return [200, "image/jpeg", dec]
                if dec[:8] == b"\x89PNG\r\n\x1a\n":
                    return [200, "image/png", dec]
                if dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
                    return [200, "image/webp", dec]
                if dec[:3] == b"GIF":
                    return [200, "image/gif", dec]
                return [200, "image/jpeg", dec]
            return [200, "image/jpeg", ct]
        except Exception:
            return [404, "text/plain", "err"]
