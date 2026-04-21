# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import re
import json

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'
}

class Spider:
    def getName(self):
        return "青禾影视"

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "电视剧"},
                {"type_id": "3", "type_name": "综艺"},
                {"type_id": "4", "type_name": "动漫"}
            ]
        }

    def homeVideoContent(self):
        return self.categoryContent("1", 1, True, None)

    def categoryContent(self, cid, pg, filter, ext):
        url = f"https://www.bestqh.com/?m=list&tid={cid}&page={pg}"
        try:
            res = requests.get(url, headers=headerx, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            videos = []
            for item in soup.select(".myui-vodlist__box")[:36]:
                a = item.find("a")
                img = item.find("img")
                note = item.find("span", class_="pic-text text-right")
                if not a: continue
                videos.append({
                    "vod_id": a["href"].split("/")[-1].replace(".html", ""),
                    "vod_name": img.get("alt", "") if img else a.get("title", ""),
                    "vod_pic": img.get("data-src", "") if img else "",
                    "vod_remarks": note.get_text(strip=True) if note else ""
                })
            return {
                "list": videos,
                "page": pg,
                "pagecount": 9999,
                "limit": 36,
                "total": 999999
            }
        except:
            return {"list": []}

    def detailContent(self, ids):
        did = ids[0]
        url = f"https://www.bestqh.com/vod/{did}.html"
        try:
            res = requests.get(url, headers=headerx, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            title = soup.find("h4").get_text(strip=True) if soup.find("h4") else ""
            content = soup.find("div", class_="myui-content__detail").get_text(strip=True) if soup.find("div", class_="myui-content__detail") else ""

            play_from = ""
            play_url = ""
            idx = 1

            for a in soup.select(".myui-content__list a"):
                pname = a.get_text(strip=True)
                purl = a["href"]
                play_from += f"线路{idx}$$$"
                play_url += f"{pname}${purl}#"
                idx += 1

            play_from = play_from.rstrip("$$$")
            play_url = play_url.rstrip("#")

            return {
                "list": [{
                    "vod_id": did,
                    "vod_name": title,
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": content,
                    "vod_remarks": "",
                    "vod_year": "",
                    "vod_area": "",
                    "vod_play_from": play_from,
                    "vod_play_url": play_url
                }]
            }
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            if not id.startswith("http"):
                id = "https://www.bestqh.com" + id
            res = requests.get(id, headers=headerx, timeout=10)
            # 提取 iframe 真实地址
            match = re.search(r'<iframe[^>]+src="([^"]+)"', res.text)
            if match:
                parse_url = match.group(1)
                return {
                    "parse": 1,
                    "playUrl": "",
                    "url": parse_url,
                    "header": headerx
                }
        except:
            pass

        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": headerx
        }

    def searchContent(self, key, quick):
        return self.searchContentPage(key, quick, "1")

    def searchContentPage(self, key, quick, pg):
        url = f"https://www.bestqh.com/search.php?searchword={key}"
        try:
            res = requests.get(url, headers=headerx, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            videos = []
            for item in soup.select(".myui-vodlist__box")[:36]:
                a = item.find("a")
                img = item.find("img")
                if not a: continue
                videos.append({
                    "vod_id": a["href"].split("/")[-1].replace(".html", ""),
                    "vod_name": img.get("alt", "") if img else a.get("title", ""),
                    "vod_pic": img.get("data-src", "") if img else "",
                    "vod_remarks": ""
                })
            return {"list": videos, "page": pg, "pagecount": 9999, "limit": 36, "total": 999999}
        except:
            return {"list": []}

if __name__ == "__main__":
    s = Spider()
    print("测试搜索：")
    print(json.dumps(s.searchContent("哪吒", False), ensure_ascii=False))
