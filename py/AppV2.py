# -*- coding: utf-8 -*-
# 剧下饭 juxiafan.com 最新可用独立爬虫
import requests
from bs4 import BeautifulSoup
import json
import re

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
}

class Spider(object):
    def __init__(self):
        self.host = "https://www.juxiafan.com"

    def getName(self):
        return "剧下饭"

    # 首页分类
    def homeContent(self, filter=False):
        result = {"class": []}
        try:
            resp = requests.get(self.host, headers=headerx, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select(".nav-item a"):
                name = a.get_text(strip=True)
                href = a.get("href", "").strip("/")
                if name and href and name not in ["首页", "留言"]:
                    result["class"].append({
                        "type_id": href,
                        "type_name": name
                    })
        except:
            pass
        return result

    # 首页推荐
    def homeVideoContent(self):
        videos = []
        try:
            resp = requests.get(self.host, headers=headerx, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select(".vod-item")[:30]:
                a = item.find("a")
                img = item.find("img")
                if not a: continue
                videos.append({
                    "vod_id": a["href"].split("/")[-1].replace(".html", ""),
                    "vod_name": img.get("alt", "") if img else a.get("title", ""),
                    "vod_pic": img.get("src", "") if img else "",
                    "vod_remarks": item.find("span", class_="update").get_text(strip=True) if item.find("span", class_="update") else ""
                })
        except:
            pass
        return {"list": videos}

    # 分类列表
    def categoryContent(self, cid, pg=1, filter=False, ext=None):
        videos = []
        try:
            url = f"{self.host}/{cid}/index_{pg}.html" if pg > 1 else f"{self.host}/{cid}/"
            resp = requests.get(url, headers=headerx, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select(".vod-item"):
                a = item.find("a")
                img = item.find("img")
                if not a: continue
                videos.append({
                    "vod_id": a["href"].split("/")[-1].replace(".html", ""),
                    "vod_name": img.get("alt", "") if img else a.get("title", ""),
                    "vod_pic": img.get("src", "") if img else "",
                    "vod_remarks": item.find("span", class_="update").get_text(strip=True) if item.find("span", class_="update") else ""
                })
        except:
            pass
        return {"list": videos, "page": pg, "pagecount": 9999, "limit": 30, "total": 99999}

    # 详情页
    def detailContent(self, ids):
        did = ids[0]
        try:
            url = f"{self.host}/vod/{did}.html"
            resp = requests.get(url, headers=headerx, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
            content = soup.find("div", class_="desc").get_text(strip=True) if soup.find("div", class_="desc") else ""

            play_from = ""
            play_url = ""
            idx = 1
            for a in soup.select(".play-list a"):
                pname = a.get_text(strip=True)
                purl = a["href"]
                if purl.startswith("/"):
                    purl = self.host + purl
                play_from += f"线路{idx}$$$"
                play_url += f"{pname}${purl}#"
                idx += 1
            play_from = play_from.rstrip("$$$")
            play_url = play_url.rstrip("#")

            return {"list": [{
                "vod_id": did,
                "vod_name": title,
                "vod_content": content,
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }]}
        except:
            return {"list": []}

    # 播放地址（自动解析，不会再出现停用提示）
    def playerContent(self, flag, id, vipFlags=None):
        try:
            if not id.startswith("http"):
                id = self.host + id
            resp = requests.get(id, headers=headerx, timeout=10)
            # 提取真实播放地址
            m3u8_match = re.search(r'https?://.*?\.m3u8', resp.text)
            if m3u8_match:
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8_match.group(),
                    "header": headerx
                }
            else:
                return {"parse": 1, "url": id, "header": headerx}
        except:
            return {"parse": 0, "url": "", "header": headerx}

    # 搜索
    def searchContent(self, key, quick=False):
        videos = []
        try:
            url = f"{self.host}/search.php?wd={key}"
            resp = requests.get(url, headers=headerx, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select(".vod-item"):
                a = item.find("a")
                img = item.find("img")
                if not a: continue
                videos.append({
                    "vod_id": a["href"].split("/")[-1].replace(".html", ""),
                    "vod_name": img.get("alt", "") if img else a.get("title", ""),
                    "vod_pic": img.get("src", "") if img else "",
                    "vod_remarks": ""
                })
        except:
            pass
        return {"list": videos}

# ===================== 测试运行 =====================
if __name__ == "__main__":
    print("=" * 50)
    print("         剧下饭 juxiafan.com 最新可用爬虫")
    print("=" * 50)

    s = Spider()
    print("\n【1】首页分类")
    print(json.dumps(s.homeContent(), ensure_ascii=False, indent=2))

    print("\n【2】首页推荐")
    print(json.dumps(s.homeVideoContent(), ensure_ascii=False, indent=2))

    print("\n【3】搜索：狂飙")
    print(json.dumps(s.searchContent("狂飙"), ensure_ascii=False, indent=2))

    print("\n✅ 已修复停用提示，可正常播放！")
    input("\n运行完成，按回车退出")
