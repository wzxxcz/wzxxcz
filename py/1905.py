# coding=utf-8
"""
1905电影网 (1905.com) 爬虫
适配影视仓 / OK影视 / TVBox 等空壳影视APP
主域名: https://www.1905.com (可跳转防失效)
数据源: https://vip.1905.com (VIP影院,支持HTTP直连)

接口规范：
- homeContent(filter)       → {"class":[...], "filters":{...}}
- homeVideoContent()        → {"list":[...]}
- categoryContent(tid,pg,filter,extend) → {"list":[...], "page":..., "pagecount":..., ...}
- detailContent(ids)        → {"list":[{...}]}
- playerContent(flag,id,vipFlags) → {"parse":..., "url":..., "header":...}
- searchContent(key,quick,pg) → {"list":[...], ...}
"""

import re
import json
import time
import uuid
import urllib.parse
import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.name = "1905电影网"
        # 主域名 - 防失效,可跳转
        self.host = "https://www.1905.com"
        # 实际数据源 (VIP站可被直接HTTP访问,www站会403)
        self.vip_host = "https://vip.1905.com"
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.vip_host
        }

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    def _get(self, url, params=None, allow_redirects=True):
        """发送GET请求"""
        try:
            r = requests.get(url, headers=self.header, params=params,
                             timeout=20, allow_redirects=allow_redirects)
            r.encoding = 'utf-8'
            return r.text
        except Exception as e:
            print(f"请求异常: {e}")
            return ''

    def _fix_url(self, url):
        """修复相对URL为绝对URL"""
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.vip_host + url
        if url.startswith('http://'):
            return url.replace('http://', 'https://')
        return url

    def _parse_list_item(self, li):
        """解析单个视频卡片 (电影+电视剧通用)"""
        try:
            # 查找带img class的链接
            a = li.xpath('.//a[contains(@class, "img")]')
            if not a:
                return None
            a = a[0]

            href = a.get('href', '')
            title = a.get('title', '')
            if not href:
                return None

            play_url = self._fix_url(href)

            # 提取ID
            m = re.search(r'/play/(\d+)\.shtml', href)
            if not m:
                return None
            vod_id = m.group(1)

            # 图片 - 优先data-lazysrc
            vod_pic = ''
            img = a.xpath('.//img')
            if img:
                vod_pic = img[0].get('data-lazysrc') or img[0].get('src', '')
                vod_pic = self._fix_url(vod_pic)

            # 评分
            score = ''
            score_el = li.xpath('.//span[contains(@class, "score")]/text()')
            if score_el:
                score = score_el[0].strip()

            # 简介
            intro = ''
            intro_el = li.xpath('.//span[contains(@class, "intro")]/text()')
            if intro_el:
                intro = intro_el[0].strip()

            # 年份
            year = ''
            year_el = li.xpath('.//span[contains(@class, "hidden") and contains(@class, "year")]/text()')
            if year_el:
                year = year_el[0].strip()

            # 集数(电视剧)
            ep = ''
            ep_el = li.xpath('.//em[contains(@class, "shorttv")]/text()')
            if ep_el:
                ep = ep_el[0].strip()

            # 备注
            remarks = ep if ep else (score if score else intro)
            if year and not ep:
                remarks = (remarks + ' ' if remarks else '') + year

            if not title:
                name_el = li.xpath('.//span[contains(@class, "name")]/text()')
                if name_el:
                    title = name_el[0].strip()

            if not title:
                return None

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": vod_pic,
                "vod_remarks": remarks
            }
        except Exception as e:
            print(f"解析卡片异常: {e}")
            return None

    def _parse_video_list(self, html):
        """解析视频列表页"""
        videos = []
        try:
            root = etree.HTML(html)
            cards = root.xpath('//li[contains(@class, "borderBox")]')
            print(f"找到 {len(cards)} 个卡片")

            for card in cards:
                video = self._parse_list_item(card)
                if video and video.get("vod_name"):
                    videos.append(video)
        except Exception as e:
            print(f"解析列表异常: {e}")

        print(f"解析到 {len(videos)} 个视频")
        return videos

    def _parse_pagecount(self, html):
        """解析总页数"""
        total = 1
        try:
            root = etree.HTML(html)
            # 查找分页链接中的最大页码
            page_links = root.xpath('//a[contains(@href, "/list") or contains(@href, "/listtv")]')
            max_page = 0
            for link in page_links:
                href = link.get('href', '')
                m = re.search(r'p(\d+)[o\.]', href)
                if m:
                    max_page = max(max_page, int(m.group(1)))

            # 检查是否有"下一页"
            has_next = False
            for link in page_links:
                text = (link.text or '').strip()
                if '下一页' in text or 'next' in text.lower():
                    has_next = True
                    break
            # 也检查class
            if not has_next:
                next_links = root.xpath('//a[contains(@class, "next")]')
                if next_links:
                    has_next = True

            if has_next:
                total = max(max_page, 2)
            elif max_page > 0:
                total = max_page
        except Exception as e:
            print(f"解析分页异常: {e}")
        return total

    # ==================== 首页接口 ====================

    def homeContent(self, filter):
        result = {"class": []}

        classes = [
            {"type_name": "全部电影", "type_id": "movie_all"},
            {"type_name": "华语电影", "type_id": "movie_a_1"},
            {"type_name": "港台电影", "type_id": "movie_a_2"},
            {"type_name": "欧美电影", "type_id": "movie_a_4"},
            {"type_name": "其他电影", "type_id": "movie_a_5"},
            {"type_name": "会员免费", "type_id": "movie_free"},
            {"type_name": "CCTV6强片", "type_id": "movie_cctv6"},
            {"type_name": "好莱坞大片", "type_id": "movie_jiaflix"},
            {"type_name": "全部电视剧", "type_id": "tv_all"},
            {"type_name": "内地剧", "type_id": "tv_a_1"},
            {"type_name": "港台剧", "type_id": "tv_a_2"},
            {"type_name": "其他剧", "type_id": "tv_a_99"},
        ]
        result["class"] = classes

        # ===== 筛选器 =====
        type_movie = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "t_1"}, {"n": "喜剧", "v": "t_2"},
            {"n": "爱情", "v": "t_3"}, {"n": "冒险", "v": "t_4"},
            {"n": "文艺", "v": "t_5"}, {"n": "惊悚", "v": "t_6"},
            {"n": "战争", "v": "t_8"}, {"n": "剧情", "v": "t_9"},
            {"n": "科幻", "v": "t_10"}, {"n": "家庭", "v": "t_12"},
            {"n": "警匪", "v": "t_13"}, {"n": "运动", "v": "t_14"},
            {"n": "神话", "v": "t_15"}, {"n": "武侠", "v": "t_16"},
            {"n": "动画", "v": "t_20"}, {"n": "儿童", "v": "t_21"},
            {"n": "传记", "v": "t_24"}, {"n": "灾难", "v": "t_25"},
            {"n": "青春", "v": "t_27"}, {"n": "女性", "v": "t_29"},
            {"n": "经典", "v": "t_30"}, {"n": "系列", "v": "t_31"},
            {"n": "悬疑", "v": "t_33"}, {"n": "历史", "v": "t_35"},
            {"n": "伦理", "v": "t_36"},
        ]
        type_movie_short = [
            {"n": "全部", "v": ""},
            {"n": "动作", "v": "t_1"}, {"n": "喜剧", "v": "t_2"},
            {"n": "爱情", "v": "t_3"}, {"n": "剧情", "v": "t_9"},
            {"n": "武侠", "v": "t_16"}, {"n": "警匪", "v": "t_13"},
            {"n": "战争", "v": "t_8"},
        ]
        type_tv = [
            {"n": "全部", "v": ""},
            {"n": "古装", "v": "t_1"}, {"n": "都市", "v": "t_2"},
            {"n": "言情", "v": "t_3"}, {"n": "武侠", "v": "t_4"},
            {"n": "战争", "v": "t_5"}, {"n": "青春", "v": "t_6"},
            {"n": "喜剧", "v": "t_7"}, {"n": "家庭", "v": "t_8"},
            {"n": "军旅", "v": "t_11"}, {"n": "犯罪", "v": "t_12"},
            {"n": "动作", "v": "t_15"}, {"n": "剧情", "v": "t_18"},
            {"n": "历史", "v": "t_19"}, {"n": "乡村", "v": "t_20"},
            {"n": "悬疑", "v": "t_26"},
        ]
        year_movie = [
            {"n": "全部", "v": ""},
            {"n": "2025", "v": "y_2025"}, {"n": "2024", "v": "y_2024"},
            {"n": "2023", "v": "y_2023"}, {"n": "2022", "v": "y_2022"},
            {"n": "2021", "v": "y_2021"}, {"n": "2020", "v": "y_2020"},
            {"n": "2019", "v": "y_2019"}, {"n": "2018", "v": "y_2018"},
            {"n": "2017", "v": "y_2017"}, {"n": "2016", "v": "y_2016"},
            {"n": "2015", "v": "y_2015"}, {"n": "2014-2011", "v": "y_2014"},
            {"n": "2010-2000", "v": "y_2010"}, {"n": "更早", "v": "y_more"},
        ]
        area_movie = [
            {"n": "全部", "v": ""},
            {"n": "内地", "v": "a_1"}, {"n": "港台", "v": "a_2"},
            {"n": "欧美", "v": "a_4"}, {"n": "其他", "v": "a_5"},
        ]
        fee_vals = [
            {"n": "全部", "v": ""},
            {"n": "会员免费", "v": "r_free"}, {"n": "会员用券", "v": "r_5"},
        ]
        sort_movie = [
            {"n": "热播榜", "v": "o6"}, {"n": "历史热播", "v": "o2"},
            {"n": "新上线", "v": "o1"}, {"n": "好评榜", "v": "o3"},
        ]
        sort_tv = [
            {"n": "热播榜", "v": "o6"}, {"n": "新上线", "v": "o1"},
        ]
        area_tv = [
            {"n": "全部", "v": ""},
            {"n": "内地", "v": "y_1"}, {"n": "港台", "v": "y_2"},
            {"n": "其他", "v": "y_99"},
        ]

        filters = {}
        # 电影分类筛选器
        full_movie_filter = [
            {"key": "type", "name": "类型", "value": type_movie},
            {"key": "year", "name": "年代", "value": year_movie},
            {"key": "area", "name": "地区", "value": area_movie},
            {"key": "fee", "name": "资费", "value": fee_vals},
            {"key": "sort", "name": "排序", "value": sort_movie},
        ]
        short_movie_filter = [
            {"key": "type", "name": "类型", "value": type_movie_short},
            {"key": "sort", "name": "排序", "value": sort_movie},
        ]
        sort_only_movie = [
            {"key": "sort", "name": "排序", "value": sort_movie},
        ]

        filters["movie_all"] = full_movie_filter
        filters["movie_a_1"] = [
            {"key": "type", "name": "类型", "value": type_movie_short},
            {"key": "year", "name": "年代", "value": year_movie},
            {"key": "fee", "name": "资费", "value": fee_vals},
            {"key": "sort", "name": "排序", "value": sort_movie},
        ]
        filters["movie_a_2"] = short_movie_filter
        filters["movie_a_4"] = short_movie_filter
        filters["movie_a_5"] = sort_only_movie
        filters["movie_free"] = short_movie_filter
        filters["movie_cctv6"] = sort_only_movie
        filters["movie_jiaflix"] = sort_only_movie

        # 电视剧分类筛选器
        filters["tv_all"] = [
            {"key": "type", "name": "类型", "value": type_tv},
            {"key": "area", "name": "地区", "value": area_tv},
            {"key": "fee", "name": "资费", "value": fee_vals},
            {"key": "sort", "name": "排序", "value": sort_tv},
        ]
        filters["tv_a_1"] = [
            {"key": "type", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "古装", "v": "t_1"}, {"n": "都市", "v": "t_2"},
                {"n": "言情", "v": "t_3"}, {"n": "武侠", "v": "t_4"},
                {"n": "战争", "v": "t_5"}, {"n": "青春", "v": "t_6"},
            ]},
            {"key": "sort", "name": "排序", "value": sort_tv},
        ]
        filters["tv_a_2"] = [
            {"key": "type", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "古装", "v": "t_1"}, {"n": "都市", "v": "t_2"},
                {"n": "言情", "v": "t_3"}, {"n": "武侠", "v": "t_4"},
            ]},
            {"key": "sort", "name": "排序", "value": sort_tv},
        ]
        filters["tv_a_99"] = [
            {"key": "sort", "name": "排序", "value": sort_tv},
        ]

        result["filters"] = filters
        return result

    def homeVideoContent(self):
        """首页推荐列表"""
        videos = []
        try:
            html = self._get(self.vip_host + '/list/p1o6.shtml')
            if html:
                videos = self._parse_video_list(html)
        except Exception as e:
            print(f"首页获取异常: {e}")
        return {"list": videos[:30]}

    # ==================== 分类接口 ====================

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容列表"""
        try:
            pg = int(pg) if pg else 1

            if isinstance(extend, str) and extend:
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            elif not extend:
                extend = {}

            sort = extend.get('sort', 'o6')

            if tid.startswith('tv_'):
                url = self._build_tv_url(tid, pg, extend, sort)
            else:
                url = self._build_movie_url(tid, pg, extend, sort)

            print(f"分类URL: {url}")
            html = self._get(url)

            if html:
                videos = self._parse_video_list(html)
                total_pages = self._parse_pagecount(html)
            else:
                videos = []
                total_pages = 1

            return {
                'list': videos,
                'page': pg,
                'pagecount': total_pages,
                'limit': len(videos),
                'total': total_pages * 30 if videos else 0
            }
        except Exception as e:
            print(f"分类获取异常: {e}")
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def _build_movie_url(self, tid, pg, extend, sort):
        """构建电影列表URL"""
        parts = []
        # 固定筛选
        fixed = {
            "movie_a_1": "a_1", "movie_a_2": "a_2", "movie_a_4": "a_4",
            "movie_a_5": "a_5", "movie_free": "r_free",
            "movie_cctv6": "t_cctv6", "movie_jiaflix": "t_jiaflix",
        }
        if tid in fixed:
            parts.append(fixed[tid])

        # 动态筛选
        for key in ["type", "year", "area", "fee"]:
            val = extend.get(key, '')
            if val:
                parts.append(val)

        filter_str = '_'.join(parts)
        if filter_str:
            return f"{self.vip_host}/list/{filter_str}/p{pg}{sort}.shtml"
        else:
            return f"{self.vip_host}/list/p{pg}{sort}.shtml"

    def _build_tv_url(self, tid, pg, extend, sort):
        """构建电视剧列表URL"""
        # 电视剧URL格式: /listtv/r_all_t_X_y_Y/oZpN.shtml
        area = extend.get('area', '')
        if tid == "tv_a_1":
            area = area or "y_1"
        elif tid == "tv_a_2":
            area = area or "y_2"
        elif tid == "tv_a_99":
            area = area or "y_99"
        else:
            area = area or ""

        type_val = extend.get('type', '')
        fee_val = extend.get('fee', '')

        # 构建路径: r_all_t_X_y_Y
        path_parts = ["r_all"]
        if type_val:
            path_parts.append(type_val)
        else:
            path_parts.append("t_0")
        if area:
            path_parts.append(area)
        else:
            path_parts.append("y_0")

        path = '_'.join(path_parts)
        if fee_val and fee_val != "r_all":
            path = fee_val + '_' + '_'.join(path_parts[1:])

        sort_num = sort.replace('o', '')
        return f"{self.vip_host}/listtv/{path}/o{sort_num}p{pg}.shtml"

    # ==================== 详情接口 ====================

    def detailContent(self, ids):
        """获取视频详情"""
        try:
            vod_id = ids[0]
            detail_url = f"{self.vip_host}/play/{vod_id}.shtml"
            print(f"详情URL: {detail_url}")

            html = self._get(detail_url)
            if not html:
                return {'list': []}

            root = etree.HTML(html)

            # ---- 标题 ----
            vod_name = ''
            # 优先从CONFIG提取
            m = re.search(r"CONFIG\['contentname'\]\s*=\s*'([^']*)'", html)
            if m:
                vod_name = m.group(1)
            if not vod_name:
                h1 = root.xpath('//h1/text()')
                if h1:
                    vod_name = h1[0].strip()
            if not vod_name:
                title_el = root.xpath('//title/text()')
                if title_el:
                    vod_name = title_el[0].split('—')[0].split('-')[0].strip()

            # ---- 封面 ----
            vod_pic = ''
            # 优先: 电视剧介绍区海报
            tv_img = root.xpath('//div[contains(@class, "conTv_introduce")]//img/@src')
            if tv_img:
                vod_pic = self._fix_url(tv_img[0])
            # 其次: itemprop image
            if not vod_pic:
                item_img = root.xpath('//meta[@itemprop="image"]/@content')
                if item_img:
                    vod_pic = self._fix_url(item_img[0])
                    vod_pic = vod_pic.replace('thumb_1_60_60_', 'thumb_1_265_376_')
            # 最后: 页面内任意uploadfile图片
            if not vod_pic or '114x114' in vod_pic:
                page_imgs = root.xpath('//img[contains(@src, "uploadfile")]/@src')
                if page_imgs:
                    for img_url in page_imgs:
                        if 'thumb_1_' in img_url:
                            vod_pic = self._fix_url(img_url)
                            break

            # ---- 信息字段 ----
            vod_year = vod_area = vod_class = vod_actor = vod_director = vod_remarks = vod_content = ''
            vod_score = ''

            # 评分
            score_el = root.xpath('//span[contains(@class, "score")]/text()')
            if score_el:
                vod_score = score_el[0].strip()

            # ===== 电视剧详情页: 从 conTv_introduce 区域提取 =====
            tv_intro = root.xpath('//div[contains(@class, "conTv_introduce")]')
            if tv_intro:
                tv_html = etree.tostring(tv_intro[0], encoding='unicode')
                # 导演
                d_m = re.search(r'导演：.*?<span>(?:<a[^>]*>)?(.*?)(?:</a>)?</span>', tv_html, re.DOTALL)
                if d_m:
                    vod_director = d_m.group(1).strip()
                # 地区
                ar_m = re.search(r'地区：<span>(.*?)</span>', tv_html)
                if ar_m:
                    vod_area = ar_m.group(1).strip()
                # 类型
                t_m = re.search(r'类型：<span>(.*?)</span>', tv_html)
                if t_m:
                    vod_class = t_m.group(1).strip()
                # 年份
                y_m = re.search(r'年份：<span>(.*?)</span>', tv_html)
                if y_m:
                    vod_year = y_m.group(1).strip()
                # 简介
                desc_m = re.search(r'<p class="intro"><span>简介：</span>(.*?)</p>', tv_html, re.DOTALL)
                if desc_m:
                    vod_content = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()

            # ===== 电影详情页: 从 player_tab 和 meta 提取 =====
            # 类型 - player_tab 中的类型链接
            if not vod_class:
                type_links = root.xpath('//div[contains(@class, "player_tab")]//a/text()')
                if type_links:
                    vod_class = ' '.join([t.strip() for t in type_links if t.strip()][:4])

            # 简介 - meta description
            if not vod_content:
                desc_meta = root.xpath('//meta[@name="description"]/@content')
                if desc_meta:
                    vod_content = desc_meta[0].strip()

            # 隐藏信息 (列表页卡片格式遗留)
            if not vod_year:
                hidden_year = root.xpath('//span[contains(@class, "hidden") and contains(@class, "year")]/text()')
                if hidden_year:
                    vod_year = hidden_year[0].strip()
            if not vod_actor:
                hidden_actor = root.xpath('//span[contains(@class, "hidden") and contains(@class, "actor")]/text()')
                if hidden_actor:
                    vod_actor = hidden_actor[0].strip()
            if not vod_content:
                hidden_desc = root.xpath('//span[contains(@class, "hidden") and contains(@class, "descr")]/text()')
                if hidden_desc:
                    vod_content = hidden_desc[0].strip()

            # 集数信息
            ep_info = ''
            ep_m = re.search(r'(\d+集全|更新至\d+集|全\d+集)', html)
            if ep_m:
                ep_info = ep_m.group(1)
                vod_remarks = ep_info

            # ---- 播放列表 ----
            vod_play_from = []
            vod_play_url = []

            # 检查是否有剧集列表(电视剧)
            episodes = root.xpath('//li[@video-id]')
            if episodes and len(episodes) > 1:
                # 电视剧 - 多集
                play_list = []
                for ep in episodes:
                    ep_a = ep.xpath('.//a/@href')
                    ep_span = ep.xpath('.//span/text()')
                    if ep_a and ep_span:
                        ep_href = self._fix_url(ep_a[0])
                        ep_num = ep_span[0].strip()
                        ep_id_m = re.search(r'/play/(\d+)\.shtml', ep_href)
                        ep_id = ep_id_m.group(1) if ep_id_m else ''
                        play_list.append(f"第{ep_num}集${ep_id}")
                if play_list:
                    vod_play_from.append('1905电视剧')
                    vod_play_url.append('#'.join(play_list))

            # 如果不是电视剧,就是电影单集
            if not vod_play_from:
                vod_play_from.append('1905影院')
                vod_play_url.append(f'正片${vod_id}')

            # 构建内容描述
            content_parts = []
            if vod_class:
                content_parts.append(f"类型: {vod_class}")
            if vod_year:
                content_parts.append(f"年份: {vod_year}")
            if vod_area:
                content_parts.append(f"地区: {vod_area}")
            if vod_director:
                content_parts.append(f"导演: {vod_director}")
            if vod_actor:
                content_parts.append(f"主演: {vod_actor}")
            if ep_info:
                content_parts.append(f"集数: {ep_info}")
            if vod_content:
                content_parts.append(f"简介: {vod_content}")
            vod_content_full = '\n'.join(content_parts) if content_parts else '暂无简介'

            detail = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_remarks": vod_remarks,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_content": vod_content_full,
                "vod_class": vod_class,
                "vod_score": vod_score,
                "vod_play_from": '$$$'.join(vod_play_from),
                "vod_play_url": '$$$'.join(vod_play_url)
            }
            return {'list': [detail]}
        except Exception as e:
            print(f"详情解析异常: {e}")
            import traceback
            traceback.print_exc()
            return {'list': []}

    # ==================== 播放接口 ====================

    def playerContent(self, flag, id, vipFlags):
        """解析播放地址 - 调用1905官方API获取真实视频直链"""
        try:
            # 1905官方播放API: 返回真实视频直链(mp4)
            # 免费老片返回完整视频, 新片/VIP片返回5分钟试看片段
            api_url = f"{self.vip_host}/playerhtml5/ygp"
            params = {
                'vipid': id,
                'uuid': str(uuid.uuid4()),
                'playerid': str(int(time.time() * 1000))
            }
            req_header = {
                'User-Agent': self.header['User-Agent'],
                'Referer': f"{self.vip_host}/play/{id}.shtml"
            }

            print(f"播放API: {api_url}?vipid={id}")
            r = requests.get(api_url, headers=req_header, params=params,
                             timeout=15, allow_redirects=True)
            r.encoding = 'utf-8'
            data = r.json()

            if data.get('status') == 200 and data.get('data', {}).get('path'):
                paths = data['data']['path']
                # 按优先级取视频地址
                # hdexpmp4i = 高清试看MP4, hdmp4i = 高清MP4
                play_url = ''
                for key in ['hdexpmp4i', 'hdmp4i', 'sdexpmp4i', 'sdmp4i']:
                    if key in paths and paths[key]:
                        play_url = paths[key]
                        print(f"获取到视频地址({key}): {play_url[:80]}...")
                        break

                if play_url:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": play_url,
                        "header": json.dumps({
                            "User-Agent": self.header['User-Agent'],
                            "Referer": self.vip_host + '/'
                        })
                    }

            # Fallback: 返回播放页URL, 交给播放器内置解析
            print("API未返回视频地址, fallback到网页解析")
            play_url = f"{self.vip_host}/play/{id}.shtml"
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": json.dumps({
                    "User-Agent": self.header['User-Agent'],
                    "Referer": self.vip_host + '/'
                })
            }
        except Exception as e:
            print(f"播放解析异常: {e}")
            import traceback
            traceback.print_exc()
            # 最终fallback
            try:
                play_url = f"{self.vip_host}/play/{id}.shtml"
                return {
                    "parse": 1,
                    "playUrl": "",
                    "url": play_url,
                    "header": json.dumps({
                        "User-Agent": self.header['User-Agent'],
                        "Referer": self.vip_host + '/'
                    })
                }
            except Exception:
                return {"parse": 0, "playUrl": "", "url": ""}

    # ==================== 搜索接口 ====================

    def searchContent(self, key, quick, pg='1'):
        """搜索"""
        videos = []
        try:
            pg = int(pg) if pg else 1
            key = key.strip() if key else ''

            if not key:
                return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

            if pg > 1:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

            keyword = urllib.parse.quote(key)
            url = f"{self.vip_host}/Search?q={keyword}"
            print(f"搜索URL: {url}")

            html = self._get(url)
            if not html:
                print("搜索页面获取失败")
                return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

            videos = self._parse_search_result(html)
            print(f"搜索到 {len(videos)} 个结果")

            return {
                'list': videos,
                'page': 1,
                'pagecount': 1,
                'limit': len(videos),
                'total': len(videos)
            }
        except Exception as e:
            print(f"搜索异常: {e}")
            import traceback
            traceback.print_exc()
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    def _parse_search_result(self, html):
        """解析搜索结果页面"""
        videos = []
        try:
            root = etree.HTML(html)

            # 搜索结果在 clearfix_smile 的 li 中
            cards = root.xpath('//li[contains(@class, "clearfix_smile")]')
            if not cards:
                cards = root.xpath('//li[.//a[contains(@href, "play/")]]')

            print(f"搜索结果找到 {len(cards)} 个卡片")

            for card in cards:
                try:
                    # 查找播放链接
                    a = card.xpath('.//a[contains(@href, "play/") and contains(@class, "img")]')
                    if not a:
                        a = card.xpath('.//a[contains(@href, "play/")]')
                    if not a:
                        continue
                    a = a[0]
                    href = a.get('href', '')
                    title = a.get('title', '')
                    if not href:
                        continue

                    play_url = self._fix_url(href)
                    m = re.search(r'/play/(\d+)\.shtml', href)
                    if not m:
                        continue
                    vod_id = m.group(1)

                    # 标题
                    if not title:
                        name_el = card.xpath('.//span[contains(@class, "name")]//text()')
                        if name_el:
                            title = ''.join(name_el).strip()
                    if not title:
                        name_el = card.xpath('.//a[contains(@href, "play/")]/@title')
                        if name_el:
                            title = name_el[0].strip()
                    if not title:
                        img_alt = card.xpath('.//img/@alt')
                        if img_alt:
                            title = img_alt[0].strip()

                    if not title:
                        continue

                    # 图片
                    vod_pic = ''
                    img = card.xpath('.//img')
                    if img:
                        vod_pic = img[0].get('data-lazysrc') or img[0].get('data-src') or img[0].get('src', '')
                        vod_pic = self._fix_url(vod_pic)

                    # 类型/备注
                    vod_remarks = ''
                    type_el = card.xpath('.//span[contains(@class, "label")]/following-sibling::text()')
                    if type_el:
                        vod_remarks = type_el[0].strip()
                    if not vod_remarks:
                        # 尝试从info区域获取
                        info_el = card.xpath('.//span[contains(@class, "clr9")]/following-sibling::text()')
                        if info_el:
                            vod_remarks = info_el[0].strip()
                    if not vod_remarks:
                        vod_remarks = '1905'

                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
                except Exception as e:
                    print(f"解析搜索卡片失败: {e}")
                    continue

        except Exception as e:
            print(f"解析搜索结果异常: {e}")
            import traceback
            traceback.print_exc()

        print(f"解析到 {len(videos)} 个搜索结果")
        return videos

    # ==================== 辅助方法 ====================

    def isVideoFormat(self, url):
        """判断URL是否为直链视频格式"""
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return None

    def destroy(self):
        pass
