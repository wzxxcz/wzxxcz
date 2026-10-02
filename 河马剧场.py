# -*- coding: utf-8 -*-
"""河马剧场（OPENHIPPO / com.dz.hmjc）——「影视+」数据源

协议来源：APK 3.12.0（MD5 805565ADCA81FC09A626CF9F9CE6FBC9）jadx 反编译 +
          App 网关实测。探索与验证脚本见 d:\\py\\河马剧场破解\\。

两条线路（实测，2026-09-29，均直连 200/206，支持 Range，无需 DRM）：

  1) 河马剧场App（com.dz.hmjc）App 网关，覆盖全集：
     POST https://freevideo.zqqds.cn/free-video-portal/portal/{code}
     签名算法（反编译 com.dz.business.base.network.e.u + encrypt.c/b 得到）：
       stringToSign = timestamp + "\\n" + nonce + "\\n" + body
       sign = Base64_NO_WRAP(HMAC_SHA256(
                key="1pQ86jdDNQR584CmGICPnfdzydOLfU/EebtAKkZ5jkE=",
                msg=stringToSign))
     1103 初始化拿游客 userId（无需登录）；
     1132 章节表（App 端对游客返回全部集，且 isCharge 全为 0）；
     1131 视频详情，对每一集（含付费集）都下发 content.mp4SwitchUrl 多条线路。
     ★ 该网关对未登录游客照常下发付费集地址，是本源的主线路。

  2) Web 端补充（www.kuaikaw.cn）：
     homeContent / categoryContent / searchContent 用 Next.js SSR，
     detailContent 的基础信息用 RPC /seo/video/6002。

若网关不可用，则自动回退到 Web 端，但 Web 端只暴露每剧前几集。
"""

import base64
import hashlib
import hmac
import json
import random
import re
import string
import time
import uuid

import requests

try:
    from base.spider import Spider as _Base
except ImportError:
    class _Base(object):
        def __init__(self):
            pass


# ═══════════════════════ App 网关客户端（复刻自 APK） ═══════════════════════

class _AppClient(object):
    """河马剧场 App 网关客户端。签名算法逐行对应反编译结果，非经验推测。"""

    PORTAL = "https://freevideo.zqqds.cn/free-video-portal/portal"
    HMAC_KEY = "1pQ86jdDNQR584CmGICPnfdzydOLfU/EebtAKkZ5jkE="
    UA = "okhttp/3.12.13"

    def __init__(self, timeout=20):
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.trust_env = False
        self.sess.verify = False
        self.utdid = uuid.uuid4().hex
        self.user_id = ""
        self.token = ""

    # --- 签名 ---
    @staticmethod
    def _sign(timestamp, nonce, body):
        msg = "%s\n%s\n%s" % (timestamp, nonce, "" if body is None else body)
        mac = hmac.new(_AppClient.HMAC_KEY.encode("utf-8"),
                       msg.encode("utf-8"), hashlib.sha256).digest()
        # android.util.Base64.NO_WRAP == b64encode 无换行
        return base64.b64encode(mac).decode("ascii")

    @staticmethod
    def _nonce(n=16):
        pool = string.ascii_lowercase + string.digits
        return "".join(random.choice(pool) for _ in range(n))

    def _headers(self, body):
        ts = str(int(time.time() * 1000))
        nonce = self._nonce()
        head = {
            "freeflow": 0, "version": "3.12.0", "pname": "com.dz.hmjc",
            "channelCode": "HMJC1000000", "utdidTmp": self.utdid,
            "token": self.token, "utdid": self.utdid, "os": "android",
            "osv": 33, "brand": "Xiaomi", "model": "MI 8", "manu": "Xiaomi",
            "userId": self.user_id, "session1": "", "session2": "",
            "ds": 0, "p": 65, "nonce": nonce, "timeZone": "8",
            "timestamp": ts, "recSwitch": True,
        }
        return {
            "alg": "HG45LKBS",
            "sign": self._sign(ts, nonce, body),
            "datas": json.dumps(head, ensure_ascii=False,
                                separators=(",", ":")),
            "wetruwtty": "mhdfiheowjfcslkjfwojo636",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
            "X-Request-ID": str(uuid.uuid4()),
            "User-Agent": self.UA,
        }

    def call(self, code, params):
        body = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        r = self.sess.post("%s/%s" % (self.PORTAL, code),
                           data=body.encode("utf-8"),
                           headers=self._headers(body), timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError("portal/%s HTTP %s" % (code, r.status_code))
        return r.json()

    def bootstrap(self):
        """1103 初始化，拿游客 userId（无需登录）。"""
        j = self.call("1103", {})
        if j.get("code") != 0:
            raise RuntimeError("1103 code=%s %s" % (j.get("code"),
                                                    j.get("msg")))
        uid = str(j.get("userId") or "")
        info = j.get("userInfoVo") or (j.get("data") or {}).get(
            "userInfoVo") or {}
        if info.get("userId"):
            uid = str(info["userId"])
        if not uid:
            raise RuntimeError("1103 未返回 userId")
        self.user_id = uid
        return j

    # --- 业务 ---
    def chapters(self, book_id):
        """1132 章节表。App 端游客可见全部集。"""
        j = self.call("1132", {"bookId": str(book_id)})
        if j.get("code") != 0:
            raise RuntimeError("1132 code=%s %s" % (j.get("code"),
                                                    j.get("msg")))
        return ((j.get("data") or {}).get("chapterList") or [])

    def video(self, book_id, chapter_id, rate=None):
        """1131 视频详情：返回 (完整 videoInfo, mp4SwitchUrl 列表)。

        rate: 清晰度档位 "720P" / "540P"（1080P 服务端恒降级为 720P）。
        """
        params = {"bookId": str(book_id), "chapterId": str(chapter_id)}
        if rate:
            params["resolutionRate"] = str(rate)
        j = self.call("1131", params)
        if j.get("code") != 0:
            raise RuntimeError("1131 code=%s %s" % (j.get("code"),
                                                    j.get("msg")))
        vi = ((j.get("data") or {}).get("videoInfo") or {})
        urls = [u for u in ((vi.get("content") or {}).get("mp4SwitchUrl")
                            or []) if isinstance(u, str) and u.startswith(
                                "http")]
        return vi, urls


# ═══════════════════════════ 影视+ 数据源 ═══════════════════════════

class Spider(_Base):
    HOST = "https://www.kuaikaw.cn"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # 6007 搜索接口要求 tmpid 非空，否则恒返回 totalSize=0
    TMPID = "00000000000000000000000000000001"
    PAGE_SIZE = 10          # 站点每页固定 10 条（pageSize 实测被忽略）
    CACHE_MAX = 400         # 视频地址缓存条数上限

    # 线路展示名（按 mp4SwitchUrl 顺序，含 fallback）
    LINE_NAMES = ["河马线路", "河马备用", "河马H265"]
    # 清晰度档位（对应 App 的 resolutionRate 取值，也是界面上的线路名）。
    # 实测：720P / 540P 为真实码率；1080P 服务端会静默降级为 720P
    # （8 部剧 0/8 命中，CDN 上也 404），保留该档以贴合官方配置表，
    # 选它播放不会失败，但拿到的是 720P 码流。
    RATE_ORDER = ["1080P", "720P", "540P"]

    def getName(self):
        return "河马剧场"

    def init(self, extend=""):
        self.sess = requests.Session()
        self.sess.trust_env = False
        self.sess.verify = False
        self.sess.headers.update({"User-Agent": self.UA, "Accept": "*/*"})
        self._json_hdr = {
            "User-Agent": self.UA,
            "Content-Type": "application/json",
            "pname": "www.kuaikaw.cn",
            "tmpid": self.TMPID,
            "Origin": self.HOST,
            "Referer": self.HOST + "/",
        }
        self._class_cache = None
        # playerContent 需要按集解析视频地址；详情页一次点播就是几十次请求，
        # 故做 LRU 缓存 + 串行节流（同一本剧不并发打网关）。
        self._app = None
        self._app_failed = False
        self._url_cache = {}
        self._chapter_cache = {}
        self._last_app_call = 0.0

    # ─────────────── App 网关（带节流与惰性初始化） ───────────────

    def _get_app(self):
        if self._app_failed:
            return None
        if self._app is None:
            cli = _AppClient()
            try:
                cli.bootstrap()
            except Exception:
                self._app_failed = True          # 失败后本会话不再重试
                return None
            self._app = cli
        return self._app

    def _app_call(self, method, *a):
        """串行化 + >=1s 节流，尊重目标站点反爬规则。

        注意：method 传字符串，客户端在内部惰性初始化后再 getattr，
        避免 self._app 尚为 None 时提前求值 self._app.xxx 抛 AttributeError。
        """
        cli = self._get_app()
        if cli is None:
            raise RuntimeError("App 网关不可用")
        gap = 1.0 - (time.time() - self._last_app_call)
        if gap > 0:
            time.sleep(gap)
        self._last_app_call = time.time()
        return getattr(cli, method)(*a)

    def _chapters(self, book_id):
        """章节表：优先 App（游客可见全集），失败回退 Web。"""
        bid = str(book_id)
        if bid in self._chapter_cache:
            return self._chapter_cache[bid]
        rows = None
        try:
            rows = self._app_call("chapters", bid)
        except Exception:
            rows = None
        if not rows:
            try:
                props = self._seo("6002", {"bookId": bid, "type": 1})
                rows = props.get("chapterList") or []
            except Exception:
                rows = []
        out = []
        for r in rows or []:
            cid = str(r.get("chapterId") or "").strip()
            if not cid:
                continue
            idx = r.get("chapterIndex")
            name = str(r.get("chapterName") or "").strip()
            out.append({
                "id": cid,
                "name": name or ("第%s集" % idx if idx else "正片"),
                "index": idx or 0,
            })
        if out:
            self._chapter_cache[bid] = out
        return out

    def _resolve_urls(self, book_id, chapter_id, rate=None):
        """解析某集的多线路地址。返回 [(显示名, url), ...]。"""
        key = "%s~%s~%s" % (book_id, chapter_id, rate or "")
        if key in self._url_cache:
            self._url_cache[key] = self._url_cache.pop(key)   # LRU 提位
            return self._url_cache[key]
        lines = []
        try:
            _vi, urls = self._app_call("video", book_id, chapter_id, rate)
            for i, u in enumerate(urls):
                name = (self.LINE_NAMES[i] if i < len(self.LINE_NAMES)
                        else "河马线路%d" % (i + 1))
                lines.append((name, u))
        except Exception:
            lines = []
        if not lines and not rate:
            # 回退：Web 端只对免费集下发地址
            try:
                props = self._seo("6002", {"bookId": str(book_id), "type": 1})
                for ch in props.get("chapterList") or []:
                    if str(ch.get("chapterId")) != str(chapter_id):
                        continue
                    u = str((ch.get("chapterVideoVo") or {}).get("mp4")
                            or "").strip()
                    if u.startswith("http"):
                        lines = [("河马线路", u)]
                    break
            except Exception:
                lines = []
        if lines:
            self._url_cache[key] = lines
            while len(self._url_cache) > self.CACHE_MAX:
                self._url_cache.pop(next(iter(self._url_cache)))
        return lines

    # ─────────────────────── Web 端基础请求 ───────────────────────

    def _seo(self, code, payload=None):
        r = self.sess.post("%s/seo/video/%s" % (self.HOST, code),
                           json=payload or {}, headers=self._json_hdr,
                           timeout=15)
        if r.status_code != 200:
            raise RuntimeError("seo/%s HTTP %s" % (code, r.status_code))
        j = r.json()
        if j.get("retCode") != 0:
            raise RuntimeError("seo/%s retCode=%s %s"
                               % (code, j.get("retCode"), j.get("retMsg")))
        return j.get("data") or {}

    def _next_data(self, path):
        """抓 Next.js SSR 页面的 __NEXT_DATA__.props.pageProps"""
        r = self.sess.get(self.HOST + path, timeout=15)
        if r.status_code != 200:
            raise RuntimeError("%s HTTP %s" % (path, r.status_code))
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                      r.text, re.S)
        if not m:
            raise RuntimeError("%s 无 __NEXT_DATA__" % path)
        return (json.loads(m.group(1)).get("props") or {}).get(
            "pageProps") or {}

    # ─────────────────────────── 数据映射 ───────────────────────────

    @staticmethod
    def _item(row):
        if not isinstance(row, dict):
            return None
        bid = str(row.get("bookId") or "").strip()
        if not bid:
            return None
        total = str(row.get("totalChapterNum") or "").strip()
        return {
            "vod_id": bid,
            "vod_name": str(row.get("bookName") or "").strip(),
            "vod_pic": str(row.get("coverWap") or "").strip(),
            "vod_remarks": ("全%s集" % total) if total
                           else str(row.get("statusDesc") or "").strip(),
        }

    def _list(self, rows):
        out = []
        for row in rows or []:
            it = self._item(row)
            if it and it["vod_name"]:
                out.append(it)
        return out

    # ─────────────────────────── 分类 ───────────────────────────

    def _classes(self):
        if self._class_cache:
            return self._class_cache
        classes = []
        try:
            data = self._seo("6000")
        except Exception:
            data = {}
        for c in data.get("typeThreeList") or []:
            ids = c.get("typeThreeIds") or []
            name = str(c.get("name") or "").strip()
            if ids and name:
                classes.append({"type_id": ",".join(str(i) for i in ids),
                                "type_name": name})
        if not classes:
            try:
                page = self._next_data("/browse")
                for c in page.get("typeThreeList") or []:
                    ids = c.get("typeThreeIds") or []
                    if ids and str(c.get("name") or "").strip():
                        classes.append(
                            {"type_id": ",".join(str(i) for i in ids),
                             "type_name": c["name"]})
            except Exception:
                pass
        self._class_cache = classes
        return classes

    def homeContent(self, filter):
        try:
            return {"class": self._classes()}
        except Exception:
            return {"class": []}

    def homeVideoContent(self):
        try:
            data = self._seo("6000")
        except Exception:
            return {"list": []}
        out, seen = [], set()
        for col in data.get("seoColumnVos") or []:
            for it in self._list(col.get("bookInfos")):
                if it["vod_id"] in seen:
                    continue
                seen.add(it["vod_id"])
                out.append(it)
        return {"list": out}

    # ─────────────────────────── 分类内容 ───────────────────────────

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(int(pg), 1)
        except (TypeError, ValueError):
            page = 1
        ids = [x.strip() for x in str(tid or "").split(",") if x.strip()]
        if not ids:
            ids = ["0"]
        videos, seen, pages = [], set(), 1
        for one in ids:
            try:
                props = self._next_data("/browse/%s/%d" % (one, page))
            except Exception:
                continue                    # 单 id 失败不拖垮整体
            try:
                pages = max(pages, int(props.get("pages") or 1))
            except (TypeError, ValueError):
                pass
            for it in self._list(props.get("bookList")):
                if it["vod_id"] in seen:
                    continue
                seen.add(it["vod_id"])
                videos.append(it)
        return {"list": videos, "page": page, "pagecount": pages,
                "limit": self.PAGE_SIZE, "total": pages * self.PAGE_SIZE}

    # ─────────────────────────── 详情 ───────────────────────────

    def detailContent(self, array):
        if not array:
            return {"list": []}
        vod_id = array[0]
        if isinstance(vod_id, dict):
            vod_id = vod_id.get("vod_id") or vod_id.get("id") or ""
        vod_id = str(vod_id or "").strip()
        if not vod_id:
            return {"list": []}

        # 基础信息优先 RPC 6002，失败回退 SSR /drama/{id}
        props = None
        try:
            props = self._seo("6002", {"bookId": vod_id, "type": 1})
        except Exception:
            props = None
        if not props or not props.get("bookInfoVo"):
            try:
                props = self._next_data("/drama/%s" % vod_id)
            except Exception:
                props = {}
        info = props.get("bookInfoVo") or {}

        # 播放列表：App 端返回全部集（含付费集）。
        # 三条线路 = 三个清晰度档（1080P / 720P / 540P），用 $$$ 分隔；
        # 每条线路内部集名正常（第一集/第二集/…），集 ID 编码 "bookId@chapterId"。
        chapters = self._chapters(vod_id)
        play_from, play_url = "", ""
        if chapters:
            play_from = "$$$".join(self.RATE_ORDER)
            eps = "%s$%s@%s" % (chapters[0]["name"], vod_id,
                                chapters[0]["id"])
            for ch in chapters[1:]:
                eps += "#%s$%s@%s" % (ch["name"], vod_id, ch["id"])
            play_url = "$$$".join([eps] * len(self.RATE_ORDER))
        
        tag_names = [str(t.get("name") or "").strip()
                     for t in (info.get("bookTypeThree") or [])]
        tag_names = [t for t in tag_names if t]
        total = str(info.get("totalChapterNum") or "").strip()
        return {"list": [{
            "vod_id": vod_id,
            "vod_name": str(info.get("bookName") or "").strip() or vod_id,
            "vod_pic": str(info.get("coverWap") or "").strip(),
            "type_name": " ".join(tag_names),
            "vod_remarks": ("全%s集" % total) if total
                           else ("%d集" % len(chapters)),
            "vod_actor": str(info.get("actor") or "").strip(),
            "vod_director": str(info.get("actress") or "").strip(),
            "vod_content": str(info.get("introduction") or "").strip(),
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }]}

    # ─────────────────────────── 搜索 ───────────────────────────

    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(int(pg), 1)
        except (TypeError, ValueError):
            page = 1
        word = str(key or "").strip()
        if not word:
            return {"list": [], "page": page, "pagecount": page}
        try:
            data = self._seo("6007", {"sourceType": 1, "keyword": word,
                                      "index": page})
        except Exception:
            return {"list": [], "page": page, "pagecount": page}
        videos = self._list(data.get("bookList"))
        try:
            total = int(data.get("totalSize") or 0)
        except (TypeError, ValueError):
            total = 0
        pagecount = ((total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
                     if total else page)
        return {"list": videos, "page": page,
                "pagecount": max(pagecount, page, 1)}

    # ─────────────────────────── 播放 ───────────────────────────

    def playerContent(self, flag, id, vipFlags):
        """flag = 清晰度档（1080P/720P/540P）；id = "集名$bookId@chapterId"。

        清晰度由 flag 决定；同一清晰度下按线路顺序取第一条可用地址
        （河马线路 → 河马备用 → 河马H265），真正点播时才按需解析。
        """
        payload = str(id or "").split("$")[-1].strip()
        book_id, _, cid = payload.partition("@")
        if not cid:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": "{}", "headers": {}}

        # flag 是线路名（即清晰度档）。兼容壳可能追加的下标，如 "720P_1"。
        flag_s = str(flag or "")
        rate = ""
        for r in self.RATE_ORDER:
            if r in flag_s:
                rate = r
                break
        if not rate:
            rate = self.RATE_ORDER[0]

        lines = self._resolve_urls(book_id, cid, rate)
        if not lines:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": "{}", "headers": {}}

        header = {"User-Agent": self.UA, "Accept": "*/*"}
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": lines[0][1],
            "header": json.dumps(header, ensure_ascii=False),
            "headers": header,
        }

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(mp4|m3u8|ts|m4s)(\?|$)", str(url or ""),
                              re.I))

    def manualVideoCheck(self):
        return False


# ─────────────────────────── 自测 ───────────────────────────
if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    requests.packages.urllib3.disable_warnings()

    sp = Spider()
    sp.init("")

    print("== 名称 ==")
    print(" ", sp.getName())

    print("\n== 分类 ==")
    cls = sp.homeContent(None)["class"]
    print("  共 %d 个分类" % len(cls))
    for c in cls[:6]:
        print("   ", c["type_id"], c["type_name"])

    print("\n== 首页推荐 ==")
    hv = sp.homeVideoContent()
    print("  共 %d 部" % len(hv["list"]))
    for v in hv["list"][:3]:
        print("   ", v["vod_id"], v["vod_name"], v["vod_remarks"])

    print("\n== 分类内容 ==")
    cat = sp.categoryContent("1170", "1", False, {})
    print("  page=%s pagecount=%s n=%d"
          % (cat["page"], cat["pagecount"], len(cat["list"])))
    for v in cat["list"][:3]:
        print("   ", v["vod_id"], v["vod_name"], v["vod_remarks"])

    print("\n== 详情（含付费全集） ==")
    BOOK = "41000372415"
    det = sp.detailContent([BOOK])["list"][0]
    froms = det["vod_play_from"].split("$$$")
    urlblocks = det["vod_play_url"].split("$$$")
    print("  名称:", det["vod_name"], "| 标签:", det["type_name"][:40])
    print("  线路数: %d  %s" % (len(froms), froms))
    print("  每条线路集数:", [len(b.split("#")) for b in urlblocks])
    eps = urlblocks[0].split("#")
    print("  第1集 :", eps[0])
    print("  第6集 :", eps[5])
    print("  末集  :", eps[-1])

    print("\n== 播放（免费集 + 付费集 × 1080P/720P/540P） ==")
    for label, ep in (("免费第1集", eps[0]), ("付费第6集", eps[5])):
        for flag in sp.RATE_ORDER:
            pc = sp.playerContent(flag, ep, [])
            u = pc["url"]
            if not u:
                print("  %-8s %-6s → 无地址" % (label, flag))
                continue
            r = sp.sess.get(u, headers={"User-Agent": sp.UA}, timeout=25,
                            stream=True)
            head = next(r.iter_content(4096), b"")
            print("  %-8s %-6s HTTP %s %-9s 真实MP4=%s  大小=%-9s 码率段=%s"
                  % (label, flag, r.status_code,
                     r.headers.get("Content-Type"), b"ftyp" in head[:64],
                     r.headers.get("Content-Length"),
                     u.split("/")[-1].split(".")[-3]))
            r.close()

    print("\n== 换一部剧核对线路区/选集区布局 ==")
    det2 = sp.detailContent(["41000115755"])["list"][0]
    froms2 = det2["vod_play_from"].split("$$$")
    blk2 = det2["vod_play_url"].split("$$$")[0].split("#")
    print("  名称:", det2["vod_name"], "| 备注:", det2["vod_remarks"])
    print("  线路区:", froms2)
    print("  选集区前4格:", [e.split("$")[0] for e in blk2[:4]])
    print("  选集区末格:", blk2[-1].split("$")[0])

    print("\n== 搜索 ==")
    for kw in ("星河不渡旧时月", "龙王"):
        se = sp.searchContent(kw, False, "1")
        print("  %-12s n=%d %s"
              % (kw, len(se["list"]), [x["vod_name"] for x in se["list"][:3]]))

    print("\n全部自测完成")
