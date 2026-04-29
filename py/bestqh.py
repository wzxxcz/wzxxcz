# ==============================================
# TVBox 影视爬虫 通用强化版（支持过验证）
# ==============================================
CONFIG = {
    "HOST": "https://www.bestqh.com",
    "NAME": "🍊支持验证的源",

    # 分类可自由增删
    "CATEGORIES": [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "电视剧"},
        {"type_id": "3", "type_name": "综艺"},
        {"type_id": "4", "type_name": "动漫"},
        {"type_id": "6", "type_name": "短剧"},
    ],

    # ----------------------
    # 验证配置（有就填，没有留空）
    # ----------------------
    "COOKIE": "",  # 登录后的Cookie
    "USER_AGENT": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "REFERER": "https://www.bestqh.com",
    "ENABLE_TIMEOUT": True,  # 开启防封延时
    "TIMEOUT": 15,
}

# ===================== 核心引擎（不用动） =====================
import requests
import re
import json
import time
import random
from urllib.parse import urljoin

HOST = CONFIG["HOST"]

def get_headers():
    h = {
        "User-Agent": CONFIG["USER_AGENT"],
        "Referer": CONFIG["REFERER"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    if CONFIG["COOKIE"]:
        h["Cookie"] = CONFIG["COOKIE"]
    return h

def sleep():
    if CONFIG["ENABLE_TIMEOUT"]:
        time.sleep(random.uniform(0.4, 0.9))

def get_html(url):
    sleep()
    try:
        r = requests.get(
            url,
            headers=get_headers(),
            timeout=CONFIG["TIMEOUT"],
            verify=False
        )
        r.encoding = "utf-8"
        return r.text
    except Exception as e:
        return ""

# 分类
def get_class():
    return CONFIG["CATEGORIES"]

# 首页
def get_home():
    html = get_html(HOST)
    rule = r'<li class="video-item">.*?<a href="([^"]+)".*?data-original="([^"]+)".*?<h3><a[^>]+>([^<]+)</a>'
    items = re.findall(rule, html, re.S)
    res = []
    for href, img, title in items:
        res.append({
            "vod_id": href,
            "vod_name": title.strip(),
            "vod_pic": img
        })
    return res[:30]

# 列表
def get_list(tid, pg=1):
    url = f"{HOST}/type/{tid}/{pg}.html"
    html = get_html(url)
    rule = r'<li class="video-item">.*?<a href="([^"]+)".*?data-original="([^"]+)".*?<h3><a[^>]+>([^<]+)</a>'
    items = re.findall(rule, html, re.S)
    res = []
    for href, img, title in items:
        res.append({
            "vod_id": href,
            "vod_name": title.strip(),
            "vod_pic": img
        })
    return res

# 搜索
def get_search(wd, pg=1):
    url = f"{HOST}/search/{wd}/{pg}.html"
    html = get_html(url)
    rule = r'<li class="video-item">.*?<a href="([^"]+)".*?data-original="([^"]+)".*?<h3><a[^>]+>([^<]+)</a>'
    items = re.findall(rule, html, re.S)
    res = []
    for href, img, title in items:
        res.append({
            "vod_id": href,
            "vod_name": title.strip(),
            "vod_pic": img
        })
    return res

# 详情
def get_detail(did):
    url = HOST + did
    html = get_html(url)

    title = re.search(r'<div class="video-info">.*?<h2>([^<]+)</h2>', html, re.S)
    title = title.group(1).strip() if title else "未知"

    pic = re.search(r'data-original="([^"]+)"', html)
    pic = pic.group(1) if pic else ""

    desc = re.search(r'<div class="video-desc">([^<]+)</div>', html)
    desc = desc.group(1).strip() if desc else "暂无简介"

    line_names = []
    lines = re.findall(r'<div class="play-nav">.*?<ul.*?>(.*?)</ul>', html, re.S)
    if lines:
        line_names = re.findall(r'<li>([^<]+)</li>', lines[0])

    play_urls = []
    boxes = re.findall(r'<div class="play-box">.*?</div>', html, re.S)
    for box in boxes:
        eps = re.findall(r'<a href="([^"]+)">([^<]+)</a>', box)
        tmp = [f"{n.strip()}${urljoin(HOST, u)}" for u, n in eps]
        play_urls.append("$$$".join(tmp))

    return {
        "vod_name": title,
        "vod_pic": pic,
        "vod_content": desc,
        "vod_play_from": "$$$".join(line_names),
        "vod_play_url": "$$$".join(play_urls)
    }

# 输出
if __name__ == "__main__":
    import sys
    argv = sys.argv
    if len(argv) < 2:
        print(json.dumps(get_class(), ensure_ascii=False))
    elif argv[1] == "home":
        print(json.dumps(get_home(), ensure_ascii=False))
    elif argv[1] == "list":
        tid = argv[2] if len(argv) > 2 else "1"
        pg = int(argv[3]) if len(argv) > 3 else 1
        print(json.dumps(get_list(tid, pg), ensure_ascii=False))
    elif argv[1] == "search":
        wd = argv[2] if len(argv) > 2 else ""
        pg = int(argv[3]) if len(argv) > 3 else 1
        print(json.dumps(get_search(wd, pg), ensure_ascii=False))
    elif argv[1] == "detail":
        did = argv[2] if len(argv) > 2 else ""
        print(json.dumps(get_detail(did), ensure_ascii=False))
