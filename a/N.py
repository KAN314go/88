# ============================================================
# 主聚合 Spider（C 方案：三级导航）
# 首页 → [源] → 点进去看分类 → 点分类看频道 → 播放
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

    # ---------- 首页：只显示 3 个源 ----------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": YushanSource.PREFIX, "type_name": "📺 玉山"},
            {"type_id": AnboSource.PREFIX,   "type_name": "📺 安博"},
            {"type_id": QuanqiuSource.PREFIX,"type_name": "📺 全球"},
        ]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    # ---------- 分类页：显示该源的分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        key = str(tid or "").strip()
        src = self.sources.get(key)
        if src is None:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": 0, "total": 0}

        # 取分类
        cats = []
        try:
            if hasattr(src, "categories") and callable(src.categories):
                cats = src.categories() or []
            elif hasattr(src, "categories_list") and callable(src.categories_list):
                cats = src.categories_list() or []
        except Exception as e:
            cats = ["❌ 加载异常: %s" % str(e)[:40]]

        # 分类本身显示为"视频卡片"
        videos = []
        for i, c in enumerate(cats):
            if not c:
                continue
            c_str = str(c)
            videos.append({
                "vod_id": "%s@@cat@@%s" % (key, c_str),
                "vod_name": c_str,
                "vod_pic": "",
                "vod_remarks": "点击查看频道",
            })

        # 如果没有任何分类（玉山加载失败会显示错误提示）
        if not videos:
            videos.append({
                "vod_id": "%s@@cat@@__EMPTY__" % key,
                "vod_name": "❌ 无分类（源加载失败）",
                "vod_pic": "",
                "vod_remarks": "点击看详情",
            })

        return {"list": videos, "page": 1, "pagecount": 1,
                "limit": len(videos), "total": len(videos)}

    # ---------- 详情页：两种入口 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        full_id = str(ids[0])
        key, real_id = _split(full_id)
        src = self.sources.get(key)
        if src is None:
            return {"list": []}

        # 入口 A：用户点了分类 → 返回该分类下所有频道作为"剧集"
        if real_id.startswith("cat@@"):
            return self._cat_detail(src, key, full_id, real_id[5:])

        # 入口 B：用户直接点了频道（搜索结果进入） → 走正常详情
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
        """把分类下的所有频道，打包成 vod_play_url 里的"剧集" """
        # 空分类提示
        if cat == "__EMPTY__":
            return {"list": [{
                "vod_id": full_id,
                "vod_name": "源加载失败",
                "vod_content": "该源没有返回任何分类",
                "vod_play_from": src.NAME,
                "vod_play_url": "无内容$error",
            }]}

        # 拉该分类下的频道
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

        # 频道列表 → 剧集列表
        eps = []
        for v in channels:
            vid = v.get("vod_id")
            vname = v.get("vod_name") or "频道"
            if not vid:
                continue
            safe_name = str(vname).replace("$", " ").replace("#", " ")
            eps.append("%s$%s@@%s" % (safe_name, key, vid))

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
                out.append("%s$%s@@%s" % (name, key, pid))
            else:
                out.append(p)
        return "#".join(out)

    # ---------- 播放 ----------
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

    # ---------- 搜索 ----------
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
                    v["vod_id"] = "%s@@%s" % (prefix, v["vod_id"])
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