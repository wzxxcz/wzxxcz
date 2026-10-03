from base.spider import Spider
import re
import json
import base64
from urllib.parse import quote, unquote


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://yc.movie1080.online"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    # ================= 基础 =================
    def _get(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=20)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
        except Exception:
            pass
        return ""

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&quot;", '"').replace("&#39;", "'")
              .replace("&lt;", "<").replace("&gt;", ">"))
        return re.sub(r"\s+", " ", s).strip()

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("//"):
            return "https:" + u
        return self.host + (u if u.startswith("/") else "/" + u)

    # ================= 列表解析 =================
    def _items(self, html):
        vods = []
        seen = set()

        # 主匹配：标准 MacCMS 详情页链接 /voddetail/{vid}.html
        for m in re.finditer(
                r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                html, re.S):
            vid, title, body = m.group(1), m.group(2).strip(), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            pic = self._pick_pic(body)
            remark = self._pick_remark(body)
            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs(pic),
                "vod_remarks": remark,
            })

        # 兜底1：原文件的写法 /vodplay/{vid}-1-1.html
        if not vods:
            for m in re.finditer(
                    r'<a[^>]*href="/vodplay/(\d+)-1-1\.html"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                    html, re.S):
                vid, title, body = m.group(1), m.group(2).strip(), m.group(3)
                if vid in seen:
                    continue
                seen.add(vid)
                pic = self._pick_pic(body)
                remark = self._pick_remark(body)
                vods.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._abs(pic),
                    "vod_remarks": remark,
                })

        # 兜底2：更宽松的匹配，不要求 title 属性
        if not vods:
            for m in re.finditer(
                    r'<a[^>]*href="/voddetail/(\d+)\.html"[^>]*>(.*?)</a>',
                    html, re.S):
                vid, body = m.group(1), m.group(2)
                if vid in seen:
                    continue
                tm = re.search(r'title="([^"]+)"', m.group(0))
                if tm:
                    title = tm.group(1).strip()
                else:
                    tm2 = re.search(r'<[^>]*>([^<]+)</', body)
                    title = tm2.group(1).strip() if tm2 else ""
                if not title:
                    continue
                seen.add(vid)
                pic = self._pick_pic(body)
                remark = self._pick_remark(body)
                vods.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._abs(pic),
                    "vod_remarks": remark,
                })
        return vods

    def _pick_pic(self, body):
        pic = ""
        pm = re.search(r'data-original="([^"]+)"', body)
        if pm:
            pic = pm.group(1)
        else:
            pm = re.search(r'data-src="([^"]+)"', body)
            if pm:
                pic = pm.group(1)
            else:
                pm = re.search(r'<img[^>]*src="([^"]+)"', body)
                if pm and "load.gif" not in pm.group(1) and "blank" not in pm.group(1):
                    pic = pm.group(1)
        return pic

    def _pick_remark(self, body):
        remark = ""
        rm = re.search(r'module-item-note">([^<]+)<', body)
        if rm:
            remark = rm.group(1).strip()
        if not remark:
            rm = re.search(r'pic-text[^>]*>([^<]+)<', body)
            if rm:
                remark = rm.group(1).strip()
        if not remark:
            rm = re.search(r'<span[^>]*class="[^"]*note[^"]*"[^>]*>([^<]+)<', body)
            if rm:
                remark = rm.group(1).strip()
        return remark

    # ================= 筛选 =================
    def _filters(self, tid):
        html = self._get("{0}/vodshow/{1}-----------.html".format(self.host, tid))
        f = {}
        subs = []
        for m in re.finditer(r'<a[^>]*href="/vodshow/(\d+)-{11}\.html"[^>]*>([^<]{1,12})</a>', html):
            sid, sname = m.group(1), m.group(2).strip()
            if sid != str(tid) and sname not in ("全部", "字母") and (sname, sid) not in subs:
                subs.append((sname, sid))
        if subs:
            f["class"] = {"key": "class", "name": "类型",
                          "value": [{"n": "全部", "v": str(tid)}] + [{"n": n, "v": v} for n, v in subs]}
        f["area"] = {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}] + [
            {"n": a, "v": a} for a in ["大陆", "香港", "台湾", "美国", "法国", "英国",
                                       "日本", "韩国", "德国", "泰国", "印度", "意大利",
                                       "西班牙", "加拿大", "其他"]]}
        f["year"] = {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [
            {"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)] + [{"n": "更早", "v": "更早"}]}
        bys = []
        for m in re.finditer(r'<a[^>]*href="/vodshow/' + tid + r'--([a-z]+)---------+\.html"[^>]*>([^<]{2,8})</a>', html):
            if (m.group(2), m.group(1)) not in bys:
                bys.append((m.group(2), m.group(1)))
        if bys:
            f["by"] = {"key": "by", "name": "排序",
                       "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for n, v in bys]}
        letters = []
        for m in re.finditer(r'<a[^>]*href="/vodshow/' + tid + r'-----([A-Z])------\.html"[^>]*>[A-Z]</a>', html):
            if m.group(1) not in letters:
                letters.append(m.group(1))
        if letters:
            f["letter"] = {"key": "letter", "name": "字母",
                           "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in letters]}
        return f

    def homeContent(self, filter):
        html = self._get(self.host + "/")
        classes = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*title="([^"]+)"', html):
            tid, name = m.group(1), m.group(2).strip()
            if tid not in seen and name:
                seen.add(tid)
                classes.append({"type_id": tid, "type_name": name})
        # 兜底：没有 title 属性时用链接文本
        if not classes:
            for m in re.finditer(r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>', html):
                tid, name = m.group(1), self._clean(m.group(2))
                if tid not in seen and name:
                    seen.add(tid)
                    classes.append({"type_id": tid, "type_name": name})
        filters = {}
        if filter:
            for c in classes:
                filters[c["type_id"]] = self._filters(c["type_id"])
        rec = self._items(html)[:24]
        return {"class": classes, "filters": filters, "list": rec}

    def homeVideoContent(self):
        try:
            html = self._get(self.host + "/")
            return {"list": self._items(html)[:24]}
        except Exception:
            return {"list": []}

    # ================= 分类列表 =================
    def _show_url(self, tid, pg, by="", letter="", area="", year=""):
        segs = [""] * 11
        segs[0] = quote(area) if area else ""
        segs[1] = by
        segs[4] = letter
        segs[7] = str(pg)
        segs[10] = year
        return "{0}/vodshow/{1}-{2}.html".format(self.host, tid, "-".join(segs))

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend) if extend.strip().startswith("{") else {}
                except Exception:
                    extend = {}
            if not isinstance(extend, dict):
                extend = {}
            by = extend.get("by", "")
            letter = extend.get("letter", "")
            area = extend.get("area", "")
            year = extend.get("year", "")
            cls = extend.get("class", "")
            use_tid = cls if cls else tid
            html = self._get(self._show_url(use_tid, pg, by=by, letter=letter, area=area, year=year))
            vods = self._items(html)
            pagecount = 1
            m = re.search(r'href="(/vodshow/' + re.escape(str(use_tid)) + r'-[^"]+)\.html"[^>]*>尾页', html)
            if m:
                parts = m.group(1).split("-")
                if len(parts) >= 9:
                    try:
                        pagecount = int(parts[8])
                    except Exception:
                        pagecount = 1
            if not vods:
                pagecount = 0
            return {"list": vods, "page": int(pg), "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[movie1080] categoryContent 异常: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ================= 简介提取（重点） =================
    def _extract_desc(self, html):
        """从详情页 HTML 中提取干净简介"""
        desc_raw = ""

        # 1. 多容器优先级匹配
        patterns = [
            # 主容器（原文件用的就是这个）
            r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>(.*?)</div>',
            # 兼容其他苹果CMS模板
            r'<div[^>]*class="[^"]*module-info-introduction[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*video-info-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*video-info-items[^"]*"[^>]*>(.*?)</div>',
            # sketch 类容器
            r'<div[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</span>',
            r'<span[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</span>',
            # 通用类名
            r'<div[^>]*class="[^"]*(?:detail-content|vod-content|vod_content)[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m and m.group(1).strip():
                desc_raw = m.group(1)
                break

        # 2. 关键词兜底
        if not desc_raw:
            m = re.search(
                r'(?:剧情介绍|内容简介|故事简介|简介|剧情)[：:]\s*(?:</span>)?\s*(?:<p[^>]*>|<div[^>]*>)?(.*?)'
                r'(?:</div>|</p>|<div\s+class|详情|立即播放|$)',
                html, re.S)
            if m:
                desc_raw = m.group(1)

        if not desc_raw:
            return ""

        # 3. 若容器里有多段 <p>，拼起来
        ps = re.findall(r'<p[^>]*>(.*?)</p>', desc_raw, re.S)
        if ps:
            desc = " ".join(ps)
        else:
            desc = desc_raw

        # 4. 去 HTML 标签 + 实体
        desc = re.sub(r"<[^>]+>", "", desc)
        desc = (desc.replace("&nbsp;", " ").replace("&amp;", "&")
                    .replace("&quot;", '"').replace("&#39;", "'")
                    .replace("&lt;", "<").replace("&gt;", ">"))

        # 5. 强制切断底部导航 / 播放列表误抓文本
        for sw in ["详情", "立即播放", "报错", "收藏", "扫一扫",
                   "排序", "播放地址", "第01集", "第1集", "百度网盘",
                   "版权声明", "免责声明"]:
            if sw in desc:
                desc = desc.split(sw)[0]

        # 6. 清理空白
        desc = re.sub(r"\s+", " ", desc).strip()
        return desc[:3000]

    # ================= 详情 =================
    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            vid = re.sub(r"\D", "", str(vid))
            if not vid:
                return {"list": []}
            html = self._get("{0}/voddetail/{1}.html".format(self.host, vid))
            if not html:
                return {"list": []}

            vod = {"vod_id": vid}

            # 标题
            m = re.search(r"<h1[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</h1>", html, re.S)
            if not m:
                m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
            if m:
                vod["vod_name"] = self._clean(m.group(1))
            else:
                vod["vod_name"] = vid

            # 封面
            m = re.search(r'data-original="([^"]+)"', html)
            if not m:
                m = re.search(r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*src="([^"]+)"', html)
            if m:
                vod["vod_pic"] = self._abs(m.group(1))

            # ============ 简介（重点加固） ============
            vod["vod_content"] = self._extract_desc(html)
            # ==========================================

            # 结构化信息（导演/主演/年份/地区/类型/语言/备注）
            info = {}
            for m in re.finditer(
                    r'<span[^>]*class="[^"]*module-info-item-title[^"]*"[^>]*>([^<]+)</span>\s*'
                    r'<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>',
                    html, re.S):
                key = m.group(1).strip("：: ")
                val = self._clean(m.group(2)).replace(" / ", " ").strip()
                if key and val:
                    info[key] = val

            if "导演" in info:
                vod["vod_director"] = info["导演"]
            if "主演" in info:
                vod["vod_actor"] = info["主演"]
            if "类型" in info:
                vod["type_name"] = info["类型"]
            if "地区" in info:
                vod["vod_area"] = info["地区"]
            if "年份" in info:
                vod["vod_year"] = re.sub(r"[^\d]", "", info["年份"])[:4]
            if "语言" in info:
                vod["vod_lang"] = info["语言"]

            # 备注优先级：备注 > 更新 > 状态
            for k in ("备注", "更新", "状态"):
                if k in info:
                    vod["vod_remarks"] = info[k]
                    break

            # 播放源（tab 名 + panel 剧集）
            tabs = []
            for m in re.finditer(
                    r'<div[^>]*class="[^"]*module-tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"',
                    html):
                tabs.append(m.group(1).strip())

            # 兼容两种 panel 容器
            panels = re.findall(
                r'<div[^>]*class="[^"]*his-tab-list[^"]*"[^>]*>(.*?)</div>\s*</div>',
                html, re.S)
            if not panels:
                panels = re.findall(
                    r'<div[^>]*class="[^"]*(?:module-play-list|playlist-content)[^"]*"[^>]*>(.*?)</div>\s*</div>',
                    html, re.S)

            src_names = []
            src_urls = []
            for i, p in enumerate(panels):
                name = tabs[i] if i < len(tabs) else "线路{0}".format(i + 1)
                eps = []
                for m in re.finditer(
                        r'href="(/vodplay/\d+-\d+-(\d+)\.html)"[^>]*><span>([^<]+)</span>', p):
                    epurl = self.host + m.group(1)
                    epname = m.group(3).strip()
                    eps.append("{0}${1}".format(epname, epurl))
                # 兜底：span 缺失时从 <a> 里直接取文本
                if not eps:
                    for m in re.finditer(
                            r'href="(/vodplay/\d+-\d+-(\d+)\.html)"[^>]*>([^<]+)</a>', p):
                        epurl = self.host + m.group(1)
                        epname = m.group(3).strip()
                        eps.append("{0}${1}".format(epname, epurl))
                if eps:
                    src_names.append(name)
                    src_urls.append("#".join(eps))

            # 全页兜底：直接扫所有 /vodplay/ 链接
            if not src_names:
                all_eps = re.findall(
                    r'<a[^>]*href="(/vodplay/(\d+)-([a-z0-9]+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
                    html)
                groups = {}
                for href, _vid, sid, _nid, nm in all_eps:
                    nm = nm.strip() or "正片"
                    groups.setdefault(sid, []).append(
                        "{0}${1}".format(nm, self.host + href))
                for sid in sorted(groups.keys()):
                    src_names.append("线路{0}".format(sid))
                    src_urls.append("#".join(groups[sid]))

            vod["vod_play_from"] = "$$$".join(src_names)
            vod["vod_play_url"] = "$$$".join(src_urls)
            return {"list": [vod]}
        except Exception as e:
            print("[movie1080] detailContent 异常: %s" % e)
            return {"list": []}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        header = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
            "Origin": self.host,
        }
        try:
            pid = (id or "").strip()
            if "$" in pid:
                pid = pid.split("$")[-1]
            if not pid:
                return {"parse": 0, "playUrl": "", "url": "", "header": header}

            # 已是 m3u8/mp4 直链
            if pid.startswith("http") and (".m3u8" in pid or ".mp4" in pid):
                return {"parse": 0, "playUrl": pid, "url": pid, "header": header}

            page_url = pid if pid.startswith("http") else self._abs(pid)
            html = self._get(page_url)
            if not html:
                return {"parse": 1, "playUrl": page_url, "url": page_url, "header": header}

            url = ""

            # 1. 优先解析 player_aaaa 标准结构
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if not m:
                m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{[^<]+\})', html, re.S)
            if m:
                try:
                    data = json.loads(m.group(1))
                    url = (data.get("url") or "").replace("\\/", "/")
                    if data.get("encrypt") == 1 and url:
                        try:
                            url = base64.b64decode(
                                url + "=" * (-len(url) % 4)
                            ).decode("utf-8", "replace").replace("\\/", "/")
                        except Exception:
                            pass
                except Exception:
                    pass

            # 2. 兼容原文件的 vod_play_url 写法（兼容单/双引号）
            if not url:
                m = re.search(r'vod_play_url\s*:\s*"([^"]+)"', html)
                if not m:
                    m = re.search(r"vod_play_url\s*:\s*'([^']+)'", html)
                if m:
                    url = m.group(1).replace("\\/", "/")

            # 3. 兜底：直接扫 HTML 里的 m3u8
            if not url:
                mm = re.search(r'(https?:[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
                if mm:
                    url = mm.group(1).replace("\\/", "/")

            if url.startswith("//"):
                url = "https:" + url

            if url and (".m3u8" in url or ".mp4" in url):
                return {"parse": 0, "playUrl": url, "url": url, "header": header}
            if url:
                return {"parse": 1, "playUrl": url, "url": url, "header": header}

            # 兜底：交给壳嗅探
            return {"parse": 1, "playUrl": page_url, "url": page_url, "header": header}
        except Exception as e:
            print("[movie1080] playerContent 异常: %s" % e)
            return {"parse": 0, "playUrl": "", "url": "", "header": header}

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            html = self._get("{0}/vodsearch/{1}-------------.html".format(
                self.host, quote(key)))
            vods = self._items(html)
            pagecount = 1
            m = re.search(r'href="/vodsearch/[^"]*-(\d+)---\.html"[^>]*>尾页', html)
            if m:
                try:
                    pagecount = int(m.group(1))
                except Exception:
                    pagecount = 1
            if not vods:
                pagecount = 0
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": len(vods)}
        except Exception as e:
            print("[movie1080] searchContent 异常: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    # ================= 其他壳方法 =================
    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower().split("?")[0]
        return u.endswith((".m3u8", ".mp4", ".flv", ".ts", ".mkv"))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None
