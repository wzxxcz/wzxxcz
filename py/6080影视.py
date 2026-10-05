# -*- coding: utf-8 -*-
import sys, re, time, json
from html import unescape
from urllib.parse import urljoin, quote, urlsplit, urlunsplit
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = requests.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = 'https://www.6080video.tv'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

CATEGORIES = {
    '19': '电影', '20': '电视剧', '23': '短剧', '22': '动漫', '21': '综艺',
    '24': '动作片', '25': '喜剧片', '26': '爱情片', '27': '科幻片', '28': '恐怖片',
    '29': '剧情片', '30': '战争片', '31': '纪录片',
    '38': '国产剧', '39': '港台剧', '40': '美剧', '41': '日韩剧', '42': '海外剧',
    '43': '泰剧', '44': 'Netflix自制剧',
    '45': '国产动漫', '46': '日韩动漫', '47': '港台动漫', '48': '欧美动漫', '50': '有声动漫',
    '1': '国产综艺', '2': '港台综艺', '3': '日韩综艺', '4': '欧美综艺',
    '51': '女频恋爱', '52': '反转爽剧', '54': '年代穿越', '55': '古装仙侠',
    '56': '现代都市', '57': '擦边短剧',
}

# ============================================================
# 筛选器（海螺模板路径段: /showcase/013-{tid}-{area}-{year}-{by}-{letter}--{pg}.html）
# 注意：参数名与顺序需抓包验证，若失效请改 _build_cate_url
# ============================================================

def _mk(k, n, pairs):
    return {'key': k, 'name': n, 'value': [{'n': a, 'v': b} for a, b in pairs]}

_AREA_OPTS = [('全部', ''), ('大陆', '大陆'), ('香港', '香港'), ('台湾', '台湾'),
              ('美国', '美国'), ('韩国', '韩国'), ('日本', '日本'), ('泰国', '泰国'),
              ('英国', '英国'), ('法国', '法国'), ('德国', '德国'), ('印度', '印度'),
              ('其它', '其它')]
_YEAR_OPTS = [('全部', '')] + [(str(y), str(y)) for y in range(2026, 2004, -1)]
_BY_OPTS = [('最新', 'time'), ('最热', 'hit'), ('评分', 'score')]
_LETTER_OPTS = [('全部', '')] + [(c, c) for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] + [('0-9', '0-9')]

_FILTERS = {tid: [
    _mk('area', '地区', _AREA_OPTS),
    _mk('year', '年份', _YEAR_OPTS),
    _mk('by', '排序', _BY_OPTS),
    _mk('letter', '字母', _LETTER_OPTS),
] for tid in CATEGORIES}


# ============================================================
# 正则
# ============================================================

# 列表卡片：前瞻式匹配 anchor，属性顺序无关
_RE_ITEM_BLOCK = re.compile(
    r'<li\b[^>]*class="[^"]*fed-list-item[^"]*"[^>]*>([\s\S]*?)</li>',
    re.I
)
_RE_ITEM_ANCHOR = re.compile(
    r'<a\b'
    r'(?=[^>]*class="[^"]*fed-list-pics[^"]*")'
    r'(?=[^>]*href="(/titlebox/(013-[A-Za-z0-9]+)\.html)")'
    r'(?=[^>]*(?:data-original|data-src|src)="(https?://[^"]+)")'
    r'[^>]*>',
    re.I
)
_RE_TITLE = re.compile(r'class="[^"]*fed-list-title[^"]*"[^>]*>\s*([^<]{1,80}?)\s*</a>')
_RE_REMARK = re.compile(r'class="[^"]*fed-list-remarks[^"]*"[^>]*>([^<]*)')

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>')
_RE_META_DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
_RE_OG_DESC = re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.I)
_RE_IFRAME = re.compile(r'<iframe[^>]*\bsrc=["\']([^"\']+)["\']', re.I)
_RE_M3U8_BARE = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.I)

# 分页
_RE_PAGECOUNT_1 = re.compile(r'共\s*(\d+)\s*页')
_RE_PAGECOUNT_2 = re.compile(r'(\d+)\s*/\s*(\d+)\s*页')
_RE_PAGE_LINKS = re.compile(r'/showcase/013-\d+(?:-[^"\s]*?-)?(\d+)\.html')


# ============================================================
# Spider
# ============================================================

class Spider(Spider):

    def init(self, extend=''):
        self.base = HOST.rstrip('/')
        self.ua = UA
        self.types = dict(CATEGORIES)
        self._c = {}
        try:
            r = self._fetch(self.base, headers={'User-Agent': self.ua}, t=8)
            if hasattr(r, 'url') and r.url and r.url != self.base:
                self.base = r.url.rstrip('/')
            h = r.text if hasattr(r, 'text') else r
            if isinstance(h, bytes):
                h = h.decode('utf-8', 'ignore')
            if h:
                self._c[self.base] = [time.time(), h]
        except Exception:
            pass

    # -------- 网络 --------
    def _fetch(self, url, headers=None, t=15):
        hd = headers or {'User-Agent': self.ua, 'Referer': self.base}
        try:
            return self.fetch(url, headers=hd, timeout=t)
        except TypeError:
            return self.fetch(url, headers=hd)

    def _get(self, url, ttl=0, t=15):
        k = url
        if ttl and k in self._c and time.time() - self._c[k][0] < ttl:
            return self._c[k][1]
        try:
            r = self._fetch(url, t=t)
            h = r.text if hasattr(r, 'text') else r
            if isinstance(h, bytes):
                h = h.decode('utf-8', 'ignore')
            if h:
                self._c[k] = [time.time(), h]
            return h
        except Exception:
            return ''

    def _enc(self, u):
        """只对含中文的 URL 做 path 编码，保留 query"""
        if not u or not re.search(r'[^\x00-\x7f]', u):
            return u
        try:
            p = urlsplit(u)
            return urlunsplit((p.scheme, p.netloc,
                               quote(p.path, safe='/%:@'), p.query, p.fragment))
        except Exception:
            return u

    # -------- 卡片解析 --------
    def _items(self, h):
        out, seen = [], set()
        if not h:
            return out
        for blk in _RE_ITEM_BLOCK.finditer(h):
            b = blk.group(1)
            vm = _RE_ITEM_ANCHOR.search(b)
            if not vm:
                continue
            vid = vm.group(2)
            if vid in seen:
                continue
            pic = vm.group(3)
            nm = _RE_TITLE.search(b)
            name = unescape(nm.group(1)).strip() if nm else ''
            if not name or len(name) > 80:
                continue
            rm = _RE_REMARK.search(b)
            remark = unescape(rm.group(1)).strip()[:20] if rm else ''
            seen.add(vid)
            out.append({
                'vod_id': vid,
                'vod_name': name[:50],
                'vod_pic': pic,
                'vod_remarks': remark,
            })
        return out

    # ============================================================
    # 首页
    # ============================================================
    def homeContent(self, filter=False):
        return {
            'class': [{'type_id': k, 'type_name': v} for k, v in self.types.items()],
            'filters': _FILTERS,
            'list': self.homeVideoContent().get('list', []),
        }

    def homeVideoContent(self):
        h = self._get(self.base, ttl=120)
        items = self._items(h)
        if len(items) < 10:
            h2 = self._get(self.base + '/showcase/013-19.html', ttl=300)
            items = self._items(h2)
        if len(items) < 10:
            # 再降一级：热门分类
            for t in ('20', '22', '21'):
                h3 = self._get(f'{self.base}/showcase/013-{t}.html', ttl=300)
                items = self._items(h3)
                if len(items) >= 10:
                    break
        return {'list': items[:60]}

    # ============================================================
    # 分类（带分页 + 筛选）
    # ============================================================
    def _build_cate_url(self, tid, pg, ext):
        """
        构造分类 URL。
        海螺模板常见格式（需抓包验证）:
          无筛选: /showcase/013-{tid}.html          （第 1 页）
                  /showcase/013-{tid}-{pg}.html     （第 N 页）
          带筛选: /showcase/013-{tid}-{area}-{year}-{by}-{letter}--{pg}.html
        如抓包后发现不同，改这里即可。
        """
        area = (ext.get('area') or '').strip()
        year = (ext.get('year') or '').strip()
        by = (ext.get('by') or '').strip()
        letter = (ext.get('letter') or '').strip()

        if not (area or year or by or letter):
            if pg <= 1:
                return f'{self.base}/showcase/013-{tid}.html'
            return f'{self.base}/showcase/013-{tid}-{pg}.html'

        area_e = quote(area, safe='') if area else ''
        by_e = quote(by, safe='') if by else ''
        letter_e = quote(letter, safe='') if letter else ''
        pg_s = str(pg) if pg > 1 else ''
        return (f'{self.base}/showcase/013-{tid}-{area_e}-{year}-'
                f'{by_e}-{letter_e}--{pg_s}.html')

    def _parse_pagecount(self, h, current_pg):
        if not h:
            return max(current_pg, 1)
        m = _RE_PAGECOUNT_1.search(h)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = _RE_PAGECOUNT_2.search(h)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        pages = _RE_PAGE_LINKS.findall(h)
        if pages:
            try:
                mx = max(int(x) for x in pages if x.isdigit())
                return max(mx, current_pg)
            except Exception:
                pass
        # 找不到 → 允许继续翻，翻到空数据自然停
        return 999

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        t = str(tid).split('|')[0]
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1

        ext = {}
        if extend:
            if isinstance(extend, dict):
                ext = extend
            elif isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}

        url = self._build_cate_url(t, pg, ext)
        h = self._get(url, ttl=300)
        if not h:
            # 筛选 URL 拼错时，回退到无筛选分页 URL
            if any(ext.get(k) for k in ('area', 'year', 'by', 'letter')):
                url2 = (f'{self.base}/showcase/013-{t}.html' if pg <= 1
                        else f'{self.base}/showcase/013-{t}-{pg}.html')
                h = self._get(url2, ttl=300)
                if not h:
                    return {'page': pg, 'pagecount': 1, 'limit': 180,
                            'total': 0, 'list': []}
                pc = self._parse_pagecount(h, pg)
                items = self._items(h)
                return {'page': pg, 'pagecount': pc, 'limit': 180,
                        'total': pc * 180, 'list': items}
            return {'page': pg, 'pagecount': 1, 'limit': 180, 'total': 0, 'list': []}

        items = self._items(h)
        pc = self._parse_pagecount(h, pg)
        return {'page': pg, 'pagecount': pc, 'limit': 180,
                'total': pc * 180, 'list': items}

    # ============================================================
    # 详情（重点：简介 / 主演 / 导演）
    # ============================================================
    def _balanced_scan(self, h, start, max_len=10000):
        """
        从 start 位置开始，扫到第一个平衡闭合标签为止。
        用于提取 div 嵌套的简介。
        """
        end = min(len(h), start + max_len)
        depth = 0
        i = start
        stop_tags = {'div', 'li', 'p', 'dd', 'dl', 'section', 'article'}
        while i < end:
            lt = h.find('<', i)
            if lt < 0:
                return h[start:end]
            gt = h.find('>', lt)
            if gt < 0:
                return h[start:end]
            tag = h[lt + 1:gt].strip()
            if tag.startswith('/'):
                name = tag[1:].split()[0].lower() if tag[1:] else ''
                if depth == 0 and name in stop_tags:
                    return h[start:lt]
                depth -= 1
            elif not tag.startswith('!') and not tag.endswith('/'):
                name = tag.split()[0].lower()
                if name in stop_tags:
                    depth += 1
            i = gt + 1
        return h[start:end]

    def _clean_content(self, raw):
        """简介清洗：保留换行、去标签、去尾部站点推荐"""
        if not raw:
            return ''
        raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
        raw = re.sub(r'</p>', '\n', raw, flags=re.I)
        txt = re.sub(r'<[^>]+>', '', raw)
        txt = unescape(txt)
        # 去尾部站点推广
        txt = re.sub(r'更多精彩[^\n。！]*[。！]?', '', txt)
        txt = re.sub(r'本站[^\n。！]*[。！]?', '', txt)
        txt = re.sub(r'免费在线观看[^\n。！]*[。！]?', '', txt)
        txt = re.sub(r'【[^】]{0,40}】', '', txt)
        # 空白归一
        txt = re.sub(r'[ \t\u3000]+', ' ', txt)
        txt = re.sub(r'\n\s*\n+', '\n', txt)
        return txt.strip()[:500]

    def _extract_content(self, h):
        """
        简介多层回退（重点修复）：
          1. 简介/剧情/剧情介绍/内容简介 标签 + 平衡扫描
          2. meta description / og:description
        """
        # --- 1. 标签法 ---
        for lab in ('简介', '剧情', '剧情介绍', '内容简介', '简 介'):
            m = re.search(
                r'<span[^>]*class="[^"]*fed-text-muted[^"]*"[^>]*>\s*'
                + lab + r'[:：]?\s*</span>',
                h
            )
            if not m:
                # 宽松一点：可能是 <b>简介：</b> 或直接文本
                m = re.search(lab + r'[:：]\s*</(?:span|b|strong|em)>', h)
                if not m:
                    continue
            raw = self._balanced_scan(h, m.end())
            txt = self._clean_content(raw)
            if len(txt) > 15:
                return txt

        # --- 2. meta 回退 ---
        for pat in (_RE_META_DESC, _RE_OG_DESC):
            m = pat.search(h)
            if m:
                txt = self._clean_content(m.group(1))
                if len(txt) > 15:
                    return txt

        return ''

    def _clean_persons(self, raw):
        """清洗人物列表：优先取 <a> 链接文本，否则去标签"""
        if not raw:
            return ''
        links = re.findall(r'<a[^>]*>([^<]+)</a>', raw)
        if links:
            names = [unescape(x).strip() for x in links if unescape(x).strip()]
            return ', '.join(names[:20])
        txt = re.sub(r'<[^>]+>', ' ', raw)
        txt = unescape(txt)
        txt = re.sub(r'\s+', ' ', txt).strip().strip('，,。;；')
        return txt[:300]

    def _extract_persons(self, h, labels):
        """多标签回退提取人物列表"""
        for lab in labels:
            # 精确：fed-text-muted 标签
            m = re.search(
                r'<span[^>]*class="[^"]*fed-text-muted[^"]*"[^>]*>\s*'
                + lab + r'[:：]?\s*</span>([\s\S]*?)</(?:p|li|div)>',
                h
            )
            if m:
                txt = self._clean_persons(m.group(1))
                if txt:
                    return txt
            # 宽松：任意标签后跟冒号
            m = re.search(lab + r'[:：]\s*(?:</[^>]+>\s*)*([\s\S]*?)</(?:p|li|div)>', h)
            if m:
                txt = self._clean_persons(m.group(1))
                if txt:
                    return txt
        return ''

    def detailContent(self, ids, quick='1'):
        vid_raw = str(ids[0] if isinstance(ids, list) else ids or '')
        m = re.search(r'(013-[A-Za-z0-9]+)', vid_raw)
        vid = m.group(1) if m else ''
        if not vid:
            return {'list': []}

        h = self._get(self.base + f'/titlebox/{vid}.html', ttl=300, t=25)
        if not h:
            return {'list': []}

        d = {
            'vod_id': vid, 'vod_name': '', 'vod_pic': '',
            'vod_year': '', 'vod_area': '', 'vod_director': '',
            'vod_actor': '', 'vod_content': '', 'vod_remarks': '',
            'vod_play_from': '', 'vod_play_url': '',
        }

        # 标题
        m = _RE_H1.search(h)
        if m:
            d['vod_name'] = unescape(
                re.sub(r'<[^>]+>', '', m.group(1))).strip()

        # 封面
        m = re.search(r'data-original="(https?://[^"]+)"', h)
        if not m:
            m = re.search(r'data-src="(https?://[^"]+)"', h)
        if m:
            d['vod_pic'] = m.group(1)

        # 备注
        m = _RE_REMARK.search(h)
        if m:
            d['vod_remarks'] = unescape(m.group(1)).strip()[:20]

        # 年份 / 地区
        for k, lab in (('vod_year', '年份'), ('vod_area', '地区')):
            m = re.search(
                r'<span[^>]*class="[^"]*fed-text-muted[^"]*"[^>]*>\s*'
                + lab + r'[:：]?\s*</span>([\s\S]*?)</li>',
                h
            )
            if not m:
                m = re.search(lab + r'[:：]\s*([^<\n]{1,40})', h)
            if m:
                v = re.sub(r'\s+', ' ', unescape(
                    re.sub(r'<[^>]+>', ' ', m.group(1)))).strip().strip('，,').strip()
                d[k] = v[:100]

        # 主演 / 导演（多标签回退）
        d['vod_actor'] = self._extract_persons(h, ('主演', '演员', '领衔主演'))
        d['vod_director'] = self._extract_persons(h, ('导演', '执导'))

        # ---- 简介（重点）----
        content = self._extract_content(h)
        if content:
            d['vod_content'] = content

        # 播放列表
        pf, pu = self._lines(vid, h)
        if pf:
            d['vod_play_from'] = '$$$'.join(pf)
            d['vod_play_url'] = '$$$'.join(pu)

        return {'list': [d]}

    def _lines(self, vid, h):
        """解析线路 + 集数"""
        btns = [unescape(n).strip() for n in re.findall(
            r'<li class="fed-drop-btns[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', h)]
        skip = set(btns) | {'立即播放', ''}
        hmap = {}
        for href, sid, nid, ename in re.findall(
                r'href="(/playzone/(?:' + re.escape(vid) +
                r')-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>', h):
            e = unescape(ename).strip()
            if not e or e in skip:
                continue
            e = e.replace('#', '-').replace('$', '|')
            if href not in hmap:
                hmap[href] = (int(sid), int(nid), e)
            elif '第' in e:
                hmap[href] = (int(sid), int(nid), e)
        g = {}
        for href, (sid, nid, e) in hmap.items():
            g.setdefault(sid, [])
            g[sid].append((nid, e, href))
        pf, pu = [], []
        for sid in sorted(g):
            ns = sorted(g[sid], key=lambda x: x[0])
            nm = btns[sid - 1] if sid - 1 < len(btns) and btns[sid - 1] else f'线路{sid}'
            pf.append(nm)
            pu.append('#'.join(
                f'{e}${urljoin(self.base, href)}' for _, e, href in ns))
        return pf, pu

    # ============================================================
    # 搜索（用站内接口）
    # ============================================================
    def searchContent(self, key, quick=False, pg='1'):
        k = str(key).strip()
        if not k:
            return {'list': [], 'page': 1}
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        encoded = quote(k)
        items = []

        # 1) 主搜索：海螺模板 /vodsearch/{wd}----------{pg}---.html
        if page <= 1:
            url1 = f'{self.base}/vodsearch/{encoded}----------.html'
        else:
            url1 = f'{self.base}/vodsearch/{encoded}----------{page}---.html'
        h = self._get(url1, ttl=120)
        items = self._items(h) if h else []

        # 2) 回退：search.php
        if not items:
            h = self._get(f'{self.base}/search.php?searchword={encoded}', ttl=120)
            items = self._items(h) if h else []

        # 3) 回退：ajax suggest（仅名字，无图）
        if not items:
            h = self._get(
                f'{self.base}/index.php/ajax/suggest?mid=1&wd={encoded}&limit=20',
                ttl=120)
            if h:
                try:
                    data = json.loads(h).get('list') or []
                    for it in data:
                        items.append({
                            'vod_id': str(it.get('id', '')),
                            'vod_name': it.get('name', ''),
                            'vod_pic': it.get('pic', ''),
                            'vod_remarks': '',
                        })
                except Exception:
                    pass

        return {'list': items[:50], 'page': page}

    # ============================================================
    # 播放解析（多路径回退）
    # ============================================================
    def playerContent(self, flag, id, vipFlags=None):
        u = str(id) if id else str(flag)

        # 直链
        if '://' in u and re.search(r'\.(m3u8|mp4|flv)(\?|$)', u, re.I):
            return {'parse': 0, 'url': self._enc(u)}

        full = u if u.startswith('http') else urljoin(self.base, u)
        h = self._get(full, ttl=60, t=25)
        if not h:
            return {'parse': 0, 'url': ''}

        # 1) player_aaaa / player_data JSON 对象
        for var in ('player_aaaa', 'player_data', 'playerinfo', 'video_info',
                    'MacPlayer'):
            m = re.search(var + r'\s*=\s*(\{[\s\S]*?\})\s*[;\n]', h)
            if not m:
                continue
            try:
                obj = json.loads(m.group(1))
            except Exception:
                continue
            for k in ('url', 'link', 'videoUrl', 'video_url', 'playUrl'):
                v = obj.get(k)
                if v and '://' in v:
                    return {'parse': 0, 'url': self._enc(v)}

        # 2) 内联 JSON: "url":"..."
        m = re.search(r'"url"\s*:\s*"((?:[^"\\]|\\.)*)"', h)
        if m:
            try:
                v = json.loads('"' + m.group(1) + '"')
                if v and '://' in v:
                    return {'parse': 0, 'url': self._enc(v)}
            except Exception:
                pass

        # 3) var now / var url / file / source
        for pat in (
            r'var\s+now\s*=\s*"([^"]+)"',
            r'var\s+url\s*=\s*"([^"]+)"',
            r'file\s*:\s*"([^"]+)"',
            r'source\s*:\s*"([^"]+)"',
            r'video_url\s*=\s*"([^"]+)"',
        ):
            m = re.search(pat, h, re.I)
            if m and '://' in m.group(1):
                v = m.group(1).replace('\\/', '/')
                if v.startswith('//'):
                    v = 'https:' + v
                return {'parse': 0, 'url': self._enc(v)}

        # 4) 裸 m3u8
        m = _RE_M3U8_BARE.search(h)
        if m:
            return {'parse': 0, 'url': self._enc(m.group(1))}

        # 5) iframe 回退（最多 1 层）
        m = _RE_IFRAME.search(h)
        if m:
            iframe_url = m.group(1)
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            elif not iframe_url.startswith('http'):
                iframe_url = urljoin(full, iframe_url)
            if iframe_url != full:
                nested = self._get(iframe_url, ttl=60, t=15)
                m2 = _RE_M3U8_BARE.search(nested or '')
                if m2:
                    return {'parse': 0, 'url': self._enc(m2.group(1))}

        return {'parse': 0, 'url': ''}
