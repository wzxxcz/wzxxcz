# coding=utf-8
# TVBox Python 爬虫：极速追剧 jisuzhuiju.com
# 依赖：requests、lxml
import json
import re
import sys
from urllib.parse import quote, urlencode, urljoin

import requests
from lxml import etree

class Spider(object):
    def __init__(self):
        self.base = "https://jisuzhuiju.com"
        self.timeout = 12
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Referer": self.base + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session.headers.update(self.headers)

    def init(self, extend=""):
        self.extend = extend or ""

    def _get(self, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", self.headers)
        r = self.session.get(url, **kwargs)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r

    def _abs(self, url):
        if not url:
            return ""
        return urljoin(self.base, url)

    def _json(self, obj):
        return json.dumps(obj, ensure_ascii=False)

    def _parse_list(self, tree):
        """解析 vod-card 列表，首页/筛选/搜索通用"""
        videos = []
        for a in tree.xpath('//a[contains(@class,"text-decoration-none")]'):
            card = a.xpath('.//div[contains(@class,"vod-card")]')
            if not card:
                continue
            href = a.xpath('./@href')
            if not href:
                continue
            m = re.search(r'/detail/(\d+)\.html', href[0])
            if not m:
                continue

            card = card[0]
            name = card.xpath('.//p[contains(@class,"vod-title")]/text()')
            sub = card.xpath('.//p[contains(@class,"vod-subtitle")]/text()')
            pic = card.xpath('.//img/@src')
            badge = card.xpath('.//span[contains(@class,"vod-badge")]/text()')

            videos.append({
                "vod_id": m.group(1),
                "vod_name": (name[0] if name else "").strip(),
                "vod_pic": self._abs(pic[0] if pic else ""),
                "vod_remarks": (badge[0] if badge else "").strip(),
                "vod_content": (sub[0] if sub else "").strip(),
            })
        return videos

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "电视剧"},
            {"type_id": "2", "type_name": "电影"},
            {"type_id": "3", "type_name": "动漫"},
            {"type_id": "4", "type_name": "综艺"},
            {"type_id": "5", "type_name": "短剧"},
        ]
        filters = {}
        if filter:
            sort_filter = {
                "key": "sort",
                "name": "排序",
                "value": [
                    {"n": "热度", "v": "hot"},
                    {"n": "时间", "v": "time"},
                    {"n": "评分", "v": "score"},
                ],
            }
            filters = {
                "1": [sort_filter],
                "2": [sort_filter],
                "3": [sort_filter],
                "4": [sort_filter],
                "5": [sort_filter],
            }

        videos = []
        try:
            html = self._get(self.base + "/").text
            tree = etree.HTML(html)
            sec = tree.xpath('//div[contains(@class,"vod-section")][1]')
            if sec:
                videos = self._parse_list(sec[0])
        except Exception as e:
            print("homeContent error:", e, file=sys.stderr)

        return self._json({
            "class": classes,
            "filters": filters,
            "list": videos,
        })

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        ext = extend or {}
        params = {
            "channel": tid,
            "type": ext.get("type", ""),
            "area": ext.get("area", ""),
            "year": ext.get("year", ""),
            "sort": ext.get("sort", "hot"),
            "page": page,
        }
        url = self.base + "/filter?" + urlencode(params)
        videos = []
        pagecount = 1
        try:
            html = self._get(url).text
            tree = etree.HTML(html)
            videos = self._parse_list(tree)
            total = tree.xpath('//div[@id="pageData"]/@data-totalpages')
            if total:
                pagecount = int(total[0])
            else:
                em = tree.xpath('//div[contains(@class,"search-pagination-jump")]//em/text()')
                if em:
                    pagecount = int(em[0])
        except Exception as e:
            print("categoryContent error:", e, file=sys.stderr)

        return self._json({
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * len(videos) if videos else 0,
            "list": videos,
        })

    def detailContent(self, ids):
        if isinstance(ids, list):
            vod_id = ids[0]
        else:
            vod_id = str(ids)

        url = f"{self.base}/detail/{vod_id}.html"
        try:
            html = self._get(url).text
            tree = etree.HTML(html)
            name = tree.xpath('//h1[contains(@class,"detail-title")]/text()')
            name = name[0].strip() if name else ""
            pic = tree.xpath('//div[contains(@class,"detail-poster-wrapper")]//img/@src')
            pic = self._abs(pic[0]) if pic else ""
            tags = tree.xpath('//div[contains(@class,"detail-tags")]//span/text()')
            type_name = ",".join([t.strip() for t in tags if t.strip()])
            meta = {}
            for item in tree.xpath('//div[contains(@class,"detail-meta-grid")]//div[contains(@class,"meta-item")]'):
                label = item.xpath('.//span[contains(@class,"meta-label")]/text()')
                value = item.xpath('.//span[contains(@class,"meta-value")]/text()')
                if label and value:
                    meta[label[0].strip().rstrip("：")] = value[0].strip()
            content = tree.xpath('//div[contains(@class,"synopsis-content")]/text()')
            content = content[0].strip() if content else ""

            play_from = []
            play_url = []
            tabs = tree.xpath('//div[contains(@class,"source-tabs")]/button[contains(@class,"source-tab")]')
            for tab in tabs:
                target = tab.xpath('./@data-target')
                if not target:
                    continue
                target = target[0]
                from_name = "".join(tab.xpath('.//text()')).strip()
                panel = tree.xpath(f'//div[@id="{target}"]')
                if not panel:
                    continue
                eps = []
                for a in panel[0].xpath('.//a[contains(@class,"episode-btn")]'):
                    href = a.xpath('./@href')
                    if not href:
                        continue
                    ep_name = "".join(a.xpath('.//text()')).strip()
                    if not ep_name:
                        continue
                    eps.append(f"{ep_name}${href[0]}")
                if eps:
                    play_from.append(from_name)
                    play_url.append("#".join(eps))

            vod = {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": meta.get("年份", ""),
                "vod_area": meta.get("地区", ""),
                "vod_remarks": meta.get("备注", ""),
                "vod_actor": meta.get("主演", ""),
                "vod_director": meta.get("导演", ""),
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }
            return self._json({"list": [vod]})
        except Exception as e:
            print("detailContent error:", e, file=sys.stderr)
            return self._json({"list": []})

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        # 如果实际搜索地址不一样，请按 F12 抓包替换这里
        url = f"{self.base}/search?keyword={quote(key)}&page={page}"
        videos = []
        pagecount = 1
        try:
            html = self._get(url).text
            tree = etree.HTML(html)
            videos = self._parse_list(tree)
            total = tree.xpath('//div[@id="pageData"]/@data-totalpages')
            if total:
                pagecount = int(total[0])
            else:
                em = tree.xpath('//div[contains(@class,"search-pagination-jump")]//em/text()')
                if em:
                    pagecount = int(em[0])
        except Exception as e:
            print("searchContent error:", e, file=sys.stderr)
        return self._json({
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * len(videos) if videos else 0,
            "list": videos,
        })

    def playerContent(self, flag, id, vipFlags):
        """播放解析：向 /api/play-url 请求真实地址"""
        # id 的格式为 /vodplay/6807-bfzym3u8-1.html
        m = re.search(r'/vodplay/(\d+)-([^/]+?)-(\d+)\.html', id)
        if not m:
            return self._json({"parse": 0, "playUrl": "", "url": id, "header": ""})
        
        vod_id, play_from, index = m.groups()
        api_url = f"{self.base}/api/play-url"
        params = {
            "vodId": vod_id,
            "playFrom": play_from,
            "index": index
        }
        
        try:
            # 根据 JS 代码，这里是 GET 请求
            r = self.session.get(api_url, params=params, headers=self.headers, timeout=self.timeout)
            data = r.json()
            
            if data.get('code') == 200 and data.get('url'):
                real_url = data['url']
                # 提取服务器返回的 headers，如果没有则用默认的
                play_headers = data.get('headers', {})
                # TVBox 需要 header 为 JSON 字符串
                header_json = self._json(play_headers) if play_headers else self._json(self.headers)
                
                return self._json({
                    "parse": 0,           # 0 表示直接播放链接
                    "playUrl": "",
                    "url": real_url,
                    "header": header_json
                })
        except Exception as e:
            print("playerContent error:", e, file=sys.stderr)

        # 如果解析失败，回退到播放页地址（可能触发 TVBox 内置嗅探）
        return self._json({
            "parse": 0,
            "playUrl": "",
            "url": self._abs(id),
            "header": self._json(self.headers),
        })