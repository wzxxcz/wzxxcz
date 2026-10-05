# coding: utf-8
"""Gimy TV 劇迷 drpy source.

Cloudflare 处理（在 extend 中配置）：
  1. FlareSolverr：extend = 'http://127.0.0.1:8191'
  2. Cookie 注入：extend = 'https://gimyai.tw||cookie=cf_clearance=xxx;__cf_bm=yyy'
  3. 双保险：extend = 'flaresolverr=http://127.0.0.1:8191||cookie=cf_clearance=xxx'
"""
import re
import json
import time
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    host = 'https://gimyai.tw'
    UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    CATEGORIES = [
        {'type_id': '2',  'type_name': '電視劇'},
        {'type_id': '1',  'type_name': '電影'},
        {'type_id': '4',  'type_name': '動漫'},
        {'type_id': '29', 'type_name': '綜藝'},
        {'type_id': '13', 'type_name': '陸劇'},
        {'type_id': '20', 'type_name': '韓劇'},
        {'type_id': '16', 'type_name': '美劇'},
        {'type_id': '15', 'type_name': '日劇'},
        {'type_id': '14', 'type_name': '台劇'},
        {'type_id': '21', 'type_name': '港劇'},
        {'type_id': '34', 'type_name': '短劇'},
        {'type_id': '38', 'type_name': 'AI漫劇'},
        {'type_id': '31', 'type_name': '海外劇'},
        {'type_id': '22', 'type_name': '紀錄片'},
    ]

    # ==================== 初始化 ====================
    def init(self, extend=''):
        ext = (extend or '').strip()
        self.cookie = ''
        self.flaresolverr = ''
        self.host = 'https://gimyai.tw'

        if '||' in ext:
            left, right = ext.split('||', 1)
            left, right = left.strip(), right.strip()
        else:
            left, right = ext, ''

        if left.startswith('flaresolverr='):
            self.flaresolverr = left.split('=', 1)[1].strip().rstrip('/')
        elif left.startswith('http'):
            if ':8191' in left or 'flaresolverr' in left.lower():
                self.flaresolverr = left.rstrip('/')
            else:
                self.host = left.rstrip('/')

        if right.startswith('cookie='):
            self.cookie = right[7:].strip()
        elif right:
            self.cookie = right

        if not self.flaresolverr and not self.cookie:
            self._warmup()

    def _warmup(self):
        try:
            resp = self.fetch(self.host + '/', headers=self._headers(self.host))
            ck = ''
            h = getattr(resp, 'headers', None)
            if h:
                try:
                    ck = h.get('set-cookie') or h.get('Set-Cookie') or ''
                except Exception:
                    ck = ''
            if not ck:
                try:
                    ck = self.getCookie(self.host)
                except Exception:
                    ck = ''
            if ck:
                self.cookie = self._merge_cookie(self.cookie, ck)
        except Exception:
            pass

    @staticmethod
    def _merge_cookie(old, new):
        jar = {}
        for part in (old or '').split(';') + (new or '').split(';'):
            part = part.strip()
            if not part or '=' not in part:
                continue
            k, v = part.split('=', 1)
            jar[k.strip()] = v.strip()
        return '; '.join('%s=%s' % (k, v) for k, v in jar.items())

    # ==================== 基础工具 ====================
    def _text(self, resp):
        if resp is None:
            return ''
        if hasattr(resp, 'text'):
            return resp.text or ''
        if isinstance(resp, bytes):
            return resp.decode('utf-8', 'ignore')
        return str(resp)

    def _headers(self, referer=''):
        h = {
            'User-Agent': self.UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8',
            'Cache-Control': 'no-cache',
        }
        if referer:
            h['Referer'] = referer
        if self.cookie:
            h['Cookie'] = self.cookie
        return h

    def _is_challenge(self, html):
        """判断是不是 Cloudflare 挑战页"""
        if not html:
            return True
        if len(html) > 6000:
            return False
        keys = ('Just a moment', 'cf-challenge', 'cf_chl_opt',
                'Checking your browser', '正在进行安全验证', '進行安全驗證',
                'DDoS protection', 'challenge-platform', '__cf_chl',
                'Enable JavaScript and cookies', 'needs to review the security')
        low = html.lower()
        return any(k.lower() in low for k in keys)

    def _fs_get(self, url):
        """走 FlareSolverr"""
        try:
            body = json.dumps({
                'cmd': 'request.get',
                'url': url,
                'maxTimeout': 90000,
            })
            headers = {'Content-Type': 'application/json'}
            resp = None
            try:
                resp = self.fetch(self.flaresolverr + '/v1',
                                  headers=headers,
                                  data=body.encode('utf-8'),
                                  method='POST')
            except TypeError:
                try:
                    resp = self.post(self.flaresolverr + '/v1',
                                     data=body, headers=headers)
                except Exception:
                    resp = None
            text = self._text(resp)
            data = json.loads(text)
            if data.get('status') == 'ok':
                sol = data.get('solution') or {}
                return sol.get('response') or ''
        except Exception:
            pass
        return ''

    def _get(self, url, referer=None, retry=2):
        """统一请求入口"""
        if self.flaresolverr:
            html = self._fs_get(url)
            if html and not self._is_challenge(html):
                return html
            if not self.cookie:
                return html or ''

        last = ''
        for i in range(retry + 1):
            try:
                resp = self.fetch(url, headers=self._headers(referer or self.host))
                try:
                    ck = self.getCookie(self.host)
                    if ck:
                        self.cookie = self._merge_cookie(self.cookie, ck)
                except Exception:
                    pass
                text = self._text(resp)
                last = text
                if text and not self._is_challenge(text):
                    return text
            except Exception:
                pass
            time.sleep(0.5 * (i + 1))
        return last

    # ==================== 诊断辅助 ====================
    def _err_item(self, url, html, hint=''):
        """生成一个能在 TVBox 界面上直接看到的错误条目"""
        size = len(html or '')
        title = ''
        if html:
            m = re.search(r'<title>([^<]{1,80})</title>', html, re.I)
            if m:
                title = m.group(1).strip()
        if not title and html:
            title = html.strip()[:60].replace('\n', ' ')
        msg = 'CF盾拦/%dB' % size
        if hint:
            msg += ' | ' + hint[:30]
        return {
            'vod_id': '_diag_',
            'vod_name': '⚠ 被 Cloudflare 拦截',
            'vod_pic': '',
            'vod_remarks': msg,
            'vod_actor': 'URL: %s' % url,
            'vod_content': title,
        }

    def _empty_with_diag(self, url, html, pg=1, hint=''):
        """空列表时带上诊断条目"""
        if self._is_challenge(html):
            return {
                'list': [self._err_item(url, html, hint)],
                'page': pg, 'pagecount': 1, 'limit': 1, 'total': 1,
            }
        # 真拿到了页面但解析 0 条 —— 说明是解析问题
        size = len(html or '')
        return {
            'list': [{
                'vod_id': '_diag_',
                'vod_name': '⚠ 页面解析出 0 条',
                'vod_pic': '',
                'vod_remarks': '%dB 已拿到' % size,
                'vod_actor': 'URL: %s' % url,
                'vod_content': '页面拿到了但卡片正则没匹配到，需要看 HTML 结构',
            }],
            'page': pg, 'pagecount': 1, 'limit': 1, 'total': 1,
        }

    @staticmethod
    def _clean(s):
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
                r'<img[^>]+alt=["\']([^"\']+)["\']',
                r'class=["\'][^"\']*poster__title[^"\']*["\'][^>]*>([\s\S]*?)</',
                r'<h[23][^>]*>([\s\S]*?)</h[23]>',
            ])

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
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in self.CATEGORIES]
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
        flt = {c['type_id']: filters for c in self.CATEGORIES}
        return {'class': classes, 'filters': flt, 'list': []}

    def homeVideoContent(self, filter=None):
        url = self.host + '/'
        html = self._get(url, referer=self.host)
        items = self._cards(html)
        if not items:
            url = self.host + '/genre/2.html'
            html = self._get(url, referer=self.host)
            items = self._cards(html)
        if not items:
            return self._empty_with_diag(url, html, 1, '首页')
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

        if not (area or year or sort) and pg <= 1:
            url = '%s/genre/%s.html' % (self.host, tid)
        else:
            parts = [''] * 12
            parts[0] = str(tid)
            if area:
                parts[1] = quote(area)
            if sort:
                parts[2] = sort
            if pg > 1:
                parts[8] = str(pg)
            if year:
                parts[11] = year
            url = '%s/explore/%s.html' % (self.host, '-'.join(parts))

        html = self._get(url, referer=self.host)
        items = self._cards(html)

        if not items and pg == 1 and not (area or year or sort):
            alt = '%s/genre/%s.html' % (self.host, tid)
            if alt != url:
                html = self._get(alt, referer=self.host)
                items = self._cards(html)
                url = alt

        if not items:
            return self._empty_with_diag(url, html, pg, '分类 tid=%s' % tid)

        pagecount = pg
        if html:
            for m in re.finditer(r'href="[^"]*?(\d+)---\.html"', html):
                try:
                    n = int(m.group(1))
                    if 1 <= n <= 5000 and n > pagecount:
                        pagecount = n
                except Exception:
                    pass

        return {
            'list': items,
            'page': pg,
            'pagecount': pagecount,
            'limit': len(items),
            'total': len(items) * pagecount,
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
        if not items and pg == 1:
            return self._empty_with_diag(url, html, pg, '搜索')
        return {
            'list': items,
            'page': pg,
            'pagecount': pg if items else max(1, pg - 1),
            'limit': len(items),
            'total': len(items) * pg if items else 0,
        }

    # ==================== 详情 ====================
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid)
        url = vid if vid.startswith('http') else self._abs('/detail/%s.html' % vid)
        html = self._get(url, referer=self.host)

        if self._is_challenge(html):
            return {'list': [self._err_item(url, html, 'detail')]}

        title = self._pick(html, [
            r'<h1[^>]*class=["\'][^"\']*detail__title[^"\']*["\'][^>]*>([\s\S]*?)</h1>',
            r'class=["\'][^"\']*detail__title[^"\']*["\'][^>]*>([\s\S]*?)</',
            r'<h1[^>]*>([\s\S]*?)</h1>',
        ])

        pic = ''
        pm = re.search(
            r'class=["\'][^"\']*detail__poster[^"\']*["\'][\s\S]{0,800}?'
            r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)', html, re.I)
        if not pm:
            pm = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if pm:
            pic = self._abs(pm.group(1))

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

        content = self._pick(html, [
            r'<div[^>]+class=["\'][^"\']*\bdetail__content\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__desc\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__intro\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\bdetail__summary\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<div[^>]+class=["\'][^"\']*\b(?:plot|summary|synopsis|intro|description|desc|content|txt)\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            r'<p[^>]+class=["\'][^"\']*\b(?:plot|summary|synopsis|intro|description|desc|content)\b[^"\']*["\'][^>]*>([\s\S]*?)</p>',
            r'(?:劇情簡介|剧情简介|簡\s*介|简\s*介|故事簡介)[：:]?\s*</[^>]+>\s*([\s\S]*?)</(?:div|p|section|article)>',
            r'(?:劇情簡介|剧情简介|簡\s*介|简\s*介|故事簡介)[：:]\s*([\s\S]*?)</(?:div|p|section|article)>',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
        ])
        if not content:
            dm = re.search(
                r'<div[^>]+class=["\'][^"\']*\bdetail\b[^"\']*["\'][^>]*>([\s\S]*?)</div>\s*</div>',
                html, re.S | re.I)
            if dm:
                content = self._clean(dm.group(1))

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
            'vod_content': content,
            'vod_play_from': '$$$'.join(routes.keys()),
            'vod_play_url': '$$$'.join(routes.values()),
        }
        return {'list': [vod]}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith('http') else self._abs(str(id))
        html = self._get(url, referer=self.host)
        media = ''

        for key in ('player_data', 'player_aaaa', 'playerData', 'playerdata'):
            raw = self._extract_json(html, key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
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

        if not media:
            m = re.search(
                r'https?:\\?/\\?/[^"\'<>\s\\]+?\.(?:m3u8|mp4)(?:\?[^"\'<>\s\\]*)?',
                html, re.I)
            if m:
                media = m.group(0)

        if not media:
            m = re.search(r'["\'](//[^"\']+?\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', html, re.I)
            if m:
                media = m.group(1)

        headers = {'User-Agent': self.UA, 'Referer': url}
        if self.cookie:
            headers['Cookie'] = self.cookie

        if media:
            media = media.replace('\\/', '/').replace('\\u002F', '/').strip()
            if media.startswith('//'):
                media = 'https:' + media
            return {
                'parse': 0, 'jx': 0, 'playUrl': '',
                'url': media, 'header': headers,
            }

        return {
            'parse': 1, 'jx': 1, 'playUrl': '',
            'url': url, 'header': headers,
        }
