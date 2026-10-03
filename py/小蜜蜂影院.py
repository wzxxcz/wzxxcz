# -*- coding: utf-8 -*-
"""
小蜜蜂影院 TVBox Spider
站点: https://www.xmfyy.com/ (小蜜蜂影院 · 服务端直渲染 · 无反爬)
一级分类: 电视剧(1) / 电影(2) / 动漫(3) / 综艺(4) / 短剧(5)
二级分类(filters): 类型 type / 地区 area / 年份 year / 排序 sort
  列表页 /filter?channel={ch}&type={type}&area={area}&year={year}&sort={sort}&page={pg}
详情页 /detail/{vid}.html: 线路 tab(source-0..n) 与选集 /vodplay/{vid}-{from}-{n}.html 一一对应
播放: GET /api/play-url?vodId={vid}&playFrom={from}&index={n} -> {"code":200,"mode":"native","url":"*.m3u8"}
搜索: /search?keyword={key}&sort=hits&page={pg}
契约: class Spider 无继承 · 14 壳方法全实现 · 位置参数契约 · $/#/$$$ 分隔
      playerContent.header 为 dict · Python 层不调用 setCache/getCache
修订: 2026-10-03 · 修复重复/串位 · 彻底去掉标题中的“封面图片”等后缀
"""
import re
import json
import gzip
import urllib.request
import urllib.parse
import urllib.error
import html as _html


class Spider:
    def __init__(self):
        self.host = 'https://www.xmfyy.com'
        self.ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        self.headers = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
        }
        self.classes = [
            ('电视剧', '1'), ('电影', '2'), ('动漫', '3'),
            ('综艺', '4'), ('短剧', '5'),
        ]
        self.type_map = {
            '1': [('7', '剧情'), ('9', '古装'), ('10', '战争'), ('11', '谍战'),
                  ('12', '爱情'), ('13', '罪案'), ('14', '悬疑'), ('15', '家庭'),
                  ('16', '军旅'), ('17', '喜剧'), ('18', '都市'), ('19', '武侠'),
                  ('20', '言情'), ('21', '偶像'), ('22', '青春'), ('23', '农村'),
                  ('24', '穿越'), ('25', '奇幻'), ('26', '历史'), ('27', '年代'),
                  ('28', '科幻'), ('29', '生活'), ('30', '剧情'), ('31', '励志'),
                  ('32', '婚姻'), ('33', '警匪'), ('34', '犯罪'), ('35', '推理'),
                  ('36', '商战'), ('37', '宫廷'), ('38', '仙侠'), ('39', '神话'),
                  ('40', '动作'), ('41', '复仇'), ('42', '惊悚')],
            '2': [('43', '动作'), ('44', '喜剧'), ('45', '爱情'), ('46', '科幻'),
                  ('47', '恐怖'), ('48', '剧情'), ('49', '战争'), ('50', '犯罪'),
                  ('51', '惊悚'), ('52', '冒险'), ('53', '悬疑'), ('54', '动画'),
                  ('55', '武侠'), ('56', '古装'), ('57', '历史'), ('58', '传记'),
                  ('59', '纪录片')],
            '3': [('60', '热血'), ('61', '恋爱'), ('62', '校园'), ('63', '搞笑'),
                  ('64', '机甲'), ('65', '神魔'), ('66', '竞技'), ('67', '冒险'),
                  ('68', '治愈'), ('69', '百合'), ('70', '萝莉'), ('71', '后宫'),
                  ('72', '励志'), ('73', '泡面番'), ('74', '国产动漫'),
                  ('75', '日本动漫'), ('76', '欧美动漫')],
            '4': [('77', '选秀'), ('78', '情感'), ('79', '访谈'), ('80', '播报'),
                  ('81', '旅游'), ('82', '音乐'), ('83', '美食'), ('84', '纪实'),
                  ('85', '曲艺'), ('86', '游戏'), ('87', '亲子'), ('88', '职场'),
                  ('89', '脱口秀'), ('90', '真人秀'), ('91', '晚会')],
            '5': [],
        }
        self.areas = ['大陆', '香港', '台湾', '韩国', '日本', '美国',
                      '泰国', '法国', '英国', '德国', '印度', '其他']
        self.years = ['2026', '2025', '2024', '2023', '2022', '2021',
                      '2020', '2019', '2018']
        self.sorts = [('hot', '热度排序'), ('time', '上映时间'), ('score', '评分排序')]

    # ================= 内部工具 =================
    def _fetch(self, url, referer=None, timeout=20):
        h = dict(self.headers)
        if referer:
            h['Referer'] = referer
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            enc = (resp.headers.get('Content-Encoding') or '').lower()
            if 'gzip' in enc:
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
        for e in ('utf-8', 'gbk', 'gb18030'):
            try:
                return data.decode(e)
            except Exception:
                continue
        return data.decode('utf-8', 'ignore')

    def _clean(self, s):
        if not s:
            return ''
        s = _html.unescape(s)
        s = re.sub(r'<[^>]+>', '', s)
        s = s.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')
        s = re.sub(r'\s+', ' ', s)
        return s.strip()

    def _abs_url(self, u):
        if not u:
            return ''
        u = u.strip()
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        return u

    # 标题后缀/噪声词（出现在任意位置都会被去掉）
    _TITLE_NOISE = re.compile(
        r'封面图片|封面图集|封面图|海报图片|海报图集|海报图|封面照|海报照|封面|海报|图片|poster|image|picture',
        re.I,
    )

    def _strip_title_suffix(self, t):
        """去掉标题里“封面图片/封面图/海报图/图片”等噪声词。
        先做 Unicode 空白归一化，再删除任意位置出现的噪声词，
        最后清理残留的标点、空白与括号。"""
        if not t:
            return ''
        t = _html.unescape(str(t))
        t = t.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')
        t = re.sub(r'\s+', ' ', t).strip()
        # 去掉 “《…封面图片》” 这种括号包裹的噪声
        t = re.sub(r'[\(\[（【]\s*(?:封面图片|封面图|海报图|图片)\s*[\)\]）】]', '', t)
        # 删除任意位置出现的噪声词
        t = self._TITLE_NOISE.sub('', t)
        # 清理两端标点
        t = re.sub(r'^[\s\-—–·、,，。:：;；\(\)\[\]（）【】《》<>"\']+|[\s\-—–·、,，。:：;；\(\)\[\]（）【】《》<>"\']+$', '', t)
        return t.strip()

    def _pick_img(self, chunk):
        for attr in ('data-src', 'data-original', 'data-echo', 'src'):
            pm = re.search(r'<img[^>]+' + attr + r'="([^"]+)"', chunk)
            if pm and pm.group(1) and not pm.group(1).startswith('data:'):
                return self._abs_url(pm.group(1))
        return ''

    # 判定“通用噪声标题”，剥完为空或只剩这些词的，视为无效标题
    _GENERIC_TITLES = {
        '封面图片', '封面图', '封面', '海报图片', '海报图', '海报',
        '图片', 'poster', 'image', 'picture',
    }

    def _parse_cards(self, html):
        """通用卡片解析 (v5):
        - 卡片唯一定位: 含 <img> 的 /detail/{id}.html 海报锚
        - 标题三级回退, 每一级都先做“封面图片”等噪声清洗:
            1) img alt
            2) 全局文本锚映射 title_map
            3) 锚的 title 属性
        - 剥完为空则回退下一级候选; 全空则丢弃该卡片
        - (标题, 封面) 二次去重
        """
        items = []
        seen = set()
        seen_sig = set()

        # 全局文本锚标题映射: 每个 vid 第一次出现的非图片锚文本
        title_map = {}
        for tm in re.finditer(
                r'<a\b[^>]*href="/detail/(\d+)\.html"[^>]*>(.*?)</a>', html, re.S):
            v = tm.group(1)
            inner_txt = tm.group(2)
            if '<img' in inner_txt:
                continue
            t = self._strip_title_suffix(self._clean(inner_txt))
            if not t or t.isdigit() or t.lower() in self._GENERIC_TITLES:
                continue
            if v not in title_map:
                title_map[v] = t

        # 卡片锚: 含 <img> 的 /detail 锚
        poster_anchors = []
        for m in re.finditer(
                r'<a\b[^>]*href="/detail/(\d+)\.html"[^>]*>(.*?)</a>', html, re.S):
            if '<img' in m.group(2):
                poster_anchors.append(m)

        for idx, m in enumerate(poster_anchors):
            vid = m.group(1)
            if vid in seen:
                continue
            inner = m.group(2)
            anchor_full = m.group(0)

            pic = self._pick_img(inner)

            # 标题三级回退: 每级先剥后缀, 空则往下
            title = ''

            # 1) img alt
            am = re.search(r'<img[^>]+alt="([^"]+)"', inner)
            if am:
                cand = self._strip_title_suffix(self._clean(am.group(1)))
                if cand and not cand.isdigit() and cand.lower() not in self._GENERIC_TITLES:
                    title = cand

            # 2) 全局文本锚
            if not title and vid in title_map:
                cand = self._strip_title_suffix(title_map[vid])
                if cand and cand.lower() not in self._GENERIC_TITLES:
                    title = cand

            # 3) 锚的 title 属性
            if not title:
                tm = re.search(r'\btitle="([^"]+)"', anchor_full)
                if tm:
                    cand = self._strip_title_suffix(self._clean(tm.group(1)))
                    if cand and not cand.isdigit() and cand.lower() not in self._GENERIC_TITLES:
                        title = cand

            if not title:
                continue

            # 内容级去重
            sig = (title, pic)
            if sig in seen_sig:
                seen.add(vid)
                continue
            seen_sig.add(sig)

            # 备注: 本海报锚到下一个海报锚之间的区间
            if idx + 1 < len(poster_anchors):
                end = poster_anchors[idx + 1].start()
            else:
                end = min(len(html), m.end() + 800)
            block = html[m.start():end]
            remark = ''
            for rp in (r'class="vod-badge[^"]*"[^>]*>([^<]+)<',
                       r'class="module-item-note[^"]*"[^>]*>([^<]+)<',
                       r'class="module-card-item-note[^"]*"[^>]*>([^<]+)<',
                       r'class="vod-subtitle[^"]*"[^>]*>([^<]+)<',
                       r'class="note[^"]*"[^>]*>([^<]+)<'):
                rm = re.search(rp, block)
                if rm:
                    r = self._clean(rm.group(1))[:30]
                    if r:
                        remark = r
                        break

            seen.add(vid)
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
            })

        return items

    def _parse_pagecount(self, html, pg):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        text = html.replace('&amp;', '&')
        pages = [int(x) for x in re.findall(r'[?&]page=(\d+)', text)]
        pc = max(pages) if pages else pg
        if pc < pg:
            pc = pg
        return str(pg), str(pc)

    def _extract_content(self, html):
        patterns = (
            r'<div[^>]*class="[^"]*synopsis-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*vod-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*vod-detail-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*introduction[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*synopsis[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</p>',
            r'<section[^>]*class="[^"]*synopsis[^"]*"[^>]*>(.*?)</section>',
            r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*intro[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
        )
        for p in patterns:
            cm = re.search(p, html, re.S)
            if cm:
                txt = self._clean(cm.group(1))
                if txt and len(txt) > 3:
                    return txt
        for mp in (r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
                   r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"'):
            dm = re.search(mp, html, re.I)
            if dm:
                txt = self._clean(dm.group(1))
                if txt:
                    return txt
        return ''

    def _filters(self):
        out = {}
        for _, ch in self.classes:
            groups = []
            types = self.type_map.get(ch, [])
            if types:
                groups.append({
                    'key': 'type', 'name': '类型',
                    'value': [{'n': '全部', 'v': ''}] +
                             [{'n': n, 'v': v} for v, n in types],
                })
            groups.append({
                'key': 'area', 'name': '地区',
                'value': [{'n': '全部', 'v': ''}] +
                         [{'n': a, 'v': a} for a in self.areas],
            })
            groups.append({
                'key': 'year', 'name': '年份',
                'value': [{'n': '全部', 'v': ''}] +
                         [{'n': y, 'v': y} for y in self.years] +
                         [{'n': '其他', 'v': '-1'}],
            })
            groups.append({
                'key': 'sort', 'name': '排序',
                'value': [{'n': n, 'v': v} for v, n in self.sorts],
            })
            out[ch] = groups
        return out

    def _first_id(self, ids):
        if isinstance(ids, (list, tuple)):
            return str(ids[0]) if ids else ''
        if isinstance(ids, dict):
            for k in ('id', 'vod_id', 'value'):
                if ids.get(k):
                    return str(ids[k])
            return ''
        s = str(ids or '').strip()
        if s.startswith('['):
            try:
                arr = json.loads(s)
                if isinstance(arr, list) and arr:
                    return str(arr[0])
            except Exception:
                pass
        m = re.search(r'\d+', s)
        return m.group(0) if m else s

    # ================= 壳接口 =================
    def getName(self):
        return '小蜜蜂影院'

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = (url or '').lower()
        return (u.endswith('.m3u8') or u.endswith('.mp4')
                or '.m3u8?' in u or '.mp4?' in u)

    def manualVideoCheck(self):
        return False

    def init(self, extend):
        return None

    def destroy(self):
        return None

    def homeContent(self, filter):
        classes = [{'type_id': tid, 'type_name': name} for name, tid in self.classes]
        items = []
        try:
            html = self._fetch(self.host + '/')
            items = self._parse_cards(html)
        except Exception:
            items = []
        return {'class': classes, 'list': items, 'filters': self._filters()}

    def homeVideoContent(self):
        items = []
        try:
            html = self._fetch(self.host + '/')
            items = self._parse_cards(html)
        except Exception:
            items = []
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        ext = extend if isinstance(extend, dict) else {}
        if isinstance(extend, str) and extend.strip().startswith('{'):
            try:
                ext = json.loads(extend)
            except Exception:
                ext = {}
        ftype = str(ext.get('type') or '')
        area = str(ext.get('area') or '')
        year = str(ext.get('year') or '')
        sort = str(ext.get('sort') or 'hot')
        q = urllib.parse.urlencode({
            'channel': tid, 'type': ftype, 'area': area,
            'year': year, 'sort': sort, 'page': pg,
        })
        url = '{0}/filter?{1}'.format(self.host, q)
        try:
            html = self._fetch(url)
        except Exception:
            html = ''
        items = self._parse_cards(html)
        page, pagecount = self._parse_pagecount(html, pg)
        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': 90,
            'total': 999999,
        }

    def detailContent(self, ids):
        vid = self._first_id(ids)
        url = '{0}/detail/{1}.html'.format(self.host, vid)
        html = self._fetch(url)

        title = ''
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            title = self._strip_title_suffix(self._clean(m.group(1)))
        if not title:
            m = re.search(r'og:title"[^>]*content="《?([^》"]+)》?"', html)
            if m:
                title = self._strip_title_suffix(self._clean(m.group(1)))
        if not title:
            title = vid

        pic = ''
        pm = re.search(r'og:image"[^>]*content="([^"]+)"', html)
        if pm:
            pic = self._abs_url(pm.group(1))

        meta = {}
        for k, v in re.findall(
                r'class="[^"]*meta-label[^"]*"[^>]*>([^<]+)<[^>]*>\s*<[^>]*class="[^"]*meta-value[^"]*"[^>]*>([^<]*)<',
                html):
            meta[self._clean(k).rstrip('：:')] = self._clean(v)
        if not meta:
            for k, v in re.findall(
                    r'<span[^>]*class="[^"]*meta-label[^"]*"[^>]*>([^<]+)</span>\s*<span[^>]*class="[^"]*meta-value[^"]*"[^>]*>([^<]*)</span>',
                    html):
                meta[self._clean(k).rstrip('：:')] = self._clean(v)

        content = self._extract_content(html)

        from_names = re.findall(r'data-target="source-\d+"[^>]*>([^<]+)<', html)
        if not from_names:
            from_names = re.findall(r'class="[^"]*source-tab[^"]*"[^>]*>([^<]+)<', html)
        panels = re.split(r'<div[^>]*class="[^"]*source-panel[^"]*"', html)[1:]
        play_from, play_url = [], []
        for i, panel in enumerate(panels):
            eps = re.findall(r'href="(/vodplay/[^"]+)"[^>]*>([^<]+)</a>', panel)
            eps = [(u, t) for u, t in eps if '/vodplay/{0}-'.format(vid) in u]
            if not eps:
                continue
            fm = re.search(r'/vodplay/\d+-(.+)-\d+\.html', eps[0][0])
            if fm and fm.group(1) == 'bfzym3u8':
                continue
            name = self._clean(from_names[i]) if i < len(from_names) else '线路{0}'.format(i + 1)
            play_from.append(name)
            play_url.append('#'.join(
                '{0}${1}{2}'.format(self._clean(t), self.host, u) for u, t in eps))

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': meta.get('类型', ''),
            'vod_year': meta.get('年份', ''),
            'vod_area': meta.get('地区', ''),
            'vod_actor': meta.get('主演', ''),
            'vod_director': meta.get('导演', ''),
            'vod_remarks': meta.get('备注', ''),
            'vod_content': content,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        q = urllib.parse.urlencode({'keyword': key, 'sort': 'hits', 'page': pg})
        url = '{0}/search?{1}'.format(self.host, q)
        try:
            html = self._fetch(url)
        except Exception:
            html = ''
        items = self._parse_cards(html)
        page, pagecount = self._parse_pagecount(html, pg)
        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': 90,
            'total': 999999,
        }

    def playerContent(self, flag, id, vipFlags):
        header = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        play_page = id if str(id).startswith('http') else self.host + str(id)
        m = re.search(r'/vodplay/(\d+)-(.+)-(\d+)\.html', play_page)
        if m:
            api = '{0}/api/play-url?vodId={1}&playFrom={2}&index={3}'.format(
                self.host, m.group(1),
                urllib.parse.quote(m.group(2)), m.group(3))
            try:
                text = self._fetch(api, referer=play_page)
                data = json.loads(text)
                if data.get('code') == 200 and data.get('url'):
                    if data.get('mode') == 'iframe':
                        return {'parse': 1, 'url': data['url'], 'header': header}
                    return {'parse': 0, 'url': data['url'], 'header': header}
            except Exception:
                pass
        return {'parse': 1, 'url': play_page, 'header': header}

    def localProxy(self, param):
        return [404, 'text/plain', b'not found', {}]

    def action(self, action):
        return None
