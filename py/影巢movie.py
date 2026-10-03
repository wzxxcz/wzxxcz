from base.spider import Spider
import re
import json
from urllib.parse import quote, unquote


class Spider(Spider):
    def getName(self):
        return "1080电影"

    def init(self, extend=""):
        self.host = "https://yc.movie1080.online"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    # ================= 基础（原样） =================
    def _get(self, url):
        r = self.fetch(url, headers=self.headers, timeout=20)
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text
        return ""

    def _clean(self, s):
        return re.sub(r"<[^>]+>", "", s or "").strip()

    # ================= 列表（原样，不做任何改动） =================
    def _items(self, html):
        vods = []
        seen = set()
        for m in re.finditer(
                r'<a[^>]*href="/vodplay/(\d+)-1-1\.html"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                html, re.S):
            vid, title, body = m.group(1), m.group(2).strip(), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            pic = ""
            pm = re.search(r'data-original="([^"]+)"', body)
            if pm:
                pic = pm.group(1)
            else:
                pm = re.search(r'<img[^>]*src="([^"]+)"', body)
                if pm and "load.gif" not in pm.group(1):
                    pic = pm.group(1)
            remark = ""
            rm = re.search(r'module-item-note">([^<]+)<', body)
            if rm:
                remark = rm.group(1).strip()
            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return vods

    # ================= 筛选（原样） =================
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

    # ================= 首页（原样） =================
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        classes = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*title="([^"]+)"', html):
            tid, name = m.group(1), m.group(2).strip()
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

    # ================= 分类（原样） =================
    def _show_url(self, tid, pg, by="", letter="", area="", year=""):
        segs = [""] * 11
        segs[0] = quote(area) if area else ""
        segs[1] = by
        segs[4] = letter
        segs[7] = str(pg)
        segs[10] = year
        return "{0}/vodshow/{1}-{2}.html".format(self.host, tid, "-".join(segs))

    def categoryContent(self, tid, pg, filter, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend.strip().startswith("{") else {}
            except Exception:
                extend = {}
        by = extend.get("by", "") if isinstance(extend, dict) else ""
        letter = extend.get("letter", "") if isinstance(extend, dict) else ""
        area = extend.get("area", "") if isinstance(extend, dict) else ""
        year = extend.get("year", "") if isinstance(extend, dict) else ""
        cls = extend.get("class", "") if isinstance(extend, dict) else ""
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
        return {"list": vods, "page": int(pg), "pagecount": pagecount, "limit": 90, "total": 999999}

    # ================= 简介提取（重点加固） =================
    def _extract_desc(self, html):
        """从详情页 HTML 中提取干净简介"""
        desc_raw = ""

        # 1. 多容器优先级匹配（第一个是原文件用的容器）
        patterns = [
            # 原文件主用容器
            r'module-info-introduction-content">\s*<p>(.*?)</p>',
            # 同类模板容器
            r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*module-info-introduction[^"]*"[^>]*>(.*?)</div>',
            # 其他 MacCMS 模板常见容器
            r'<div[^>]*class="[^"]*video-info-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*video-info-items[^"]*"[^>]*>(.*?)</div>',
            # sketch 类容器
            r'<span[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</span>',
            r'<span[^>]*class="[^"]*sketch[^"]*"[^>]*>(.*?)</span>',
            r'<div[^>]*class="[^"]*sketch[^"]*content[^"]*"[^>]*>(.*?)</div>',
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

        # 3. 若容器内有多段 <p>，拼起来
        ps = re.findall(r'<p[^>]*>(.*?)</p>', desc_raw, re.S)
        desc = " ".join(ps) if ps else desc_raw

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

    # ================= 详情（只改简介提取，其他原样） =================
    def detailContent(self, ids):
        vid = ids[0]
        html = self._get("{0}/voddetail/{1}.html".format(self.host, vid))
        vod = {"vod_id": vid}
        m = re.search(r"<h1[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</h1>", html, re.S)
        if m:
            vod["vod_name"] = m.group(1).strip()
        else:
            m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
            if m:
                vod["vod_name"] = m.group(1).strip()
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            vod["vod_pic"] = m.group(1)

        # ============ 简介（重点加固） ============
        vod["vod_content"] = self._extract_desc(html)
        # ==========================================

        info = {}
        for m in re.finditer(
                r'<span[^>]*class="[^"]*module-info-item-title[^"]*"[^>]*>([^<]+)</span>\s*'
                r'<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>',
                html, re.S):
            info[m.group(1).strip("：: ")] = self._clean(m.group(2)).replace(" / ", " ").strip()
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
        if "备注" in info:
            vod["vod_remarks"] = info["备注"]
        elif "更新" in info:
            vod["vod_remarks"] = info["更新"]

        tabs = []
        for m in re.finditer(
                r'<div[^>]*class="[^"]*module-tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"',
                html):
            tabs.append(m.group(1).strip())

        panels = re.findall(
            r'<div[^>]*class="[^"]*his-tab-list[^"]*"[^>]*>(.*?)</div>\s*</div>',
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
            if eps:
                src_names.append(name)
                src_urls.append("#".join(eps))
        vod["vod_play_from"] = "$$$".join(src_names)
        vod["vod_play_url"] = "$$$".join(src_urls)
        return {"list": [vod]}

    # ================= 播放（原样） =================
    def playerContent(self, flag, id, vipFlags):
        html = self._get(id if id.startswith("http") else self.host + id)
        m = re.search(r'vod_play_url\s*:\s*"([^"]+)"', html)
        url = m.group(1) if m else ""
        if not url:
            m = re.search(r'vod_play_url\s*:\s*\'([^\']+)\'', html)
            if m:
                url = m.group(1)
        url = url.replace("\\/", "/")
        return {"parse": 1, "url": url,
                "header": {"User-Agent": self.headers["User-Agent"],
                           "Referer": self.host + "/"}}

    # ================= 搜索（原样） =================
    def searchContent(self, key, quick, pg="1"):
        html = self._get("{0}/vodsearch/{1}-------------.html".format(self.host, quote(key)))
        vods = self._items(html)
        return {"list": vods, "page": int(pg), "pagecount": 1 if vods else 0}

    # ================= 其他壳方法（原样） =================
    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/mpeg", "", {}]
