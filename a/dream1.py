# -*- coding: utf-8 -*-
import sys
import time
import json
import hashlib
import re
import requests
import urllib3
from urllib.parse import quote

urllib3.disable_warnings()

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    # ============================================================
    # ★★★ 内置关键词映射表（归一化后的 key → 112114 库里的名字）★★★
    #     按长度从长到短排列，保证长 key 优先匹配
    # ============================================================
    _KEYWORD_LOGOS = {
        # ===== CCTV 特殊频道（长的先） =====
        "CCTV5PLUS": "CCTV5+",
        "CCTV5+": "CCTV5+",
        "CCTV5体育": "CCTV5",
        "CCTV5": "CCTV5",
        "CCTV1综合": "CCTV1",
        "CCTV1": "CCTV1",
        "CCTV2财经": "CCTV2",
        "CCTV2": "CCTV2",
        "CCTV3综艺": "CCTV3",
        "CCTV3": "CCTV3",
        "CCTV4中文国际": "CCTV4",
        "CCTV4": "CCTV4",
        "CCTV6电影": "CCTV6",
        "CCTV6": "CCTV6",
        "CCTV7军事": "CCTV7",
        "CCTV7": "CCTV7",
        "CCTV8电视剧": "CCTV8",
        "CCTV8": "CCTV8",
        "CCTV9纪录": "CCTV9",
        "CCTV9": "CCTV9",
        "CCTV10科教": "CCTV10",
        "CCTV10": "CCTV10",
        "CCTV11戏曲": "CCTV11",
        "CCTV11": "CCTV11",
        "CCTV12社会与法": "CCTV12",
        "CCTV12": "CCTV12",
        "CCTV13新闻": "CCTV13",
        "CCTV13": "CCTV13",
        "CCTV14少儿": "CCTV14",
        "CCTV14": "CCTV14",
        "CCTV15音乐": "CCTV15",
        "CCTV15": "CCTV15",
        "CCTV16奥林匹克": "CCTV16",
        "CCTV16": "CCTV16",
        "CCTV17农业": "CCTV17",
        "CCTV17": "CCTV17",

        # ===== 各大卫视 =====
        "湖南卫视": "湖南卫视",
        "浙江卫视": "浙江卫视",
        "江苏卫视": "江苏卫视",
        "东方卫视": "东方卫视",
        "北京卫视": "北京卫视",
        "安徽卫视": "安徽卫视",
        "山东卫视": "山东卫视",
        "广东卫视": "广东卫视",
        "深圳卫视": "深圳卫视",
        "天津卫视": "天津卫视",
        "湖北卫视": "湖北卫视",
        "四川卫视": "四川卫视",
        "重庆卫视": "重庆卫视",
        "辽宁卫视": "辽宁卫视",
        "黑龙江卫视": "黑龙江卫视",
        "吉林卫视": "吉林卫视",
        "河南卫视": "河南卫视",
        "河北卫视": "河北卫视",
        "山西卫视": "山西卫视",
        "陕西卫视": "陕西卫视",
        "甘肃卫视": "甘肃卫视",
        "宁夏卫视": "宁夏卫视",
        "青海卫视": "青海卫视",
        "新疆卫视": "新疆卫视",
        "西藏卫视": "西藏卫视",
        "云南卫视": "云南卫视",
        "贵州卫视": "贵州卫视",
        "广西卫视": "广西卫视",
        "海南卫视": "海南卫视",
        "东南卫视": "东南卫视",
        "江西卫视": "江西卫视",
        "内蒙古卫视": "内蒙古卫视",
        "厦门卫视": "厦门卫视",
        "延边卫视": "延边卫视",
        "兵团卫视": "兵团卫视",

        # ===== 港澳台 =====
        "翡翠台": "翡翠台",
        "明珠台": "明珠台",
        "无线新闻": "无线新闻台",
        "无线财经": "无线财经资讯台",
        "TVB": "翡翠台",
        "J2": "J2",
        "VIUTV": "ViuTV",
        "HOYTV": "HOY TV",
        "凤凰卫视中文台": "凤凰卫视中文台",
        "凤凰卫视资讯台": "凤凰卫视资讯台",
        "凤凰卫视香港台": "凤凰卫视香港台",
        "凤凰卫视电影台": "凤凰卫视电影台",
        "凤凰中文": "凤凰卫视中文台",
        "凤凰资讯": "凤凰卫视资讯台",
        "凤凰香港": "凤凰卫视香港台",
        "凤凰电影": "凤凰卫视电影台",
        "澳视澳门": "澳视澳门",
        "澳门莲花": "澳门莲花卫视",
        "民视": "民视新闻台",
        "中视": "中视",
        "华视": "华视",
        "台视": "台视",
        "公视": "公视",
        "大爱": "大爱一台",
        "中天": "中天新闻台",
        "东森": "东森新闻台",
        "三立": "三立新闻台",
        "TVBS": "TVBS新闻台",
        "年代": "年代新闻",
        "八大": "八大第一台",
        "非凡": "非凡新闻台",
        "纬来": "纬来综合台",
        "龙华": "龙华偶像台",

        # ===== 地方台常见 =====
        "上海新闻综合": "上海新闻综合",
        "上海东方卫视": "东方卫视",
        "湖南经视": "湖南经视",
        "江苏城市": "江苏城市",
        "北京新闻": "北京新闻",
        "广东珠江": "广东珠江",
        "南方卫视": "南方卫视",
        "深圳都市": "深圳都市频道",
    }

    def __init__(self):
        super().__init__()
        self.session = requests.Session()

        # ===== Dream TV 原 PHP 固定參數 =====
        self.device_ids = [
            '00:fa:20:22:02:8cf4:09:d8:88:51:7a',
            '00:fa:20:22:05:07d0:22:be:7f:28:f5',
            '00:fa:20:22:1f:09f0:25:b7:76:b1:1a',
            '00:ea:20:21:4b:96d0:22:be:c1:c7:bb',
            '00:ea:20:21:53:5900:00:00:00:00:00',
        ]
        self.devid = self.device_ids[4]
        self.hardware = "Dream TV-Amlogic-8.1.73GB-11.50 GB-nw"
        self.version = "DreamTV 20220516"
        self.salt = "MZkF@270mp#cOKD0%8Y8dV&5AmH&BTzq"
        self.from_id = "2011"

        self.api_urls = [
            "https://b51d520253d0cfed.boxtv.win/api/wbtj5hmx",
            "http://api.2011.boxtv.win/api/wbtj5hmx",
            "https://n1ox3.asiaw.top/api/wbtj5hmx",
        ]

        self.client_id = ""
        self.password = ""
        self.token = ""
        self.server = ""
        self.server_time = 0

        self.channels_cache = []
        self.cache_time = 0
        self.auth_time = 0

        # ★ 台标 CDN 前缀，如果这个不通，换备用（见文末）
        self.LOGO_CDN = "https://epg.112114.eu.org/logo/{}.png"

        # 预排序：长 key 优先
        self._sorted_keys = sorted(
            self._KEYWORD_LOGOS.keys(), key=len, reverse=True
        )

        # 调试开关：打印没匹配到的频道名，方便补充映射
        self.DEBUG_LOG = False

    # =========================================================
    # 基本資訊
    # =========================================================
    def getName(self):
        return "DreamTV"

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    # =========================================================
    # 首頁 / 分類 / 詳情 / 搜尋
    # =========================================================
    def homeContent(self, filter):
        try:
            channels = self._get_channels()
            categories = []
            for item in channels:
                c = self.get_channel_category(item)
                if c and c not in categories:
                    categories.append(c)
            classes = [{"type_id": "all", "type_name": "全部頻道"}]
            for c in categories:
                classes.append({"type_id": c, "type_name": c})
            return {"class": classes, "filters": {}}
        except Exception as e:
            return {
                "class": [{"type_id": "all", "type_name": "全部頻道"}],
                "filters": {}, "msg": "DreamTV: %s" % str(e)
            }

    def homeVideoContent(self):
        try:
            channels = self._get_channels()
            return {"list": self._make_videos(channels)}
        except Exception as e:
            return {"list": [], "msg": "homeVideoContent: %s" % str(e)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            channels = self._get_channels()
            if not tid:
                tid = "all"
            videos = []
            for item in channels:
                if tid != "all" and self.get_channel_category(item) != tid:
                    continue
                v = self._channel_to_video(item)
                if v:
                    videos.append(v)
            return {
                "page": 1, "pagecount": 1, "limit": len(videos),
                "total": len(videos), "list": videos
            }
        except Exception as e:
            return {
                "page": 1, "pagecount": 1, "limit": 0, "total": 0,
                "list": [], "msg": "categoryContent: %s" % str(e)
            }

    def detailContent(self, array):
        if not array:
            return {"list": []}
        pid = str(array[0])
        name, logo = "DreamTV直播", ""
        for item in self.channels_cache:
            if self.get_channel_play_url(item) == pid:
                name = self.get_channel_name(item)
                logo = self.get_channel_logo(item)
                break
        return {
            "list": [{
                "vod_id": pid, "vod_name": name, "vod_pic": logo,
                "vod_remarks": "直播", "vod_content": "DreamTV直播頻道",
                "vod_play_from": "DreamTV", "vod_play_url": "播放$" + pid
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            if not key:
                return {"list": []}
            key = str(key).lower()
            channels = self._get_channels()
            videos = []
            for item in channels:
                if key not in self.get_channel_name(item).lower():
                    continue
                v = self._channel_to_video(item)
                if v:
                    videos.append(v)
            return {"list": videos}
        except Exception as e:
            return {"list": [], "msg": "searchContent: %s" % str(e)}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    def playerContent(self, flag, pid, vipFlags):
        if not pid:
            return {"parse": 0, "playUrl": "", "url": ""}
        header = {
            "User-Agent": "Lavf/58.12.100", "Accept": "*/*",
            "Connection": "keep-alive", "Icy-MetaData": "1",
            "userid": str(self.client_id), "usertoken": str(self.token),
            "Cache-Control": "no-cache", "Pragma": "no-cache"
        }
        try:
            self._ensure_auth()
            return {"parse": 0, "playUrl": "", "url": str(pid), "header": header}
        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": str(pid),
                    "header": header, "msg": "playerContent: %s" % str(e)}

    # =========================================================
    # Dream API
    # =========================================================
    def _sign(self, ts, method):
        raw = self.from_id + self.salt + str(ts) + method + self.devid
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _headers(self, body):
        b = body.encode("utf-8")
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(b)),
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/3.12.5",
            "Accept-Encoding": "identity"
        }

    def _post(self, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        last_error = "Dream API request failed"
        for api_url in self.api_urls:
            try:
                r = self.session.post(
                    api_url, data=body.encode("utf-8"),
                    headers=self._headers(body), timeout=15, verify=False
                )
                if r.status_code != 200:
                    last_error = "HTTP %s" % r.status_code
                    continue
                result = r.json()
                if isinstance(result, dict):
                    if result.get("data") is not None:
                        return result.get("data")
                    last_error = "API 沒有 data"
                else:
                    last_error = "API 回應格式錯誤"
            except Exception as e:
                last_error = str(e)
        raise Exception(last_error)

    def _login_step_1(self):
        ts = int(time.time())
        method = "1-1-2"
        payload = {
            "method": method,
            "params": {
                "device_id": self.devid, "hardware": self.hardware,
                "sn": self.devid, "version": self.version
            },
            "system": {
                "from": self.from_id, "sign": self._sign(ts, method),
                "time": ts, "version": "V1"
            }
        }
        data = self._post(payload)
        if not isinstance(data, dict):
            raise Exception("1-1-2 data 格式錯誤")
        client = data.get("client") or {}
        server = data.get("server") or {}
        token = client.get("token")
        if not token:
            raise Exception("你的 IP 或 devid 被 Dream 封鎖")
        self.token = str(token)
        self.client_id = str(client.get("client_id") or "")
        self.password = str(client.get("password") or "")
        self.server_time = int(client.get("time") or ts)
        hosts = server.get("hosts") or []
        if hosts:
            first = hosts[0]
            self.server = str(first.get("url") or "") if isinstance(first, dict) else str(first)
        if not self.server:
            raise Exception("Dream API 沒有 server")

    def _login_step_2(self):
        method = "1-1-3"
        ts = int(self.server_time or time.time())
        payload = {
            "method": method,
            "params": {
                "client_id": self.client_id, "device_id": self.devid,
                "hardware": self.hardware, "password": self.password,
                "sn": self.devid, "token": self.token, "version": self.version
            },
            "system": {
                "from": self.from_id, "sign": self._sign(ts, method),
                "time": ts, "version": "V1"
            }
        }
        data = self._post(payload)
        if isinstance(data, dict):
            client = data.get("client") or {}
            if client.get("token"):
                self.token = str(client.get("token"))

    def _fetch_channel_data(self):
        method = "1-1-4"
        ts = int(self.server_time or time.time())
        payload = {
            "method": method,
            "params": {
                "client_id": self.client_id, "device_id": self.devid,
                "hardware": self.hardware, "password": self.password,
                "sn": self.devid, "token": self.token, "version": self.version
            },
            "system": {
                "from": self.from_id, "sign": self._sign(ts, method),
                "time": ts, "version": "V1"
            }
        }
        data = self._post(payload)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("channels", "list", "items", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    def _ensure_auth(self):
        if (self.token and self.client_id
                and (time.time() - self.auth_time) < 1800):
            return
        self._login_step_1()
        self._login_step_2()
        self.auth_time = time.time()

    def _get_channels(self):
        if (self.channels_cache
                and (time.time() - self.cache_time) < 600):
            return self.channels_cache
        self._login_step_1()
        self._login_step_2()
        channels = self._fetch_channel_data()
        self.channels_cache = channels
        self.cache_time = time.time()
        self.auth_time = time.time()
        return channels

    def get_channels(self):
        return self._get_channels()

    # =========================================================
    # 頻道欄位
    # =========================================================
    def get_channel_name(self, item):
        if not isinstance(item, dict):
            return "DreamTV"
        return str(item.get("name") or item.get("title")
                   or item.get("channel_name") or "DreamTV")

    def get_channel_category(self, item):
        if not isinstance(item, dict):
            return "DreamTV"
        return str(item.get("category") or item.get("group")
                   or item.get("group_name") or "DreamTV")

    def get_channel_url(self, item):
        if not isinstance(item, dict):
            return ""
        return str(item.get("url") or item.get("play_url")
                   or item.get("stream_url") or "")

    # =========================================================
    # ★★★ 台标匹配（内置关键词，零网络依赖）★★★
    # =========================================================
    def _normalize(self, name):
        """归一化：去后缀、去符号、转大写"""
        if not name:
            return ""
        name = str(name).strip()
        # 去掉常见后缀（可重复出现）
        for _ in range(2):
            name = re.sub(
                r'(?:[-\s_·]*)(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清|高码|HD1080)$',
                '', name, flags=re.IGNORECASE
            )
        # 去掉所有符号
        name = re.sub(r'[\s\-_\.\(\)\[\]（）【】·]', '', name)
        return name.upper()

    def _match_keyword(self, ch_name):
        """关键词匹配，长 key 优先"""
        norm = self._normalize(ch_name)
        if not norm:
            return ""
        for key in self._sorted_keys:
            if key in norm:
                return self._KEYWORD_LOGOS[key]
        return ""

    def get_channel_logo(self, item):
        if not isinstance(item, dict):
            return ""

        name = self.get_channel_name(item)

        # Level 0: API 自带 logo（相对路径拼 server）
        raw_logo = str(
            item.get("logo") or item.get("pic") or item.get("icon") or ""
        ).strip()
        if raw_logo and raw_logo.lower() not in ("null", "none", "0", ""):
            if raw_logo.startswith("http"):
                return raw_logo
            if self.server:
                if raw_logo.startswith("/"):
                    return self.server.rstrip("/") + raw_logo
                return self.server.rstrip("/") + "/" + raw_logo.lstrip("/")
            return raw_logo

        # Level 1: 内置关键词匹配
        matched = self._match_keyword(name)
        if matched:
            return self.LOGO_CDN.format(quote(matched))

        # Level 2: 直接拿原名再试一次（中文频道可能 112114 里就有）
        norm_for_cdn = re.sub(
            r'(?:[-\s]*(?:高清|超清|标清|HD|FHD|UHD|4K|1080P))$',
            '', name, flags=re.IGNORECASE
        ).replace(" ", "").strip()
        if norm_for_cdn:
            # 只在 DEBUG 时打印，方便补充映射
            if self.DEBUG_LOG:
                print("★ [未匹配] %s (归一化: %s)" % (name, self._normalize(name)))
            return self.LOGO_CDN.format(quote(norm_for_cdn))

        return ""

    def get_channel_play_url(self, item):
        raw_url = self.get_channel_url(item)
        if not raw_url:
            return ""
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        return self._join_stream_url(self.server, raw_url)

    # =========================================================
    # 產生 VOD 列表
    # =========================================================
    def _channel_to_video(self, item):
        if not isinstance(item, dict):
            return None
        if not self.get_channel_url(item):
            return None
        play_url = self.get_channel_play_url(item)
        if not play_url:
            return None
        return {
            "vod_id": play_url,
            "vod_name": self.get_channel_name(item),
            "vod_pic": self.get_channel_logo(item),
            "vod_remarks": self.get_channel_category(item),
            "vod_content": "DreamTV直播頻道"
        }

    def _make_videos(self, channels):
        videos = []
        for item in channels:
            v = self._channel_to_video(item)
            if v:
                videos.append(v)
        return videos

    def _join_stream_url(self, server, path):
        if not server:
            return path
        server = str(server).strip()
        path = str(path).strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return server.rstrip("/") + path
        return server.rstrip("/") + "/" + path.lstrip("/")

    # =========================================================
    # 直播內容
    # =========================================================
    def liveContent(self, url):
        try:
            channels = self._get_channels()
            lines = ["#EXTM3U"]
            for item in channels:
                play_url = self.get_channel_play_url(item)
                if not play_url:
                    continue
                lines.append(
                    '#EXTINF:-1 tvg-logo="{}" group-title="{}",{}'.format(
                        self.get_channel_logo(item),
                        self.get_channel_category(item),
                        self.get_channel_name(item)
                    )
                )
                lines.append(play_url)
            return "\n".join(lines)
        except Exception:
            return "#EXTM3U"

    def localProxy(self, param):
        return [404, "text/plain", ""]