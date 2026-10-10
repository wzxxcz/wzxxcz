# coding=utf-8
import re
import sys
import json
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
import urllib3
urllib3.disable_warnings()

# 兼容 TVBox 基类
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):
            self.session = requests.Session()
            self.session.verify = False
            self.session.mount('https://', HTTPAdapter(max_retries=3))
            self.session.mount('http://', HTTPAdapter(max_retries=3))
        def fetch(self, url, headers=None, timeout=15):
            r = self.session.get(url, headers=headers, timeout=timeout)
            r.encoding = 'utf-8'
            return r
        def log(self, *args):
            print("[cupfox]", *args)

class Spider(Spider):
    def getName(self):
        return "茶杯狐电影"

    def init(self, extend=""):
        self.host = "https://www.cupfoxdy.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.log("init")

    def homeContent(self, filter=False):
        # 分类 ID 根据网站实际 tid 调整：电影=1，电视剧=2，综艺=3，动漫=4，短剧=25
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "25", "type_name": "短剧"},
        ]
        filters = {}
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        url = self.host + "/"
        html = self.fetch(url, headers=self.headers).text
        videos = self._parse_list(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 使用 search.php 统一获取分类列表，支持分页
        url = f"{self.host}/search.php?page={page}&searchtype=5&tid={tid}&year=&area=&yuyan=&order=time"
        self.log(f"category: {url}")
        html = self.fetch(url, headers=self.headers).text
        videos = self._parse_list(html)
        pagecount = self._parse_pagecount(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = f"{self.host}/search.php?searchword={keyword}&page={page}"
        self.log(f"search: {url}")
        html = self.fetch(url, headers=self.headers).text
        videos = self._parse_list(html)
        pagecount = self._parse_pagecount(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = vod_id if vod_id.startswith("http") else self.host + vod_id
        self.log(f"detail: {url}")
        html = self.fetch(url, headers=self.headers).text

        # 标题
        name = ""
        m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        else:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = m.group(1).split('_')[0].split('-')[0].strip()

        # 海报
        pic = ""
        m = re.search(r'<img class="lazyload"[^>]*data-original="([^"]+)"', html)
        if not m:
            m = re.search(r'id="js-poster-img"[^>]*data-original="([^"]+)"', html)
        if m:
            pic = m.group(1)

        # 简介
        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html)
        if not m:
            m = re.search(r'<span class="detail-sketch">([\s\S]*?)</span>', html)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 主演
        actor = ""
        m = re.search(r'<span class="meta-item">主演：([\s\S]*?)</span>', html)
        if m:
            actor = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 导演
        director = ""
        m = re.search(r'<span class="meta-item">导演：([\s\S]*?)</span>', html)
        if m:
            director = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 播放列表（支持多线路）
        play_from = []
        play_url = []
        # 匹配每个线路面板：<h3>线路名</h3> 和后面的 <ul class="stui-content__playlist clearfix">
        panel_pattern = re.compile(
            r'<h3>([^<]+)</h3>.*?<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
            re.S)
        for m in panel_pattern.finditer(html):
            line_name = m.group(1).strip()
            ul_html = m.group(2)
            episodes = re.findall(r'<li[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></li>', ul_html)
            if episodes:
                play_from.append(line_name)
                # 拼接完整 URL
                ep_list = []
                for href, ep_name in episodes:
                    if href.startswith('/'):
                        full_url = self.host + href
                    else:
                        full_url = href
                    ep_list.append(f"{ep_name}${full_url}")
                play_url.append("#".join(ep_list))

        if not play_from:
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        # id 是播放页链接，如 /fox/17111-0-0.html
        url = id if id.startswith("http") else self.host + id
        self.log(f"player: {url}")
        html = self.fetch(url, headers=self.headers).text

        # 提取 now 变量（真实播放地址）
        m = re.search(r'var now="([^"]+)"', html)
        if m:
            play_url = m.group(1)
            self.log(f"  play_url: {play_url}")
            # 返回解析，让 TVBox 嗅探（若确定是 m3u8 可改为 parse:0）
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                }
            }
        # 兜底
        return {"parse": 1, "playUrl": "", "url": url, "header": self.headers}

    # ---------- 辅助方法 ----------
    def _parse_list(self, html):
        """解析视频列表（分类页、搜索页、首页通用）"""
        videos = []
        # 匹配视频卡片：<a class="stui-vodlist__thumb lazyload" href="..." title="..." data-original="...">
        pattern = re.compile(
            r'<a class="stui-vodlist__thumb lazyload" href="([^"]+)" title="([^"]*)" data-original="([^"]*)"[^>]*>[\s\S]*?<span class="pic-text text-right"><b>([^<]*)</b></span>',
            re.S)
        for m in pattern.finditer(html):
            href, title, pic, remark = m.groups()
            if not href.startswith('http'):
                href = self.host + href
            videos.append({
                "vod_id": href,
                "vod_name": title.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": remark.strip(),
            })
        return videos

    def _parse_pagecount(self, html):
        """从分页条提取总页数"""
        m = re.search(r'<li class="active num"><a>(\d+)/(\d+)</a></li>', html)
        if m:
            return int(m.group(2))
        m = re.search(r'<a href="[^"]*page=(\d+)[^"]*">尾页</a>', html)
        if m:
            return int(m.group(1))
        return 1

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
