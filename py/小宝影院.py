# -*- coding: utf-8 -*-
# 小宝影院 https://www.xiaobaotv.com/ TVBox 蜘蛛
# 标准 MacCMS 站（mytheme 模板）：5 分类；列表 /vod/type/{id}[-{pg}].html；
# 二级筛选走 /vod/show/ 路由；详情 /vod/detail/id/{id}.html；
# 播放 /vod/play/{id}-{sid}-{nid}.html，player_aaaa JSON 中 url 即 m3u8 直链
#
# 【反爬适配】网站启用了 Cloudflare WAF，必须使用 curl_cffi 模拟 Chrome TLS 指纹
# 若环境未安装 curl_cffi，会自动回退到 requests（此时极易被拦截，列表可能为空）
try:
    from curl_cffi import requests as _curl_requests
    _HAS_CURL_CFFI = True
except Exception:
    try:
        import requests as _curl_requests
    except Exception:
        _curl_requests = None
    _HAS_CURL_CFFI = False

import re
import json
import base64
from urllib.parse import quote, unquote
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "小宝影院"

    def init(self, extend=""):
        self.host = "https://www.xiaobaotv.com"

        # ============ 核心：用 curl_cffi 模拟 Chrome 绕过 Cloudflare ============
        if _HAS_CURL_CFFI:
            try:
                self.session = _curl_requests.Session(impersonate="chrome120")
            except Exception:
                try:
                    self.session = _curl_requests.Session(impersonate="chrome110")
                except Exception:
                    self.session = _curl_requests.Session()
        else:
            self.session = _curl_requests.Session()

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.host + "/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
        })

        # 先访问一次首页，走通 Cloudflare 的握手，拿到 cf_clearance（如果有）
        try:
            self.session.get(self.host + "/", timeout=20)
        except Exception:
            pass

        self._filter_cache = {}
        return {}

    CATS = [
        ("1", "电影"),
        ("2", "电视剧"),
        ("3", "动漫"),
        ("4", "综艺"),
        ("11", "短剧"),
    ]

    FILTERS = {
        "1": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "动作片", "v": "101"},
                {"n": "喜剧片", "v": "102"}, {"n": "爱情片", "v": "103"},
                {"n": "科幻片", "v": "104"}, {"n": "剧情片", "v": "105"},
                {"n": "悬疑片", "v": "106"}, {"n": "惊悚片", "v": "107"},
                {"n": "恐怖片", "v": "108"}, {"n": "犯罪片", "v": "109"},
                {"n": "冒险片", "v": "111"}, {"n": "奇幻片", "v": "112"},
                {"n": "灾难片", "v": "113"}, {"n": "战争片", "v": "114"},
                {"n": "动画电影片", "v": "115"}, {"n": "歌舞片", "v": "116"},
                {"n": "网络电影片", "v": "117"}, {"n": "同性片", "v": "118"},
                {"n": "经典片", "v": "121"}, {"n": "其它片", "v": "122"},
                {"n": "记录片", "v": "124"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""}, {"n": "爱情", "v": "爱情"},
                {"n": "古装", "v": "古装"}, {"n": "动作", "v": "动作"},
                {"n": "伦理", "v": "伦理"}, {"n": "悬疑", "v": "悬疑"},
                {"n": "犯罪", "v": "犯罪"}, {"n": "谍战", "v": "谍战"},
                {"n": "历史", "v": "历史"}, {"n": "喜剧", "v": "喜剧"},
                {"n": "奇幻", "v": "奇幻"}, {"n": "科幻", "v": "科幻"},
                {"n": "家庭", "v": "家庭"}, {"n": "青春", "v": "青春"},
                {"n": "剧情", "v": "剧情"}, {"n": "冒险", "v": "冒险"},
                {"n": "纪录", "v": "纪录"}, {"n": "动画", "v": "动画"},
                {"n": "人物", "v": "人物"}, {"n": "文化", "v": "文化"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""}, {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"}, {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"}, {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "2": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "国产剧", "v": "201"},
                {"n": "港台剧", "v": "202"}, {"n": "台湾剧", "v": "203"},
                {"n": "日韩剧", "v": "204"}, {"n": "日本剧", "v": "205"},
                {"n": "欧美剧", "v": "206"}, {"n": "泰国剧", "v": "207"},
                {"n": "海外剧", "v": "208"}, {"n": "新马泰剧", "v": "209"},
                {"n": "其他剧", "v": "210"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""}, {"n": "爱情", "v": "爱情"},
                {"n": "古装", "v": "古装"}, {"n": "悬疑", "v": "悬疑"},
                {"n": "都市", "v": "都市"}, {"n": "喜剧", "v": "喜剧"},
                {"n": "战争", "v": "战争"}, {"n": "剧情", "v": "剧情"},
                {"n": "青春", "v": "青春"}, {"n": "历史", "v": "历史"},
                {"n": "网剧", "v": "网剧"}, {"n": "奇幻", "v": "奇幻"},
                {"n": "冒险", "v": "冒险"}, {"n": "励志", "v": "励志"},
                {"n": "犯罪", "v": "犯罪"}, {"n": "商战", "v": "商战"},
                {"n": "恐怖", "v": "恐怖"}, {"n": "穿越", "v": "穿越"},
                {"n": "农村", "v": "农村"}, {"n": "人物", "v": "人物"},
                {"n": "商业", "v": "商业"}, {"n": "生活", "v": "生活"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""}, {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"}, {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"}, {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "3": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "国产动漫", "v": "301"},
                {"n": "日韩动漫", "v": "302"}, {"n": "港台动漫", "v": "304"},
                {"n": "欧美动漫", "v": "306"}, {"n": "其它动漫", "v": "310"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""}, {"n": "冒险", "v": "冒险"},
                {"n": "战斗", "v": "战斗"}, {"n": "搞笑", "v": "搞笑"},
                {"n": "经典", "v": "经典"}, {"n": "科幻", "v": "科幻"},
                {"n": "玄幻", "v": "玄幻"}, {"n": "魔幻", "v": "魔幻"},
                {"n": "武侠", "v": "武侠"}, {"n": "恋爱", "v": "恋爱"},
                {"n": "推理", "v": "推理"}, {"n": "日常", "v": "日常"},
                {"n": "校园", "v": "校园"}, {"n": "悬疑", "v": "悬疑"},
                {"n": "真人", "v": "真人"}, {"n": "历史", "v": "历史"},
                {"n": "竞技", "v": "竞技"}, {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""}, {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"}, {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"}, {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "4": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "大陆综艺", "v": "401"},
                {"n": "日韩综艺", "v": "402"}, {"n": "港台综艺", "v": "404"},
                {"n": "欧美综艺", "v": "406"}, {"n": "新马泰综艺", "v": "407"},
                {"n": "其它综艺", "v": "410"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""}, {"n": "游戏", "v": "游戏"},
                {"n": "脱口秀", "v": "脱口秀"}, {"n": "音乐", "v": "音乐"},
                {"n": "情感", "v": "情感"}, {"n": "生活", "v": "生活"},
                {"n": "职场", "v": "职场"}, {"n": "真人秀", "v": "真人秀"},
                {"n": "搞笑", "v": "搞笑"}, {"n": "公益", "v": "公益"},
                {"n": "艺术", "v": "艺术"}, {"n": "访谈", "v": "访谈"},
                {"n": "益智", "v": "益智"}, {"n": "体育", "v": "体育"},
                {"n": "少儿", "v": "少儿"}, {"n": "时尚", "v": "时尚"},
                {"n": "人物", "v": "人物"}, {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""}, {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"}, {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"}, {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "11": [
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""}, {"n": "古装", "v": "古装"},
                {"n": "复仇", "v": "复仇"}, {"n": "强者", "v": "强者"},
                {"n": "悬疑", "v": "悬疑"}, {"n": "甜宠", "v": "甜宠"},
                {"n": "神豪", "v": "神豪"}, {"n": "穿越", "v": "穿越"},
                {"n": "虐恋", "v": "虐恋"}, {"n": "逆袭", "v": "逆袭"},
                {"n": "重生", "v": "重生"}, {"n": "萌宝", "v": "萌宝"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"}, {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""}, {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"}, {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"}, {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
    }

    # ---------- 基础 ----------
    def _fetch(self, url, params=None, referer=None):
        try:
            headers = {}
            if referer:
                headers["Referer"] = referer
            r = self.session.get(url, params=params, timeout=20,
                                 headers=headers if headers else None)
            if r.status_code != 200:
                return ""
            # Cloudflare 拦截页特征
            txt = r.text
            if "Sorry, you have been blocked" in txt or \
               "Attention Required! | Cloudflare" in txt:
                print("[%s] 被 Cloudflare 拦截: %s" % (self.getName(), url))
                return ""
            r.encoding = "utf-8"
            return txt
        except Exception as e:
            print("[%s] _fetch 异常 %s: %s" % (self.getName(), url, e))
            return ""

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self.host + (u if u.startswith("/") else "/" + u)

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        if not html:
            return []
        vods = []
        seen = set()
        for m in re.finditer(
                r'<a\b[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'href="([^"]+)"', tag)
            if not hm:
                continue
            href = hm.group(1)
            vid_m = re.search(r'/(\d+)\.html', href)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue

            tm = re.search(r'title="([^"]*)"', tag)
            if not tm:
                continue
            title = tm.group(1).strip()
            if not title:
                continue
            seen.add(vid)

            sm = re.search(r'data-original="([^"]+)"', tag)
            if not sm:
                sm = re.search(r'data-src="([^"]+)"', tag)
            if not sm:
                sm = re.search(r'src="([^"]+)"', tag)

            tail = html[m.end():m.end() + 800]
            rm = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', tail)

            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs(sm.group(1).strip() if sm else ""),
                "vod_remarks": (rm.group(1).strip() if rm else ""),
            })
        return vods

    # ---------- 二级分类 ----------
    def _opt_keyval(self, href, parent):
        u = unquote(href)
        m = re.search(r"/vod/show/id/(\d+)\.html", u)
        if m:
            return ("child", "") if m.group(1) == parent else ("child", m.group(1))
        m = re.search(r"/vod/show/class/([^/]+)/id/", u)
        if m:
            return ("class", m.group(1))
        m = re.search(r"/vod/show/area/([^/]+)/id/", u)
        if m:
            return ("area", m.group(1))
        m = re.search(r"/vod/show/id/\d+/year/(\d+)", u)
        if m:
            return ("year", m.group(1))
        m = re.search(r"/vod/show/id/\d+/lang/([^/]+?)(?:\.html|/|$)", u)
        if m:
            return ("lang", m.group(1))
        m = re.search(r"/vod/show/by/([^/]+)/id/", u)
        if m:
            return ("by", m.group(1))
        return (None, None)

    def _load_filters(self, cid):
        if cid in self._filter_cache:
            return self._filter_cache[cid]
        html = self._fetch("%s/vod/type/%s.html" % (self.host, cid))
        groups = []
        seen_keys = set()
        for um in re.finditer(
                r'<ul class="myui-screen__list[^"]*"[^>]*>(.*?)</ul>', html, re.S):
            block = um.group(1)
            dm = re.search(r'<li[^>]*>\s*<a[^>]*class="[^"]*text-muted[^"]*"[^>]*>([^<]{1,12})</a>',
                           block)
            dim_name = dm.group(1).strip() if dm else "筛选"
            items = []
            fkey = None
            for href, nm in re.findall(r'<a[^>]*href="(/vod/show/[^"]+)"[^>]*>([^<]+)</a>',
                                       block):
                if nm.strip() == "全部":
                    continue
                key, _ = self._opt_keyval(href, cid)
                if key:
                    fkey = key
                    break
            if not fkey:
                continue
            for href, nm in re.findall(r'<a[^>]*href="(/vod/show/[^"]+)"[^>]*>([^<]+)</a>',
                                       block):
                key, val = self._opt_keyval(href, cid)
                nm = nm.strip()
                if nm == "全部":
                    if not any(x["v"] == "" for x in items):
                        items.insert(0, {"n": "全部", "v": ""})
                    continue
                if key != fkey:
                    continue
                if nm and all(x["n"] != nm for x in items):
                    items.append({"n": nm, "v": val})
            if fkey and fkey not in seen_keys and len(items) > 1:
                seen_keys.add(fkey)
                groups.append({"key": fkey, "name": dim_name, "value": items})
        self._filter_cache[cid] = groups
        return groups

    def homeContent(self, filter=False):
        classes = [{"type_id": cid, "type_name": cn} for cid, cn in self.CATS]
        result = {"class": classes}
        if filter:
            result["filters"] = self.FILTERS
        return result

    def homeVideoContent(self):
        html = self._fetch(self.host + "/")
        return {"list": self._parse_cards(html), "parse": 0, "jx": 0}

    def _show_url(self, cid, pg, extend):
        ext = extend if isinstance(extend, dict) else {}
        child = (ext.get("child") or "").strip()
        base = "/vod/show/id/%s" % (child if child else cid)
        for key, tmpl in (("class", "/class/%s"), ("area", "/area/%s"),
                          ("year", "/year/%s"), ("lang", "/lang/%s"),
                          ("by", "/by/%s")):
            v = (ext.get(key) or "").strip()
            if v:
                base += tmpl % quote(v)
        if pg > 1:
            base += "/page/%d" % pg
        return self.host + base + ".html"

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            cid = tid if any(tid == c for c, _ in self.CATS) else "1"
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}

            urls = []
            if extend and any((extend.get(k) or "").strip()
                              for k in ("child", "class", "area", "year", "lang", "by")):
                urls.append(self._show_url(cid, pg, extend))
            else:
                # 多 URL 兼容，同时注意 MacCMS 有 -N.html 与 /page/N 两种分页风格
                if pg > 1:
                    urls.append("%s/vod/type/id/%s/page/%d.html" % (self.host, cid, pg))
                    urls.append("%s/vod/type/%s-%d.html" % (self.host, cid, pg))
                    urls.append("%s/vod/type/id/%s.html?page=%d" % (self.host, cid, pg))
                else:
                    urls.append("%s/vod/type/id/%s.html" % (self.host, cid))
                    urls.append("%s/vod/type/%s.html" % (self.host, cid))

            vods = []
            html = ""
            for url in urls:
                html = self._fetch(url)
                if html and "myui-vodlist__thumb" in html:
                    vods = self._parse_cards(html)
                    if vods:
                        break

            pagecount = pg
            if html:
                pages = re.findall(r'/page/(\d+)', html)
                if not pages:
                    pages = re.findall(r'/vod/type/\d+-(\d+)\.html', html)
                if pages:
                    pagecount = max(int(p) for p in pages)
                elif len(vods) >= 20:
                    pagecount = pg + 1

            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[%s] categoryContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ---------- 简介提取 ----------
    def _extract_desc(self, html):
        desc = ""
        patterns = [
            r'<div[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*(?:vod-content|vod_content|detail-content|detail_content|desc)[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*(?:desc|content|detail)[^"]*"[^>]*>(.*?)</p>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                desc = m.group(1)
                break

        if not desc:
            m = re.search(
                r'(?:剧情介绍|简介|剧情)[：:]\s*(?:</span>)?\s*(?:<p[^>]*>|<div[^>]*>)?(.*?)(?:</div>|</p>|<div|详情|立即播放|$)',
                html, re.S)
            if m:
                desc = m.group(1)

        if not desc:
            return ""

        desc = re.sub(r'<[^>]+>', '', desc)
        desc = (desc.replace('&nbsp;', ' ').replace('&amp;', '&')
                    .replace('&quot;', '"').replace('&#39;', "'")
                    .replace('&lt;', '<').replace('&gt;', '>'))
        for sw in ['详情', '立即播放', '报错', '收藏', '扫一扫',
                   '排序', '播放地址', '第01集', '第1集']:
            if sw in desc:
                desc = desc.split(sw)[0]
        desc = re.sub(r'\s+', ' ', desc).strip()
        return desc[:2000]

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vods = []
        try:
            vid = re.sub(r"\D", "", ids[0] if ids else "")
            if not vid:
                return {"list": []}

            urls = [
                "%s/vod/detail/id/%s.html" % (self.host, vid),
                "%s/vod/detail/%s.html" % (self.host, vid),
            ]
            html = ""
            for url in urls:
                html = self._fetch(url)
                if html and ("player_aaaa" in html or "myui-content__thumb" in html):
                    break
            if not html:
                return {"list": []}

            vod = {"vod_id": vid}
            m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            if not m:
                m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else vid

            m = re.search(r'myui-content__thumb.*?data-original="([^"]+)"', html, re.S)
            if not m:
                m = re.search(r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"', html)
            vod["vod_pic"] = self._abs(m.group(1).strip() if m else "")

            m = re.search(r'<span class="text-red">([^<]*)</span>', html)
            vod["vod_remarks"] = m.group(1).strip() if m else ""

            vod["vod_content"] = self._extract_desc(html)

            actors = re.findall(r'/search/actor/[^"]*"[^>]*>([^<]+)</a>', html)
            if not actors:
                actors = re.findall(r'/vod/search/actor[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_actor"] = ",".join(dict.fromkeys(a.strip() for a in actors if a.strip()))[:200]

            directors = re.findall(r'/search/director/[^"]*"[^>]*>([^<]+)</a>', html)
            if not directors:
                directors = re.findall(r'/vod/search/director[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_director"] = ",".join(dict.fromkeys(d.strip() for d in directors if d.strip()))[:200]

            # 年份 / 地区 / 类型 / 语言
            def _field(label):
                pat = r'{}[：:]\s*(?:</span>)?\s*(?:<a[^>]*>)?(.*?)(?:</a>|<br|<p|</div|</li|</span>|$)'.format(label)
                mm = re.search(pat, html, re.S)
                if mm:
                    t = re.sub(r'<[^>]+>', '', mm.group(1))
                    return t.replace('&nbsp;', ' ').strip()
                return ""

            vod["vod_year"] = _field("年份")
            vod["vod_area"] = _field("地区")
            vod["vod_lang"] = _field("语言")
            tname = _field("类型")
            if tname:
                vod["type_name"] = tname

            # 播放源
            play_from, play_url = [], []
            tabs = re.findall(
                r'<a[^>]*href="#playlist(\d+)"[^>]*>([^<]+)</a>', html)
            for num, src_name in tabs:
                src_name = src_name.strip()
                start = html.find('id="playlist%s"' % num)
                if start < 0:
                    continue
                nxt_m = re.search(r'id="playlist\d+"', html[start + 10:])
                end = start + 10 + nxt_m.start() if nxt_m else len(html)
                seg = html[start:end]
                eps = []
                for href, nm in re.findall(
                        r'<a[^>]*href="(/vod/play/\d+-\d+-\d+\.html)"[^>]*>([^<]*)</a>',
                        seg):
                    nm = nm.strip() or "正片"
                    eps.append("%s$%s" % (nm, self._abs(href)))
                if eps:
                    play_from.append(src_name)
                    play_url.append("#".join(eps))

            if not play_from:
                all_eps = re.findall(
                    r'<a[^>]*href="(/vod/play/(\d+)-([a-z0-9]+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                    html)
                groups = {}
                for href, _vid, sid, _nid, nm in all_eps:
                    groups.setdefault(sid, []).append(
                        ("%s$%s" % (nm.strip() or "正片", self._abs(href))))
                for sid in sorted(groups.keys()):
                    play_from.append("线路%s" % sid)
                    play_url.append("#".join(x[0] for x in groups[sid]))

            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)
            vods.append(vod)
        except Exception as e:
            print("[%s] detailContent 异常: %s" % (self.getName(), e))
        return {"list": vods}

    def searchContent(self, key, quick=False, pg=1):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            html = self._fetch("%s/search.html" % self.host,
                               params={"wd": key, "submit": ""})
            vods = self._parse_cards(html)
            return {"list": vods, "page": pg, "pagecount": 1,
                    "limit": 90, "total": len(vods)}
        except Exception as e:
            print("[%s] searchContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            pid = (id or "").strip()
            if "$" in pid:
                pid = pid.split("$")[-1]
            if not pid:
                return result

            if pid.startswith("http") and (".m3u8" in pid or ".mp4" in pid):
                result["url"] = pid
            else:
                page_url = pid if pid.startswith("http") else self._abs(pid)
                html = self._fetch(page_url)
                m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>',
                              html, re.S)
                if not m:
                    m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                    except Exception:
                        data = {}
                    url = (data.get("url") or "").replace("\\/", "/")
                    if data.get("encrypt") == 1 and url:
                        try:
                            url = base64.b64decode(
                                url + "=" * (-len(url) % 4)
                            ).decode("utf-8", "replace").replace("\\/", "/")
                        except Exception:
                            pass
                    if url.startswith("//"):
                        url = "https:" + url
                    if url and (".m3u8" in url or ".mp4" in url):
                        result["url"] = url
            if result["url"]:
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
            return result
        except Exception as e:
            print("[%s] playerContent 异常: %s" % (self.getName(), e))
            return result

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", ""]
