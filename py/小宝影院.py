# -*- coding: utf-8 -*-
# 小宝影院 https://www.xiaobaotv.com/ TVBox 蜘蛛
# 标准 MacCMS 站（mytheme 模板）：5 分类动态；列表 /vod/type/{id}[-{pg}].html；
# 二级筛选走 /vod/show/ 路由（id/class/area/year/lang/by 组合）；详情 /vod/detail/{id}.html；
# 播放 /vod/play/{id}-{sid}-{nid}.html，player_aaaa JSON 中 url 即 m3u8 直链（encrypt=0）
import re
import json
from urllib.parse import quote, unquote
import requests
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "小宝影院"

    def init(self, extend=""):
        self.host = "https://www.xiaobaotv.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        })
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
                {"n": "全部", "v": ""},
                {"n": "动作片", "v": "101"},
                {"n": "喜剧片", "v": "102"},
                {"n": "爱情片", "v": "103"},
                {"n": "科幻片", "v": "104"},
                {"n": "剧情片", "v": "105"},
                {"n": "悬疑片", "v": "106"},
                {"n": "惊悚片", "v": "107"},
                {"n": "恐怖片", "v": "108"},
                {"n": "犯罪片", "v": "109"},
                {"n": "冒险片", "v": "111"},
                {"n": "奇幻片", "v": "112"},
                {"n": "灾难片", "v": "113"},
                {"n": "战争片", "v": "114"},
                {"n": "动画电影片", "v": "115"},
                {"n": "歌舞片", "v": "116"},
                {"n": "网络电影片", "v": "117"},
                {"n": "同性片", "v": "118"},
                {"n": "经典片", "v": "121"},
                {"n": "其它片", "v": "122"},
                {"n": "记录片", "v": "124"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "爱情", "v": "爱情"},
                {"n": "古装", "v": "古装"},
                {"n": "动作", "v": "动作"},
                {"n": "伦理", "v": "伦理"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "谍战", "v": "谍战"},
                {"n": "历史", "v": "历史"},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "科幻", "v": "科幻"},
                {"n": "家庭", "v": "家庭"},
                {"n": "青春", "v": "青春"},
                {"n": "剧情", "v": "剧情"},
                {"n": "冒险", "v": "冒险"},
                {"n": "纪录", "v": "纪录"},
                {"n": "动画", "v": "动画"},
                {"n": "人物", "v": "人物"},
                {"n": "文化", "v": "文化"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
                {"n": "2011", "v": "2011"},
                {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"},
                {"n": "2008", "v": "2008"},
                {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"},
                {"n": "2005", "v": "2005"},
                {"n": "2004", "v": "2004"},
                {"n": "2003", "v": "2003"},
                {"n": "2002", "v": "2002"},
                {"n": "2001", "v": "2001"},
                {"n": "2000", "v": "2000"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"},
                {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"},
                {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"},
                {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "2": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "国产剧", "v": "201"},
                {"n": "港台剧", "v": "202"},
                {"n": "台湾剧", "v": "203"},
                {"n": "日韩剧", "v": "204"},
                {"n": "日本剧", "v": "205"},
                {"n": "欧美剧", "v": "206"},
                {"n": "泰国剧", "v": "207"},
                {"n": "海外剧", "v": "208"},
                {"n": "新马泰剧", "v": "209"},
                {"n": "其他剧", "v": "210"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "爱情", "v": "爱情"},
                {"n": "古装", "v": "古装"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "都市", "v": "都市"},
                {"n": "喜剧", "v": "喜剧"},
                {"n": "战争", "v": "战争"},
                {"n": "剧情", "v": "剧情"},
                {"n": "青春", "v": "青春"},
                {"n": "历史", "v": "历史"},
                {"n": "网剧", "v": "网剧"},
                {"n": "奇幻", "v": "奇幻"},
                {"n": "冒险", "v": "冒险"},
                {"n": "励志", "v": "励志"},
                {"n": "犯罪", "v": "犯罪"},
                {"n": "商战", "v": "商战"},
                {"n": "恐怖", "v": "恐怖"},
                {"n": "穿越", "v": "穿越"},
                {"n": "农村", "v": "农村"},
                {"n": "人物", "v": "人物"},
                {"n": "商业", "v": "商业"},
                {"n": "生活", "v": "生活"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
                {"n": "2011", "v": "2011"},
                {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"},
                {"n": "2008", "v": "2008"},
                {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"},
                {"n": "2005", "v": "2005"},
                {"n": "2004", "v": "2004"},
                {"n": "2003", "v": "2003"},
                {"n": "2002", "v": "2002"},
                {"n": "2001", "v": "2001"},
                {"n": "2000", "v": "2000"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"},
                {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"},
                {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"},
                {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "3": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "国产动漫", "v": "301"},
                {"n": "日韩动漫", "v": "302"},
                {"n": "港台动漫", "v": "304"},
                {"n": "欧美动漫", "v": "306"},
                {"n": "其它动漫", "v": "310"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "冒险", "v": "冒险"},
                {"n": "战斗", "v": "战斗"},
                {"n": "搞笑", "v": "搞笑"},
                {"n": "经典", "v": "经典"},
                {"n": "科幻", "v": "科幻"},
                {"n": "玄幻", "v": "玄幻"},
                {"n": "魔幻", "v": "魔幻"},
                {"n": "武侠", "v": "武侠"},
                {"n": "恋爱", "v": "恋爱"},
                {"n": "推理", "v": "推理"},
                {"n": "日常", "v": "日常"},
                {"n": "校园", "v": "校园"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "真人", "v": "真人"},
                {"n": "历史", "v": "历史"},
                {"n": "竞技", "v": "竞技"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
                {"n": "2011", "v": "2011"},
                {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"},
                {"n": "2008", "v": "2008"},
                {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"},
                {"n": "2005", "v": "2005"},
                {"n": "2004", "v": "2004"},
                {"n": "2003", "v": "2003"},
                {"n": "2002", "v": "2002"},
                {"n": "2001", "v": "2001"},
                {"n": "2000", "v": "2000"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"},
                {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"},
                {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"},
                {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "4": [
            {"key": "child", "name": "类型", "value": [
                {"n": "全部", "v": ""},
                {"n": "大陆综艺", "v": "401"},
                {"n": "日韩综艺", "v": "402"},
                {"n": "港台综艺", "v": "404"},
                {"n": "欧美综艺", "v": "406"},
                {"n": "新马泰综艺", "v": "407"},
                {"n": "其它综艺", "v": "410"},
            ]},
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "游戏", "v": "游戏"},
                {"n": "脱口秀", "v": "脱口秀"},
                {"n": "音乐", "v": "音乐"},
                {"n": "情感", "v": "情感"},
                {"n": "生活", "v": "生活"},
                {"n": "职场", "v": "职场"},
                {"n": "真人秀", "v": "真人秀"},
                {"n": "搞笑", "v": "搞笑"},
                {"n": "公益", "v": "公益"},
                {"n": "艺术", "v": "艺术"},
                {"n": "访谈", "v": "访谈"},
                {"n": "益智", "v": "益智"},
                {"n": "体育", "v": "体育"},
                {"n": "少儿", "v": "少儿"},
                {"n": "时尚", "v": "时尚"},
                {"n": "人物", "v": "人物"},
                {"n": "其他", "v": "其他"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
                {"n": "2011", "v": "2011"},
                {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"},
                {"n": "2008", "v": "2008"},
                {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"},
                {"n": "2005", "v": "2005"},
                {"n": "2004", "v": "2004"},
                {"n": "2003", "v": "2003"},
                {"n": "2002", "v": "2002"},
                {"n": "2001", "v": "2001"},
                {"n": "2000", "v": "2000"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"},
                {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"},
                {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"},
                {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
        "11": [
            {"key": "class", "name": "剧情", "value": [
                {"n": "全部", "v": ""},
                {"n": "古装", "v": "古装"},
                {"n": "复仇", "v": "复仇"},
                {"n": "强者", "v": "强者"},
                {"n": "悬疑", "v": "悬疑"},
                {"n": "甜宠", "v": "甜宠"},
                {"n": "神豪", "v": "神豪"},
                {"n": "穿越", "v": "穿越"},
                {"n": "虐恋", "v": "虐恋"},
                {"n": "逆袭", "v": "逆袭"},
                {"n": "重生", "v": "重生"},
                {"n": "萌宝", "v": "萌宝"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""},
                {"n": "中国大陆", "v": "中国大陆"},
                {"n": "中国香港", "v": "中国香港"},
                {"n": "中国台湾", "v": "中国台湾"},
                {"n": "欧美", "v": "欧美"},
                {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"},
                {"n": "泰国", "v": "泰国"},
                {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"},
                {"n": "印度", "v": "印度"},
                {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"},
                {"n": "加拿大", "v": "加拿大"},
                {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "year", "name": "年份", "value": [
                {"n": "全部", "v": ""},
                {"n": "2026", "v": "2026"},
                {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"},
                {"n": "2023", "v": "2023"},
                {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"},
                {"n": "2020", "v": "2020"},
                {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"},
                {"n": "2017", "v": "2017"},
                {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"},
                {"n": "2014", "v": "2014"},
                {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"},
                {"n": "2011", "v": "2011"},
                {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"},
                {"n": "2008", "v": "2008"},
                {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"},
                {"n": "2005", "v": "2005"},
                {"n": "2004", "v": "2004"},
                {"n": "2003", "v": "2003"},
                {"n": "2002", "v": "2002"},
                {"n": "2001", "v": "2001"},
                {"n": "2000", "v": "2000"},
            ]},
            {"key": "lang", "name": "语言", "value": [
                {"n": "全部", "v": ""},
                {"n": "汉语普通话", "v": "汉语普通话"},
                {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"},
                {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"},
                {"n": "法语", "v": "法语"},
                {"n": "德语", "v": "德语"},
                {"n": "西班牙语", "v": "西班牙语"},
                {"n": "意大利语", "v": "意大利语"},
                {"n": "泰语", "v": "泰语"},
                {"n": "其它", "v": "其它"},
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "时间", "v": "time"},
                {"n": "人气", "v": "hits"},
                {"n": "评分", "v": "score"},
            ]},
        ],
    }

    # ---------- 基础 ----------
    def _fetch(self, url, params=None):
        try:
            r = self.session.get(url, params=params, timeout=20)
            if r.status_code != 200:
                return ""
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self.host + (u if u.startswith("/") else "/" + u)

    # ---------- 卡片解析 ----------
    def _parse_cards(self, html):
        vods = []
        seen = set()
        for m in re.finditer(
                r'<a\b[^>]*class="myui-vodlist__thumb[^"]*"[^>]*>', html):
            tag = m.group(0)
            hm = re.search(r'href="(/vod/detail/(\d+)\.html)"', tag)
            tm = re.search(r'title="([^"]*)"', tag)
            sm = re.search(r'data-original="([^"]+)"', tag)
            if not hm or not tm:
                continue
            vid = hm.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            # 备注：同卡片内 span.pic-text（在 a 标签之后一段 HTML 内找最近的一个）
            tail = html[m.end():m.end() + 800]
            rm = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', tail)
            vods.append({
                "vod_id": vid,
                "vod_name": tm.group(1).strip(),
                "vod_pic": self._abs(sm.group(1).strip() if sm else ""),
                "vod_remarks": (rm.group(1).strip() if rm else ""),
            })
        return vods

    # ---------- 二级分类 ----------
    def _opt_keyval(self, href, parent):
        """从筛选项 href 解析出 (key, value)"""
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
            # 先扫非"全部"选项确定本行维度 key（"全部"按钮 href 固定指向父 id，会误判）
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
            # 二级分类内置静态数据，不再现抓（避免 homeContent 网络超时导致筛选按钮不显示）
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
            if extend and any((extend.get(k) or "").strip()
                              for k in ("child", "class", "area", "year", "lang", "by")):
                url = self._show_url(cid, pg, extend)
            else:
                url = "%s/vod/type/%s%s.html" % (
                    self.host, cid, "-%d" % pg if pg > 1 else "")
            html = self._fetch(url)
            vods = self._parse_cards(html)
            pagecount = 1
            pages = re.findall(r'/vod/type/%s-(\d+)\.html' % cid, html)
            if pages:
                pagecount = max(int(p) for p in pages)
            else:
                mp = re.search(r'/page/(\d+)\.html', html)
                if mp:
                    allp = re.findall(r'/page/(\d+)\.html', html)
                    pagecount = max(int(p) for p in allp)
                elif len(vods) < 20:
                    pagecount = pg
            return {"list": vods, "page": pg, "pagecount": pagecount,
                    "limit": 90, "total": 999999}
        except Exception as e:
            print("[%s] categoryContent 异常: %s" % (self.getName(), e))
            return {"list": [], "page": 1, "pagecount": 1, "limit": 90, "total": 0}

    def detailContent(self, ids):
        vods = []
        try:
            vid = re.sub(r"\D", "", ids[0] if ids else "")
            html = self._fetch("%s/vod/detail/%s.html" % (self.host, vid))
            if not html:
                return {"list": []}
            vod = {"vod_id": vid}
            m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
            vod["vod_name"] = m.group(1).strip() if m else vid
            m = re.search(r'myui-content__thumb.*?data-original="([^"]+)"', html, re.S)
            vod["vod_pic"] = self._abs(m.group(1).strip() if m else "")
            m = re.search(r'<span class="text-red">([^<]*)</span>', html)
            vod["vod_remarks"] = m.group(1).strip() if m else ""
            m = re.search(r'<span class="sketch[^"]*"[^>]*>(.*?)</span>', html, re.S)
            if m:
                vod["vod_content"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()[:500]
            actors = re.findall(r'/search/actor/[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_actor"] = ",".join(dict.fromkeys(a.strip() for a in actors))[:200]
            directors = re.findall(r'/search/director/[^"]*"[^>]*>([^<]+)</a>', html)
            vod["vod_director"] = ",".join(dict.fromkeys(d.strip() for d in directors))[:200]

            # 播放源：ul.nav-tabs 的 a[href=#playlistN] 顺序对应 div#playlistN 顺序
            play_from, play_url = [], []
            tabs = re.findall(
                r'<a[^>]*href="#playlist(\d+)"[^>]*>([^<]+)</a>', html)
            for num, src_name in tabs:
                src_name = src_name.strip()
                pm = re.search(
                    r'<div[^>]*id="playlist%s"[^>]*>(.*?)</div>\s*</div>' % num,
                    html, re.S)
                if not pm:
                    pm = re.search(r'id="playlist%s"' % num, html)
                    seg = html[pm.start():pm.start() + 20000] if pm else ""
                else:
                    seg = pm.group(1)
                eps = []
                for href, nm in re.findall(
                        r'<a[^>]*href="(/vod/play/\d+-\d+-\d+\.html)"[^>]*>([^<]*)</a>',
                        seg):
                    nm = nm.strip() or "正片"
                    eps.append("%s$%s" % (nm, self._abs(href)))
                if eps:
                    play_from.append(src_name)
                    play_url.append("#".join(eps))
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

    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            pid = (id or "").strip()
            if not pid:
                return result
            if pid.startswith("http") and ".m3u8" in pid:
                result["url"] = pid
            else:
                page_url = pid if pid.startswith("http") else self._abs(pid)
                html = self._fetch(page_url)
                m = re.search(r'var player_aaaa=(\{.*\})</script>', html, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                    except Exception:
                        data = {}
                    url = (data.get("url") or "").replace("\\/", "/")
                    if url.startswith("http") and ".m3u8" in url:
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
        return bool(url) and ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", ""]
