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
    """
    DreamTV -> 影視壳 / TVBox Spider
    依照 dream.php 的 1-1-2 -> 1-1-3 -> 1-1-4 流程取得頻道。
    """

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

        # ===== 频道别名库（懒加载，避免影响启动速度） =====
        self._alias_map = None
        self._alias_load_time = 0
        self._alias_url = (
            "https://gcore.jsdelivr.net/gh/taksssss/tv@main/ku9/epg_data.json"
        )

        # 默认占位图
        self.default_logo = "https://img.icons8.com/color/48/tv.png"

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
    # 首頁
    # =========================================================
    def homeContent(self, filter):
        try:
            channels = self._get_channels()
            categories = []
            for item in channels:
                category = self.get_channel_category(item)
                if category and category not in categories:
                    categories.append(category)

            classes = [{"type_id": "all", "type_name": "全部頻道"}]
            for category in categories:
                classes.append({
                    "type_id": category,
                    "type_name": category
                })

            return {"class": classes, "filters": {}}
        except Exception as e:
            return {
                "class": [{"type_id": "all", "type_name": "全部頻道"}],
                "filters": {},
                "msg": "DreamTV: %s" % str(e)
            }

    def homeVideoContent(self):
        try:
            channels = self._get_channels()
            videos = self._make_videos(channels)
            return {"list": videos}
        except Exception as e:
            return {"list": [], "msg": "DreamTV homeVideoContent: %s" % str(e)}

    # =========================================================
    # 分類列表
    # =========================================================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            channels = self._get_channels()
            if not tid:
                tid = "all"

            videos = []
            for item in channels:
                category = self.get_channel_category(item)
                if tid != "all" and category != tid:
                    continue
                video = self._channel_to_video(item)
                if video:
                    videos.append(video)

            return {
                "page": 1,
                "pagecount": 1,
                "limit": len(videos),
                "total": len(videos),
                "list": videos
            }
        except Exception as e:
            return {
                "page": 1, "pagecount": 1, "limit": 0, "total": 0,
                "list": [], "msg": "DreamTV categoryContent: %s" % str(e)
            }

    # =========================================================
    # 詳情
    # =========================================================
    def detailContent(self, array):
        if not array:
            return {"list": []}

        pid = str(array[0])
        name = "DreamTV直播"
        logo = ""

        for item in self.channels_cache:
            play_url = self.get_channel_play_url(item)
            if play_url == pid:
                name = self.get_channel_name(item)
                logo = self.get_channel_logo(item)
                break

        return {
            "list": [{
                "vod_id": pid,
                "vod_name": name,
                "vod_pic": logo,
                "vod_remarks": "直播",
                "vod_content": "DreamTV直播頻道",
                "vod_play_from": "DreamTV",
                "vod_play_url": "播放$" + pid
            }]
        }

    # =========================================================
    # 搜尋
    # =========================================================
    def searchContent(self, key, quick, pg="1"):
        try:
            if not key:
                return {"list": []}

            key = str(key).lower()
            channels = self._get_channels()
            videos = []

            for item in channels:
                name = self.get_channel_name(item)
                if key not in name.lower():
                    continue
                video = self._channel_to_video(item)
                if video:
                    videos.append(video)

            return {"list": videos}
        except Exception as e:
            return {"list": [], "msg": "DreamTV searchContent: %s" % str(e)}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    # =========================================================
    # 播放
    # =========================================================
    def playerContent(self, flag, pid, vipFlags):
        if not pid:
            return {"parse": 0, "playUrl": "", "url": ""}

        try:
            self._ensure_auth()
            return {
                "parse": 0,
                "playUrl": "",
                "url": str(pid),
                "header": {
                    "User-Agent": "Lavf/58.12.100",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                    "Icy-MetaData": "1",
                    "userid": str(self.client_id),
                    "usertoken": str(self.token),
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }
            }
        except Exception as e:
            return {
                "parse": 0, "playUrl": "", "url": str(pid),
                "header": {
                    "User-Agent": "Lavf/58.12.100", "Accept": "*/*",
                    "Connection": "keep-alive", "Icy-MetaData": "1",
                    "userid": str(self.client_id), "usertoken": str(self.token),
                    "Cache-Control": "no-cache", "Pragma": "no-cache"
                },
                "msg": "DreamTV playerContent: %s" % str(e)
            }

    # =========================================================
    # Dream API
    # =========================================================
    def _sign(self, ts, method):
        raw = self.from_id + self.salt + str(ts) + method + self.devid
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _headers(self, body):
        body_bytes = body.encode("utf-8")
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body_bytes)),
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/3.12.5",
            "Accept-Encoding": "identity"
        }

    def _post(self, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        last_error = "Dream API request failed"

        for api_url in self.api_urls:
            try:
                response = self.session.post(
                    api_url,
                    data=body.encode("utf-8"),
                    headers=self._headers(body),
                    timeout=15,
                    verify=False
                )
                if response.status_code != 200:
                    last_error = "HTTP %s" % response.status_code
                    continue
                result = response.json()
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
                "device_id": self.devid,
                "hardware": self.hardware,
                "sn": self.devid,
                "version": self.version
            },
            "system": {
                "from": self.from_id,
                "sign": self._sign(ts, method),
                "time": ts,
                "version": "V1"
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

    # =========================================================
    # 認證 / 頻道快取
    # =========================================================
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
        return str(
            item.get("name") or item.get("title")
            or item.get("channel_name") or "DreamTV"
        )

    def get_channel_category(self, item):
        if not isinstance(item, dict):
            return "DreamTV"
        return str(
            item.get("category") or item.get("group")
            or item.get("group_name") or "DreamTV"
        )

    def get_channel_url(self, item):
        if not isinstance(item, dict):
            return ""
        return str(
            item.get("url") or item.get("play_url")
            or item.get("stream_url") or ""
        )

    # =========================================================
    # ★★★ 多级回退台标匹配 ★★★
    # =========================================================
    def _load_alias_map(self):
        """加载社区别名库（epg_data.json），缓存1小时"""
        now = time.time()
        if self._alias_map is not None and (now - self._alias_load_time) < 3600:
            return self._alias_map

        alias_map = {}
        try:
            resp = self.session.get(
                self._alias_url, timeout=10, verify=False,
                headers={"User-Agent": "okhttp/3.12.0"}
            )
            if resp.status_code == 200 and resp.text:
                data = resp.json()
                for item in data.get("epgs", []):
                    epgid = str(item.get("epgid", "")).strip()
                    logo = str(item.get("logo", "")).strip()
                    name_str = str(item.get("name", "")).strip()
                    if not epgid or not logo:
                        continue
                    # name 字段格式: "CCTV1,CCTV-1,CCTV1综合,..."（逗号分隔）
                    aliases = [a.strip() for a in name_str.split(",") if a.strip()]
                    # 把 epgid 本身也作为别名
                    aliases.append(epgid)
                    for a in aliases:
                        # 统一清洗后作为 key
                        clean_a = self._clean_name(a)
                        if clean_a:
                            alias_map[clean_a] = logo
        except Exception as e:
            print("★ 别名库加载失败:", e)

        self._alias_map = alias_map
        self._alias_load_time = now
        return alias_map

    def _clean_name(self, name):
        """统一清洗频道名：去后缀、去空格、去横杠、转大写"""
        if not name:
            return ""
        name = str(name).strip()
        # 去掉高清/超清/HD/4K 等后缀（可能在末尾或 - 后）
        name = re.sub(
            r'(?:[-\s]*(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清|高码|HD1080))$',
            '', name, flags=re.IGNORECASE
        )
        # 去掉所有横杠、空格、点、括号
        name = re.sub(r'[\s\-\.\(\)\[\]（）【】]', '', name)
        return name.upper()

    def _match_from_alias(self, ch_name):
        """从社区别名库匹配，返回 logo URL 或空"""
        alias_map = self._load_alias_map()
        if not alias_map:
            return ""

        clean = self._clean_name(ch_name)
        if not clean:
            return ""

        # 1) 精确匹配
        if clean in alias_map:
            return alias_map[clean]

        # 2) 尝试去掉末尾数字/字母后匹配（处理 "CCTV1HD" -> "CCTV1"）
        stripped = re.sub(r'[A-Z0-9]+$', '', clean)
        if stripped and stripped in alias_map:
            return alias_map[stripped]

        return ""

    def _match_from_112114(self, ch_name):
        """112114 接口兜底"""
        clean = self._clean_name(ch_name)
        if not clean:
            return ""
        # 112114 需要原始格式，这里用清洗后的但保留中文和数字
        # 重新生成一个适合 112114 的名字
        raw = str(ch_name).strip()
        raw = re.sub(
            r'(?:[-\s]*(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清))$',
            '', raw, flags=re.IGNORECASE
        )
        raw = raw.replace(' ', '').strip()
        if not raw:
            return ""
        return f"https://epg.112114.eu.org/logo/{quote(raw)}.png"

    # ★★★ 改后的台标获取（多级回退） ★★★
    def get_channel_logo(self, item):
        if not isinstance(item, dict):
            return self.default_logo

        name = self.get_channel_name(item)

        # Level 1: API 自带 logo
        raw_logo = str(
            item.get("logo") or item.get("pic") or item.get("icon") or ""
        ).strip()
        if raw_logo and raw_logo.lower() not in ("null", "none", "0", ""):
            # 相对路径拼 server
            if raw_logo.startswith("/") and self.server:
                return self.server.rstrip("/") + raw_logo
            if raw_logo.startswith("http"):
                return raw_logo
            # 其他相对路径也拼一下
            if self.server:
                return self.server.rstrip("/") + "/" + raw_logo.lstrip("/")
            return raw_logo

        # Level 2: 社区别名库
        logo = self._match_from_alias(name)
        if logo:
            return logo

        # Level 3: 112114 接口
        logo = self._match_from_112114(name)
        if logo:
            return logo

        # Level 4: 默认图
        return self.default_logo

    def get_channel_play_url(self, item):
        raw_url = self.get_channel_url(item)
        if not raw_url:
            return ""
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        return self._join_stream_url(self.server, raw_url)

    # =========================================================
    # 產生影視壳 VOD 列表
    # =========================================================
    def _channel_to_video(self, item):
        if not isinstance(item, dict):
            return None
        raw_url = self.get_channel_url(item)
        if not raw_url:
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
            video = self._channel_to_video(item)
            if video:
                videos.append(video)
        return videos

    # =========================================================
    # URL
    # =========================================================
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

    # =========================================================
    # 本地代理介面保留
    # =========================================================
    def localProxy(self, param):
        return [404, "text/plain", ""]