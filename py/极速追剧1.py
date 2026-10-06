# coding=utf-8
# TVBox Python 爬虫：极速追剧 jisuzhuiju.com
# 依赖：requests（TVBox 自带，无需 lxml）
import json
import re
import sys
from urllib.parse import quote, urlencode

import requests

class Spider(object):
    def __init__(self):
        self.base = "https://jisuzhuiju.com"
        self.timeout = 12
        self.session = requests.Session()
        # 完善请求头，尽量模拟浏览器，避免被反爬拦截
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
        # 防止网站乱码，手动指定 UTF-8
        r.encoding = r.apparent_encoding or "utf-8"
        return r

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.base + url
        return url

    def _json(self, obj):
        return json.dumps(obj, ensure_ascii=False)

    def _parse_list(self, html):
        """使用正则解析 vod-card 列表，无需 lxml"""
        videos = []
        # 匹配详情页链接和区块内容
        blocks = re.findall(r'<a[^>]+href="(/detail/\d+\.html)"[^>]*>(.*?)</a>', html, re.S)
        for href, content in blocks:
            vod_id = re.search(r'/detail/(\d+)\.html', href)
            if not vod_id:
                continue
            
            title_m = re.search(r'<p[^>]*class="[^"]*vod-title[^"]*"[^>]*>(.*?)</p>', content, re.S)
            title = title_m.group(1).strip() if title_m else ""
            
            img_m = re.search(r'<img[^>]+src="([^"]+)"', content)
            pic = self._abs(img_m.group(1).strip()) if img_m else ""
            
            # 尝试获取备注（更新至xx集）
            badge_m = re.search(r'<span[^>]*class="[^"]*vod-badge[^"]*"[^>]*>(.*?)</span>', content, re.S)
            remarks = badge_m.group(1).strip() if badge_m else ""
            
            sub_m = re.search(r'<p[^>]*class="[^"]*vod-subtitle[^"]*"[^>]*>(.*?)</p>', content, re.S)
            sub = sub_m.group(1).strip() if sub_m else ""

            videos.append({
                "vod_id": vod_id.group(1),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks or sub,
                "vod_content": sub,
            })
        return videos

    def homeContent(self, filter):
        """返回首页分类配置"""
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
                "1": [sort_filter], "2": [sort_filter], "3": [sort_filter],
                "4": [sort_filter], "5": [sort_filter],
            }
        return self._json({"class": classes, "filters": filters})

    def homeVideoContent(self):
        """TVBox 首页推荐视频（必须要有）"""
        videos = []
        try:
            html = self._get(self.base + "/").text
            # 直接抓取首页全部影片列表
            videos = self._parse_list(html)
        except Exception as e:
            print("homeVideoContent error:", e, file=sys.stderr)
        return self._json({"list": videos})

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
            videos = self._parse_list(html)
            total = re.search(r'data-totalpages="(\d+)"', html)
            if total:
                pagecount = int(total.group(1))
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
            
            # 正则提取详情页信息
            name = re.search(r'<h1 class="detail-title">([^<]+)</h1>', html)
            name = name.group(1).strip() if name else ""
            
            pic = re.search(r'<div class="detail-poster-wrapper">.*?<img src="([^"]+)"', html, re.S)
            pic = self._abs(pic.group(1)) if pic else ""
            
            content = re.search(r'<div class="synopsis-content"[^>]*>(.*?)</div>', html, re.S)
            content = content.group(1).strip() if content else ""

            # 提取元数据（年份、地区、主演等）
            meta = {}
            for label, val in re.findall(r'<span class="meta-label">([^：]+)：</span>\s*<span class="meta-value">([^<]+)</span>', html):
                meta[label.strip()] = val.strip()

            # 提取播放线路
            play_from = []
            play_url = []
            
            # 找到所有线路面板
            tabs = re.findall(r'<button class="source-tab[^"]*"[^>]*data-target="([^"]+)"[^>]*>([^<]+)</button>', html)
            for target, from_name in tabs:
                from_name = from_name.strip()
                # 提取对应面板里的剧集
                panel_re = r'<div class="source-panel"[^>]*id="{}"[^>]*>(.*?)</div>'.format(target)
                panel = re.search(panel_re, html, re.S)
                if not panel:
                    continue
                
                eps = []
                for href, ep_name in re.findall(r'<a href="([^"]+)"[^>]*class="[^"]*episode-btn[^"]*"[^>]*>([^<]+)</a>', panel.group(1)):
                    eps.append(f"{ep_name.strip()}${href}")
                
                if eps:
                    play_from.append(from_name)
                    play_url.append("#".join(eps))

            vod = {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": "",
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
        url = f"{self.base}/search?keyword={quote(key)}&page={page}"
        videos = []
        pagecount = 1
        try:
            html = self._get(url).text
            videos = self._parse_list(html)
            total = re.search(r'data-totalpages="(\d+)"', html)
            if total:
                pagecount = int(total.group(1))
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
        """调用 /api/play-url 获取真实播放地址"""
        m = re.search(r'/vodplay/(\d+)-([^/]+?)-(\d+)\.html', id)
        if not m:
            return self._json({"parse": 0, "playUrl": "", "url": self._abs(id), "header": ""})
        
        vod_id, play_from, index = m.groups()
        api_url = f"{self.base}/api/play-url"
        params = {
            "vodId": vod_id,
            "playFrom": play_from,
            "index": index
        }
        
        try:
            # 增加 X-Requested-With 头，伪装成 AJAX 请求
            headers = self.headers.copy()
            headers["X-Requested-With"] = "XMLHttpRequest"
            
            r = self.session.get(api_url, params=params, headers=headers, timeout=self.timeout)
            data = r.json()
            
            if data.get('code') == 200 and data.get('url'):
                real_url = data['url']
                play_headers = data.get('headers', {})
                header_json = self._json(play_headers) if play_headers else self._json(self.headers)
                
                return self._json({
                    "parse": 0, # 0 表示直接播放
                    "playUrl": "",
                    "url": real_url,
                    "header": header_json
                })
            else:
                # 接口返回异常
                print("API Error:", data.get('msg', 'unknown'), file=sys.stderr)
        except Exception as e:
            print("playerContent error:", e, file=sys.stderr)

        # 解析失败，返回播放页地址让 TVBox 嗅探
        return self._json({
            "parse": 0,
            "playUrl": "",
            "url": self._abs(id),
            "header": self._json(self.headers),
        })
