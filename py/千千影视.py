# -*- coding: utf-8 -*-
"""
title: 千千影视(QQYS)
host: https://www.qqys01.com/
说明: FongMi/OK影视 Python Spider · 苹果CMS V10(MXO主题模板)
      按《OK影视爬虫开发文档》第2节骨架直接编写(铁律: 不参考本机其他py)

URL规则(2026-09-27 实测):
  分类  /vodtype/{tid}.html              tid: 1电影 2连续剧 3综艺 4动漫
  筛选  /vodshow/ 共12段11个连字符:
        {tid}-{area}-{by}-{class}-{lang}-{ver}-{state}-{letter}-{pg}-{?}-{?}-{year}
        实测样本:
          /vodshow/1-----------.html          电影全部
          /vodshow/1--------2---.html         第2页(第9段)
          /vodshow/1-----------2026.html      2026年(第12段)
          /vodshow/1-大陆----------.html      地区(第2段, 需quote)
          /vodshow/1---剧情--------.html      剧情(第4段, 需quote)
          /vodshow/1----国语-------.html      语言(第5段, 需quote)
  详情  /voddetail{id}.html
  播放  /vodplay/{id}-{sid}-{nid}.html
        页内 var player_data={...,"encrypt":2,"from":"lzm3u8","url":"BASE64",...}
        encrypt=2 解码: base64解码 -> unquote(最多2次) -> 真实地址
        from 含 m3u8/mp4 等为直链(parse=0); from 为 qq/youku 等平台源时
        url 是平台播放页, 返回 parse=1 交给客户端嗅探
  搜索  /vodsearch.html?wd={词}   分页 /vodsearch/page/{pg}/wd/{quote词}.html
"""

import json
import re
import sys
import os
import base64
from urllib.parse import quote, unquote

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self, query_params=None, t4_api=None):
            self.query_params = query_params or {}
            self.t4_api = t4_api or ''
            self.extend = ''

        def fetch(self, url, params=None, headers=None, cookies=None, timeout=10, **kwargs):
            import requests
            return requests.get(url, params=params, headers=headers,
                                cookies=cookies, timeout=timeout, verify=False)


# 强制规范0: 免责声明(文档固定格式), 拼接在每个 vod_content 最顶部
DISCLAIMER = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


class Spider(BaseSpider):
    HOST = "https://www.qqys01.com"
    UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")

    # 站点自带解析(static/js/playerconfig.js 的 player_list, ps=1 的线路全用它):
    # 腾讯/爱奇艺/优酷/芒果/哔哩哔哩等平台线路的url是平台播放页
    PARSE_PAGE = "https://svip.qlplayer.cyou"
    # 解析页流程: 打开 ?url=平台页 → 页内 apiToken → 同会话调 api/resolve.php?token=
    # → {code:200, url:"真实m3u8"} (实测需 Cookie会话+Referer链路, 否则404)
    PARSE_URL = PARSE_PAGE + "/?url="

    def init(self, extend=""):
        self.extend = extend or ""
        self.timeout = 20   # 该站偶发响应慢(实测有19s的情况), 15s会误超时
        self._cache = {}
        return {"status": 0}

    def getName(self):
        return "🅿️千千影视"

    # ---------- 基础 ----------

    def _headers(self):
        # 踩坑12: 请求头带完整 Accept/Accept-Language 模拟浏览器
        return {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _get(self, url):
        if url in self._cache:
            return self._cache[url]
        html = ""
        for i in range(2):   # 站点偶发慢, 超时重试一次
            try:
                rsp = self.fetch(url, headers=self._headers(), timeout=self.timeout)
                rsp.encoding = "utf-8"
                html = rsp.text or ""
                break
            except Exception as e:
                if i == 1:
                    print("[QianQian] _get fail:", url, e)
        if len(self._cache) > 32:
            self._cache.clear()
        self._cache[url] = html
        return html

    @staticmethod
    def _parse_extend(extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        try:
            obj = json.loads(extend)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _pick_first_id(ids):
        if ids is None:
            return ""
        if isinstance(ids, list):
            return str(ids[0]) if ids else ""
        s = str(ids)
        if s.startswith("["):
            try:
                arr = json.loads(s)
                if arr and len(arr):
                    return str(arr[0])
            except Exception:
                pass
        return s

    # ---------- 列表卡片 ----------

    def _pic(self, raw):
        p = (raw or "").strip()
        if not p:
            return ""
        if p.startswith("//"):
            return "https:" + p
        if p.startswith("/"):
            return self.HOST + p
        return p

    def _cards(self, html):
        # 覆盖三种卡片: 分类/筛选页 module-poster-item、搜索页 module-card-item、首页
        videos, seen = [], set()
        for m in re.finditer(r'<a[^>]*href="/voddetail(\d+)\.html"[^>]*>([\s\S]*?)</a>', html):
            vid, body = m.group(1), m.group(2)
            if vid in seen or len(body) > 4000:
                continue
            seen.add(vid)
            # 标题: 优先 a 的 title 属性, 其次 img 的 alt
            t = re.search(r'title="([^"]+)"', m.group(0))
            if not t:
                t = re.search(r'alt="([^"]+)"', body)
            if not t:
                continue  # 轮播banner等无标题链接跳过
            pic = ""
            pm = re.search(r'data-original="([^"]+)"', body)
            if not pm:
                pm = re.search(r'<img[^>]*\ssrc="([^"]+)"', body)
            if pm:
                pic = self._pic(pm.group(1))
            rk = re.search(r'class="module-item-note">([^<]*)<', body)
            videos.append({
                "vod_id": vid,           # 纯数字id, 不以/开头(踩坑3)
                "vod_name": t.group(1).strip(),
                "vod_pic": pic,
                "vod_remarks": rk.group(1).strip() if rk else "",
            })
        return videos

    def _pagecount(self, html, pg):
        # 从底部分页条"尾页"链接解析总页数, 取不到则认为当前即末页
        m = re.search(r'href="/vodshow/[^"]*?-(\d+)---\.html"[^>]*title="尾页"', html)
        if not m:
            m = re.search(r'href="/vodsearch/page/(\d+)/[^"]*"[^>]*title="尾页"', html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        return max(1, int(pg))

    # ---------- 筛选 ----------

    def _build_filters(self):
        def nv(n, v):
            return {"n": n, "v": v}

        def fg(key, name, values):
            return {"key": key, "name": name, "value": [nv("全部", "")] + values}

        def tags(*args):
            return [nv(a, a) for a in args]

        areas = tags("大陆", "香港", "台湾", "美国", "韩国", "日本", "英国",
                     "法国", "德国", "泰国", "印度", "其他")
        langs = tags("国语", "英语", "粤语", "闽南语", "韩语", "日语", "泰语", "其它")
        years = tags(*[str(y) for y in range(2026, 2009, -1)])
        bys = [nv("最近更新", "time"), nv("最多播放", "hits"), nv("最高评分", "score")]
        common = [fg("area", "地区", areas), fg("lang", "语言", langs),
                  fg("year", "年份", years), fg("by", "排序", bys)]
        # 电影子类型tid(筛选页实测): /vodshow/{tid}-----------.html
        movie_types = [nv("动作片", "6"), nv("喜剧片", "7"), nv("爱情片", "8"),
                       nv("科幻片", "9"), nv("恐怖片", "10"), nv("剧情片", "11"),
                       nv("战争片", "12"), nv("纪录片", "53"), nv("动画片", "57")]
        movie = [fg("t", "类型", movie_types),
                 fg("class", "剧情", tags("喜剧", "爱情", "动作", "恐怖", "科幻", "剧情",
                                      "犯罪", "惊悚", "战争", "悬疑", "动画", "奇幻",
                                      "冒险", "家庭", "传记", "历史"))] + common
        return {"1": movie, "2": common, "3": common, "4": common}

    # ---------- 首页 ----------

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "连续剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
        ]
        return {"class": classes, "filters": self._build_filters() if filter else {}}

    def homeVideoContent(self):
        try:
            return {"list": self._cards(self._get(self.HOST + "/"))}
        except Exception as e:
            print("[QianQian] homeVideoContent error:", e)
            return {"list": []}

    # ---------- 分类 ----------

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(1, int(pg or 1))
            fl = self._parse_extend(extend)
            # "类型"筛选(t)直接切换 vodshow 的子类型tid
            real_tid = str(fl.get("t") or tid).strip() or "1"
            segs = ["", "", "", "", "", "", "", "", "", "", "", ""]  # 12段
            segs[0] = real_tid
            segs[1] = str(fl.get("area") or "").strip()
            segs[2] = str(fl.get("by") or "").strip()
            segs[3] = str(fl.get("class") or "").strip()
            segs[4] = str(fl.get("lang") or "").strip()
            if pg > 1:
                segs[8] = str(pg)
            segs[11] = str(fl.get("year") or "").strip()
            url = "%s/vodshow/%s.html" % (self.HOST, "-".join(quote(s) for s in segs))
            html = self._get(url)
            lst = self._cards(html)
            return {"list": lst, "page": pg,
                    "pagecount": self._pagecount(html, pg),
                    "limit": 24, "total": 999999}
        except Exception as e:
            print("[QianQian] categoryContent error:", e)
            pg = max(1, int(pg or 1))
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    # ---------- 搜索 ----------

    def searchContent(self, key, quick, pg=1):
        try:
            if not key:
                return {"list": []}
            pg = max(1, int(pg or 1))
            # 苹果CMS路径式搜索分页(踩坑7); 站点同时支持 /vodsearch.html?wd=
            url = "%s/vodsearch/page/%d/wd/%s.html" % (self.HOST, pg, quote(key))
            html = self._get(url)
            lst = self._cards(html)
            return {"list": lst, "page": pg,
                    "pagecount": self._pagecount(html, pg),
                    "limit": 20, "total": 999999}
        except Exception as e:
            print("[QianQian] searchContent error:", e)
            return {"list": []}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vod_id = self._pick_first_id(ids).lstrip("/")
            if not vod_id:
                return result
            html = self._get("%s/voddetail%s.html" % (self.HOST, vod_id))

            def g(pattern):
                m = re.search(pattern, html)
                return m.group(1).strip() if m else ""

            name = g(r'<div class="module-info-heading">\s*<h1>([^<]+)</h1>') or vod_id
            pic = self._pic(g(r'<div class="module-info-poster">[\s\S]*?data-original="([^"]+)"'))

            # 头部tag: <a title="2026">年份 / <a title="美国">地区 / 无title的<a>是类型
            year, area, tname = "", "", ""
            for attrs, text in re.findall(
                    r'<div class="module-info-tag-link">\s*<a([^>]*)>([^<]+)</a>', html):
                tm = re.search(r'title="([^"]*)"', attrs)
                if tm:
                    v = tm.group(1).strip()
                    if re.match(r'^\d{4}$', v):
                        year = year or v
                    else:
                        area = area or v
                elif not tname:
                    tname = text.strip()

            def labeled(label):
                # <span class="module-info-item-title">导演：</span> ... content里<a>文本 或纯文本
                m = re.search(r'module-info-item-title">\s*' + label +
                              r'[\s\S]*?module-info-item-content">([\s\S]*?)</div>', html)
                if not m:
                    return ""
                seg = m.group(1)
                items = re.findall(r'<a[^>]*>([^<]+)</a>', seg)
                if items:
                    return "/".join(x.strip() for x in items if x.strip())
                return re.sub(r'<[^>]+>', '', seg).strip()

            plot = g(r'module-info-introduction-content">\s*<p>([\s\S]*?)</p>')
            plot = re.sub(r'<[^>]+>', '', plot).strip()

            # 播放线路: tab(data-dropdown-value=线路名) 与 panel(集列表) 按出现顺序一一对应
            # 保留全部线路(含腾讯/爱奇艺等平台源), 播放时走站点解析页
            play_from, play_url = [], []
            tabs = re.findall(
                r'<div class="module-tab-item tab-item" data-dropdown-value="([^"]*)">', html)
            panels = re.split(r'<div class="module-list sort-list', html)[1:]
            for i, seg in enumerate(panels):
                eps = re.findall(
                    r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>\s*<span>([^<]+)</span>', seg)
                if not eps:
                    continue
                fname = tabs[i].strip().replace("$", "_") if i < len(tabs) \
                    else ("线路%d" % (i + 1))
                play_from.append(fname)
                # 集名$相对路径, #连集, $$$连线路; 集名中的$替换(踩坑11)
                play_url.append("#".join(
                    "%s$%s" % (n.strip().replace("$", "_"), h) for h, n in eps))
            if not play_from:
                # 极端兜底: 无线路时不至于白屏
                play_from = ["LZ线路"]
                play_url = ["第01集$/vodplay/%s-1-1.html" % vod_id]

            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": tname,
                "vod_year": year,
                "vod_area": area,
                "vod_remarks": labeled("备注"),
                "vod_director": labeled("导演"),
                "vod_actor": labeled("主演"),
                "vod_content": (DISCLAIMER + "\n" + plot).strip(),
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]}
        except Exception as e:
            print("[QianQian] detailContent error:", e)
            return result

    # ---------- 播放 ----------

    @staticmethod
    def _decode_play_url(s):
        # encrypt=2: base64 -> unquote(最多2次) -> 真实地址
        s = (s or "").strip()
        if not s:
            return ""
        try:
            s = base64.b64decode(s).decode("utf-8", "ignore")
        except Exception:
            pass
        for _ in range(2):
            if "%" not in s:
                break
            d = unquote(s)
            if d == s:
                break
            s = d
        return s.strip()

    def _platform_resolve(self, page_url):
        """平台播放页 → 站点解析页两步流程 → 真实m3u8直链(失败返回"")
        解析服务对首次链接要现场解析(可能>20s), 结果有缓存 → 超时后重试通常秒回"""
        u1 = self.PARSE_URL + quote(page_url, safe="")
        tos = [30, 20]   # 首次冷解析可能>25s, 重试走缓存会快; 总上限~50s
        try:
            import requests
            for attempt, to in enumerate(tos):
                try:
                    sess = requests.Session()
                    sess.verify = False
                    sess.headers.update({"User-Agent": self.UA, "Referer": self.HOST + "/"})
                    r1 = sess.get(u1, timeout=to)
                    m = re.search(r'apiToken:\s*"([^"]+)"', r1.text or "")
                    if not m:
                        print("[QianQian] resolve: no token (未授权页?)")
                        return ""
                    r2 = sess.get(self.PARSE_PAGE + "/api/resolve.php?token=" + quote(m.group(1), safe=""),
                                  headers={"Referer": u1, "X-Requested-With": "XMLHttpRequest"},
                                  timeout=to)
                    try:
                        data = r2.json()
                    except Exception:
                        data = {}
                    if str(data.get("code")) == "200":
                        return str(data.get("url") or "").strip()
                    # 接口明确"无法解析"(404)是片源问题, 重试无意义
                    print("[QianQian] resolve fail:", data.get("code"), data.get("msg"))
                    return ""
                except Exception as e:
                    print("[QianQian] resolve timeout, retry%d: %s" % (attempt, str(e)[:70]))
            return ""
        except ImportError:
            pass  # 无requests, 走urllib会话
        except Exception as e:
            print("[QianQian] resolve error:", e)
            return ""
        # urllib + cookiejar 会话版(同样重试)
        for attempt, to in enumerate(tos):
            try:
                import http.cookiejar, ssl
                import urllib.request
                cj = http.cookiejar.CookieJar()
                ctx = ssl._create_unverified_context()
                op = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(cj),
                    urllib.request.HTTPSHandler(context=ctx))
                req1 = urllib.request.Request(u1, headers={"User-Agent": self.UA, "Referer": self.HOST + "/"})
                html = op.open(req1, timeout=to).read().decode("utf-8", "ignore")
                m = re.search(r'apiToken:\s*"([^"]+)"', html)
                if not m:
                    return ""
                req2 = urllib.request.Request(
                    self.PARSE_PAGE + "/api/resolve.php?token=" + quote(m.group(1), safe=""),
                    headers={"User-Agent": self.UA, "Referer": u1,
                             "X-Requested-With": "XMLHttpRequest"})
                data = json.loads(op.open(req2, timeout=to).read().decode("utf-8", "ignore"))
                if str(data.get("code")) == "200":
                    return str(data.get("url") or "").strip()
                return ""
            except Exception as e:
                print("[QianQian] resolve(urllib) retry%d: %s" % (attempt, str(e)[:70]))
        return ""

    def _probe_alive(self, direct):
        """探测解析直链的第一个分片是否可下载(解析服务缓存源可能已失效)
        活->True; 死/异常->False"""
        try:
            from urllib.parse import urljoin
            rsp = self.fetch(direct, headers={"User-Agent": self.UA}, timeout=15)
            body = rsp.text or ""
            segs = [l.strip() for l in body.splitlines()
                    if l.strip() and not l.strip().startswith("#")]
            if not segs:
                return False
            su = urljoin(direct, segs[0])
            r2 = self.fetch(su, headers={"User-Agent": self.UA}, timeout=15)
            data = getattr(r2, "content", None) or b""
            return len(data) > 1000
        except Exception:
            return False

    def playerContent(self, flag, vid, vip_flags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        try:
            play = self._pick_first_id(vid)
            if "$" in play:
                play = play.split("$")[-1]
            play = play.strip()
            if not play:
                return result
            if not play.startswith("http"):
                if not play.startswith("/"):
                    play = "/" + play
                play = self.HOST + play
            html = self._get(play)
            m = re.search(r'var\s+player_data\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
            data = {}
            if m:
                try:
                    data = json.loads(m.group(1))
                except Exception:
                    data = {}
            real = self._decode_play_url(str(data.get("url") or ""))
            result["url"] = real
            low = real.lower()
            # 直链(m3u8/mp4等) → parse=0 硬解
            if low.startswith("http") and any(
                    x in low for x in (".m3u8", ".mp4", ".flv", ".ts")):
                result["parse"] = 0
                result["jx"] = 0
            elif low.startswith("http"):
                # 平台播放页(v.qq.com/iqiyi/youku等) → 站点解析页两步流程取真实直链
                direct = self._platform_resolve(real)
                if direct:
                    # 探测分片活性: 解析服务的缓存源可能已失效(实测出现过),
                    # 死源返回空地址让客户端秒切线路, 不给用户0KB/s转圈
                    if self._probe_alive(direct):
                        # 分片是"PNG伪装壳"(真TS藏在壳后), 经本地代理剥壳播放
                        # ★ FongMi约定: proxy://do=py&... 才会路由到py爬虫的localProxy
                        result["url"] = ("proxy://do=py&type=m3u8&url="
                                         + quote(direct, safe=""))
                        result["parse"] = 0
                        result["jx"] = 0
                    else:
                        print("[QianQian] 分片已失效, 切线路: %s" % direct[:60])
                        result["url"] = ""
                        result["parse"] = 1
                        result["jx"] = 1
                else:
                    # 解析失败(超时/片源不支持): 返回空地址让客户端自动换线路
                    # (嗅探解析页地址实测播不动, 只会卡0KB/s)
                    result["url"] = ""
                    result["parse"] = 1
                    result["jx"] = 1
            else:
                result["parse"] = 0
                result["jx"] = 0
            # 踩坑5: py源 header 必须是 json.dumps 字符串
            result["header"] = json.dumps(
                {"User-Agent": self.UA, "Referer": self.HOST + "/"}, ensure_ascii=False)
            return result
        except Exception as e:
            print("[QianQian] playerContent error:", e)
            return result

    # ---------- 本地代理: 平台线路"PNG伪装壳"剥壳 ----------
    # 站点解析出的m3u8分片是伪装的PNG图片(真TS藏在IEND+CRC之后),
    # 只能经脚本本地代理(fetch原始分片->剥壳->吐TS)播放

    @staticmethod
    def _strip_png(data):
        # PNG伪装壳 -> 真TS: 壳厚度不定(alicdn贴IEND+8, chaoxing在+23),
        # 通用算法: IEND之后扫描"连续3个188间隔的0x47"确定TS起点
        if not data:
            return data
        if data[:1] == b"\x47":
            return data
        i = data.find(b"IEND")
        if i < 0:
            return data
        start = i + 4   # 跳过IEND类型名(CRC等后面的杂项统一扫描)
        limit = min(len(data) - 3 * 188, i + 256)
        for off in range(start, limit):
            if (data[off] == 0x47 and data[off + 188] == 0x47
                    and data[off + 376] == 0x47):
                return data[off:]
        return data

    def _proxy_fetch(self, url):
        # 分片CDN(alicdn/chaoxing/kuaishou等)实测: 裸UA放行,
        # 带外部Referer会被部分CDN拒403, 所以这里只带UA
        rsp = self.fetch(url, headers={"User-Agent": self.UA}, timeout=self.timeout)
        return getattr(rsp, "content", None) or (rsp.text or "").encode("utf-8", "ignore")

    def _rewrite_m3u8(self, base_url, text):
        from urllib.parse import urljoin
        out, pending = [], None   # pending = 待配对的 #EXTINF
        segs, drop = [], 0
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#EXTINF"):
                pending = s
                continue
            if s.startswith("#"):
                out.append(ln)
                continue
            absu = urljoin(base_url, s)
            segs.append((pending, absu))
            pending = None
        # ts.php 分片是过期签名干扰(实测404), 有其他正常分片时剔除
        real = [x for x in segs if "ts.php" not in x[1]]
        if len(real) >= max(1, len(segs) // 2):
            segs, drop = real, len(segs) - len(real)
        if drop:
            print("[QianQian] proxy: 剔除 %d 个 ts.php 干扰分片" % drop)
        for ext, u in segs:
            if ext:
                out.append(ext)
            # 客户端本地代理固定用 do=py, 相对路径自动落到 127.0.0.1:9978
            out.append("/proxy?do=py&type=ts&url=" + quote(u, safe=""))
        return "\n".join(out) + "\n"

    def localProxy(self, param):
        # 返回约定: [code, contentType, body]
        try:
            p = param or {}
            if isinstance(p, str):
                from urllib.parse import parse_qs
                p = {k: v[0] for k, v in parse_qs(p).items()}
            t = p.get("type", "ts")
            u = p.get("url", "")
            if not u:
                return [404, "text/plain", b"not found"]
            if t == "m3u8":
                raw = self._proxy_fetch(u)
                body = self._rewrite_m3u8(u, raw.decode("utf-8", "ignore"))
                return [200, "application/vnd.apple.mpegurl", body.encode("utf-8")]
            raw = self._proxy_fetch(u)
            ts = self._strip_png(raw)
            if not ts:
                return [404, "text/plain", b"empty"]
            return [200, "video/mp2t", ts]
        except Exception as e:
            print("[QianQian] localProxy error:", e)
            return [404, "text/plain", b"error"]

    # ---------- 杂项 ----------

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".ts"))

    def manualVideoCheck(self):
        return False
