# -*- coding: utf-8 -*-
# TVBox 聚合直播源：玉山 + 安博 + 全球
# 首页显示 3 个板块，点进去用 filter 条切换分类

import sys
import os
import re
import time
import json
import gzip
import base64
import random
import hashlib
import urllib.parse
import urllib.request
import ssl

try:
    import requests as _requests
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

try:
    from curl_cffi import requests as _cffi
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

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


# 全局分隔符：源前缀与真实 id 之间用 ":"（避免与 URL 里的 / ? # 冲突）
SEP = ":"
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/131.0.0.0 Safari/537.36")


def _log(msg):
    print("[聚合] %s" % msg, flush=True)


def _split_full_id(full_id):
    """拆分 'ys:live#5' → ('ys', 'live#5')，只 split 一次"""
    s = str(full_id or "")
    if ":" in s:
        prefix, real = s.split(":", 1)
        return prefix, real
    # 兼容老格式 __
    if "__" in s:
        prefix, real = s.split("__", 1)
        return prefix, real
    return "", s


# ============================================================
# 源 1：玉山
# ============================================================
class YushanSource(object):
    PREFIX = "ys"
    NAME = "玉山"
    PLAY_FROM = "玉山直播"
    DEFAULT_M3U_URL = "https://www.liaobagua.com/tv/tv.php?a=play"

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
    CATEGORY_ORDER = ["大陆", "香港", "台湾", "日本", "国际",
                      "新闻", "体育", "影视", "限制"]

    def __init__(self):
        self.m3u_url = self.DEFAULT_M3U_URL
        self._channels = None
        self._flat = None

    def init(self, extend=""):
        if not extend:
            return
        try:
            cfg = json.loads(extend) if isinstance(extend, str) else extend
            if isinstance(cfg, dict) and cfg.get("m3u"):
                self.m3u_url = str(cfg["m3u"])
        except Exception:
            pass

    # ---------- 工具 ----------
    @staticmethod
    def _clean(name):
        return re.sub(r'\s*\[[^\]]*\]\s*$', '', str(name or '')).strip()

    def _detect_cat(self, name):
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

    # ---------- 网络 ----------
    def _fetch(self):
        h = dict(self.FETCH_HEADERS)
        if HAS_CFFI:
            try:
                r = _cffi.get(self.m3u_url, headers=h, impersonate="chrome131",
                              verify=False, timeout=15, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    _log("[玉山] cffi 拿到 %d 字节" % len(r.text))
                    return r.text
            except Exception as e:
                _log("[玉山] cffi err: %s" % str(e)[:60])
        if HAS_REQ:
            try:
                r = _requests.get(self.m3u_url, headers=h, verify=False,
                                  timeout=15, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    _log("[玉山] req 拿到 %d 字节" % len(r.text))
                    return r.text
            except Exception as e:
                _log("[玉山] req err: %s" % str(e)[:60])
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx))
            rq = urllib.request.Request(self.m3u_url, headers=h)
            with opener.open(rq, timeout=15) as resp:
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", errors="ignore")
                _log("[玉山] urllib 拿到 %d 字节" % len(text))
                return text
        except Exception as e:
            _log("[玉山] urllib err: %s" % str(e)[:60])
        return ""

    def _parse(self, text):
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
                # 从最后一个引号后取逗号
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

    def _load(self):
        if self._channels is not None:
            return self._channels
        text = self._fetch()
        if not text:
            self._channels = []
            return self._channels
        raw = self._parse(text)
        _log("[玉山] 解析出 %d 个频道" % len(raw))

        grouped = {}
        restricted = []
        for item in raw:
            display = self._clean(item["display"] or item["tvg"])
            if not display:
                continue
            rec = {"name": display, "url": item["url"], "logo": item["logo"],
                   "ua": item["ua"], "referer": item["referer"]}
            if item["tvg"] in self.RESTRICTED_NAMES or display in self.RESTRICTED_NAMES:
                restricted.append(rec)
                continue
            cat = self._detect_cat(display or item["tvg"])
            grouped.setdefault(cat, []).append(rec)

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
        self._channels = ordered
        return ordered

    def _flat(self):
        if self._flat is not None:
            return self._flat
        arr = []
        for cat, lst in self._load():
            for ch in lst:
                ch2 = dict(ch)
                ch2["cat"] = cat
                arr.append(ch2)
        self._flat = arr
        return arr

    # ---------- 子源接口 ----------
    def categories(self):
        """给 homeContent 用的分类列表（不触发 M3U 拉取）"""
        return list(self.CATEGORY_ORDER)

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid).strip()
        vids = []
        for i, ch in enumerate(self._flat()):
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
            arr = self._flat()
            if 0 <= idx < len(arr):
                ch = arr[idx]
                return {"list": [{
                    "vod_id": s, "vod_name": ch["name"], "vod_pic": ch["logo"],
                    "vod_remarks": ch["cat"],
                    "vod_play_from": self.PLAY_FROM,
                    "vod_play_url": "%s$%s" % (ch["name"], ch["url"]),
                }]}
        return {"list": []}

    def playerContent(self, flag, pid, vipFlags):
        s = str(pid or "")
        if "$" in s:
            s = s.split("$", 1)[1]
        if s.startswith("live#"):
            try:
                idx = int(s.split("#", 1)[1])
            except Exception:
                return {"parse": 0, "jx": 0, "url": "", "header": {}}
            arr = self._flat()
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
        for i, ch in enumerate(self._flat()):
            if key in ch["name"].lower():
                out.append({
                    "vod_id": "live#%d" % i,
                    "vod_name": ch["name"],
                    "vod_pic": ch["logo"],
                    "vod_remarks": ch["cat"],
                })
        return out


# ============================================================
# 源 2：安博（UBLive）
# ============================================================
class AnboSource(object):
    PREFIX = "ab"
    NAME = "安博"
    PLAY_FROM = "UBLive"

    def __init__(self):
        self.api = "https://www.usplaytvonphone.com"
        self.login_ep = "info.php"
        self.ch_ep = "live.php"
        self.uri_ep = "uri.php"
        self.aes_key = b"W@ms7+2HZ34<iZz>"
        self.user = "12345678"
        self.pwd = "12345678"
        self.mac = "00:1a:3b:5c:7d:9e"
        self.base_dir = (os.path.dirname(os.path.abspath(__file__))
                         if "__file__" in globals() else "/sdcard/tvbox/py")
        self.channels = []
        self.categories = []
        self.default_logo = "https://img.icons8.com/color/48/tv.png"

        # token 缓存（★ 修复）
        self._token = None
        self._token_time = 0

        self.session = _requests.Session() if HAS_REQ else None

    def init(self, extend=""):
        pass

    # ---------- 加密 ----------
    @staticmethod
    def _rand(n):
        c = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(random.choice(c) for _ in range(n))

    @staticmethod
    def _get_index(c):
        if '0' <= c <= '9':
            return 10 + int(c)
        if 'a' <= c <= 'z':
            return 10 + ord(c) - ord('a')
        if 'A' <= c <= 'Z':
            return 36 + ord(c) - ord('A')
        return 10

    def _sub_enc(self, i, s, iv):
        try:
            v = int(iv[i])
        except (ValueError, TypeError):
            v = 0
        if v == 0:
            v = 10
        return s[:v] + self._rand(v) + s[v:]

    def _sub_dec(self, i, s, iv):
        try:
            v = int(iv[i])
        except (ValueError, TypeError):
            v = 0
        if v == 0:
            v = 10
        return s[:v] + s[v * 2:]

    @staticmethod
    def _md5(t):
        return hashlib.md5(t.encode("utf-8")).hexdigest()

    def _serial_md5(self, u):
        a = self._md5(u)
        b = self._md5("Gooooogle")
        c = self._md5(a + b + "201306@202106>")
        return self._md5(c + "Ub")

    def _enc(self, payload):
        if not HAS_AES:
            return {"sign": "", "iv": ""}
        s = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        iv = self._rand(16)
        pad = 16 - (len(s.encode("utf-8")) % 16)
        s2 = s + chr(pad) * pad
        c = AES.new(self.aes_key, AES.MODE_CBC, iv.encode("utf-8"))
        sign = base64.b64encode(c.encrypt(s2.encode("utf-8"))).decode("utf-8")
        sign = self._sub_enc(5, sign, iv)
        sign = self._sub_enc(12, sign, iv)
        rnd = self._rand(self._get_index(sign[-6]))
        return {"sign": rnd + sign, "iv": iv}

    def _dec(self, sign, iv):
        if not sign or not iv or not HAS_AES:
            return ""
        try:
            idx = self._get_index(sign[-6])
            sign = sign[idx:]
            sign = self._sub_dec(12, sign, iv)
            sign = self._sub_dec(5, sign, iv)
            p = 4 - len(sign) % 4
            if p < 4:
                sign += "=" * p
            data = AES.new(self.aes_key, AES.MODE_CBC,
                           iv.encode("utf-8")).decrypt(base64.b64decode(sign))
            if not data:
                return ""
            pl = data[-1]
            if pl <= 0 or pl > len(data) or pl > 16:
                pl = 0
            if pl:
                data = data[:-pl]
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _headers(self, dev):
        return {
            "device_info": json.dumps(self._enc(dev), separators=(',', ':')),
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.12.0",
            "Connection": "close",
        }

    def _dev(self, token, ts):
        return {
            "app_laguage": 2, "brand": "Unblock", "cpu_api": "arm64-v8a",
            "cpu_api2": "", "device_flag": "", "mac": self.mac,
            "model": "UBOX10", "time": ts, "token": token,
            "ubcode": "88888888",
        }

    def _fetch_token(self):
        if self.session is None:
            return None
        body = {"icode": "", "icode_name": self.user,
                "icode_passwd": self.pwd,
                "icode_sign": self._serial_md5(self.user), "signup": 0}
        ts = int(time.time())
        h = self._headers(self._dev("a1391713a32e61d249b319def67ed961", ts))
        try:
            r = self.session.post(f"{self.api}/{self.login_ep}",
                                  json=self._enc(body), headers=h,
                                  timeout=6, verify=False)
            if r.status_code == 200 and r.text:
                j = r.json()
                d = json.loads(self._dec(j.get("sign"), j.get("iv")))
                if str(d.get("return_code")) == "99":
                    return d.get("return_token")
        except Exception as e:
            _log("[安博] token err: %s" % str(e)[:60])
        return None

    def _ensure_token(self):
        # ★ 30 分钟内复用
        if self._token and (time.time() - self._token_time) < 1800:
            return self._token
        self._token = self._fetch_token()
        self._token_time = time.time()
        if not self._token:
            _log("[安博] ⚠ 拿不到 token")
        return self._token

    def _get_uri(self, token, cid):
        if self.session is None:
            return None
        ts = int(time.time())
        live = {"icode_name": self.user, "icode_passwd": self.pwd,
                "icode_sign": self._serial_md5(self.user), "token": token}
        h = self._headers(self._dev(token, ts))
        try:
            self.session.post(f"{self.api}/{self.ch_ep}",
                              json=self._enc(live), headers=h,
                              timeout=4, verify=False)
            uri_body = {"icode_name": self.user, "icode_passwd": self.pwd,
                        "icode_sign": self._serial_md5(self.user),
                        "token": token, "id": str(cid)}
            for _ in range(2):
                r = self.session.post(f"{self.api}/{self.uri_ep}",
                                      json=self._enc(uri_body), headers=h,
                                      timeout=5, verify=False)
                if r.status_code == 200 and r.text:
                    j = r.json()
                    d = json.loads(self._dec(j.get("sign"), j.get("iv")))
                    if str(d.get("return_code")) == "99":
                        return {"uri": d.get("return_uri"),
                                "fftoken": d.get("return_fftoken") or "",
                                "playtoken": d.get("return_playtoken") or ""}
                time.sleep(0.2)
        except Exception as e:
            _log("[安博] uri err: %s" % str(e)[:60])
        return None

    # ---------- 加载 ----------
    def _load_json(self, loc, fname):
        if str(loc).startswith(("http://", "https://")):
            if self.session is None:
                return None
            try:
                r = self.session.get(loc.rstrip("/") + "/" + fname,
                                     timeout=8, verify=False,
                                     headers={"User-Agent": "okhttp/3.12.0"})
                if r.status_code == 200 and r.text:
                    return r.json()
            except Exception:
                return None
        else:
            p = os.path.join(loc, fname)
            try:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                return None
        return None

    @staticmethod
    def _clean_name(n):
        n = str(n).strip()
        n = re.sub(r'(高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清)$',
                   '', n, flags=re.IGNORECASE)
        return n.replace(' ', '').strip()

    def _match_logo(self, n):
        c = self._clean_name(n)
        if not c:
            return self.default_logo
        alias = {"凤凰中文": "凤凰卫视中文台", "凤凰资讯": "凤凰卫视资讯台",
                 "凤凰香港": "凤凰卫视香港台", "凤凰电影": "凤凰卫视电影台",
                 "无线新闻": "无线新闻台", "无线财经": "无线财经资讯台",
                 "TVB": "无线新闻台", "湖南金鹰": "金鹰卡通"}
        c = alias.get(c, c)
        return "https://epg.112114.eu.org/logo/%s.png" % urllib.parse.quote(c)

    def _load(self):
        if self.channels:
            return self.channels
        arr = []
        cats_order = []
        for d in [self.base_dir, "/sdcard/tvbox/py/", "/sdcard/Download/",
                  "https://raw.githubusercontent.com/kan1314go/9988/refs/heads/main/py/"]:
            for fn in ("channels.json", "extra.json"):
                data = self._load_json(d, fn)
                if not data:
                    continue
                _log("[安博] 加载 %s/%s" % (d, fn))
                for cat in data.get("return_live", []):
                    g = str(cat.get("name", "未分類")).strip()
                    if g not in cats_order:
                        cats_order.append(g)
                    for ch in cat.get("channel", []):
                        cid = str(ch.get("id", ""))
                        ct = str(ch.get("title", "")).strip()
                        if not cid or not ct:
                            continue
                        cl = str(ch.get("logo", "")).strip() or self._match_logo(ct)
                        arr.append({"id": cid, "name": ct, "category": g,
                                    "logo": cl})
        if not arr:
            arr.append({"id": "1", "name": "未偵測到 channels.json",
                        "category": "系統提示", "logo": self.default_logo})
            cats_order.append("系統提示")
        self.channels = arr
        self.categories = cats_order
        return arr

    # ---------- 接口 ----------
    def categories(self):
        self._load()
        return list(self.categories)

    def categoryContent(self, tid, pg, filter, extend):
        arr = self._load()
        vids = []
        for ch in arr:
            if tid != "all" and ch["category"] != tid:
                continue
            vids.append({
                "vod_id": ch["id"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"] or self.default_logo,
                "vod_remarks": ch["category"],
            })
        return {"list": vids, "page": 1, "pagecount": 1,
                "limit": len(vids), "total": len(vids)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        cid = str(ids[0])
        arr = self._load()
        name, cat, logo = "UBLive", "直播", self.default_logo
        for ch in arr:
            if ch["id"] == cid:
                name, cat, logo = ch["name"], ch["category"], ch["logo"]
                break

        token = self._ensure_token()
        if not token:
            return {"list": [{
                "vod_id": cid, "vod_name": name, "vod_pic": logo,
                "vod_remarks": cat,
                "vod_play_from": self.PLAY_FROM,
                "vod_play_url": "播放$__ERROR__:登录失败",
            }]}
        info = self._get_uri(token, cid)
        if not info or not info.get("uri"):
            return {"list": [{
                "vod_id": cid, "vod_name": name, "vod_pic": logo,
                "vod_remarks": cat,
                "vod_play_from": self.PLAY_FROM,
                "vod_play_url": "播放$__ERROR__:拿不到播放地址",
            }]}
        # 关键：vod_play_url 里的 pid 编码成 "id|fftoken|playtoken"
        # 但需要保证 pid 里不含 "$" 或 "#"
        u = info["uri"]
        ff = info.get("fftoken", "") or ""
        pt = info.get("playtoken", "") or ""
        return {"list": [{
            "vod_id": cid, "vod_name": name, "vod_pic": logo,
            "vod_remarks": cat,
            "vod_play_from": self.PLAY_FROM,
            "vod_play_url": "%s$%s|%s|%s" % (name, u, ff, pt),
        }]}

    def playerContent(self, flag, pid, vipFlags):
        s = str(pid or "")
        if "$" in s:
            s = s.split("$", 1)[1]
        if s.startswith("__ERROR__:"):
            _log("[安博] 播放失败: %s" % s[10:])
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        parts = s.split("|")
        url = parts[0] if parts else ""
        headers = {"User-Agent": "okhttp/3.12.0"}
        if len(parts) > 1 and parts[1]:
            headers["fftoken"] = parts[1]
        if len(parts) > 2 and parts[2]:
            headers["playtoken"] = parts[2]
        return {"parse": 0, "jx": 0, "url": url, "header": headers}

    def search(self, key):
        key = str(key or "").lower().strip()
        if not key:
            return []
        out = []
        for ch in self._load():
            if key in ch["name"].lower():
                out.append({
                    "vod_id": ch["id"], "vod_name": ch["name"],
                    "vod_pic": ch["logo"] or self.default_logo,
                    "vod_remarks": ch["category"],
                })
        return out


# ============================================================
# 源 3：全球（DreamTV）
# ============================================================
class QuanqiuSource(object):
    PREFIX = "qq"
    NAME = "全球"
    PLAY_FROM = "DreamTV"

    def __init__(self):
        self.devid = '00:ea:20:21:53:5900:00:00:00:00:00'
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
        self.session = _requests.Session() if HAS_REQ else None

    def init(self, extend=""):
        pass

    # ---------- 签名 ----------
    def _sign(self, ts, m):
        return hashlib.md5((self.from_id + self.salt + str(ts) + m
                            + self.devid).encode("utf-8")).hexdigest()

    def _headers(self, body):
        # ★ 不再手动填 Content-Length
        return {"Content-Type": "application/json; charset=utf-8",
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/3.12.5",
                "Accept-Encoding": "identity"}

    def _post(self, payload):
        if self.session is None:
            raise Exception("no requests")
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        last_err = "Dream API failed"
        for url in list(self.api_urls):
            try:
                r = self.session.post(url, data=body.encode("utf-8"),
                                      headers=self._headers(body),
                                      timeout=15, verify=False)
                if r.status_code != 200:
                    last_err = "HTTP %s" % r.status_code
                    continue
                j = r.json()
                if isinstance(j, dict) and j.get("data") is not None:
                    # 成功域名提到最前
                    try:
                        self.api_urls.remove(url)
                        self.api_urls.insert(0, url)
                    except Exception:
                        pass
                    return j["data"]
                last_err = "no data"
            except Exception as e:
                last_err = str(e)[:80]
        raise Exception(last_err)

    def _login1(self):
        ts = int(time.time())
        m = "1-1-2"
        p = {"method": m,
             "params": {"device_id": self.devid, "hardware": self.hardware,
                        "sn": self.devid, "version": self.version},
             "system": {"from": self.from_id, "sign": self._sign(ts, m),
                        "time": ts, "version": "V1"}}
        d = self._post(p)
        if not isinstance(d, dict):
            raise Exception("1-1-2 bad data")
        c = d.get("client") or {}
        s = d.get("server") or {}
        tk = c.get("token")
        if not tk:
            raise Exception("IP 或 devid 被封")
        self.token = str(tk)
        self.client_id = str(c.get("client_id") or "")
        self.password = str(c.get("password") or "")
        self.server_time = int(c.get("time") or ts)
        hosts = s.get("hosts") or []
        if hosts:
            f = hosts[0]
            self.server = (str(f.get("url") or "") if isinstance(f, dict)
                           else str(f))
        if not self.server:
            raise Exception("no server")

    def _login2(self):
        m = "1-1-3"
        ts = int(self.server_time or time.time())
        p = {"method": m,
             "params": {"client_id": self.client_id, "device_id": self.devid,
                        "hardware": self.hardware, "password": self.password,
                        "sn": self.devid, "token": self.token,
                        "version": self.version},
             "system": {"from": self.from_id, "sign": self._sign(ts, m),
                        "time": ts, "version": "V1"}}
        d = self._post(p)
        if isinstance(d, dict):
            c = d.get("client") or {}
            if c.get("token"):
                self.token = str(c["token"])

    def _fetch_ch(self):
        m = "1-1-4"
        ts = int(self.server_time or time.time())
        p = {"method": m,
             "params": {"client_id": self.client_id, "device_id": self.devid,
                        "hardware": self.hardware, "password": self.password,
                        "sn": self.devid, "token": self.token,
                        "version": self.version},
             "system": {"from": self.from_id, "sign": self._sign(ts, m),
                        "time": ts, "version": "V1"}}
        d = self._post(p)
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("channels", "list", "items", "data"):
                if isinstance(d.get(k), list):
                    return d[k]
        return []

    def _get_channels(self):
        if self.channels_cache and (time.time() - self.cache_time) < 600:
            return self.channels_cache
        self._login1()
        self._login2()
        chs = self._fetch_ch()
        self.channels_cache = chs
        self.cache_time = time.time()
        self.auth_time = time.time()
        return chs

    # ---------- 字段 ----------
    @staticmethod
    def _n(it):
        return str(it.get("name") or it.get("title")
                   or it.get("channel_name") or "DreamTV") \
            if isinstance(it, dict) else "DreamTV"

    @staticmethod
    def _c(it):
        return str(it.get("category") or it.get("group")
                   or it.get("group_name") or "DreamTV") \
            if isinstance(it, dict) else "DreamTV"

    @staticmethod
    def _u(it):
        return str(it.get("url") or it.get("play_url")
                   or it.get("stream_url") or "") \
            if isinstance(it, dict) else ""

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
    _SORTED_KEYS = None
    LOGO_CDN = "https://epg.112114.eu.org/logo/{}.png"

    def _norm(self, n):
        if not n:
            return ""
        n = str(n).strip()
        for _ in range(2):
            n = re.sub(r'(?:[-\s_·]*)(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清|高码|HD1080)$',
                       '', n, flags=re.IGNORECASE)
        return re.sub(r'[\s\-_\.\(\)\[\]（）【】·]', '', n).upper()

    def _match_kw(self, n):
        if QuanqiuSource._SORTED_KEYS is None:
            QuanqiuSource._SORTED_KEYS = sorted(
                self._KEYWORD_LOGOS.keys(), key=len, reverse=True)
        norm = self._norm(n)
        if not norm:
            return ""
        for k in QuanqiuSource._SORTED_KEYS:
            if k in norm:
                return self._KEYWORD_LOGOS[k]
        return ""

    def _logo(self, it):
        name = self._n(it)
        raw = str(it.get("logo") or it.get("pic")
                  or it.get("icon") or "").strip() \
            if isinstance(it, dict) else ""
        if raw and raw.lower() not in ("null", "none", "0"):
            if raw.startswith("http"):
                return raw
            if self.server:
                return self.server.rstrip("/") + "/" + raw.lstrip("/")
            return raw
        mk = self._match_kw(name)
        if mk:
            return self.LOGO_CDN.format(urllib.parse.quote(mk))
        return ""

    def _join(self, server, path):
        if not server:
            return ""
        server = str(server).strip()
        path = str(path).strip()
        if path.startswith(("http://", "https://")):
            return path
        if path.startswith("/"):
            return server.rstrip("/") + path
        return server.rstrip("/") + "/" + path.lstrip("/")

    def _play_url(self, it):
        raw = self._u(it)
        if not raw:
            return ""
        if raw.startswith(("http://", "https://")):
            return raw
        return self._join(self.server, raw)

    def _to_video(self, it):
        if not self._u(it):
            return None
        u = self._play_url(it)
        if not u:
            return None
        return {"vod_id": u, "vod_name": self._n(it),
                "vod_pic": self._logo(it), "vod_remarks": self._c(it)}

    # ---------- 接口 ----------
    def categories(self):
        try:
            self._get_channels()
        except Exception:
            pass
        seen = []
        for it in self.channels_cache:
            c = self._c(it)
            if c and c not in seen:
                seen.append(c)
        return seen

    def categoryContent(self, tid, pg, filter, extend):
        try:
            chs = self._get_channels()
        except Exception as e:
            _log("[全球] 加载失败: %s" % str(e)[:80])
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 0, "total": 0}
        vids = []
        for it in chs:
            if tid != "all" and self._c(it) != tid:
                continue
            v = self._to_video(it)
            if v:
                vids.append(v)
        return {"list": vids, "page": 1, "pagecount": 1,
                "limit": len(vids), "total": len(vids)}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        pid = str(ids[0])
        name, logo = "DreamTV", ""
        try:
            chs = self._get_channels()
        except Exception:
            chs = self.channels_cache
        for it in chs:
            if self._play_url(it) == pid:
                name, logo = self._n(it), self._logo(it)
                break
        return {"list": [{
            "vod_id": pid, "vod_name": name, "vod_pic": logo,
            "vod_remarks": "直播",
            "vod_play_from": self.PLAY_FROM,
            "vod_play_url": "播放$%s" % pid,
        }]}

    def playerContent(self, flag, pid, vipFlags):
        s = str(pid or "")
        if "$" in s:
            s = s.split("$", 1)[1]
        header = {"User-Agent": "Lavf/58.12.100", "Accept": "*/*",
                  "Connection": "keep-alive", "Icy-MetaData": "1",
                  "userid": str(self.client_id),
                  "usertoken": str(self.token),
                  "Cache-Control": "no-cache", "Pragma": "no-cache"}
        return {"parse": 0, "playUrl": "", "url": s, "header": header}

    def search(self, key):
        key = str(key or "").lower().strip()
        if not key:
            return []
        try:
            chs = self._get_channels()
        except Exception:
            return []
        out = []
        for it in chs:
            if key in self._n(it).lower():
                v = self._to_video(it)
                if v:
                    out.append(v)
        return out


# ============================================================
# 主聚合 Spider
# ============================================================
class Spider(_TVBoxBase):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._sources = {
            YushanSource.PREFIX: YushanSource(),
            AnboSource.PREFIX: AnboSource(),
            QuanqiuSource.PREFIX: QuanqiuSource(),
        }

    def getName(self):
        return "聚合直播"

    def init(self, extend=""):
        for s in self._sources.values():
            try:
                s.init(extend)
            except Exception as e:
                _log("init %s 失败: %s" % (s.NAME, e))

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------- 首页：3 个板块 + 各自的 filter 分类条 ----------
    def homeContent(self, filter=None):
        classes = [
            {"type_id": YushanSource.PREFIX, "type_name": "📺 " + YushanSource.NAME},
            {"type_id": AnboSource.PREFIX, "type_name": "📺 " + AnboSource.NAME},
            {"type_id": QuanqiuSource.PREFIX, "type_name": "📺 " + QuanqiuSource.NAME},
        ]
        filters = {}
        for prefix, src in self._sources.items():
            try:
                cats = src.categories()
            except Exception as e:
                _log("[%s] categories 失败: %s" % (src.NAME, e))
                cats = []
            vals = [{"n": "全部", "v": "all"}]
            for c in cats:
                if c and c != "all":
                    vals.append({"n": c, "v": c})
            filters[prefix] = [{"key": "cat", "name": "分类", "value": vals}]
        return {"class": classes, "filters": filters, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    # ---------- 分类列表：根据 extend.cat 筛选 ----------
    def categoryContent(self, tid, pg, filter, extend):
        prefix = str(tid).strip()
        src = self._sources.get(prefix)
        if src is None:
            # 兼容带 ":" 的旧格式
            p, real = _split_full_id(tid)
            src = self._sources.get(p)
            if src is None:
                return {"list": [], "page": 1, "pagecount": 1,
                        "limit": 0, "total": 0}
            target_cat = real or "all"
        else:
            target_cat = "all"

        if isinstance(extend, dict):
            v = extend.get("cat")
            if v:
                target_cat = v

        try:
            res = src.categoryContent(target_cat, pg, filter, extend)
        except Exception as e:
            _log("[%s] categoryContent 失败: %s" % (src.NAME, e))
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 0, "total": 0}

        # 给每个 vod_id 加前缀
        for v in res.get("list", []):
            if v.get("vod_id"):
                v["vod_id"] = "%s%s%s" % (prefix, SEP, v["vod_id"])
        return res

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        full_id = str(ids[0])
        prefix, real_id = _split_full_id(full_id)
        src = self._sources.get(prefix)
        if src is None:
            return {"list": [{"vod_id": full_id, "vod_name": "未知源",
                              "vod_content": "prefix=%s" % prefix}]}
        try:
            res = src.detailContent([real_id])
        except Exception as e:
            _log("[%s] detailContent 失败: %s" % (src.NAME, e))
            return {"list": [{"vod_id": full_id, "vod_name": "详情失败",
                              "vod_content": str(e)}]}

        for v in res.get("list", []):
            v["vod_id"] = full_id
            purl = v.get("vod_play_url", "")
            if purl:
                v["vod_play_url"] = self._prefix_play_url(purl, prefix)
            vf = v.get("vod_play_from") or "直播"
            if not vf.startswith("[%s]" % src.NAME):
                v["vod_play_from"] = "[%s] %s" % (src.NAME, vf)
        return res

    @staticmethod
    def _prefix_play_url(purl, prefix):
        """给 vod_play_url 里每个 '名称$pid' 的 pid 加前缀 'prefix:'"""
        out = []
        for p in str(purl).split("#"):
            if "$" in p:
                name, pid = p.split("$", 1)
                out.append("%s$%s%s%s" % (name, prefix, SEP, pid))
            else:
                out.append(p)
        return "#".join(out)

    # ---------- 播放 ----------
    def playerContent(self, flag, pid, vipFlags):
        full_pid = str(pid or "")
        prefix, real_pid = _split_full_id(full_pid)
        src = self._sources.get(prefix)
        if src is None:
            _log("未知源前缀: %s (完整 pid=%s)" % (prefix, full_pid[:80]))
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        try:
            return src.playerContent(flag, real_pid, vipFlags)
        except Exception as e:
            _log("[%s] playerContent 失败: %s" % (src.NAME, e))
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

    # ---------- 搜索：三源聚合 ----------
    def searchContent(self, key, quick, pg="1"):
        key = str(key or "").strip()
        if not key:
            return {"list": []}
        all_videos = []
        for prefix, src in self._sources.items():
            try:
                arr = src.search(key)
            except Exception as e:
                _log("[%s] search 失败: %s" % (src.NAME, e))
                continue
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
        for s in self._sources.values():
            sess = getattr(s, "session", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
        return "正在Destroy"


if __name__ == '__main__':
    pass