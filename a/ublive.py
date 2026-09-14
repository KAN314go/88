# -*- coding: utf-8 -*-
# UBLive TVBox Python Spider (改寫自 ublive33.php)

import sys
import json
import os
import time
import base64
import hashlib
import re
import requests
import urllib3
from urllib.parse import quote
from Crypto.Cipher import AES

urllib3.disable_warnings()

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.name = "UBLive直播"

        self.api_base_url = "https://www.usplaytvonphone.com"
        self.login_endpoint = "info.php"
        self.channel_endpoint = "live.php"
        self.uri_endpoint = "uri.php"
        self.aes_key = b"W@ms7+2HZ34<iZz>"

        self.username = "12345678"
        self.password = "12345678"
        self.real_mac = "00:1a:3b:5c:7d:9e"

        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.channels = []
        self.categories = []
        self.session = requests.Session()

        # 默认台标（匹配不到时用）
        self.default_logo = "https://img.icons8.com/color/48/tv.png"

    def getName(self):
        return self.name

    def init(self, extend):
        pass

    # ---------- 加密工具 ----------
    def get_random_string(self, length):
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        import random
        return "".join(random.choice(chars) for _ in range(length))

    def get_index(self, c):
        if '0' <= c <= '9':
            return 10 + int(c)
        elif 'a' <= c <= 'z':
            return 10 + ord(c) - ord('a')
        elif 'A' <= c <= 'Z':
            return 36 + ord(c) - ord('A')
        return 10

    def sub_encrypt(self, iv_idx, s, iv):
        try:
            i2 = int(iv[iv_idx])
        except (ValueError, TypeError):
            i2 = 0
        if i2 == 0:
            i2 = 10
        return s[:i2] + self.get_random_string(i2) + s[i2:]

    def sub_decrypt(self, iv_idx, s, iv):
        try:
            i2 = int(iv[iv_idx])
        except (ValueError, TypeError):
            i2 = 0
        if i2 == 0:
            i2 = 10
        return s[:i2] + s[i2 * 2:]

    def md5_hex(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get_serial_md5(self, username):
        inner1 = self.md5_hex(username)
        inner2 = self.md5_hex("Gooooogle")
        step3 = inner1 + inner2 + "201306@202106>"
        step4 = self.md5_hex(step3)
        step5 = step4 + "Ub"
        return self.md5_hex(step5)

    def ubed_encrypt(self, payload_dict):
        payload_str = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
        iv = self.get_random_string(16)

        block_size = 16
        pad_len = block_size - (len(payload_str.encode('utf-8')) % block_size)
        padded_str = payload_str + chr(pad_len) * pad_len

        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv.encode('utf-8'))
        enc_bytes = cipher.encrypt(padded_str.encode('utf-8'))

        sign = base64.b64encode(enc_bytes).decode('utf-8')
        sign = self.sub_encrypt(5, sign, iv)
        sign = self.sub_encrypt(12, sign, iv)

        rnd_prefix = self.get_random_string(self.get_index(sign[-6]))
        return {"sign": rnd_prefix + sign, "iv": iv}

    def ubed_decrypt(self, sign, iv):
        if not sign or not iv:
            return ""
        try:
            idx = self.get_index(sign[-6])
            sign = sign[idx:]
            sign = self.sub_decrypt(12, sign, iv)
            sign = self.sub_decrypt(5, sign, iv)

            pad = 4 - len(sign) % 4
            if pad < 4:
                sign += "=" * pad

            enc_bytes = base64.b64decode(sign)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv.encode('utf-8'))
            dec_bytes = cipher.decrypt(enc_bytes)

            pad_len = dec_bytes[-1]
            dec_str = dec_bytes[:-pad_len].decode('utf-8', errors='ignore')
            return dec_str
        except Exception:
            return ""

    # ---------- API 请求 ----------
    def fetch_dynamic_token(self):
        body_payload = {
            "icode": "", "icode_name": self.username,
            "icode_passwd": self.password, "icode_sign": self.get_serial_md5(self.username), "signup": 0
        }
        current_time = int(time.time())
        device_info = {
            "app_laguage": 2, "brand": "Unblock", "cpu_api": "arm64-v8a",
            "cpu_api2": "", "device_flag": "", "mac": self.real_mac,
            "model": "UBOX10", "time": current_time, "token": "a1391713a32e61d249b319def67ed961", "ubcode": "88888888"
        }

        headers = {
            "device_info": json.dumps(self.ubed_encrypt(device_info), separators=(',', ':')),
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.12.0",
            "Connection": "close"
        }

        try:
            resp = self.session.post(
                f"{self.api_base_url}/{self.login_endpoint}",
                json=self.ubed_encrypt(body_payload),
                headers=headers,
                timeout=6,
                verify=False
            )
            if resp.status_code == 200 and resp.text:
                res_json = resp.json()
                dec_text = self.ubed_decrypt(res_json.get('sign'), res_json.get('iv'))
                res_data = json.loads(dec_text)
                if str(res_data.get('return_code')) == "99":
                    return res_data.get('return_token')
        except Exception:
            pass
        return None

    def get_channel_info(self, token, channel_id):
        current_time = int(time.time())
        live_payload = {
            "icode_name": self.username, "icode_passwd": self.password,
            "icode_sign": self.get_serial_md5(self.username), "token": token
        }
        device_info = {
            "app_laguage": 2, "brand": "Unblock", "cpu_api": "arm64-v8a",
            "cpu_api2": "", "device_flag": "", "mac": self.real_mac,
            "model": "UBOX10", "time": current_time, "token": token, "ubcode": "88888888"
        }

        headers = {
            "device_info": json.dumps(self.ubed_encrypt(device_info), separators=(',', ':')),
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.12.0",
            "Connection": "close"
        }

        try:
            self.session.post(
                f"{self.api_base_url}/{self.channel_endpoint}",
                json=self.ubed_encrypt(live_payload),
                headers=headers,
                timeout=4,
                verify=False
            )

            uri_payload = {
                "icode_name": self.username, "icode_passwd": self.password,
                "icode_sign": self.get_serial_md5(self.username), "token": token, "id": str(channel_id)
            }

            for _ in range(2):
                resp = self.session.post(
                    f"{self.api_base_url}/{self.uri_endpoint}",
                    json=self.ubed_encrypt(uri_payload),
                    headers=headers,
                    timeout=5,
                    verify=False
                )
                if resp.status_code == 200 and resp.text:
                    res_json = resp.json()
                    dec_text = self.ubed_decrypt(res_json.get('sign'), res_json.get('iv'))
                    result = json.loads(dec_text)
                    if str(result.get('return_code')) == "99":
                        return {
                            "uri": result.get('return_uri'),
                            "fftoken": result.get('return_fftoken'),
                            "playtoken": result.get('return_playtoken')
                        }
                time.sleep(0.2)
        except Exception:
            pass
        return None

    # ---------- 加载工具 ----------
    def load_json_from_file(self, path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print("本地加载失败:", path, e)
        return None

    def load_json_from_url(self, url):
        try:
            resp = self.session.get(
                url,
                timeout=8,
                verify=False,
                headers={"User-Agent": "okhttp/3.12.0"}
            )
            if resp.status_code == 200 and resp.text:
                return resp.json()
            else:
                print("在线加载失败:", url, "状态码:", resp.status_code)
        except Exception as e:
            print("在线加载异常:", url, e)
        return None

    # ---------- 台标匹配 ----------
    def clean_channel_name(self, name):
        """清洗频道名，去掉高清/HD 等后缀"""
        name = str(name).strip()
        name = re.sub(
            r'(高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清)$',
            '', name, flags=re.IGNORECASE
        )
        name = name.replace(' ', '').strip()
        return name

    def match_channel_logo(self, ch_name):
        """使用 112114 接口匹配台标，带别名映射"""
        clean = self.clean_channel_name(ch_name)
        if not clean:
            return self.default_logo

        # ★ 别名映射表：左边 JSON 里的名字 → 右边台标库里的真实名字
        logo_alias = {
            # CCTV 系列（112114 用不带横杠的形式）
            "CCTV1": "CCTV1", "CCTV2": "CCTV2", "CCTV3": "CCTV3",
            "CCTV4": "CCTV4", "CCTV5": "CCTV5", "CCTV5+": "CCTV5+",
            "CCTV6": "CCTV6", "CCTV7": "CCTV7", "CCTV8": "CCTV8",
            "CCTV9": "CCTV9", "CCTV10": "CCTV10", "CCTV11": "CCTV11",
            "CCTV12": "CCTV12", "CCTV13": "CCTV13", "CCTV14": "CCTV14",
            "CCTV15": "CCTV15", "CCTV16": "CCTV16", "CCTV17": "CCTV17",
            # 凤凰系列
            "凤凰中文": "凤凰卫视中文台",
            "凤凰资讯": "凤凰卫视资讯台",
            "凤凰香港": "凤凰卫视香港台",
            "凤凰电影": "凤凰卫视电影台",
            # 港澳台
            "翡翠台": "翡翠台",
            "明珠台": "明珠台",
            "无线新闻": "无线新闻台",
            "无线财经": "无线财经资讯台",
            "TVB": "无线新闻台",
            # 其他别名
            "湖南金鹰": "金鹰卡通",
            "东南卫视": "东南卫视",
        }

        clean = logo_alias.get(clean, clean)

        # ★ 112114 台标接口
        return f"https://epg.112114.eu.org/logo/{quote(clean)}.png"

    # ---------- 資料載入 ----------
    def load_channels(self):
        if self.channels:
            return self.channels

        processed_channels = []
        categories_order = []

        # ★ 在线地址放第一位，本地作为兜底
        possible_dirs = [
            "https://raw.githubusercontent.com/KAN314go/88/refs/heads/main/a/",
            self.base_dir,
            "/sdcard/tvbox/py/",
            "/sdcard/Download/"
        ]

        for d in possible_dirs:
            for fname in ['channels.json', 'extra.json']:

                if str(d).startswith(('http://', 'https://')):
                    url = d.rstrip('/') + '/' + fname
                    data = self.load_json_from_url(url)
                else:
                    path = os.path.join(d, fname)
                    data = self.load_json_from_file(path)

                if not data:
                    continue

                print("★ 成功加载:", d, fname)

                cat_list = data.get('return_live', [])
                for cat in cat_list:
                    group_name = str(cat.get('name', '未分類')).strip()
                    if group_name not in categories_order:
                        categories_order.append(group_name)

                    for ch in cat.get('channel', []):
                        ch_id = str(ch.get('id', ''))
                        ch_title = str(ch.get('title', '')).strip()
                        if not ch_id or not ch_title:
                            continue

                        # ★ JSON 自带 logo 优先，没有则自动匹配
                        ch_logo = str(ch.get('logo', '')).strip()
                        if not ch_logo:
                            ch_logo = self.match_channel_logo(ch_title)

                        processed_channels.append({
                            "id": ch_id,
                            "name": ch_title,
                            "category": group_name,
                            "logo": ch_logo
                        })

        if not processed_channels:
            categories_order.append("系統提示")
            processed_channels.append({
                "id": "1",
                "name": "未偵測到 channels.json 檔案",
                "category": "系統提示",
                "logo": self.default_logo
            })

        self.channels = processed_channels
        self.categories = categories_order
        return self.channels

    # ---------- TVBox 標準介面 ----------
    def homeContent(self, filter):
        self.load_channels()
        classes = [{"type_name": "全部頻道", "type_id": "all"}]
        for cat in self.categories:
            classes.append({
                "type_name": cat,
                "type_id": cat
            })
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("all", 1, False, {})

    def categoryContent(self, tid, page, filter, ext):
        channels = self.load_channels()
        videos = []
        for ch in channels:
            if tid != "all" and ch["category"] != tid:
                continue
            videos.append({
                "vod_id": ch["id"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"] if ch["logo"] else self.default_logo,
                "vod_remarks": "直播",
                "vod_year": "",
                "vod_area": ch["category"],
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "UBLive 直播頻道"
            })

        return {
            "list": videos,
            "page": 1,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos)
        }

    def detailContent(self, array):
        if not array:
            return {"list": []}

        channel_id = array[0]
        channels = self.load_channels()
        ch_name = "UBLive直播"
        category = "直播"
        ch_logo = self.default_logo

        for ch in channels:
            if ch["id"] == channel_id:
                ch_name = ch["name"]
                category = ch["category"]
                if ch["logo"]:
                    ch_logo = ch["logo"]
                break

        token = self.fetch_dynamic_token()
        stream_url = ""
        fftoken = ""
        playtoken = ""

        if token:
            info = self.get_channel_info(token, channel_id)
            if info and info.get("uri"):
                stream_url = info.get("uri")
                fftoken = info.get("fftoken", "")
                playtoken = info.get("playtoken", "")

        return {
            "list": [
                {
                    "vod_id": channel_id,
                    "vod_name": ch_name,
                    "vod_pic": ch_logo,
                    "vod_remarks": "直播",
                    "vod_year": "",
                    "vod_area": category,
                    "vod_content": "UBLive 實時直播源",
                    "vod_play_from": "UBLive",
                    "vod_play_url": f"播放${stream_url}|{fftoken}|{playtoken}" if stream_url else "播放$error"
                }
            ]
        }

    def searchContent(self, key, quick, page="1"):
        if not key:
            return {"list": []}

        key = str(key).lower()
        channels = self.load_channels()
        videos = []

        for ch in channels:
            if key not in ch["name"].lower():
                continue
            videos.append({
                "vod_id": ch["id"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"] if ch["logo"] else self.default_logo,
                "vod_remarks": "直播",
                "vod_content": ch["category"]
            })

        return {"list": videos}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    def playerContent(self, flag, pid, vipFlags):
        if not pid or pid == "error":
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

        parts = pid.split('|')
        real_url = parts[0]
        fftoken = parts[1] if len(parts) > 1 else ""
        playtoken = parts[2] if len(parts) > 2 else ""

        headers = {
            "User-Agent": "okhttp/3.12.0"
        }
        if fftoken:
            headers["fftoken"] = fftoken
        if playtoken:
            headers["playtoken"] = playtoken

        return {
            "parse": 0,
            "playUrl": "",
            "url": real_url,
            "header": headers
        }

    def localProxy(self, params):
        return {}

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
        return "正在Destroy"


if __name__ == '__main__':
    pass