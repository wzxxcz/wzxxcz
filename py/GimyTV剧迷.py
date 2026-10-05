# coding: utf-8
"""Gimy TV 劇迷 drpy source."""
import re
import json
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    host = 'https://gimyai.tw'

    UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    def init(self, extend=''):
        ext = (extend or '').strip()
        if ext.startswith('http'):
            self.host = ext.rstrip('/')
        else:
            self.host = 'https://gimyai.tw'

    # ==================== 基础工具 ====================
    def _text(self, resp):
        if resp is None:
            return ''
        if hasattr(resp, 'text'):
            return resp.text or ''
        if isinstance(resp, bytes):
            return resp.decode('utf-8', 'ignore')
        return str(resp)

    def _get(self, url, referer=None):
        headers = {
            'User-Agent': self.UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8',
        }
        if referer:
            headers['Referer'] = referer
        try:
            return self._text(self.fetch(url, headers=headers))
        except Exception:
            return ''

    @staticmethod
    def _clean(s):
        """去标签 + 反转义 + 压缩空白"""
        if not s:
            return ''
        s = re.sub(r'<script[\s\S]*?</script>', '', s, flags=re.I)
        s = re.sub(r'<style[\s\S]*?</style>', '', s, flags=re.I)
        s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
        s = re.sub(r'</p>', '\n', s, flags=re.I)
        s = re.sub(r'<[^>]+>', '', s)
        s = (s.replace('&nbsp;', ' ')
              .replace('&amp;', '&')
              .replace('&quot;', '"')
              .replace('&#39;', "'")
              .replace('&apos;', "'")
              .replace('&lt;', '<')
              .replace('&gt;', '>')
              .replace('&hellip;', '…')
              .replace('&mdash;', '—'))
        s = re.sub(r'[ \t\r\f\v]+', ' ', s)
        s = re.sub(r'\n\s*\n+', '\n', s)
        return s.strip()

    def _pick(self, html, patterns, group=1):
        """按顺序尝试多个正则，返回第一个非空结果"""
        if not html:
            return ''
        for pat in patterns:
            m = re.search(pat, html, re.S | re.I)
            if m:
                try:
                    v = self._clean(m.group(group))
                except Exception:
                    continue
                if v:
                    return v
        return ''

    def _attr(self, tag, name):
        m = re.search(r'\b%s\s*=\s*["\']([^"\']*)' % name, tag, re.I)
        return m.group(1) if m else ''

    def _abs(self, url):
        if not url:
            return ''
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('http'):
            return url
        return urljoin(self.host, url)

    def _extract_json(self, html, key):
        """从 html 中提取 key = {...} 的完整 JSON（花括号配对）"""
        idx = html.find(key)
        if idx < 0:
            return ''
        start = html.find('{', idx)
        if start < 0:
            return ''
        depth, in_str, esc = 0, False, False
        for i in range(start, len(html)):
            c = html[i]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
        return ''

    # ==================== 列表卡片解析 ====================
    def _cards(self, html):
        out, seen = [], set()
        if not html:
            return out

        pat = r'<a\b[^>]*class=["\'][^"\']*\bposter\b[^"\']*["\'][^>]*>([\s\S]*?)</a>'
        for m in re.finditer(pat, html, re.S | re.I):
            whole = m.group(0)
            body = m.group(1)
            head = whole.split('>', 1)[0]
            href = self._attr(head, 'href')
            if not href:
                continue
            vid = self._abs(href)
            if not vid or vid in seen:
                continue
            seen.add(vid)

            title = self._pick(body, [
                r'class=["\'][^"\']*poster__title[^"\']*["\'][^>]*>([\s\S]*?)</',
                r'<h[23][^>]*>([\s\S]*?)</h[23]>',
            ])
            if not title:
                title = self._pick(body, [r'<img[^>]+alt=["\']([^"\']+)'])

            mi = re.search(r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)', body, re.I)
            pic = self._abs(mi.group(1)) if mi else ''

            remarks = self._pick(body, [
                r'class=["\'][^"\']*poster__status[^"\']*["\'][^>]*>([\s\S]*?)</',
                r'class=["\'][^"\']*(?:poster__note|poster__badge|note|badge|tag)[^"\']*["\'][^>]*>([\s\S]*?)</',
            ])
            meta = self._pick(body, [
                r'class=["\'][^"\']*poster__meta[^"\']*["\'][^>]*>([\s\S]*?)</',
            ])

            out.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'vod_actor': meta,
            })
        return out

    # ==================== 首页 ====================
    def homeContent(self, filter):
        classes = [
            {'type_id': '2',  'type_name': '電視劇'},
            {'type_id': '4',  'type_name': '動漫'},
            {'type_id': '29', 'type_name': '綜藝'},
            {'type_id': '13', 'type_name': '陸劇'},
            {'type_id': '20', 'type_name': '韓劇'},
            {'type_id': '15', 'type_name': '日劇'},
            {'type_id': '14', 'type_name': '台劇'},
            {'type_id': '21', 'type_name': '港劇'},
            {'type_id': '34', 'type_name': '短劇'},
            {'type_id': '38', 'type_name': 'AI漫劇'},
            {'type_id': '31', 'type_name': '海外劇'},
            {'type_id': '22', 'type_name': '紀錄片'},
        ]

        filters = [{
            'key': 'area', 'name': '地區', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中國大陸', 'v': '中國大陸'},
                {'n': '韓國', 'v': '韓國'},
                {'n': '日本', 'v': '日本'},
                {'n': '台灣', 'v': '台灣'},
                {'n': '香港', 'v': '香港'},
                {'n': '美國', 'v': '美國'},
                {'n': '歐美', 'v': '歐美'},
                {'n': '泰國', 'v': '泰國'},
            ]}, {
            'key': 'year', 'name': '年份', 'value':
                [{'n': '全部', 'v': ''}] +
                [{'n': str(y), 'v': str(y)} for y in range(2026, 2014, -1)]
            }, {
            'key': 'sort', 'name': '排序', 'value': [
                {'n': '最近更新', 'v': 'time'},
                {'n': '最新上架', 'v': 'time_add'},
                {'n': '本週人氣', 'v': 'hits_week'},
                {'n': '總人氣', 'v': 'hits'},
            ]},
        ]

        flt = {c['type_id']: filters for c in classes}
        return {'class': classes, 'filters': flt, 'list': []}

    def homeVideoContent(self, filter=None):
        html = self._get(self.host + '/', referer=self.host)
        items = self._cards(html)
        if not items:
            html = self._get(self.host + '/genre/2.html', referer=self.host)
            items = self._cards(html)
        return {'list': items[:24]}

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1

        f = {}
        if isinstance(filter, dict):
            f.update(filter)
        if isinstance(extend, dict):
            f.update(extend)

        area = str(f.get('area') or '').strip()
        year = str(f.get('year') or '').strip()
        sort = str(f.get('sort') or '').strip()

        # 站点 URL 结构：
        #   /genre/{tid}.html
        #   /explore/{tid}-{地區}----------{page}.html
        #   /explore/{tid}--{排序}---------{page}.html
        #   /explore/{tid}-----------{年份}.html
        # 统一按 12 段拼装，空字段留空（站点会自行忽略）
        if not (area or year or sort) and pg <= 1:
            url = '%s/genre/%s.html' % (self.host, tid)
        else:
            segs = [
                str(tid),
                quote(area),
                '',
                sort,
                '',
                '',
                '',
                '',
                '',
                '',
                year,
                str(pg) if pg > 1 else '',
            ]
            url = '%s/explore/%s.html' % (self.host, '-'.join(segs))

        html = self._get(url, referer=self.host)
        items = self._cards(html)

        # 兜底：explore 失败时退回分类页
        if not items and pg == 1:
            html = self._get('%s/genre/%s.html' % (self.host, tid), referer=self.host)
            items = self._cards(html)

        # 解析分页数
        nums = []
        if html:
            for x in re.findall(r'[-/](\d{1,4})\.html', html):
                try:
                    n = int(x)
                except Exception:
                    continue
                if 1 <= n <= 2000:
                    nums.append(n)

        if items:
            pagecount = max([pg] + nums) if nums else pg
            if pagecount < pg:
                pagecount = pg
        else:
            pagecount = max(1, pg - 1)

        return {
            'list': items,
            'page': pg,
            'pagecount': pagecount,
            'limit': len(items),
            'total': len(items) * pagecount if items else 0,
        }

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1

        url = '%s/find/-------------.html?wd=%s' % (self.host, quote(key or ''))
        if pg > 1:
            url += '&page=%d' % pg

        html = self._get(url, referer=self.host)
        items = self._cards(html)

        return {
            'list': items,
            'page': pg,
            'pagecount': pg if items else max(1, pg - 1),
            'limit': len(items),
            'total': len(items) * pg if items else 0,
        }

    # ==================== 详情（含简介） ====================
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid)
        url = vid if vid.startswith('http') else self._abs('/detail/%s.html' % vid)
        html = self._get(url, referer=self.host)

        # ---- 标题 ----
        title = self._pick(html, [
            r'<h1[^>]*class=["\'][^"\']*detail__title[^"\']*["\'][^>]*>([\s\S]*?)</h1>',
            r'class=["\'][^"\']*detail__title[^"\']*["\'][^>]*>([\s\S]*?)</',
            r'<h1[^>]*>([\s\S]*?)</h1>',
        ])

        # ---- 封面 ----
        pic = ''
        pm = re.search(
            r'class=["\'][^"\']*detail__poster[^"\']*["\'][\s\S]{0,800}?'
            r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)', html, re.I)
        if not pm:
            pm = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if pm:
            pic = self._abs(pm.group(1))

        # ---- 基本字段 ----
        actors = self._pick(html, [
            r'主\s*演[：:]\s*([\s\S]*?)</(?:div|p|li|dd)>',
            r'演\s*員[：:]\s*([\s\S]*?)</(?:div|p|li|dd)>',
            r'class=["\'][^"\']*detail__actors[^"\']*["\'][^>]*>([\s\S]*?)</',
        ])
        director = self._pick(html, [
            r'導\s*演[：:]\s*([\s\S]*?)</(?:div|p|li|dd)>',
            r'导\s*演[：:]\s*([\s\S]*?)</(?:div|p|li|dd)>',
        ])
        area = self._pick(html, [
            r'地\s*區[：:]\s*([^<\n]+)',
            r'地\s*区[：:]\s*([^<\n]+)',
        ])
        year = self._pick(html, [
            r'年\s*份[：:]\s*(\d{4})',
            r'類\s*別[：:][\s\S]{0,80}?(\d{4})',
            r'类\s*别[：:][\s\S]{0,80}?(\d{4})',
            r'(\d{4})\s*年',
        ])
        lang = self._pick(html, [
            r'語\s*言[：:]\s*([^<\n]+)',
            r'语\s*言[：:]\s*([^<\n]+)',
        ])
        vtype = self._pick(html, [
            r'類\s*型[：:]\s*([^<\n]+)',
            r'类\s*型[：:]\s*([^<\n]+)',
        ])
        remarks = self._pick(html, [
            r'class=["\'][^"\']*detail__status[^"\']*["\'][^>]*>([\s\S]*?)</',
            r'更新[：:]\s*([^<\n]+)',
            r'狀態[：:]\s*([^<\n]+)',
        ])
        score = self._pick(html, [
            r'class=["\'][^"\']*detail__score[^"\']*["\'][^>]*>([\s\S]*?)</',
            r'評\s*分[：:]\s*([\d.]+)',
        ])

        # ---- 简介（重点补全） ----
        content = self._pick(html, [
            # 详情页常见的简介容器
            r'<div[^>]+class=["\'][^"\']*\bdetail__content\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__desc\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__intro\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__summary\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            # 通用语义 class
            r'<div[^>]+class=["\'][^"\']*\b(?:plot|summary|synopsis|intro|description|desc|content|txt)\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<p[^>]+class=["\'][^"\']*\b(?:plot|summary|synopsis|intro|description|desc|content)\b[^"\']*["\'][^>]*>([\s\S]*?)</p>',
            # 「簡介：」标签
            r'(?:劇情簡介|剧情简介|簡\s*介|简\s*介|故事簡介)[：:]?\s*</[^>]+>\s*([\s\S]*?)</(?:div|p|section|article)>',
            r'(?:劇情簡介|剧情简介|簡\s*介|简\s*介|故事簡介)[：:]\s*([\s\S]*?)</(?:div|p|section|article)>',
            # 兜底：meta 描述
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
        ])

        if not content:
            # 再兜底一次：抓 detail 区块整体文本
            dm = re.search(r'<div[^>]+class=["\'][^"\']*\bdetail\b[^"\']*["\'][^>]*>([\s\S]*?)</div>\s*</div>',
                           html, re.S | re.I)
            if dm:
                content = self._clean(dm.group(1))

        # ---- 播放线路 ----
        routes = {}
        route_names = {'3': '優酷線路', '9': '藍光線路', '16': '4K畫質線路', '4': '高清線路'}

        hits = list(re.finditer(r'data-route-sid\s*=\s*["\'](\d+)["\']', html, re.I))
        for i, m in enumerate(hits):
            sid = m.group(1)
            start = m.start()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(html)
            block = html[start:end]

            rtitle = self._pick(block, [
                r'class=["\'][^"\']*route-title[^"\']*["\'][^>]*>([\s\S]*?)</div>',
                r'class=["\'][^"\']*route-title[^"\']*["\'][^>]*>([\s\S]*?)</',
            ])
            if not rtitle:
                prev = html[max(0, start - 500):start]
                tms = list(re.finditer(
                    r'class=["\'][^"\']*route-title[^"\']*["\'][^>]*>([\s\S]*?)</div>',
                    prev, re.S | re.I))
                if tms:
                    rtitle = self._clean(tms[-1].group(1))

            rtitle = (rtitle or '').replace('ᴴᴰ', '').replace('HD', '').strip()
            name = rtitle or route_names.get(sid, '線路%s' % sid)

            eps = re.findall(
                r'<a[^>]+href=["\']([^"\']*/play/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                block, re.S | re.I)
            if not eps:
                continue

            seen_ep, parts = set(), []
            for h, t in eps:
                eu = self._abs(h)
                if not eu or eu in seen_ep:
                    continue
                seen_ep.add(eu)
                et = self._clean(t) or '正片'
                parts.append('%s$%s' % (et, eu))

            if parts:
                base_name = name
                idx = 2
                while name in routes:
                    name = '%s-%d' % (base_name, idx)
                    idx += 1
                routes[name] = '#'.join(parts)

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_year': year,
            'vod_area': area,
            'vod_lang': lang,
            'vod_type': vtype,
            'vod_actor': actors,
            'vod_director': director,
            'vod_score': score,
            'vod_content': content,          # ← 简介已补全
            'vod_play_from': '$$$'.join(routes.keys()),
            'vod_play_url': '$$$'.join(routes.values()),
        }
        return {'list': [vod]}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith('http') else self._abs(str(id))
        html = self._get(url, referer=self.host)
        media = ''

        # 1) player_data / player_aaaa 等 JSON 变量
        for key in ('player_data', 'player_aaaa', 'playerData', 'playerdata'):
            raw = self._extract_json(html, key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                # JSON 里可能有转义斜杠，尝试修复
                try:
                    data = json.loads(raw.replace('\\/', '/'))
                except Exception:
                    data = None
            if isinstance(data, dict):
                for k in ('url', 'src', 'video', 'playUrl', 'vurl'):
                    v = data.get(k)
                    if isinstance(v, str) and v.strip():
                        media = v.strip()
                        break
            if media:
                break

        # 2) 直接正则抓 m3u8 / mp4
        if not media:
            m = re.search(
                r'https?:\\?/\\?/[^"\'<>\s\\]+?\.(?:m3u8|mp4)(?:\?[^"\'<>\s\\]*)?',
                html, re.I)
            if m:
                media = m.group(0)

        # 3) 相对协议链接
        if not media:
            m = re.search(r'["\'](//[^"\']+?\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', html, re.I)
            if m:
                media = m.group(1)

        headers = {'User-Agent': self.UA, 'Referer': url}

        if media:
            media = media.replace('\\/', '/').replace('\\u002F', '/').strip()
            if media.startswith('//'):
                media = 'https:' + media
            return {
                'parse': 0,
                'jx': 0,
                'playUrl': '',
                'url': media,
                'header': headers,
            }

        # 未解析出直链 → 交给壳端嗅探
        return {
            'parse': 1,
            'jx': 1,
            'playUrl': '',
            'url': url,
            'header': headers,
        }
