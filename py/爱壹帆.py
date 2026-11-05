# coding=utf-8
"""
爱壹帆影视 dtshbx.cn | TVBox Python 爬虫 
关键:
  - 突破服务端 PHP 验证码拦截 (伪装 Baiduspider 蜘蛛 UA)
  - 适配全新 eleven 模板路由 (/cast/{tid}.html / /drama/{id}.html)
  - 重构基于 CSS 混淆的卡片列表解析
  - 兼容动态线路面板 (playlist{N}) 提取
"""
import re
import sys
import json
import time
import random
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider(object):
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 20)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[aiyifan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

# ===================== 站点常量 =====================
HOST = "https://dtshbx.cn"  # 如果域名再次变化，请在此修改

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 一级分类 (基于导航栏真实ID)
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺片"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 子分类 (根据导航栏提取的真实ID)
CLASS_MAP = {
    "1":  ["全部", "6|动作片", "7|喜剧片", "8|爱情片", "9|科幻片", "10|剧情片", "11|战争片", "41|动画片", "12|记录片", "39|恐怖片"],
    "2":  ["全部", "13|国产剧", "14|香港剧", "15|韩国剧", "16|欧美剧", "22|台湾剧", "21|日本剧", "20|泰国剧", "23|海外剧"],
    "3":  ["全部", "25|大陆综艺", "26|日韩综艺", "27|港台综艺", "28|欧美综艺"],
    "4":  ["全部", "29|国产动漫", "30|日本动漫", "42|港台动漫", "31|欧美动漫", "43|海外动漫"],
    "24": ["全部", "40|短剧大全", "44|AI短剧"],
}

_SORTS = [
    {"n": "最新更新", "v": "time"},
    {"n": "最多播放", "v": "hits"},
    {"n": "评分最高", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [{"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}]

# 动态生成 filters
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    cls_values = []
    for item in CLASS_MAP.get(tid, []):
        if item == "全部":
            cls_values.append({"n": "全部", "v": ""})
        else:
            k, v = item.split("|")
            cls_values.append({"n": v, "v": k})
    
    FILTERS[tid] = [
        {"key": "class", "name": "分类", "value": cls_values},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "order", "name": "排序", "value": _SORTS},
    ]

# 伪装成百度蜘蛛，大概率绕过验证码拦截
UA_SPIDER = "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"
UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
UA_LIST = [UA_SPIDER, UA_PC]

DEFAULT_PIC = "https://dtshbx.cn/template/eleven/images/favicon.ico"

class Spider(Spider):
    def getName(self):
        return "爱壹帆影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA_SPIDER, # 默认用蜘蛛UA
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self._detail_cache = {}

    def _fetch(self, url, timeout=20, headers=None, retry=2):
        h = dict(self.headers)
        if headers:
            h.update(headers)

        last_text = ""
        for attempt in range(retry):
            try:
                if attempt > 0:
                    h["User-Agent"] = random.choice(UA_LIST)
                
                rsp = self.fetch(url, headers=h, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else str(rsp)

                if not text or len(text) < 500:
                    continue
                
                # 检测是否被防爬拦截
                if "安全验证" in text or "验证码" in text:
                    self.log(f"  [警告] 触发验证码拦截: {url}")
                    continue
                
                return text
            except Exception as e:
                self.log(f"  fetch fail: {e}")
                time.sleep(1)
        return last_text

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("\xa0", " ")
        return s.strip()

    def _fix_url(self, url):
        if not url: return ""
        url = url.strip()
        if url.startswith("//"): return "https:" + url
        if url.startswith("http"): return url
        return self.site_url + url if url.startswith("/") else urllib.parse.urljoin(self.site_url, url)

    def _extract_videos(self, html):
        videos = []
        if not html: return videos

        # 适配新模板的正则
        # 核心结构: <a href="/drama/155005.html" title="尚公主"> ... data-original="图片url" ... <p>更新至xx</p>
        card_pattern = re.compile(r'<a\s+href="(/drama/\d+\.html)"\s+title="([^"]+)">(.*?)</a>', re.S | re.I)
        
        for m in card_pattern.finditer(html):
            href = m.group(1)
            name = self._clean(m.group(2))
            inner = m.group(3)
            
            pic = DEFAULT_PIC
            m_pic = re.search(r'data-original="([^"]+)"', inner)
            if m_pic: pic = self._fix_url(m_pic.group(1))
            
            remarks = ""
            m_remark = re.search(r'<p[^>]*>(更新至[^<]+|已完结|全\d+集|第\d+集[^<]*)</p>', inner)
            if m_remark: remarks = self._clean(m_remark.group(1))
            
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks
            })
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        # 首页直接抓取 /label/new.html 最新更新
        url = f"{self.site_url}/label/new.html"
        html = self._fetch(url)
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        
        # 解析筛选参数
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except: extend = {}
        
        cls_id = extend.get("class") or tid
        if not cls_id: cls_id = tid

        # 构造 URL: /pool/id/13.html 或者带筛选的 /pool/id/13-地区-年份-排序-页码.html
        url = f"{self.site_url}/pool/id/{cls_id}.html"
        
        area = extend.get("area", "")
        year = extend.get("year", "")
        order = extend.get("order", "")
        
        if area or year or order or page > 1:
            # 近似 MacCMS 筛选路由 (根据 eleven 模板规范)
            # 实际格式通常为: /pool/id/13-大陆-2024-time-2.html
            parts = [cls_id, area, "", year, order, "", str(page) if page > 1 else ""]
            url = f"{self.site_url}/pool/id/{'-'.join(parts).rstrip('-')}.html"

        self.log(f"category: {url}")
        html = self._fetch(url)
        
        # 如果被拦截，尝试退回 /cast/{tid}.html
        if "安全验证" in html:
            url = f"{self.site_url}/cast/{cls_id}.html"
            html = self._fetch(url)

        videos = self._extract_videos(html)
        
        # 页码判断：找尾页
        pagecount = 9999
        m_page = re.search(r'尾页.*?(\d+)\.html', html)
        if m_page:
            pagecount = int(m_page.group(1))
        elif len(videos) < 20:
            pagecount = page

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) or 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick=False, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        # 新搜索接口: /lookup2.html?wd=xxx
        kw = urllib.parse.quote(key)
        url = f"{self.site_url}/lookup2.html?wd={kw}&page={page}" if page > 1 else f"{self.site_url}/lookup2.html?wd={kw}"
        
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos, "page": page, "pagecount": 9999, "limit": 24, "total": 999}

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = ids[0]
        url = self._fix_url(vod_id) if vod_id.startswith("/") else f"{self.site_url}/drama/{vod_id}.html"
        
        now = int(time.time())
        if url in self._detail_cache and now - self._detail_cache[url][0] < 300:
            return self._detail_cache[url][1]

        html = self._fetch(url)
        
        # 1. 解析基础信息
        name = ""
        m_title = re.search(r'<title>(.*?)</title>', html, re.S)
        if m_title: name = self._clean(m_title.group(1)).split('-')[0]

        pic = DEFAULT_PIC
        m_pic = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if m_pic: pic = self._fix_url(m_pic.group(1))

        # 2. 解析播放源和剧集 (eleven 模板的播放源结构)
        play_from = []
        play_url = []
        
        # 提取线路标签: <a href="#playlist1">线路1</a>
        # 提取剧集列表: <div id="playlist1"> <a href="/play/123-1-1.html">第1集</a>
        m_play_section = re.search(r'播放地址</h3>(.*?)(?:<div class="play-list">|<!-- 剧情简介)', html, re.S)
        if m_play_section:
            play_html = m_play_section.group(1)
            
            # 找出所有线路起始位置
            pane_starts = list(re.finditer(r'<div\s+id="playlist(\d+)"', play_html))
            for i, start_m in enumerate(pane_starts):
                idx = start_m.group(1)
                end = pane_starts[i+1].start() if i+1 < len(pane_starts) else len(play_html)
                pane_html = play_html[start_m.end():end]
                
                eps = []
                for ep_m in re.finditer(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', pane_html, re.S):
                    ep_url = ep_m.group(1)
                    ep_name = self._clean(ep_m.group(2))
                    if '/play/' in ep_url or 'vodplay' in ep_url:
                        eps.append(f"{ep_name}${self._fix_url(ep_url)}")
                
                if eps:
                    play_from.append(f"线路{idx}")
                    play_url.append("#".join(eps))

        # 3. 解析简介
        content = "暂无简介"
        m_desc = re.search(r'<div\s+class="vod-detail-info">.*?<p>(.*?)</p>', html, re.S) or \
                 re.search(r'<span\s+class="sketch content">(.*?)</span>', html, re.S)
        if m_desc:
            content = self._clean(m_desc.group(1))

        # ---- 补上小橙子防骗提示 ----
        if content and content != "暂无简介":
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        res = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
            "vod_remarks": ""
        }
        
        self._detail_cache[url] = (now, {"list": [res]})
        return {"list": [res]}

    def playerContent(self, flag, id, vipFlags):
        play_page = self._fix_url(id)
        
        now = int(time.time())
        if play_page in self._play_cache and now - self._play_cache[play_page][0] < 600:
            return self._play_cache[play_page][1]

        html = self._fetch(play_page)
        
        m3u8 = ""
        # 解析 player_aaaa
        m_player = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.S)
        if m_player:
            try:
                raw_json = m_player.group(1)
                # 清理非标准 JSON 字符
                raw_json = raw_json.replace('\\/', '/')
                cfg = json.loads(raw_json)
                m3u8 = cfg.get("url", "")
            except Exception as e:
                self.log(f"JSON解析失败: {e}, 尝试正则")
                
        if not m3u8:
            # 正则兜底提取 m3u8
            m3u8_m = re.search(r'"url":"(http[^"]+\.m3u8[^"]*)"', html)
            if m3u8_m: m3u8 = m3u8_m.group(1).replace("\\/", "/")

        if m3u8:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {"User-Agent": UA_PC, "Referer": self.site_url + "/"}
            }
        else:
            # 嗅探解析
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA_PC}
            }
            
        self._play_cache[play_page] = (now, res)
        return res
