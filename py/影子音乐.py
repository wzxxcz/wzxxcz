# -*- coding: utf-8 -*-
# 影子音乐 - TVBox 音乐爬虫（最终完整版）
# 支持：网易云 / 酷狗音乐
# API: https://music.yingzi.ee/api.php  (POST + callback 参数)
#
# 说明：
#   - QQ 音乐已移除（服务端 API 不支持，搜索返回 []、歌单 404）
#   - 网易云走真榜单 ID，酷狗用热门歌手名作为入口
#   - 网易云封面通过官方 API 在 detail 阶段补全
#   - 缓存带自动清理，长时间运行不会内存爆

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

        # 通用请求头
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

        # 网易云官方 API 专用头
        self.netease_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://music.163.com/",
        }

        self._cache = {}
        self._cache_ttl = 300
        self._cache_max = 500

        # 平台与榜单
        # 网易云：真歌单 ID
        # 酷狗：API 无榜单，用热门歌手名做入口
        self.platforms = {
            "netease": {
                "name": "网易云音乐",
                "playlists": {
                    "3778678": "热歌榜",
                    "19723756": "飙升榜",
                    "3779629": "新歌榜",
                    "2884035": "原创榜",
                },
            },
            "kugou": {
                "name": "酷狗音乐",
                "playlists": {
                    "周杰伦": "周杰伦",
                    "林俊杰": "林俊杰",
                    "薛之谦": "薛之谦",
                    "邓紫棋": "邓紫棋",
                    "陈奕迅": "陈奕迅",
                    "李荣浩": "李荣浩",
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

    # ==================== 缓存工具 ====================
    def _cache_get(self, key):
        item = self._cache.get(key)
        if item and time.time() - item["time"] < self._cache_ttl:
            return item["data"]
        return None

    def _cache_set(self, key, data):
        now = time.time()
        self._cache[key] = {"data": data, "time": now}
        # 超过上限时清理
        if len(self._cache) > self._cache_max:
            # 先清过期的
            expired = [k for k, v in self._cache.items()
                       if now - v["time"] > self._cache_ttl]
            for k in expired:
                self._cache.pop(k, None)
            # 还多就按时间删最老的一批
            if len(self._cache) > self._cache_max:
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1]["time"])
                for k, _ in sorted_items[:100]:
                    self._cache.pop(k, None)

    # ==================== API 请求核心 ====================
    def _api_post(self, params, timeout=15):
        """
        统一 API 请求入口。
        - POST 到 /api.php?callback=xxx
        - 参数走 body
        - 优先解析 JSON，兜底剥离 JSONP
        """
        try:
            # callback 用纯时间戳，避免中文/特殊字符
            callback = f"cb_{int(time.time() * 1000)}"
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
            songs = self._get_playlist("netease", "3778678")
            items = []
            for song in songs[:30]:
                try:
                    sid = str(song.get("id", ""))
                    name = song.get("name", "未知")
                    artists = self._extract_artists(song)
                    pic = self._get_pic("netease", song)
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

        list_id = extend.get("list", "")
        if not list_id and source in self.platforms:
            list_id = next(iter(self.platforms[source]["playlists"].keys()))
        list_name = self.platforms.get(source, {}).get("playlists", {}).get(list_id, "精选")

        songs = []
        if source == "netease" and str(list_id).isdigit():
            songs = self._get_playlist("netease", list_id)
        elif source == "kugou":
            songs = self._do_search("kugou", list_id, pg)

        if not songs:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 100, "total": 0}

        items = []
        for song in songs[:200]:
            try:
                source_of_song = song.get("source", source)
                sid = str(song.get("id", ""))
                name = song.get("name", "未知")
                artists = self._extract_artists(song)
                pic = self._get_pic(source_of_song, song)
                sign = song.get("sign", "")

                vod_id = self.e64(f"{source_of_song}###{sid}###{sign}###{name}###{pic}")
                display_name = f"{name} - {artists}" if artists else name
                items.append({
                    "vod_id": vod_id,
                    "vod_name": display_name,
                    "vod_pic": pic or "",
                    "vod_remarks": list_name,
                    "style": {"type": "rect", "ratio": 1},
                })
            except Exception as e:
                print(f"[{self.getName()}] 分类页单条解析异常: {e}")

        pagecount = 999 if source == "kugou" else 1
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
        if len(parts) == 5:
            source, sid, sign, name, pic = parts
        elif len(parts) == 4:
            source, sid, name, pic = parts
            sign = self._get_sign(source, sid, name)
        else:
            return {"list": []}

        # 网易云封面补全：搜索返回的 pic_id 是纯数字，拼不出 URL
        if not pic and source == "netease":
            pic = self._get_netease_cover(sid)

        play_id = self.e64(f"{source}###{sid}###{sign}###{name}")
        vod = {
            "vod_id": ids[0],
            "vod_name": name,
            "vod_pic": pic or "",
            "vod_remarks": self.platforms.get(source, {}).get("name", source),
            "vod_content": (
                f"平台：{self.platforms.get(source, {}).get('name', source)}\n"
                f"歌曲：{name}"
            ),
            "vod_play_from": source,
            "vod_play_url": f"播放${play_id}",
        }
        return {"list": [vod]}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg or 1)
        all_songs = []

        # 只搜网易云 + 酷狗
        sources = ["netease", "kugou"]
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(self._do_search, s, key, pg): s for s in sources}
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
                artists = self._extract_artists(s)
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
            return {
                "parse": 0, "url": "",
                "header": self.headers, "headers": self.headers,
                "msg": "无法获取播放地址",
            }

        h = self.headers.copy()
        if "kugou" in url:
            h["Referer"] = "https://www.kugou.com/"
            h["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36")
        elif "music.126.net" in url or "163.com" in url:
            h.update(self.netease_headers)

        result = {
            "parse": 0,
            "url": url,
            "header": h,
            "headers": h,   # 兼容新版 TVBox
        }

        # 网易云歌词
        if source == "netease":
            lrc = self._get_netease_lyric(sid)
            if lrc:
                result["lrc"] = lrc

        return result

    # ==================== 本地代理 ====================
    def localProxy(self, param):
        try:
            url = param.get("url", "")
            if not url:
                return None
            h = self.headers.copy()
            if "music.126.net" in url or "163.com" in url:
                h.update(self.netease_headers)
            elif "kugou" in url:
                h["Referer"] = "https://www.kugou.com/"

            r = self.session.get(url, headers=h, timeout=10, stream=True)
            try:
                ct = r.headers.get("Content-Type", "image/jpeg")
                if "image" not in ct.lower():
                    ct = "image/jpeg"
                content = r.content
            finally:
                r.close()
            return [200, ct, content, {}]
        except Exception as e:
            print(f"[{self.getName()}] localProxy 异常: {e}")
            return None

    # ==================== 内部工具 ====================

    def _pick_list(self, data):
        """从任意嵌套结构里挖出歌曲列表"""
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for k in ("list", "songs", "data", "result", "items", "tracks"):
            v = data.get(k)
            if isinstance(v, list) and v:
                return v
        for v in data.values():
            r = self._pick_list(v)
            if r:
                return r
        return []

    def _extract_artists(self, song):
        """兼容 网易云(ar) / 酷狗(artist) / 通用(singer) 的歌手字段"""
        v = (song.get("artist") or song.get("ar")
             or song.get("singers") or song.get("singer")
             or song.get("artists") or [])
        if isinstance(v, list):
            names = []
            for a in v:
                if isinstance(a, dict):
                    names.append(a.get("name") or a.get("nickname")
                                 or a.get("singerName") or "")
                else:
                    names.append(str(a))
            return ", ".join(n for n in names if n)
        if isinstance(v, dict):
            return v.get("name") or v.get("nickname") or v.get("singerName") or ""
        if isinstance(v, str):
            return v
        return ""

    def _get_playlist(self, source, list_id):
        """通用歌单（网易云）"""
        ck = f"pl_{source}_{list_id}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        data = self._api_post({
            "types": "playlist",
            "id": list_id,
            "source": source,
        })
        if not data:
            return []

        if isinstance(data, dict) and data.get("playlist"):
            tracks = (data["playlist"] or {}).get("tracks") or []
        else:
            tracks = self._pick_list(data)

        for t in tracks:
            if isinstance(t, dict):
                t["source"] = source

        self._cache_set(ck, tracks)
        return tracks

    def _do_search(self, source, keyword, pg):
        ck = f"search_{source}_{keyword}_{pg}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        data = self._api_post({
            "types": "search",
            "source": source,
            "count": 50,
            "pages": pg,
            "name": keyword or "",
        })
        # print(f"[DEBUG] {source} '{keyword}' -> {str(data)[:800]}")  # 排查时打开

        songs = self._pick_list(data)
        result = []
        for item in songs:
            if isinstance(item, dict) and (item.get("id") or item.get("song_id")):
                item["source"] = source
                if not item.get("id"):
                    item["id"] = item.get("song_id") or item.get("songmid") or ""
                result.append(item)

        self._cache_set(ck, result)
        return result

    def _get_sign(self, source, sid, name):
        ck = f"sign_{source}_{sid}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        songs = self._do_search(source, name or "a", 1)
        for song in songs:
            if str(song.get("id")) == str(sid):
                sign = song.get("sign", "")
                self._cache_set(ck, sign)
                return sign
        return ""

    def _get_play_url(self, source, sid, sign):
        """取播放地址 —— 兼容 str / dict / list 三种返回"""
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
                if not url and isinstance(data.get("data"), list) and data["data"]:
                    first = data["data"][0]
                    if isinstance(first, dict):
                        url = first.get("url", "") or ""
                    elif isinstance(first, str):
                        url = first
            elif isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    url = first.get("url", "") or ""
                elif isinstance(first, str):
                    url = first

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

    def _get_netease_cover(self, sid):
        """从网易云官方 API 拿封面（用于 detail 时补全）"""
        ck = f"cover_{sid}"
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        try:
            r = self.session.get(
                f"https://music.163.com/api/song/detail?ids=[{sid}]",
                headers=self.netease_headers, timeout=8
            )
            songs = r.json().get("songs") or []
            pic = ""
            if songs:
                pic = (songs[0].get("album") or {}).get("picUrl", "") or ""
            self._cache_set(ck, pic)
            return pic
        except Exception:
            return ""

    def _get_pic(self, source, song):
        """封面补全"""
        # 优先 al.picUrl（老结构）
        al = song.get("al") or {}
        if al.get("picUrl"):
            return al["picUrl"]
        # 通用字段
        if song.get("pic"):
            return song["pic"]
        if song.get("cover"):
            return song["cover"]

        pic_id = str(song.get("pic_id") or "")
        # 酷狗：32 位 hash 拼 singerimg 路径
        if source == "kugou" and len(pic_id) >= 32:
            return (f"https://singerimg.kugou.com/uploadpic/softhead/400/"
                    f"{pic_id[:2]}/{pic_id[:4]}/{pic_id}.jpg")
        # 网易云 pic_id 是纯数字，此处拼不出，留空由 detail 阶段补
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
