# -*- coding: utf-8 -*-
# 影子音乐 - TVBox 音乐爬虫
# 支持：网易云 / QQ音乐 / 酷狗音乐
# API: https://music.yingzi.ee/api.php  (POST + callback 参数)

import re
import sys
import json
import time
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from requests import Session, adapters
from urllib3.util.retry import Retry

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    # ==================== 初始化 ====================
    def init(self, extend=""):
        self.host = "https://music.yingzi.ee"
        self.session = Session()
        adapter = adapters.HTTPAdapter(
            max_retries=Retry(
                total=3, backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            ),
            pool_connections=30, pool_maxsize=50
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 通用请求头（含 XHR 标记，API 必需）
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.host,
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        self.session.headers.update(self.headers)

        # 网易云自己的 API 需要单独 Referer
        self.netease_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://music.163.com/",
        }

        self._cache = {}
        self._cache_ttl = 300

        # 一级分类 + 二级榜单
        # 注：netease 的两个新 ID 请你按页面实际标题修改
        self.platforms = {
            "netease": {
                "name": "网易云音乐",
                "playlists": {
                    "3778678": "热歌榜",
                    "19723756": "飙升榜",
                    "3779629": "新歌榜",
                    "2884035": "原创榜",
                    "12500142073": "新榜单1",
                    "12197785740": "新榜单2",
                },
            },
            "tencent": {
                "name": "QQ音乐",
                "playlists": {
                    "热歌": "热歌榜",
                    "新歌": "新歌榜",
                    "飙升": "飙升榜",
                    "流行": "流行榜",
                },
            },
            "kugou": {
                "name": "酷狗音乐",
                "playlists": {
                    "热歌": "热歌榜",
                    "新歌": "新歌榜",
                    "飙升": "飙升榜",
                    "DJ": "DJ榜",
                },
            },
        }

    def getName(self):
        return "影子音乐"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(mp3|m4a|flac|wav|ogg)(\?|$)', url or "", re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    # ==================== API 请求核心 ====================
    def _api_post(self, params, timeout=15):
        """
        统一 API 请求入口。
        - POST 到 /api.php?callback=xxx
        - 参数走 body
        - 优先解析 JSON，兜底剥离 JSONP
        """
        try:
            types = params.get("types", "x")
            ident = params.get("id") or params.get("name") or "x"
            callback = f"callback_{types}_{ident}"

            url = f"{self.host}/api.php?callback={callback}"
            body = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())

            r = self.session.post(url, data=body, timeout=timeout)
            if r.status_code != 200:
                print(f"[{self.getName()}] API HTTP {r.status_code} | {url}")
                return None

            text = r.text.strip()

            # 优先直接 JSON
            try:
                return json.loads(text)
            except Exception:
                pass

            # 兜底：剥离 JSONP
            m = re.match(r'^[^(]+\((.*)\)\s*;?\s*$', text, re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass

            print(f"[{self.getName()}] 无法解析响应 | 前 200 字: {text[:200]}")
            return None
        except Exception as e:
            print(f"[{self.getName()}] _api_post 异常: {e} | params={params}")
            return None

    # ==================== 首页 ====================
    def homeContent(self, filter=False):
        classes = []
        filters = {}
        for source, cfg in self.platforms.items():
            classes.append({"type_name": cfg["name"], "type_id": source})
            fvals = [{"n": v, "v": k} for k, v in cfg["playlists"].items()]
            if fvals:
                filters[source] = [{"key": "list", "name": "榜单", "value": fvals}]
        return {"class": classes, "filters": filters, "list": []}

    def homeVideoContent(self):
        """首页推荐：网易云热歌榜前 30 首"""
        try:
            songs = self._get_netease_playlist("3778678")
            items = []
            for song in songs[:30]:
                try:
                    sid = str(song.get("id", ""))
                    name = song.get("name", "未知")
                    ar = song.get("ar") or []
                    artists = ", ".join([a.get("name", "") for a in ar])
                    al = song.get("al") or {}
                    pic = al.get("picUrl", "") or ""
                    sign = song.get("sign", "")
                    vod_id = self.e64(f"netease###{sid}###{sign}###{name}###{pic}")
                    display_name = f"{name} - {artists}" if artists else name
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": display_name,
                        "vod_pic": pic,
                        "vod_remarks": "网易云热歌",
                        "style": {"type": "rect", "ratio": 1},
                    })
                except Exception as e:
                    print(f"[{self.getName()}] homeVideo 单条解析异常: {e}")
            return {"list": items}
        except Exception as e:
            print(f"[{self.getName()}] homeVideoContent 异常: {e}")
            return {"list": []}

    # ==================== 分类页 ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg or 1)
        extend = extend or {}
        source = tid

        # 默认榜单
        list_id = extend.get("list", "")
        if not list_id and source in self.platforms:
            list_id = next(iter(self.platforms[source]["playlists"].keys()))

        songs = []
        if source == "netease" and str(list_id).isdigit():
            songs = self._get_netease_playlist(list_id)
        elif source in ("tencent", "kugou"):
            # QQ/酷狗用搜索模拟榜单
            songs = self._do_search(source, list_id, pg)

        if not songs:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 100, "total": 0}

        items = []
        for song in songs[:200]:
            try:
                source_of_song = song.get("source", source)
                sid = str(song.get("id", ""))
                name = song.get("name", "未知")

                ar = song.get("ar") or song.get("artist") or []
                if isinstance(ar, list) and ar and isinstance(ar[0], dict):
                    artists = ", ".join([a.get("name", "") for a in ar])
                elif isinstance(ar, list):
                    artists = ", ".join([str(x) for x in ar])
                else:
                    artists = ""

                al = song.get("al") or {}
                pic = al.get("picUrl") or song.get("pic") or self._get_pic(source_of_song, song)
                sign = song.get("sign", "")

                vod_id = self.e64(f"{source_of_song}###{sid}###{sign}###{name}###{pic}")
                display_name = f"{name} - {artists}" if artists else name
                items.append({
                    "vod_id": vod_id,
                    "vod_name": display_name,
                    "vod_pic": pic or "",
                    "style": {"type": "rect", "ratio": 1},
                })
            except Exception as e:
                print(f"[{self.getName()}] 分类页单条解析异常: {e}")

        pagecount = 999 if source in ("tencent", "kugou") else 1
        return {
            "list": items,
            "page": pg,
            "pagecount": pagecount,
            "limit": 100,
            "total": len(items),
        }

    # ==================== 详情页 ====================
    def detailContent(self, ids):
        try:
            raw = self.d64(ids[0])
        except Exception:
            return {"list": []}

        parts = raw.split("###")
        # source###sid###sign###name###pic
        if len(parts) == 5:
            source, sid, sign, name, pic = parts
        elif len(parts) == 4:
            source, sid, name, pic = parts
            sign = self._get_sign(source, sid, name)
        else:
            return {"list": []}

        play_id = self.e64(f"{source}###{sid}###{sign}###{name}")
        vod = {
            "vod_id": ids[0],
            "vod_name": name,
            "vod_pic": pic or "",
            "vod_remarks": self.platforms.get(source, {}).get("name", source),
            "vod_content": f"平台：{self.platforms.get(source, {}).get('name', source)}\n歌曲：{name}",
            "vod_play_from": source,
            "vod_play_url": f"播放${play_id}",
        }
        return {"list": [vod]}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg or 1)
        all_songs = []

        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(self._do_search, s, key, pg): s for s in self.platforms.keys()}
            for f in as_completed(futures):
                try:
                    all_songs.extend(f.result() or [])
                except Exception as e:
                    print(f"[{self.getName()}] search 子任务异常: {e}")

        # 去重
        seen = set()
        unique = []
        for s in all_songs:
            k = f"{s.get('source')}:{s.get('id')}"
            if k not in seen:
                seen.add(k)
                unique.append(s)

        res = []
        for s in unique:
            try:
                source = s.get("source", "")
                sid = str(s.get("id", ""))
                name = s.get("name", "未知")
                ar = s.get("ar") or s.get("artist") or []
                if isinstance(ar, list) and ar and isinstance(ar[0], dict):
                    artists = ", ".join([a.get("name", "") for a in ar])
                elif isinstance(ar, list):
                    artists = ", ".join([str(x) for x in ar])
                else:
                    artists = ""
                pic = self._get_pic(source, s)
                sign = s.get("sign", "")
                vod_id = self.e64(f"{source}###{sid}###{sign}###{name}###{pic}")
                res.append({
                    "vod_id": vod_id,
                    "vod_name": f"{name} - {artists}" if artists else name,
                    "vod_pic": pic,
                    "style": {"type": "rect", "ratio": 1},
                })
            except Exception as e:
                print(f"[{self.getName()}] 搜索结果单条解析异常: {e}")

        return {
            "list": res,
            "page": pg,
            "pagecount": 999,
            "limit": 100,
            "total": len(res),
        }

    # ==================== 播放器 ====================
    def playerContent(self, flag, id, vipFlags=None):
        try:
            raw = self.d64(id)
        except Exception:
            return {"parse": 0, "url": "", "header": self.headers}

        parts = raw.split("###")
        if len(parts) >= 2:
            source = parts[0]
            sid = parts[1]
            sign = parts[2] if len(parts) >= 3 else ""
        else:
            return {"parse": 0, "url": "", "header": self.headers}

        url = self._get_play_url(source, sid, sign)
        if not url:
            return {"parse": 0, "url": "", "header": self.headers, "msg": "无法获取播放地址"}

        h = self.headers.copy()
        # 播放链接的 Referer 换成对应平台
        if "qq.com" in url or "gtimg.cn" in url:
            h["Referer"] = "https://y.qq.com/"
        elif "kugou" in url:
            h["Referer"] = "https://www.kugou.com/"
        elif "music.126.net" in url or "163.com" in url:
            h.update(self.netease_headers)

        result = {
            "parse": 0,
            "url": url,
            "header": h,
        }

        # 网易云歌词
        if source == "netease":
            lrc = self._get_netease_lyric(sid)
            if lrc:
                result["lrc"] = lrc

        return result

    # ==================== 本地代理（图片） ====================
    def localProxy(self, param):
        try:
            url = param.get("url", "")
            if not url:
                return None
            h = self.headers.copy()
            if "music.126.net" in url:
                h.update(self.netease_headers)
            elif "y.gtimg.cn" in url:
                h["Referer"] = "https://y.qq.com/"
            elif "kugou" in url:
                h["Referer"] = "https://www.kugou.com/"

            r = self.session.get(url, headers=h, timeout=10, stream=True)
            ct = r.headers.get("Content-Type", "image/jpeg")
            if "image" not in ct.lower():
                ct = "image/jpeg"
            return [200, ct, r.content, {}]
        except Exception as e:
            print(f"[{self.getName()}] localProxy 异常: {e}")
            return None

    # ==================== 内部工具 ====================

    def _get_netease_playlist(self, list_id):
        """网易云歌单 —— POST"""
        ck = f"pl_netease_{list_id}"
        cached = self._cache.get(ck)
        if cached and time.time() - cached["time"] < self._cache_ttl:
            return cached["data"]

        data = self._api_post({
            "types": "playlist",
            "id": list_id,
            "source": "netease",
        })
        if not data:
            return []

        try:
            tracks = data.get("playlist", {}).get("tracks", []) or []
            for t in tracks:
                t["source"] = "netease"
            self._cache[ck] = {"data": tracks, "time": time.time()}
            return tracks
        except Exception as e:
            print(f"[{self.getName()}] 解析歌单异常: {e}")
            return []

    def _do_search(self, source, keyword, pg):
        """搜索 —— POST"""
        ck = f"search_{source}_{keyword}_{pg}"
        cached = self._cache.get(ck)
        if cached and time.time() - cached["time"] < self._cache_ttl:
            return cached["data"]

        data = self._api_post({
            "types": "search",
            "source": source,
            "count": 30,
            "pages": pg,
            "name": keyword or "",
        })
        if not data:
            return []

        # 兼容三种返回结构
        if isinstance(data, list):
            songs = data
        elif isinstance(data, dict):
            songs = data.get("data") or data.get("songs") or data.get("list") or []
            # 有些返回 {code:200, data:{list:[...]}}
            if isinstance(songs, dict):
                songs = songs.get("list") or songs.get("songs") or []
        else:
            songs = []

        # 过滤 & 标记 source
        result = []
        for item in songs:
            if not isinstance(item, dict):
                continue
            item["source"] = source
            result.append(item)

        self._cache[ck] = {"data": result, "time": time.time()}
        return result

    def _get_sign(self, source, sid, name):
        """补全 sign（网易云/QQ/酷狗都可能需要）"""
        ck = f"sign_{source}_{sid}"
        cached = self._cache.get(ck)
        if cached and time.time() - cached["time"] < self._cache_ttl:
            return cached["data"]

        songs = self._do_search(source, name or "a", 1)
        for song in songs:
            if str(song.get("id")) == str(sid):
                sign = song.get("sign", "")
                self._cache[ck] = {"data": sign, "time": time.time()}
                return sign
        return ""

    def _get_play_url(self, source, sid, sign):
        """取播放地址 —— POST"""
        try:
            data = self._api_post({
                "types": "url",
                "id": sid,
                "source": source,
                "sign": sign or "",
            })
            if not data:
                return ""

            url = ""
            if isinstance(data, str):
                url = data
            elif isinstance(data, dict):
                url = data.get("url", "") or ""
                if not url and isinstance(data.get("data"), dict):
                    url = data["data"].get("url", "") or ""
                if not url and isinstance(data.get("data"), str):
                    url = data["data"]

            return url.replace("\\/", "/") if url else ""
        except Exception as e:
            print(f"[{self.getName()}] _get_play_url 异常: {e}")
            return ""

    def _get_netease_lyric(self, sid):
        """网易云歌词（走官方 API）"""
        try:
            r = self.session.get(
                f"https://music.163.com/api/song/lyric?id={sid}&lv=1&kv=1&tv=-1",
                headers=self.netease_headers, timeout=10
            )
            return r.json().get("lrc", {}).get("lyric", "") or ""
        except Exception:
            return ""

    def _get_pic(self, source, song):
        """封面补全"""
        # 优先 al.picUrl
        al = song.get("al") or {}
        if al.get("picUrl"):
            return al["picUrl"]

        pic_id = song.get("pic_id", "") or ""
        if source == "tencent":
            if pic_id:
                return f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{pic_id}.jpg"
            return ""
        if source == "kugou":
            if len(pic_id) >= 4:
                return (f"https://singerimg.kugou.com/uploadpic/softhead/400/"
                        f"{pic_id[:2]}/{pic_id[:4]}/{pic_id}.jpg")
            return ""
        return ""

    # ==================== Base64 ====================
    def e64(self, text):
        try:
            return base64.b64encode(text.encode("utf-8")).decode("utf-8")
        except Exception:
            return ""

    def d64(self, text):
        try:
            pad = "=" * (-len(text) % 4)
            return base64.b64decode((text + pad).encode("utf-8")).decode("utf-8")
        except Exception:
            return ""
