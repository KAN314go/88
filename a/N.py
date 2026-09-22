# -*- coding: utf-8 -*-
# 三源聚合（玉山 + 安博 + 全球）- C 方案
# 首页三块 → 点源 → 分类 → 频道 → 播放

import os
import re
import sys
import time
import json
import gzip
import base64
import random
import hashlib
import threading
import urllib.parse
import urllib.request
import ssl

try:
    import requests
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

try:
    from Crypto.Cipher import AES
    HAS_AES = True
except ImportError:
    HAS_AES = False

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from base.spider import Spider as _TVBoxBase
except ImportError:
    class _TVBoxBase(object):
        def init(self, extend=""):
            pass


SEP = "@@"
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")


def _split(full_id):
    s = str(full_id or "")
    if SEP in s:
        return s.split(SEP, 1)
    return "", s


# ============================================================
# 源 1：玉山（修复版：无锁、无后台线程、纯同步）
# ============================================================
class YushanSource(_TVBoxBase):
    PREFIX = "ys"
    NAME = "玉山"
    M3U_URL = "https://www.liaobagua.com/tv/tv.php?a=play"

    FETCH_HEADERS = {
        "User-Agent": UA_BROWSER,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.liaobagua.com/",
    }

    RESTRICTED_NAMES = [
        "乐活频道", "HiPLAY", "彩虹R频道", "潘朵拉玩美", "潘朵拉粉红",
        "K频道", "彩虹MOIVE", "彩虹e台", "星颖", "HAPPY",
    ]

    EXACT_MAP = {"凤凰卫视中文台": "大陆"}

    KEYWORD_RULES = {
        "体育": ["CCTV-5", "CCTV5", "风云足球", "高尔夫网球", "央视台球",
                 "广东体育", "五星体育", "快乐垂钓", "Now Sports", "NowSports",
                 "Now Golf", "Now Prime", "NOW CH6", "纬来体育", "ELTA体育",
                 "博斯", "DAZN", "智林体育", "欧洲体育", "EURO SPORT", "NBA"],
        "新闻": ["CCTV-13", "CCTV13", "第一财经", "东方财经", "广东新闻",
                 "广州新闻", "上海新闻", "凤凰资讯", "无线新闻", "Now新闻",
                 "Now直播", "Now财经", "华视新闻", "中视新闻", "民视新闻",
                 "台视新闻", "TVBS新闻", "TVBS News", "中天新闻", "三立新闻",
                 "寰宇新闻", "非凡新闻", "年代新闻", "年代much", "鏡電視",
                 "壹电视新闻", "三立inews", "非凡商業", "德国之声", "Sky News",
                 "NHK News", "CNN", "Bloomberg", "France24", "TV5", "天下卫视"],
        "影视": ["CCTV-8", "CCTV8", "CCTV-11", "CCTV11", "怀旧剧场",
                 "风云剧场", "第一剧场", "CHC", "TVS4", "广州影视",
                 "深圳电视剧", "TVB", "Now爆谷", "Now Viu", "Now 华剧",
                 "Now 華劇", "NowJelli", "紫金", "天映", "CCM", "美亚电影",
                 "八大戏", "龙华", "东森戏", "东森电影", "东森洋片",
                 "纬来电影", "纬来戏", "ELTA影剧", "CineMax", "CATCH", "AMC",
                 "靖天电影", "靖天映画", "靖洋", "EYE TV", "Warner",
                 "好莱坞", "HITS", "龙祥", "公视戏", "Astro",
                 "Disney", "ANIMAX", "CN卡通", "MOMO", "Momo"],
        "日本": ["FIGHTING TV", "サムライ", "HGTV", "NHK", "TVN"],
        "香港": ["翡翠台", "明珠台", "J2", "VIU", "HOY", "TVB", "凤凰",
                 "无线新闻", "Now", "NOW", "美亚", "香港国际财经"],
        "台湾": ["公视", "公視", "华视", "華視", "中视", "中視", "民视", "民視",
                 "台视", "台視", "东森", "東森", "三立", "中天", "TVBS",
                 "八大", "龙华", "龍華", "纬来", "緯來", "ELTA", "寰宇",
                 "非凡", "年代", "JET", "靖天", "靖洋", "博斯", "DAZN",
                 "NatGeo", "HBO", "CineMax", "AMC", "Warner", "HITS",
                 "好莱坞", "龙祥", "美食星球", "动物星球", "CN卡通", "MOMO",
                 "Momo", "Disney", "ANIMAX", "AXN", "MTV", "大爱", "好消息",
                 "国会", "客家", "原住民", "人间卫视", "霹雳", "国兴", "东风",
                 "亚洲旅游", "afc", "Travel", "Outdoor", "TLC", "鏡電視",
                 "佛衛", "高點", "信吉", "智林", "阿里郎", "天下卫视",
                 "CHANNEL V", "BBC", "Z频道", "Fashion", "TV5", "France24",
                 "Discovery", "探索", "CATCH", "台灣藝術", "華藏", "韓國娛樂",
                 "MTV Live", "History", "德国之声", "Bloomberg", "CNN",
                 "EURO SPORT", "TRACE", "Astro", "Sky News", "NHK",
                 "壹电视", "镜电视"],
        "大陆": ["CCTV", "央视", "央視", "浙江", "湖南", "江苏", "北京",
                 "东方卫视", "东南", "辽宁", "广西", "江西", "海南", "厦门",
                 "广东", "广州", "深圳", "TVS", "大湾区", "岭南", "江门",
                 "嘉佳", "金鹰", "卡酷"],
    }

    CATEGORY_ORDER = ["大陆", "日本", "香港", "台湾", "国际",
                      "新闻", "体育", "影视", "限制"]

    def __init__(self):
        self._channels = None
        self._flat = None

    def init(self, extend=""):
        # 不做任何预加载，纯同步：用户点玉山时才拉
        pass

    @staticmethod
    def _clean_name(name):
        return re.sub(r'\s*\[[^\]]*\]\s*$', '', str(name or '')).strip()

    def _detect_category(self, name):
        if not name:
            return "国际"
        if name in self.EXACT_MAP:
            return self.EXACT_MAP[name]
        low = name.lower()
        for cat, kws in self.KEYWORD_RULES.items():
            for kw in kws:
                if kw.lower() in low:
                    return cat
        return "国际"

    def _fetch_m3u(self):
        """简化：只用 requests + urllib 二级降级，去掉 cffi 避免版本问题"""
        h = dict(self.FETCH_HEADERS)

        if HAS_REQ:
            try:
                r = requests.get(self.M3U_URL, headers=h, verify=False,
                                 timeout=12, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    print("[玉山] requests 拉到 %d 字节" % len(r.text),
                          flush=True)
                    return r.text
                else:
                    print("[玉山] requests HTTP %s" % r.status_code, flush=True)
            except Exception as e:
                print("[玉山] requests 失败: %s" % str(e)[:80], flush=True)

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx))
            rq = urllib.request.Request(self.M3U_URL, headers=h)
            with opener.open(rq, timeout=12) as resp:
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", errors="ignore")
                print("[玉山] urllib 拉到 %d 字节" % len(text), flush=True)
                return text
        except Exception as e:
            print("[玉山] urllib 失败: %s" % str(e)[:80], flush=True)

        return ""

    def _parse_m3u(self, text):
        out = []
        cur = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                m = re.search(r'tvg-name="([^"]*)"', line)
                tvg = m.group(1).strip() if m else ""
                m = re.search(r'tvg-logo="([^"]*)"', line)
                logo = m.group(1).strip() if m else ""
                display = ""
                last_q = line.rfind('"')
                if last_q >= 0:
                    tail = line[last_q + 1:]
                    if "," in tail:
                        display = tail.split(",", 1)[1].strip()
                elif "," in line:
                    display = line.split(",", 1)[1].strip()
                cur = {"tvg": tvg, "display": display, "logo": logo,
                       "url": "", "ua": "", "referer": ""}
                continue
            if line.startswith("#EXTVLCOPT"):
                if cur is None:
                    continue
                if "http-user-agent=" in line:
                    cur["ua"] = line.split("=", 1)[1].strip()
                elif "http-referrer=" in line:
                    cur["referer"] = line.split("=", 1)[1].strip()
                continue
            if line.startswith("#"):
                continue
            if cur is not None and line.startswith(("http://", "https://")):
                cur["url"] = line
                out.append(cur)
                cur = None
        return out

    def _load_channels(self):
        """无锁，纯同步。如果已缓存直接返回"""
        if self._channels is not None:
            return self._channels

        print("[玉山] 开始拉取 M3U...", flush=True)
        text = self._fetch_m3u()
        if not text:
            print("[玉山] M3U 为空，放弃", flush=True)
            self._channels = []
            return []

        raw_list = self._parse_m3u(text)
        print("[玉山] 解析出 %d 个频道" % len(raw_list), flush=True)

        grouped = {}
        restricted = []
        for item in raw_list:
            display = self._clean_name(item["display"] or item["tvg"])
            if not display:
                continue
            record = {"name": display, "url": item["url"],
                      "logo": item["logo"], "ua": item["ua"],
                      "referer": item["referer"]}
            if (item["tvg"] in self.RESTRICTED_NAMES
                    or display in self.RESTRICTED_NAMES):
                restricted.append(record)
                continue
            cat = self._detect_category(display)
            grouped.setdefault(cat, []).append(record)

        ordered = []
        for cat in self.CATEGORY_ORDER:
            if cat == "限制":
                continue
            if cat in grouped:
                ordered.append((cat, grouped.pop(cat)))
        for cat, lst in grouped.items():
            ordered.append((cat, lst))
        if restricted:
            ordered.append(("限制", restricted))

        print("[玉山] 分组完成: %d 组" % len(ordered), flush=True)
        self._channels = ordered
        return ordered

    def _flat_list(self):
        if self._flat is not None:
            return self._flat
        arr = []
        for cat, lst in (self._load_channels() or []):
            for ch in lst:
                ch2 = dict(ch)
                ch2["cat"] = cat
                arr.append(ch2)
        self._flat = arr
        return arr

    def categories(self):
        """直接同步拉，返回分类名列表"""
        try:
            channels = self._load_channels()
        except Exception as e:
            print("[玉山] categories 异常: %s" % str(e)[:80], flush=True)
            return []
        if not channels:
            return []
        return [cat for cat, lst in channels if lst]

    def categoryContent(self, tid, pg, filter=False, extend=None):
        tid = str(tid).strip()
        vids = []
        for i, ch in enumerate(self._flat_list()):
            if tid != "all" and ch["cat"] != tid:
                continue
            vids.append({
                "vod_id": "live#%d" % i,
                "vod_name": ch["name"],
                "vod_pic": ch["logo"],
                "vod_remarks": ch["cat"],
            })
        return {"list": vids, "page": 1, "pagecount": 1,
                "limit": len(vids) or 20, "total": len(vids)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        s = str(ids[0])
        if s.startswith("live#"):
            try:
                idx = int(s.split("#", 1)[1])
            except Exception:
                return {"list": []}
            arr = self._flat_list()
            if 0 <= idx < len(arr):
                ch = arr[idx]
                safe = str(ch["name"]).replace("$", " ").replace("#", " ")
                return {"list": [{
                    "vod_id": s,
                    "vod_name": ch["name"],
                    "vod_pic": ch["logo"],
                    "vod_remarks": ch["cat"],
                    "vod_play_from": "玉山直播",
                    "vod_play_url": "%s$%s" % (safe, s),
                }]}
        return {"list": []}

    def playerContent(self, flag, pid, vipFlags=None):
        s = str(pid or "")
        if "$" in s:
            s = s.split("$", 1)[1]
        if s.startswith("live#"):
            try:
                idx = int(s.split("#", 1)[1])
            except Exception:
                return {"parse": 0, "jx": 0, "url": "", "header": {}}
            arr = self._flat_list()
            if 0 <= idx < len(arr):
                ch = arr[idx]
                headers = {"User-Agent": ch.get("ua") or UA_BROWSER}
                headers["Referer"] = (ch.get("referer")
                                      or "https://www.liaobagua.com/")
                return {"parse": 0, "jx": 0, "url": ch["url"], "header": headers}
        if s.startswith("http"):
            return {"parse": 0, "jx": 0, "url": s, "header": {}}
        return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def search(self, key):
        key = str(key or "").lower().strip()
        if not key:
            return []
        out = []
        for i, ch in enumerate(self._flat_list()):
            if key in ch["name"].lower():
                out.append({
                    "vod_id": "live#%d" % i,
                    "vod_name": ch["name"],
                    "vod_pic": ch["logo"],
                    "vod_remarks": ch["cat"],
                })
        return out


# ============================================================
# 源 2：安博（保持原样，已验证可用）
# ============================================================
class AnboSource(_TVBoxBase):
    PREFIX = "ab"
    NAME = "安博"

    def __init__(self):
        self._channels = None
        self._categories = None
        self._lock = threading.Lock()

    def init(self, extend=""):
        self.api_base_url = "https://www.usplaytvonphone.com"
        self.login_endpoint = "info.php"
        self.channel_endpoint = "live.php"
        self.uri_endpoint = "uri.php"
        self.aes_key = b"W@ms7+2HZ34<iZz>"
        self.username = "12345678"
        self.password = "12345678"
        self.real_mac = "00:1a:3b:5c:7d:9e"
        try:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            self.base_dir = "/sdcard/tvbox/py"
        self.default_logo = "https://img.icons8.com/color/48/tv.png"
        self.session = requests.Session() if HAS_REQ else None
        if self.session is not None:
            try:
                self.session.verify = False
            except Exception:
                pass

    @staticmethod
    def _get_random_string(length):
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(random.choice(chars) for _ in range(length))

    @staticmethod
    def _get_index(c):
        if '0' <= c <= '9':
            return 10 + int(c)
        elif 'a' <= c <= 'z':
            return 10 + ord(c) - ord('a')
        elif 'A' <= c <= 'Z':
            return 36 + ord(c) - ord('A')
        return 10

    def _sub_encrypt(self, iv_idx, s, iv):
        try:
            i2 = int(iv[iv_idx])
        except (ValueError, TypeError):
            i2 = 0
        if i2 == 0:
            i2 = 10
        return s[:i2] + self._get_random_string(i2) + s[i2:]

    def _sub_decrypt(self, iv_idx, s, iv):
        try:
            i2 = int(iv[iv_idx])
        except (ValueError, TypeError):
            i2 = 0
        if i2 == 0:
            i2 = 10
        return s[:i2] + s[i2 * 2:]

    @staticmethod
    def _md5_hex(text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_serial_md5(self, username):
        inner1 = self._md5_hex(username)
        inner2 = self._md5_hex("Gooooogle")
        step3 = inner1 + inner2 + "201306@202106>"
        step4 = self._md5_hex(step3)
        step5 = step4 + "Ub"
        return self._md5_hex(step5)

    def _ubed_encrypt(self, payload_dict):
        if not HAS_AES:
            return {"sign": "", "iv": ""}
        payload_str = json.dumps(payload_dict, separators=(',', ':'),
                                 ensure_ascii=False)
        iv = self._get_random_string(16)
        block_size = 16
        pad_len = block_size - (len(payload_str.encode('utf-8')) % block_size)
        padded_str = payload_str + chr(pad_len) * pad_len
        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv.encode('utf-8'))
        enc_bytes = cipher.encrypt(padded_str.encode('utf-8'))
        sign = base64.b64encode(enc_bytes).decode('utf-8')
        sign = self._sub_encrypt(5, sign, iv)
        sign = self._sub_encrypt(12, sign, iv)
        rnd_prefix = self._get_random_string(self._get_index(sign[-6]))
        return {"sign": rnd_prefix + sign, "iv": iv}

    def _ubed_decrypt(self, sign, iv):
        if not sign or not iv or not HAS_AES:
            return ""
        try:
            idx = self._get_index(sign[-6])
            sign = sign[idx:]
            sign = self._sub_decrypt(12, sign, iv)
            sign = self._sub_decrypt(5, sign, iv)
            pad = 4 - len(sign) % 4
            if pad < 4:
                sign += "=" * pad
            enc_bytes = base64.b64decode(sign)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv.encode('utf-8'))
            dec_bytes = cipher.decrypt(enc_bytes)
            if not dec_bytes:
                return ""
            pad_len = dec_bytes[-1]
            if pad_len <= 0 or pad_len > len(dec_bytes) or pad_len > 16:
                pad_len = 0
            if pad_len:
                dec_bytes = dec_bytes[:-pad_len]
            return dec_bytes.decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def _fetch_dynamic_token(self):
        if self.session is None:
            return None
        body_payload = {
            "icode": "", "icode_name": self.username,
            "icode_passwd": self.password,
            "icode_sign": self._get_serial_md5(self.username), "signup": 0
        }
        current_time = int(time.time())
        device_info = {
            "app_laguage": 2, "brand": "Unblock", "cpu_api": "arm64-v8a",
            "cpu_api2": "", "device_flag": "", "mac": self.real_mac,
            "model": "UBOX10", "time": current_time,
            "token": "a1391713a32e61d249b319def67ed961", "ubcode": "88888888"
        }
        headers = {
            "device_info": json.dumps(self._ubed_encrypt(device_info),
                                      separators=(',', ':')),
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.12.0",
            "Connection": "close"
        }
        try:
            resp = self.session.post(
                f"{self.api_base_url}/{self.login_endpoint}",
                json=self._ubed_encrypt(body_payload),
                headers=headers, timeout=6, verify=False)
            if resp.status_code == 200 and resp.text:
                res_json = resp.json()
                dec_text = self._ubed_decrypt(res_json.get('sign'),
                                              res_json.get('iv'))
                res_data = json.loads(dec_text)
                if str(res_data.get('return_code')) == "99":
                    return res_data.get('return_token')
        except Exception:
            pass
        return None

    def _get_channel_info(self, token, channel_id):
        if self.session is None:
            return None
        current_time = int(time.time())
        live_payload = {
            "icode_name": self.username, "icode_passwd": self.password,
            "icode_sign": self._get_serial_md5(self.username), "token": token
        }
        device_info = {
            "app_laguage": 2, "brand": "Unblock", "cpu_api": "arm64-v8a",
            "cpu_api2": "", "device_flag": "", "mac": self.real_mac,
            "model": "UBOX10", "time": current_time, "token": token,
            "ubcode": "88888888"
        }
        headers = {
            "device_info": json.dumps(self._ubed_encrypt(device_info),
                                      separators=(',', ':')),
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.12.0",
            "Connection": "close"
        }
        try:
            self.session.post(f"{self.api_base_url}/{self.channel_endpoint}",
                              json=self._ubed_encrypt(live_payload),
                              headers=headers, timeout=4, verify=False)
            uri_payload = {
                "icode_name": self.username, "icode_passwd": self.password,
                "icode_sign": self._get_serial_md5(self.username),
                "token": token, "id": str(channel_id)
            }
            for _ in range(2):
                resp = self.session.post(
                    f"{self.api_base_url}/{self.uri_endpoint}",
                    json=self._ubed_encrypt(uri_payload),
                    headers=headers, timeout=5, verify=False)
                if resp.status_code == 200 and resp.text:
                    res_json = resp.json()
                    dec_text = self._ubed_decrypt(res_json.get('sign'),
                                                  res_json.get('iv'))
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

    def _load_json_from_file(self, path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _load_json_from_url(self, url):
        if self.session is None:
            return None
        try:
            resp = self.session.get(url, timeout=8, verify=False,
                                    headers={"User-Agent": "okhttp/3.12.0"})
            if resp.status_code == 200 and resp.text:
                return resp.json()
        except Exception:
            pass
        return None

    def _clean_channel_name(self, name):
        name = str(name).strip()
        name = re.sub(
            r'(高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清)$',
            '', name, flags=re.IGNORECASE)
        return name.replace(' ', '').strip()

    def _match_channel_logo(self, ch_name):
        clean = self._clean_channel_name(ch_name)
        if not clean:
            return self.default_logo
        logo_alias = {
            "凤凰中文": "凤凰卫视中文台",
            "凤凰资讯": "凤凰卫视资讯台",
            "凤凰香港": "凤凰卫视香港台",
            "凤凰电影": "凤凰卫视电影台",
            "无线新闻": "无线新闻台",
            "无线财经": "无线财经资讯台",
            "TVB": "无线新闻台",
            "湖南金鹰": "金鹰卡通",
        }
        clean = logo_alias.get(clean, clean)
        return "https://epg.112114.eu.org/logo/%s.png" % urllib.parse.quote(clean)

    def load_channels(self):
        if self._channels is not None:
            return self._channels
        with self._lock:
            if self._channels is not None:
                return self._channels

            processed_channels = []
            categories_order = []

            possible_dirs = [
                "https://raw.githubusercontent.com/kan1314go/9988/refs/heads/main/py/",
                self.base_dir,
                "/sdcard/tvbox/py/",
                "/sdcard/Download/",
            ]

            for d in possible_dirs:
                for fname in ['channels.json', 'extra.json']:
                    if str(d).startswith(('http://', 'https://')):
                        url = d.rstrip('/') + '/' + fname
                        data = self._load_json_from_url(url)
                    else:
                        path = os.path.join(d, fname)
                        data = self._load_json_from_file(path)
                    if not data:
                        continue
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
                            ch_logo = str(ch.get('logo', '')).strip()
                            if not ch_logo:
                                ch_logo = self._match_channel_logo(ch_title)
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

            self._channels = processed_channels
            self._categories = categories_order
            return self._channels

    def categories(self):
        try:
            self.load_channels()
        except Exception:
            return []
        if not self._categories:
            return []
        return [c for c in self._categories
                if c and c not in ("系统提示", "系統提示")]

    def categoryContent(self, tid, pg, filter=False, extend=None):
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
                "vod_area": ch["category"],
                "vod_content": "UBLive 直播頻道"
            })
        return {
            "list": videos, "page": 1, "pagecount": 1,
            "limit": len(videos), "total": len(videos)
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

        token = self._fetch_dynamic_token()
        stream_url = ""
        fftoken = ""
        playtoken = ""
        if token:
            info = self._get_channel_info(token, channel_id)
            if info and info.get("uri"):
                stream_url = info.get("uri")
                fftoken = info.get("fftoken", "")
                playtoken = info.get("playtoken", "")

        return {
            "list": [{
                "vod_id": channel_id,
                "vod_name": ch_name,
                "vod_pic": ch_logo,
                "vod_remarks": "直播",
                "vod_year": "",
                "vod_area": category,
                "vod_content": "UBLive 實時直播源",
                "vod_play_from": "UBLive",
                "vod_play_url": ("播放$%s|%s|%s" % (stream_url, fftoken, playtoken))
                                if stream_url else "播放$error"
            }]
        }

    def playerContent(self, flag, pid, vipFlags=None):
        if not pid or pid == "error":
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        parts = pid.split('|')
        real_url = parts[0]
        fftoken = parts[1] if len(parts) > 1 else ""
        playtoken = parts[2] if len(parts) > 2 else ""
        headers = {"User-Agent": "okhttp/3.12.0"}
        if fftoken:
            headers["fftoken"] = fftoken
        if playtoken:
            headers["playtoken"] = playtoken
        return {"parse": 0, "playUrl": "", "url": real_url, "header": headers}

    def search(self, key):
        key = str(key or "").lower().strip()
        if not key:
            return []
        out = []
        for ch in self.load_channels():
            if key in ch["name"].lower():
                out.append({
                    "vod_id": ch["id"],
                    "vod_name": ch["name"],
                    "vod_pic": ch["logo"] or self.default_logo,
                    "vod_remarks": ch["category"],
                })
        return out


# ============================================================
# 源 3：全球（保持原样，已验证可用）
# ============================================================
class QuanqiuSource(_TVBoxBase):
    PREFIX = "qq"
    NAME = "全球"

    _KEYWORD_LOGOS = {
        "CCTV5PLUS": "CCTV5+", "CCTV5+": "CCTV5+",
        "CCTV5体育": "CCTV5", "CCTV5": "CCTV5",
        "CCTV1综合": "CCTV1", "CCTV1": "CCTV1",
        "CCTV2财经": "CCTV2", "CCTV2": "CCTV2",
        "CCTV3综艺": "CCTV3", "CCTV3": "CCTV3",
        "CCTV4中文国际": "CCTV4", "CCTV4": "CCTV4",
        "CCTV6电影": "CCTV6", "CCTV6": "CCTV6",
        "CCTV7军事": "CCTV7", "CCTV7": "CCTV7",
        "CCTV8电视剧": "CCTV8", "CCTV8": "CCTV8",
        "CCTV9纪录": "CCTV9", "CCTV9": "CCTV9",
        "CCTV10科教": "CCTV10", "CCTV10": "CCTV10",
        "CCTV11戏曲": "CCTV11", "CCTV11": "CCTV11",
        "CCTV12社会与法": "CCTV12", "CCTV12": "CCTV12",
        "CCTV13新闻": "CCTV13", "CCTV13": "CCTV13",
        "CCTV14少儿": "CCTV14", "CCTV14": "CCTV14",
        "CCTV15音乐": "CCTV15", "CCTV15": "CCTV15",
        "CCTV16奥林匹克": "CCTV16", "CCTV16": "CCTV16",
        "CCTV17农业": "CCTV17", "CCTV17": "CCTV17",
        "湖南卫视": "湖南卫视", "浙江卫视": "浙江卫视",
        "江苏卫视": "江苏卫视", "东方卫视": "东方卫视",
        "北京卫视": "北京卫视", "安徽卫视": "安徽卫视",
        "山东卫视": "山东卫视", "广东卫视": "广东卫视",
        "深圳卫视": "深圳卫视", "天津卫视": "天津卫视",
        "湖北卫视": "湖北卫视", "四川卫视": "四川卫视",
        "重庆卫视": "重庆卫视", "辽宁卫视": "辽宁卫视",
        "黑龙江卫视": "黑龙江卫视", "吉林卫视": "吉林卫视",
        "河南卫视": "河南卫视", "河北卫视": "河北卫视",
        "山西卫视": "山西卫视", "陕西卫视": "陕西卫视",
        "甘肃卫视": "甘肃卫视", "宁夏卫视": "宁夏卫视",
        "青海卫视": "青海卫视", "新疆卫视": "新疆卫视",
        "西藏卫视": "西藏卫视", "云南卫视": "云南卫视",
        "贵州卫视": "贵州卫视", "广西卫视": "广西卫视",
        "海南卫视": "海南卫视", "东南卫视": "东南卫视",
        "江西卫视": "江西卫视", "内蒙古卫视": "内蒙古卫视",
        "厦门卫视": "厦门卫视", "延边卫视": "延边卫视",
        "兵团卫视": "兵团卫视",
        "翡翠台": "翡翠台", "明珠台": "明珠台",
        "无线新闻": "无线新闻台", "无线财经": "无线财经资讯台",
        "TVB": "翡翠台", "J2": "J2",
        "VIUTV": "ViuTV", "HOYTV": "HOY TV",
        "凤凰卫视中文台": "凤凰卫视中文台",
        "凤凰卫视资讯台": "凤凰卫视资讯台",
        "凤凰卫视香港台": "凤凰卫视香港台",
        "凤凰卫视电影台": "凤凰卫视电影台",
        "凤凰中文": "凤凰卫视中文台",
        "凤凰资讯": "凤凰卫视资讯台",
        "凤凰香港": "凤凰卫视香港台",
        "凤凰电影": "凤凰卫视电影台",
        "澳视澳门": "澳视澳门", "澳门莲花": "澳门莲花卫视",
        "民视": "民视新闻台", "中视": "中视", "华视": "华视",
        "台视": "台视", "公视": "公视", "大爱": "大爱一台",
        "中天": "中天新闻台", "东森": "东森新闻台",
        "三立": "三立新闻台", "TVBS": "TVBS新闻台",
        "年代": "年代新闻", "八大": "八大第一台",
        "非凡": "非凡新闻台", "纬来": "纬来综合台",
        "龙华": "龙华偶像台",
        "上海新闻综合": "上海新闻综合", "上海东方卫视": "东方卫视",
        "湖南经视": "湖南经视", "江苏城市": "江苏城市",
        "北京新闻": "北京新闻", "广东珠江": "广东珠江",
        "南方卫视": "南方卫视", "深圳都市": "深圳都市频道",
    }

    def __init__(self):
        self._channels = None
        self._categories = None
        self._lock = threading.Lock()

    def init(self, extend=""):
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
        self.LOGO_CDN = "https://epg.112114.eu.org/logo/{}.png"
        self._sorted_keys = sorted(
            self._KEYWORD_LOGOS.keys(), key=len, reverse=True)
        self.session = requests.Session() if HAS_REQ else None
        if self.session is not None:
            try:
                self.session.verify = False
            except Exception:
                pass

    def _sign(self, ts, method):
        raw = self.from_id + self.salt + str(ts) + method + self.devid
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _headers(self, body):
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/3.12.5",
            "Accept-Encoding": "identity"
        }

    def _post(self, payload):
        if self.session is None:
            raise Exception("no requests")
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        last_error = "Dream API request failed"
        for api_url in self.api_urls:
            try:
                r = self.session.post(
                    api_url, data=body.encode("utf-8"),
                    headers=self._headers(body), timeout=15, verify=False)
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
            self.server = str(first.get("url") or "") \
                if isinstance(first, dict) else str(first)
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

    def _get_channels(self):
        if self._channels is not None:
            return self._channels
        with self._lock:
            if self._channels is not None:
                return self._channels
            self._login_step_1()
            self._login_step_2()
            channels = self._fetch_channel_data()
            self._channels = channels
            return channels

    @staticmethod
    def _get_channel_name(item):
        if not isinstance(item, dict):
            return "DreamTV"
        return str(item.get("name") or item.get("title")
                   or item.get("channel_name") or "DreamTV")

    @staticmethod
    def _get_channel_category(item):
        if not isinstance(item, dict):
            return "DreamTV"
        return str(item.get("category") or item.get("group")
                   or item.get("group_name") or "DreamTV")

    @staticmethod
    def _get_channel_url(item):
        if not isinstance(item, dict):
            return ""
        return str(item.get("url") or item.get("play_url")
                   or item.get("stream_url") or "")

    def _normalize(self, name):
        if not name:
            return ""
        name = str(name).strip()
        for _ in range(2):
            name = re.sub(
                r'(?:[-\s_·]*)(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清|高码|HD1080)$',
                '', name, flags=re.IGNORECASE)
        return re.sub(r'[\s\-_\.\(\)\[\]（）【】·]', '', name).upper()

    def _match_keyword(self, ch_name):
        norm = self._normalize(ch_name)
        if not norm:
            return ""
        for key in self._sorted_keys:
            if key in norm:
                return self._KEYWORD_LOGOS[key]
        return ""

    def _get_channel_logo(self, item):
        if not isinstance(item, dict):
            return ""
        name = self._get_channel_name(item)
        raw_logo = str(item.get("logo") or item.get("pic")
                       or item.get("icon") or "").strip()
        if raw_logo and raw_logo.lower() not in ("null", "none", "0", ""):
            if raw_logo.startswith("http"):
                return raw_logo
            if self.server:
                if raw_logo.startswith("/"):
                    return self.server.rstrip("/") + raw_logo
                return self.server.rstrip("/") + "/" + raw_logo.lstrip("/")
            return raw_logo
        matched = self._match_keyword(name)
        if matched:
            return self.LOGO_CDN.format(urllib.parse.quote(matched))
        return ""

    def _get_channel_play_url(self, item):
        raw_url = self._get_channel_url(item)
        if not raw_url:
            return ""
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        if self.server:
            return self.server.rstrip("/") + "/" + raw_url.lstrip("/")
        return raw_url

    def categories(self):
        try:
            self._get_channels()
        except Exception:
            return []
        if not self._channels:
            return []
        cats = []
        for item in self._channels:
            c = self._get_channel_category(item)
            if c and c not in cats:
                cats.append(c)
        return cats

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            channels = self._get_channels()
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 0, "total": 0}
        vids = []
        for item in channels:
            if tid != "all" and self._get_channel_category(item) != tid:
                continue
            play_url = self._get_channel_play_url(item)
            if not play_url:
                continue
            vids.append({
                "vod_id": play_url,
                "vod_name": self._get_channel_name(item),
                "vod_pic": self._get_channel_logo(item),
                "vod_remarks": self._get_channel_category(item),
            })
        return {"list": vids, "page": 1, "pagecount": 1,
                "limit": len(vids), "total": len(vids)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        pid = str(ids[0])
        name, logo = "DreamTV直播", ""
        try:
            channels = self._get_channels()
        except Exception:
            channels = []
        for item in channels:
            if self._get_channel_play_url(item) == pid:
                name = self._get_channel_name(item)
                logo = self._get_channel_logo(item)
                break
        return {"list": [{
            "vod_id": pid, "vod_name": name, "vod_pic": logo,
            "vod_remarks": "直播", "vod_content": "DreamTV直播頻道",
            "vod_play_from": "DreamTV",
            "vod_play_url": "播放$" + pid
        }]}

    def playerContent(self, flag, pid, vipFlags=None):
        if not pid:
            return {"parse": 0, "playUrl": "", "url": ""}
        header = {
            "User-Agent": "Lavf/58.12.100", "Accept": "*/*",
            "Connection": "keep-alive", "Icy-MetaData": "1",
            "userid": str(self.client_id), "usertoken": str(self.token),
            "Cache-Control": "no-cache", "Pragma": "no-cache"
        }
        return {"parse": 0, "playUrl": "", "url": str(pid), "header": header}

    def search(self, key):
        key = str(key or "").lower().strip()
        if not key:
            return []
        try:
            channels = self._get_channels()
        except Exception:
            return []
        out = []
        for item in channels:
            if key in self._get_channel_name(item).lower():
                play_url = self._get_channel_play_url(item)
                if not play_url:
                    continue
                out.append({
                    "vod_id": play_url,
                    "vod_name": self._get_channel_name(item),
                    "vod_pic": self._get_channel_logo(item),
                    "vod_remarks": self._get_channel_category(item),
                })
        return out


# ============================================================
# 主聚合 Spider（C 方案）
# ============================================================
class Spider(_TVBoxBase):

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.sources = {
            YushanSource.PREFIX: YushanSource(),
            AnboSource.PREFIX: AnboSource(),
            QuanqiuSource.PREFIX: QuanqiuSource(),
        }

    def getName(self):
        return "三源聚合"

    def init(self, extend=""):
        for src in self.sources.values():
            try:
                src.init(extend)
            except Exception:
                pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=False):
        classes = [
            {"type_id": YushanSource.PREFIX, "type_name": "📺 玉山"},
            {"type_id": AnboSource.PREFIX, "type_name": "📺 安博"},
            {"type_id": QuanqiuSource.PREFIX, "type_name": "📺 全球"},
        ]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        key = str(tid or "").strip()
        src = self.sources.get(key)
        if src is None:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 0, "total": 0}

        try:
            cats = src.categories() or []
        except Exception:
            cats = []

        videos = []
        for c in cats:
            if not c:
                continue
            c_str = str(c)
            videos.append({
                "vod_id": "%s%scat%s%s" % (key, SEP, SEP, c_str),
                "vod_name": c_str,
                "vod_pic": "",
                "vod_remarks": "点击查看频道",
            })

        if not videos:
            videos.append({
                "vod_id": "%s%scat%s__EMPTY__" % (key, SEP, SEP),
                "vod_name": "❌ 源未加载",
                "vod_pic": "",
                "vod_remarks": "返回重进",
            })

        return {"list": videos, "page": 1, "pagecount": 1,
                "limit": len(videos), "total": len(videos)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        full_id = str(ids[0])
        key, real_id = _split(full_id)
        src = self.sources.get(key)
        if src is None:
            return {"list": []}

        # 入口 A：点分类
        if real_id.startswith("cat" + SEP):
            cat = real_id[len("cat" + SEP):]
            return self._cat_detail(src, key, full_id, cat)

        # 入口 B：点频道
        try:
            res = src.detailContent([real_id])
        except Exception:
            return {"list": []}

        for v in res.get("list", []) or []:
            v["vod_id"] = full_id
            purl = v.get("vod_play_url", "")
            if purl:
                v["vod_play_url"] = self._prefix_play_url(purl, key)
            vf = v.get("vod_play_from") or "直播"
            if not vf.startswith("[%s]" % src.NAME):
                v["vod_play_from"] = "[%s] %s" % (src.NAME, vf)
        return res

    def _cat_detail(self, src, key, full_id, cat):
        if cat == "__EMPTY__":
            return {"list": [{
                "vod_id": full_id,
                "vod_name": "源未加载",
                "vod_content": "该源没有返回分类，返回上一级重试",
                "vod_play_from": src.NAME,
                "vod_play_url": "无内容$error",
            }]}

        try:
            res = src.categoryContent(cat, 1, False, {})
        except Exception as e:
            return {"list": [{
                "vod_id": full_id,
                "vod_name": cat,
                "vod_content": "加载失败: %s" % str(e)[:80],
                "vod_play_from": src.NAME,
                "vod_play_url": "错误$error",
            }]}

        channels = res.get("list", []) or []
        eps = []
        for v in channels:
            vid = v.get("vod_id")
            vname = v.get("vod_name") or "频道"
            if not vid:
                continue
            safe_name = str(vname).replace("$", " ").replace("#", " ")
            eps.append("%s$%s%s%s" % (safe_name, key, SEP, vid))

        if not eps:
            return {"list": [{
                "vod_id": full_id,
                "vod_name": cat,
                "vod_content": "该分类下无频道",
                "vod_play_from": src.NAME,
                "vod_play_url": "无频道$error",
            }]}

        return {"list": [{
            "vod_id": full_id,
            "vod_name": cat,
            "vod_pic": "",
            "vod_remarks": "%d 个频道" % len(eps),
            "vod_content": "%s · %s" % (src.NAME, cat),
            "vod_play_from": src.NAME,
            "vod_play_url": "#".join(eps),
        }]}

    @staticmethod
    def _prefix_play_url(purl, key):
        out = []
        for p in str(purl).split("#"):
            if "$" in p:
                name, pid = p.split("$", 1)
                out.append("%s$%s%s%s" % (name, key, SEP, pid))
            else:
                out.append(p)
        return "#".join(out)

    def playerContent(self, flag, pid, vipFlags=None):
        full_pid = str(pid or "")
        if "$" in full_pid:
            full_pid = full_pid.split("$", 1)[1]
        if full_pid == "error":
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

        key, real_pid = _split(full_pid)
        src = self.sources.get(key)
        if src is None:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

        try:
            return src.playerContent(flag, real_pid, vipFlags)
        except Exception:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def searchContent(self, key, quick=False, pg="1"):
        key_s = str(key or "").strip()
        if not key_s:
            return {"list": []}
        all_videos = []
        for prefix, src in self.sources.items():
            try:
                arr = src.search(key_s)
            except Exception:
                arr = []
            for v in arr:
                if v.get("vod_id"):
                    v["vod_id"] = "%s%s%s" % (prefix, SEP, v["vod_id"])
                v["vod_remarks"] = "[%s] %s" % (src.NAME,
                                                v.get("vod_remarks") or "直播")
                all_videos.append(v)
        return {"list": all_videos}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    def localProxy(self, param):
        return [404, "text/plain", b""]

    def action(self, action_str):
        return ""

    def destroy(self):
        for src in self.sources.values():
            s = getattr(src, "session", None)
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        return "正在Destroy"


if __name__ == '__main__':
    pass