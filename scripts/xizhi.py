#!/usr/bin/env python3
"""xizhi.py — 官方图标套件统一检索/下载 CLI（书圣王羲之：线条即图标）

子命令:
  sets                          列出支持的套件与选型摘要
  search --set S --query Q     在套件内按名称(+别名/同义词组/tag)搜索（harmonyos 离线）
  fetch --set S --name N[,...] 下载图标资产（逗号批量；iconify 合并端点；--version 钉版；
                                --sprite 打 symbol 集合；--format/--color 输出适配）
  sync --framework F --set S   取图生成为 react/solid/vue/svelte 组件（幂等标记）
  suggest [--dir D]            读项目实况（package.json/pubspec）推荐套件
  doctor [--set S]             通道健康巡检（短探针，失败非零退出）
  describe --set S             打印套件详细通道信息（URL 模板/许可/变体）

设计约束: 纯 Python 标准库（urllib），跨平台，无 pip 依赖。
fetch 模板以 {version} 槽位钉版（默认 latest）；SVG 落盘前过安全黑名单并注入溯源/许可头。
失败显性退出（exit 1），绝不静默。
"""
from __future__ import annotations

import argparse
import base64
import difflib
import html as _html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

SKILL_ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; xizhi-skill/0.1.1)"}  # 版本与 skill.json 手工同步
CACHE_DIR = Path(os.environ.get("XIZHI_CACHE", Path.home() / ".cache" / "xizhi"))
CACHE_TTL = 7 * 24 * 3600  # 名称索引缓存 7 天
BATCH_LIMIT = 200  # 单次批量上限：防失控循环，超限显性拒绝而非静默截断
MAX_DOWNLOAD = 16 * 1024 * 1024  # 单文件下载上限（鸿蒙字体 4.2MB 在内；防异常上游撑爆内存）

# ---------------------------------------------------------------------------
# 套件注册表 — 唯一事实源（确定性路由，规则5：查找表而非模型判断）
# fetch: 参数化 URL 模板, {name} 必填, 其余 {var} 由 --opt 提供
# index: 名称索引来源; kind: local-file | url-plain | url-flat-npm | url-json-lucide | none
# ---------------------------------------------------------------------------
SETS = {
    "lucide": {
        "label": "Lucide",
        "desc": "Web 默认通用套件；1500+ 线性图标，React/Vue/Svelte 全家桶",
        "license": "ISC",
        "when": "Web/跨端项目默认首选；shadcn/ui 内置",
        "fetch": "https://cdn.jsdelivr.net/npm/lucide-static@{version}/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-json-lucide", "url": "https://cdn.jsdelivr.net/npm/lucide-static@latest/tags.json"},
        "ref": "references/lucide.md",
    },
    "material-symbols": {
        "label": "Material Symbols (Google)",
        "desc": "Google 官方；可变字体（FILL/wght/GRAD/opsz 四轴），3500+ 图标",
        "license": "Apache-2.0",
        "when": "Material Design 系统 / Android / Google 生态",
        "fetch": ("https://raw.githubusercontent.com/google/material-design-icons/master/"
                  "symbols/web/{name}/materialsymbols{style}/{name}{axes}_{size}px.svg"),
        "defaults": {"style": "rounded", "size": "24", "grad": "", "fill": ""},
        "choices": {"style": ["outlined", "rounded", "sharp"], "size": ["20", "24", "40", "48"],
                    "grad": ["", "gradN25", "grad200"], "fill": ["", "fill1", "_fill1"]},
        "axes": ["grad", "fill"],  # 上游命名：轴按此序无下划线拼接（home_grad200fill1_24px，2026-10 目录实测）
        "ext": ".svg",
        "index": {"kind": "url-plain",
                  "url": ("https://raw.githubusercontent.com/google/material-design-icons/master/"
                          "variablefont/MaterialSymbolsRounded[FILL,GRAD,opsz,wght].codepoints")},
        "ref": "references/official-web.md",
    },
    "fluent": {
        "label": "Fluent UI System Icons (Microsoft)",
        "desc": "微软官方；名称自带尺寸与风格后缀（如 home_24_regular）",
        "license": "MIT",
        "when": "Fluent / Windows / 微软生态",
        "fetch": "https://cdn.jsdelivr.net/npm/@fluentui/svg-icons@{version}/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@fluentui/svg-icons", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "heroicons": {
        "label": "Heroicons (Tailwind Labs)",
        "desc": "Tailwind 官方；4 变体 24/outline、24/solid、20/solid(micro 同目录风格)、16/solid",
        "license": "MIT",
        "when": "Tailwind 生态（非 shadcn 项目）",
        "fetch": ("https://raw.githubusercontent.com/tailwindlabs/heroicons/master/"
                  "optimized/{variant}/{name}.svg"),
        "defaults": {"variant": "24/outline"},
        "choices": {"variant": ["24/outline", "24/solid", "20/solid", "16/solid"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "heroicons", "sub": "/24/outline/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "tabler": {
        "label": "Tabler Icons",
        "desc": "5000+ 线性/填充图标，stroke 可调",
        "license": "MIT",
        "when": "需要大量细分图标且保持线性风格",
        "fetch": "https://cdn.jsdelivr.net/npm/@tabler/icons@{version}/icons/{style}/{name}.svg",
        "defaults": {"style": "outline"},
        "choices": {"style": ["outline", "filled"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@tabler/icons", "sub": "/icons/outline/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "phosphor": {
        "label": "Phosphor Icons",
        "desc": "6 字重（thin/light/regular/bold/fill/duotone）9000+ 图标",
        "license": "MIT",
        "when": "需要同图标多字重/双色调配合排版系统",
        "fetch": "https://cdn.jsdelivr.net/npm/@phosphor-icons/core@{version}/assets/{weight}/{name}.svg",
        "defaults": {"weight": "regular"},
        "choices": {"weight": ["thin", "light", "regular", "bold", "fill", "duotone"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@phosphor-icons/core", "sub": "/assets/regular/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "feather": {
        "label": "Feather Icons",
        "desc": "287 个经典极简线性图标（lucide 前身），已停止新增",
        "license": "MIT",
        "when": "老项目/PWA 已在用；新项目用 lucide",
        "fetch": "https://cdn.jsdelivr.net/npm/feather-icons@{version}/dist/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "feather-icons", "sub": "/dist/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "bootstrap": {
        "label": "Bootstrap Icons",
        "desc": "2000+ 图标，Bootstrap 官方，含字体/SVG 两种用法",
        "license": "MIT",
        "when": "Bootstrap 生态",
        "fetch": "https://cdn.jsdelivr.net/npm/bootstrap-icons@{version}/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "bootstrap-icons", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "antd": {
        "label": "Ant Design Icons",
        "desc": "AntD 官方；outlined/filled/twotone 三风格",
        "license": "MIT",
        "when": "AntD / 蚂蚁系中后台生态",
        "fetch": ("https://cdn.jsdelivr.net/npm/@ant-design/icons-svg@{version}/"
                  "inline-namespaced-svg/{style}/{name}.svg"),
        "defaults": {"style": "outlined"},
        "choices": {"style": ["outlined", "filled", "twotone"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@ant-design/icons-svg",
                  "sub": "/inline-namespaced-svg/outlined/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "lordicon": {
        "label": "Lordicon",
        "desc": "Lottie 动画图标（47000+，免费+付费混排）；无公开名称索引，需官网挑选复制 CDN 链接",
        "license": "免费 CC/商业条款见官网",
        "when": "需要动效图标：loading/微交互/空状态/引导",
        "fetch": "https://cdn.lordicon.com/{name}.json",
        "ext": ".json",
        "index": {"kind": "none", "hint": "在 https://lordicon.com 搜索挑选（注意 Free 筛选），"
                                         "图标页复制 CDN 链接取 id（如 lupuorrc）"},
        "ref": "references/lordicon.md",
    },
    "morphicons": {
        "label": "Morphicons",
        "desc": "图标变形动画库（弹簧物理，零依赖），吃 stroke 型图标（lucide/tabler/heroicons）",
        "license": "MIT",
        "when": "图标状态切换动画：menu↔close、播放↔暂停、主题切换",
        "fetch": "https://cdn.jsdelivr.net/npm/morphicons@{version}/dist/{name}",
        "ext": ".js",
        "index": {"kind": "none", "hint": "npm 包 morphicons（exports: ./dom ./react ./vue ./svelte "
                                          "./element ./astro）；fetch 的 name 传 dist 下文件名如 dom.js"},
        "ref": "references/morphicons.md",
    },
    "remix": {
        "label": "Remix Icon",
        "desc": "3200+ 线性/填充（line/fill 后缀区分），国内 Web 项目常见",
        "license": "Remix Icon License v1.0（2026-01 起替代 Apache-2.0：明确允许商用、署名可选、仅禁止单独售卖图标包）",
        "when": "喜欢 Remix 风格的 Web 项目；中文名社区活跃",
        "fetch": "https://cdn.jsdelivr.net/npm/remixicon@{version}/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "remixicon", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "mdi": {
        "label": "Material Design Icons (Pictogrammers)",
        "desc": "社区维护的单体最大集之一（7400+），非 Google 官方 Material Symbols",
        "license": "Pictogrammers Free License（Apache-2.0 基底，GPL 友好，可商用）",
        "when": "Material Symbols 覆盖不到的细分图标；量优先",
        "fetch": "https://cdn.jsdelivr.net/npm/@mdi/svg@{version}/svg/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@mdi/svg", "sub": "/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "ionicons": {
        "label": "Ionicons (Ionic)",
        "desc": "Ionic 官方，1300+，outline/filled/sharp 三风格，移动端气质",
        "license": "MIT",
        "when": "Ionic/Capacitor 生态；移动 App 风格 Web 页",
        "fetch": "https://cdn.jsdelivr.net/npm/ionicons@{version}/dist/svg/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "ionicons", "sub": "/dist/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "octicons": {
        "label": "Octicons (GitHub)",
        "desc": "GitHub 官方图标，名称自带尺寸后缀（如 home-16/home-24）",
        "license": "MIT",
        "when": "GitHub 风格界面/文档、开发者工具",
        "fetch": "https://cdn.jsdelivr.net/npm/@primer/octicons@{version}/build/svg/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@primer/octicons", "sub": "/build/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "radix": {
        "label": "Radix Icons",
        "desc": "Radix UI 官方，~330 个 15px/24px 精选 UI 图标，极简克制",
        "license": "MIT",
        "when": "shadcn/Radix 生态搭配、工具型界面",
        "fetch": ("https://raw.githubusercontent.com/radix-ui/icons/main/"
                  "packages/radix-icons/icons/{name}.svg"),
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "radix", "gh": "radix-ui/icons@main",
                  "sub": "/packages/radix-icons/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "eva": {
        "label": "Eva Icons (Akveo)",
        "desc": "Akveo 官方，900+，outline/fill 双风格，圆润柔和",
        "license": "MIT",
        "when": "Nebular 生态；柔和风格界面",
        "fetch": "https://cdn.jsdelivr.net/npm/eva-icons@{version}/{style}/svg/{name}.svg",
        "defaults": {"style": "outline"},
        "choices": {"style": ["outline", "fill"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "eva-icons", "sub": "/outline/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "iconoir": {
        "label": "Iconoir",
        "desc": "1500+ 免费线性图标（regular/solid），质量与热度俱佳的新生代",
        "license": "MIT",
        "when": "lucide 之外想要差异化线性风格",
        "fetch": ("https://raw.githubusercontent.com/iconoir-icons/iconoir/main/"
                  "icons/{style}/{name}.svg"),
        "defaults": {"style": "regular"},
        "choices": {"style": ["regular", "solid"]},
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "iconoir", "gh": "iconoir-icons/iconoir@main",
                  "sub": "/icons/regular/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "simple-icons": {
        "label": "Simple Icons",
        "desc": "3200+ 品牌/技术 logo（GitHub、Python、微信…），单色 SVG",
        "license": "CC0-1.0（图标本身无版权要求；品牌 logo 使用仍受商标法约束）",
        "when": "技术栈展示、兼容列表、README 徽标",
        "fetch": "https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "simple-icons", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "iconify": {
        "label": "Iconify（聚合兜底）",
        "desc": "200,000+ 图标 / 150+ 套件聚合 API；search 跨全库、fetch 按 prefix:name 下载；响应含许可元数据",
        "license": "按来源套件（search 时自动展示，以官方仓库为准）",
        "when": "以上套件都找不到时的兜底；也覆盖 IconPark/flag/devicon/fluent-emoji 等未直接收录的套件",
        "fetch": "https://api.iconify.design/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "iconify-search"},
        "ref": "references/iconify.md",
    },
    "harmonyos": {
        "label": "HarmonyOS Symbol",
        "desc": "鸿蒙官方图标：代码内 $r 引用零下载；SVG/字体可脚本化下载（官方 name_map + HMSymbol.ttf，5705 字形实测）",
        "license": "华为系统资源（随系统分发）",
        "when": "HarmonyOS/ArkTS 项目一律首选（自动跟随主题/深色模式）",
        "fetch": None,  # 专用通道：见 cmd_fetch harmonyos 分支（字体渲染 SVG）
        "ext": ".svg",
        "channels": {
            "name_map": ("https://developer.huawei.com/allianceCmsResource/resource/"
                         "HUAWEI_Developer_VUE/template/resources/hm-symbol/name_map_new.json"),
            "font": ("https://developer.huawei.com/allianceCmsResource/resource/"
                     "HUAWEI_Developer_VUE/template/resources/hm-symbol/HMSymbol.ttf"),
        },
        "index": {"kind": "local-file", "path": "data/harmonyos-symbols.txt"},
        "ref": "references/harmonyos-symbol.md",
    },
}


# --------------------------- HTTP 基础设施（显性失败） ---------------------------
def http_get(url: str, binary: bool = False, timeout: int = 30,
             max_bytes: int = MAX_DOWNLOAD):
    """GET 并校验 HTTP 200 与内容类型，失败抛 SystemExit（规则12：禁止静默）。
    响应超 max_bytes 显性拒绝（防异常上游撑爆内存或拖挂批量）。"""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 nosemgrep -- scheme/host 均来自 https 注册表模板；file:// 重定向经实测被 stdlib 拒绝
            if resp.status != 200:
                raise SystemExit(f"[error] HTTP {resp.status}: {url}")
            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise SystemExit(f"[error] {url} 响应超过 {max_bytes} 字节上限（疑似异常上游）")
    except SystemExit:
        raise
    except Exception as e:  # URLError/timeout/SSL...
        raise SystemExit(f"[error] 请求失败 {url}: {e}")
    if not binary:
        text = data.decode("utf-8", errors="replace")
        if text.lstrip()[:15].lower().startswith("<!doctype html"):
            raise SystemExit(f"[error] {url} 返回了 HTML 而非预期内容（通道可能失效）")
        return text
    return data


def emit(msg: str):
    """诊断信息（fail/security/warn/info）走 stderr：成功产物走 stdout 可管道解析。"""
    print(msg, file=sys.stderr)


def parse_json(text: str, what: str):
    """JSON 解析统一显性失败：上游返回非法 JSON 时报解析错误而非裸 traceback。"""
    try:
        return json.loads(text)
    except ValueError as e:
        raise SystemExit(f"[error] {what} 返回非法 JSON（{e}）")


def npm_latest(pkg: str) -> str:
    url = f"https://registry.npmjs.org/{urllib.request.quote(pkg, safe='@/')}"
    data = parse_json(http_get(url), f"npm registry({pkg})")
    try:
        return data["dist-tags"]["latest"]
    except (TypeError, KeyError) as e:
        raise SystemExit(f"[error] npm registry 响应异常（{e}）：{pkg}")


def cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.txt"


def cached_names(key: str, builder) -> list[str]:
    """名称索引缓存（XIZHI_CACHE 可重定向，--refresh 跳过）。"""
    cp = cache_path(key)
    if cp.exists() and time.time() - cp.stat().st_mtime < CACHE_TTL:
        return cp.read_text(encoding="utf-8").splitlines()
    names = builder()
    cp.write_text("\n".join(names), encoding="utf-8")
    return names


# ------------------- search 助手：同义词组 / 取图 URL 构建（P4/P8） -------------------
# P4 同义词组表（icones search-alias.ts 同构）：人工策展、精确成员匹配、确定性查表。
# 纪律：只用于扩展查询词且严格套件内作用域——绝不跨套件改写名称
# （反例：Aria-Icons 全局别名表把 tabler:home 改写成 house 而 404）。
ALIAS_GROUPS = (
    ("bell", "铃", "鈴", "铃铛", "鈴鐺", "闹铃", "alarm", "notification"),
    ("home", "house", "主页", "首頁", "首页", "家"),
    ("settings", "gear", "gearshape", "cog", "设置", "設定", "偏好"),
    ("search", "magnify", "magnifier", "搜索", "搜尋", "查找"),
    ("user", "person", "account", "profile", "用户", "使用者", "账户", "帳戶"),
    ("trash", "delete", "remove", "bin", "删除", "刪除", "垃圾桶"),
    ("edit", "pencil", "write", "编辑", "編輯"),
    ("add", "plus", "create", "添加", "新增"),
    ("close", "cancel", "关闭", "關閉"),
    ("check", "tick", "done", "确认", "確認"),
    ("menu", "hamburger", "菜单", "選單", "菜單"),
    ("download", "下载", "下載"),
    ("upload", "上传", "上傳"),
    ("play", "播放"),
    ("pause", "暂停", "暫停"),
    ("star", "favorite", "收藏", "星标"),
    ("heart", "like", "喜欢", "喜歡", "爱心"),
    ("mail", "email", "message", "邮件", "郵件", "消息"),
    ("phone", "call", "电话", "電話"),
    ("camera", "photo", "相机", "相機"),
    ("calendar", "date", "日历", "日曆"),
    ("clock", "time", "时钟", "時鐘"),
    ("lock", "password", "锁", "鎖", "密码", "密碼"),
    ("eye", "view", "可见", "可見"),
    ("folder", "directory", "文件夹", "資料夾"),
    ("file", "document", "文档", "文檔"),
    ("refresh", "reload", "sync", "刷新", "重新整理"),
    ("tag", "label", "标签", "標籤"),
    ("link", "chain", "链接", "連結"),
    ("share", "分享"),
    ("filter", "筛选", "篩選"),
    ("sort", "排序"),
    ("info", "information", "信息", "資訊"),
    ("help", "question", "帮助", "幫助"),
    ("warning", "alert", "warn", "警告"),
    ("cloud", "云", "雲"),
    ("wifi", "网络", "網絡"),
    ("battery", "电池", "電池"),
    ("map", "location", "地图", "地圖", "位置"),
)


def expand_query(q: str) -> list[str]:
    """返回扩展后的查询词（原词恒在最前，组内去重保序）。匹配规则 = 组成员全等
    （大小写不敏感），无任何歧义展开。"""
    terms = [q]
    ql = q.lower()
    for group in ALIAS_GROUPS:
        if any(m.lower() == ql for m in group):
            for m in group:
                if m.lower() != ql and all(m.lower() != t.lower() for t in terms):
                    terms.append(m)
    return terms


def _build_fetch_url(set_id: str, s: dict, name: str, args, version: str) -> tuple[str, str]:
    """共享取图 URL 构建（fetch/sync/doctor 探针同源，杜绝双实现漂移）：
    {version}/{variants}/{name} 替换 + eva/phosphor 上游命名特例。
    返回 (url, 产物文件名主干)。"""
    label = name
    if set_id == "iconify":
        if ":" not in name:
            raise SystemExit(f"[error] iconify 名需 prefix:icon 格式（如 mdi:home）：{name}")
        label = name.replace(":", "/")
    if set_id == "eva" and getattr(args, "style", None) == "fill":
        # eva 布局：outline/svg/home-outline.svg vs fill/svg/home.svg（无 -outline 后缀）
        label = re.sub(r"-outline$", "", label)
    url_name = label
    if set_id == "phosphor":
        w = getattr(args, "weight", None) or s.get("defaults", {}).get("weight", "regular")
        if w != "regular":
            # 上游命名（@phosphor-icons/core 2.1.1 实测）：非 regular 字重文件带 -weight 后缀
            url_name = f"{label}-{w}"
    url = (s["fetch"] or "").replace("{version}", version)
    variant_parts = []
    for var, _choices in (s.get("choices") or {}).items():
        val = getattr(args, var.replace("/", "_").replace("-", "_"), None) or s.get("defaults", {}).get(var, "")
        if val and val != s.get("defaults", {}).get(var, ""):
            variant_parts.append(val.strip("_").replace("/", "-"))
        url = url.replace("{%s}" % var, val)
    if s.get("axes"):  # 组合轴：有轴时补名称下划线，轴间无下划线（home_grad200fill1_24px）
        axes = "".join(
            (getattr(args, v.replace("/", "_").replace("-", "_"), None)
             or s.get("defaults", {}).get(v, "") or "").strip("_")
            for v in s["axes"])
        url = url.replace("{axes}", f"_{axes}" if axes else "")
    url = re.sub(r"\{(?!name\})\w+\}", "", url).replace("{name}", url_name)
    stem = label + ("_" + "_".join(variant_parts) if variant_parts else "")
    return url, stem


def _validate_variants(s: dict, args) -> None:
    """变体合法性整批校验一次（非法值显性退出，fetch/sync 共用）。"""
    for var, choices in (s.get("choices") or {}).items():
        val = getattr(args, var.replace("/", "_").replace("-", "_"), None) or s.get("defaults", {}).get(var, "")
        if val and val not in choices:
            raise SystemExit(f"[error] --{var}={val} 非法，可选: {choices}")


def probe_url(set_id: str, name: str, overrides: dict | None = None) -> str:
    """P8：用注册表模板拼该图标的直链（miss 自取证/doctor 变体探针共用）。"""
    s = SETS[set_id]
    if not s.get("fetch"):
        return f"详见 describe --set {set_id} 与 {s['ref']}"
    args = SimpleNamespace(**{v.replace("/", "_").replace("-", "_"): None
                              for v in (s.get("choices") or {})})
    for k, v in (overrides or {}).items():
        setattr(args, k.replace("/", "_").replace("-", "_"), v)
    url, _stem = _build_fetch_url(set_id, s, name, args, "latest")
    return url


# iconify 一等收录中 prefix 与 set id 同名的子集（保守列举：宁可多警示不可漏警示）；
# 其余搜索结果的 prefix 视为第三方上游，附审阅警示。
_KNOWN_ICONIFY_PREFIXES = {"lucide", "mdi", "tabler", "simple-icons"}


# ----------------------- suggest：项目实况选型映射表（P5） -----------------------
# 与 SETS 同级的唯一事实源（键一致性由 test_xizhi_suggest 钉死）。npm/pubspec 包名
# 均为生态真实存在的包；未收录的库不在扫描范围——宁缺勿错，绝不猜包名。
LIBRARY_HINTS = {
    "lucide": ("lucide", "lucide-react", "lucide-vue-next", "lucide-svelte",
               "lucide-angular", "lucide-static"),
    "material-symbols": ("@mui/icons-material", "material-icons", "material-symbols"),
    "fluent": ("@fluentui/react-icons", "@fluentui/svg-icons"),
    "heroicons": ("@heroicons/react", "@heroicons/vue", "heroicons"),
    "antd": ("@ant-design/icons", "@ant-design/icons-svg"),
    "bootstrap": ("bootstrap-icons",),
    "phosphor": ("@phosphor-icons/react", "@phosphor-icons/web", "phosphor-icons"),
    "tabler": ("@tabler/icons", "@tabler/icons-react", "@tabler/icons-vue",
               "@tabler/icons-webfont"),
    "remix": ("remixicon", "@remixicon/react"),
    "mdi": ("@mdi/js", "@mdi/react", "@mdi/font"),
    "ionicons": ("ionicons",),
    "octicons": ("@primer/octicons", "@primer/octicons-react"),
    "radix": ("@radix-ui/react-icons",),
    "eva": ("eva-icons", "@ui-kitten/eva-icons"),
    "iconoir": ("iconoir", "iconoir-react"),
    "simple-icons": ("simple-icons",),
    "feather": ("feather-icons",),
    "lordicon": ("lord-icon-element",),
    "morphicons": ("morphicons",),
    "iconify": ("@iconify/react", "@iconify/vue", "@iconify/svelte",
                "@iconify-icon/react"),
}

# react-icons 单包多集：子路径 → xizhi 套件（只列确定映射）
REACT_ICONS_SUBPATH = {
    "lu": "lucide", "md": "material-symbols", "mdi": "mdi", "ri": "remix",
    "fi": "feather", "bs": "bootstrap", "ai": "antd", "pi": "phosphor",
    "tb": "tabler", "si": "simple-icons", "rx": "radix", "hi": "heroicons",
    "hi2": "heroicons", "go": "octicons", "eva": "eva", "io": "ionicons",
    "io5": "ionicons",
}

# Flutter pubspec.yaml 行级匹配（只列确定存在的包）
PUBSPEC_HINTS = {
    "material_symbols_icons": "material-symbols",
    "lucide_icons_flutter": "lucide",
}


def harmonyos_official(refresh: bool) -> list[dict] | None:
    """官方 name_map_new.json（name/name_cn/unicode/support_version/category）。
    缓存 7 天；下载失败且有旧缓存时用旧缓存；全无网络时返回 None（调用方降级离线清单）。"""
    cp = CACHE_DIR / "harmonyos-name-map.json"
    if refresh or not cp.exists() or time.time() - cp.stat().st_mtime > CACHE_TTL:
        url = SETS["harmonyos"]["channels"]["name_map"]
        try:
            text = http_get(url)
        except SystemExit:
            if not cp.exists():
                emit("[warn] 官方目录下载失败且无缓存，降级离线 SDK 清单（无中文名/unicode）")
                return None
        else:
            try:
                data = parse_json(text, "官方目录")
                if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
                    raise ValueError("响应缺 data 字段")
            except (SystemExit, ValueError) as e:
                # 毒化/畸形响应拒绝写入缓存（安全复审观察①：不能污染后靠 --refresh 手清）
                emit(f"[warn] 官方目录响应异常（{e}），拒绝写入缓存")
                if not cp.exists():
                    emit("[warn] 无可用缓存，降级离线 SDK 清单（无中文名/unicode）")
                    return None
            else:
                cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    parsed = parse_json(cp.read_text(encoding="utf-8"), "官方目录缓存")
    if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), dict):
        raise SystemExit("[error] 官方目录缓存格式异常（缺 data 字段），--refresh 刷新后重试")
    return parsed["data"]


def build_names(set_id: str, refresh: bool) -> list[str] | None:
    idx = SETS[set_id]["index"]
    kind = idx["kind"]
    if kind == "none":
        hint = idx.get("hint", "")
        print(f"[info] {set_id} 无名称索引。{hint}")
        return None
    if kind == "local-file":
        f = SKILL_ROOT / idx["path"]
        return [l.strip() for l in f.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
    if kind == "url-plain":  # codepoints: "home e88a" 每行
        lines = http_get(idx["url"]).splitlines()
        return [l.split()[0] for l in lines if l.strip()]
    if kind == "url-json-lucide":  # {"house": ["home", ...]} 名称+tag 双索引
        tags = parse_json(http_get(idx["url"]), "lucide tags 索引")

        def build():
            out = []
            for name, tlist in tags.items():
                out.append(name)
                for t in (tlist or []):
                    out.append(f"{name}\t{t}")
            return out
        return cached_names("lucide-names", build) if not refresh else build()
    if kind == "url-flat-npm":  # jsdelivr flat API 列出包/仓库内文件
        pkg, sub, suffix = idx["pkg"], idx["sub"], idx["suffix"]

        def build():
            if idx.get("gh"):  # GitHub 仓库直连（无 npm 包原生 SVG 时）
                base = f"https://data.jsdelivr.com/v1/package/gh/{idx['gh']}/flat"
            else:
                base = f"https://data.jsdelivr.com/v1/package/npm/{pkg}@{npm_latest(pkg)}/flat"
            data = parse_json(http_get(base, timeout=60), f"jsdelivr flat({pkg})")
            names = [f["name"][len(sub):][:-len(suffix)]
                     for f in data.get("files", [])
                     if f["name"].startswith(sub) and f["name"].endswith(suffix)]
            if not names:
                raise SystemExit(f"[error] {pkg} flat 列表为空，通道可能变化")
            return names
        key = f"{set_id}-{idx['sub'].strip('/').replace('/', '_')}"
        return cached_names(key, build) if not refresh else build()
    # kind == "iconify-search" 仅由 _search_iconify 消费，不经 build_names 路由
    raise SystemExit(f"[error] 未知索引类型 {kind}")


# --------------------------------- 子命令 ---------------------------------
def cmd_sets(_args):
    print(f"{'set':<18} {'license':<12} 定位 / 适用场景")
    print("-" * 88)
    for sid, s in SETS.items():
        print(f"{sid:<18} {s['license']:<12} {s['desc']}")
        print(f"{'':<18} {'':<12} → {s['when']}")
    print("\n详尽用法（npm 包名/变体/代码集成）见各 references/*.md；describe --set S 打印通道信息。")


def cmd_describe(args):
    s = SETS[args.set]
    print(f"== {s['label']} ({args.set}) ==")
    print(f"定位: {s['desc']}")
    print(f"场景: {s['when']}")
    print(f"许可: {s['license']}")
    print(f"下载: {s['fetch'] or '（无脚本化通道）'}")
    if s.get("defaults"):
        print(f"默认变体: {s['defaults']}  可选: {s.get('choices')}")
    if s["index"]["kind"] == "local-file":
        print(f"离线索引: {len(build_names(args.set, False))} 个名称 ({s['index']['path']})")
    print(f"详解: {s['ref']}")


def cmd_search(args):
    if args.set == "iconify":
        return _search_iconify(args)
    names = build_names(args.set, args.refresh)
    if args.set == "harmonyos":
        return _search_harmonyos(args, names)
    if names is None:
        return 0
    q = args.query.lower()
    exact, prefix, contains, tag_exact, taghits = [], [], [], [], []
    seen = set()
    for entry in names:
        if "\t" in entry:  # lucide 别名行: "house\thome"
            icon, tag = entry.split("\t", 1)
            if tag.lower() == q:
                tag_exact.append((icon, f"tag={tag}"))
                seen.add(icon)
            elif q in tag.lower() and icon not in seen:
                taghits.append((icon, f"tag≈{tag}"))
                seen.add(icon)
            continue
        name = entry
        nl = name.lower()
        if nl == q:
            exact.append((name, ""))
        elif nl.startswith(q):
            prefix.append((name, ""))
        elif q in nl:
            contains.append((name, ""))
    hits = (exact + tag_exact + prefix + contains + taghits)[: args.limit]
    if not hits:
        return _search_miss(args, names)
    print(f"[hit] {args.set}: {len(hits)} 个匹配（上限 {args.limit}）:")
    for name, note in hits:
        print(f"  {name}  {note}")
    matched = [n for n, note in hits if note.startswith("tag=") and n.lower() != q]
    if matched:  # P8：tag/别名命中非原名时，注明实际命中名（防幻觉可追溯）
        print(f"matched as: {args.query} → {matched[0]}（fetch 用实际名 {matched[0]}）")
    print(f"批量: 多图标一次落地 → fetch --set {args.set} --name <名1>,<名2>")
    return 0


def _search_miss(args, names: list[str]) -> int:
    """P4 miss 双保险：先同义词组扩展重查（严格套件内），再给近似名候选；
    P8：附注册表拼出的自取证直链。"""
    q = args.query
    terms = expand_query(q)
    if len(terms) > 1:
        alias_hits, seen = [], set()
        for t in terms[1:]:
            tl = t.lower()
            for entry in names:
                if "\t" in entry:
                    name, tag = entry.split("\t", 1)
                    hit = tag.lower() == tl
                else:
                    name, hit = entry, entry.lower() == tl
                if hit and name not in seen:
                    alias_hits.append((name, f"别名≈{t}"))
                    seen.add(name)
        if alias_hits:
            print(f"[hit] {args.set}: {len(alias_hits)} 个匹配"
                  f"（同义词组扩展 '{q}' → {'、'.join(terms[1:6])}）:")
            for name, note in alias_hits[: args.limit]:
                print(f"  {name}  {note}")
            print(f"批量: 多图标一次落地 → fetch --set {args.set} --name <名1>,<名2>")
            return 0
    plain = sorted({e.split("\t", 1)[0] for e in names})
    close = difflib.get_close_matches(q.lower(), [p.lower() for p in plain], n=3) or []
    print(f"[miss] '{q}' 在 {args.set} 中无匹配。")
    print("       换近义词重试；或用 --refresh 刷新索引；或换套件（sets 看全表）。")
    if close:
        pretty = [p for p in plain if p.lower() in close]
        print(f"       近似名: {', '.join(pretty)}（可直接 fetch）")
    print(f"       直链核验: {probe_url(args.set, q)}")
    return 1


def _search_harmonyos(args, sdk_names):
    """双源搜索：优先官方目录（含中文名/unicode，在线缓存），并集离线 SDK 清单。"""
    q = args.query
    hits, seen = [], set()
    official = harmonyos_official(args.refresh)
    if official:
        for cat, icons in official.items():
            for ic in icons:
                name, cn = ic["name"], ic.get("name_cn") or ""
                if name.lower() == q.lower():
                    hits.insert(0, (name, f"[官方] {cn} · unicode {ic['unicode']}"))
                elif q in name.lower() or (cn and q in cn):
                    hits.append((name, f"[官方] {cn} · unicode {ic['unicode']}"))
                seen.add(name)
        for n in sdk_names or []:
            if n not in seen and q in n.lower():
                hits.append((n, "[SDK]"))
        if hits:
            print(f"[hit] harmonyos: {len(hits)} 个匹配（上限 {args.limit}；[官方]=官网目录含中文名，[SDK]=仅系统资源名）:")
            for name, note in hits[: args.limit]:
                print(f"  {name}  {note}")
            return 0
        terms = expand_query(q)  # P4：繁体/别称经同义词组重查官方目录
        alias_seen = set()  # 独立于 seen（seen 是官方/SDK 去重，会挡住别名轮）
        for t in terms[1:]:
            for cat, icons in official.items():
                for ic in icons:
                    name, cn = ic["name"], ic.get("name_cn") or ""
                    if name not in alias_seen and (name.lower() == t.lower() or (cn and t in cn)):
                        hits.append((name, f"[官方] 别名≈{t} · {cn} · unicode {ic['unicode']}"))
                        alias_seen.add(name)
        if hits:
            print(f"[hit] harmonyos: {len(hits)} 个匹配（同义词组扩展 '{q}'）:")
            for name, note in hits[: args.limit]:
                print(f"  {name}  {note}")
            return 0
        sdk_close = difflib.get_close_matches(
            q.lower(), [n.lower() for n in (sdk_names or [])], n=3) or []
        print(f"[miss] '{q}' 无匹配。换近义词（中文名亦可，如 飞机/设置/铃铛）；或 --refresh 刷新官方目录。")
        if sdk_close:
            pretty = [n for n in (sdk_names or []) if n.lower() in sdk_close]
            print(f"       近似名: {', '.join(pretty)}")
        return 1
    # 纯离线降级：只有 SDK 名称清单
    hits = [(n, "[SDK]") for n in (sdk_names or []) if q in n.lower()]
    if not hits:
        print(f"[miss] '{q}' 离线清单无匹配（官方目录不可达）。联网重试可用官方目录搜中文名。")
        return 1
    print(f"[hit] harmonyos（离线 SDK 清单）: {len(hits)} 个匹配（上限 {args.limit}）:")
    for name, note in hits[: args.limit]:
        print(f"  {name}  {note}")
    return 0


def _search_iconify(args) -> int:
    """跨 150+ 套件聚合搜索；逐套件附许可元数据（iconify 快照可能滞后，以官方仓库为准）。"""
    q = urllib.parse.quote(args.query)
    data = parse_json(http_get(
        f"https://api.iconify.design/search?query={q}&limit={args.limit}"), "iconify 搜索")
    if not isinstance(data, dict):
        raise SystemExit("[error] iconify 搜索返回非对象（上游异常），稍后重试或按 references/iconify.md 直查")
    icons = data.get("icons") or []
    if not icons:
        print(f"[miss] '{args.query}' 在 iconify（200k+ 聚合库）中无匹配。换英文近义词重试。")
        return 1
    prefixes = []
    for ic in icons:
        p = ic.split(":")[0]
        if p not in prefixes:
            prefixes.append(p)
    lic = {}
    try:
        col = parse_json(http_get(
            "https://api.iconify.design/collections?prefixes=" + ",".join(prefixes)),
            "iconify collections")
        # ?prefixes= 响应按 prefix 直接作键；无参数版才嵌在 collections 字段下
        infos = col.get("collections") if isinstance(col, dict) and isinstance(col.get("collections"), dict) else {}
        for p, info in infos.items():
            if isinstance(info, dict):
                l = info.get("license") or {}
                lic[p] = l.get("title", "?")
    except SystemExit:
        pass  # 许可元数据失败不阻断搜索结果
    print(f"[hit] iconify: {len(icons)} 个匹配（上限 {args.limit}）:")
    for ic in icons:
        p = ic.split(":")[0]
        print(f"  {ic}  {lic.get(p, '?')}")
    print(f"下载: python3 {Path(__file__).name} fetch --set iconify --name <prefix:icon> --out <dir>")
    print("批量: fetch --set iconify --name <prefix:a>,<prefix:b>（合并端点一次取回）")
    print("注意：许可以各套件官方仓库为准（iconify 元数据可能滞后，如 ri 已于 2026-01 改新许可）。")
    third = [p for p in prefixes if p not in _KNOWN_ICONIFY_PREFIXES]
    if third:  # P7：非一等收录的第三方上游，附审阅警示
        head = "、".join(third[:8]) + ("…" if len(third) > 8 else "")
        print(f"⚠ {head} 不在 xizhi 一等收录——iconify 镜像的第三方上游，引入前自行审阅许可与内容")
    return 0


def _fetch_harmonyos(args, ctx=None) -> int:
    """harmonyos 专用通道：官方 name_map + HMSymbol.ttf（可变字体 wght 40-900）
    → fontTools 提取字形路径生成 SVG；--name HMSymbol.ttf 则直接下载字体。
    ctx 共享 dict（批量传入）复用字体解析与 wght 实例化（instancer 实测 ~0.9s/次）。"""
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.name.lower().endswith(".ttf"):
        data = http_get(SETS["harmonyos"]["channels"]["font"], binary=True, timeout=120)
        dest = _safe_dest(out_dir, "HMSymbol.ttf")
        dest.write_bytes(data)
        print(f"[ok] {dest}  ({len(data)} bytes)  官方符号字体（可变轴 wght 40-900，5705 字形）")
        return 0
    try:
        from fontTools.ttLib import TTFont
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.boundsPen import BoundsPen
    except ImportError:
        raise SystemExit("[error] SVG 生成需要 fontTools（一次性）：pip install fonttools；"
                         "或先 fetch --set harmonyos --name HMSymbol.ttf 拿字体用 DevEco/设计工具自取")
    ctx = ctx if ctx is not None else {}
    wght = getattr(args, "wght", None)  # 必须在 ctx 分支外赋值：批量第 2 名起分支被跳过
    if "cmap" not in ctx:
        font_path = CACHE_DIR / "HMSymbol.ttf"
        if args.refresh or not font_path.exists():
            data = http_get(SETS["harmonyos"]["channels"]["font"], binary=True, timeout=120)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            font_path.write_bytes(data)
        font = TTFont(str(font_path))
        if wght is not None and wght != 400:
            from fontTools.varLib.instancer import instantiateVariableFont
            instantiateVariableFont(font, {"wght": wght}, inplace=True)
        ctx["font"], ctx["cmap"] = font, font.getBestCmap()
        # 名称 → unicode：先查官方目录（含 _fill 等全部），再退字体字形名直查
        official = harmonyos_official(False) or {}
        ctx["unicode_map"] = {ic["name"]: ic["unicode"] for icons in official.values() for ic in icons}
    font, cmap, unicode_map = ctx["font"], ctx["cmap"], ctx["unicode_map"]
    cp_hex = unicode_map.get(args.name)
    gname = cmap.get(int(cp_hex, 16)) if cp_hex else args.name
    if gname not in set(cmap.values()):
        raise SystemExit(f"[error] '{args.name}' 不在官方目录也不在字体字形中。"
                         "先 search --set harmonyos 确认名称。")
    glyphset = font.getGlyphSet()
    glyph = glyphset[gname]
    pen = SVGPathPen(glyphset)
    glyph.draw(pen)
    d = pen.getCommands()
    if not d:
        raise SystemExit(f"[error] '{args.name}' 字形为空，无法生成 SVG")
    bp = BoundsPen(glyphset)
    glyph.draw(bp)
    x0, y0, x1, y1 = bp.bounds
    # 字体坐标 y 向上，SVG y 向下：viewBox 用负 yMax 翻转
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
           f'viewBox="{x0} {-y1} {x1 - x0} {y1 - y0}" fill="currentColor">'
           f'<path d="{d}"/></svg>\n')
    suffix = f"_{wght}" if wght else ""
    dest = _safe_dest(out_dir, f"{args.name}{suffix}{SETS['harmonyos']['ext']}")
    dest.write_text(svg, encoding="utf-8")
    note = f"官方目录: {unicode_map[args.name]}" if args.name in unicode_map else "来自字体扩展字形"
    print(f"[ok] {dest}  ({dest.stat().st_size} bytes)  {note}")
    print("     鸿蒙代码内引用无需此文件：SymbolGlyph($r('sys.symbol.<name>'))")
    return 0


# ------------------- fetch：批量 / 安全扫描 / 溯源 / 输出适配 -------------------
def split_names(raw: str) -> list[str]:
    """--name 逗号多值拆分：去空白、去重保序；空值与超上限显性拒绝（规则11）。"""
    names = []
    for part in (raw or "").split(","):
        n = part.strip()
        if n and n not in names:
            names.append(n)
    if not names:
        raise SystemExit("[error] --name 为空：至少提供一个图标名，多个用英文逗号分隔")
    if len(names) > BATCH_LIMIT:
        raise SystemExit(f"[error] 单次批量上限 {BATCH_LIMIT} 个（收到 {len(names)} 个），请分批执行")
    return names


def validate_version(args, s: dict, set_id: str) -> str:
    """P3：--version 钉版本（不传维持 latest，行为不变）；无版本槽位的通道显性拒绝。"""
    if not getattr(args, "version", None):
        return "latest"
    if "{version}" not in (s.get("fetch") or ""):
        raise SystemExit(f"[error] --set {set_id} 通道无版本概念（raw 分支或 CDN id），不支持 --version")
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", args.version):
        raise SystemExit(f"[error] --version '{args.version}' 含非法字符（仅允许字母数字与 . _ + -）")
    return args.version


def validate_color(color: str | None) -> str | None:
    if color and re.search(r"""["'<>]""", color):
        raise SystemExit(f"[error] --color '{color}' 含非法字符（会破坏 SVG 属性语法）")
    return color


def _clean_comment_text(s: str) -> str:
    """注释/标记文本消毒："--"→"__"（防 --> 提前闭合）+ 剥离控制字符与换行
    （防 react/solid 生成代码的换行注入、vue/svelte 的注释逃逸注入顶层 script）。"""
    return "".join(ch for ch in s.replace("--", "__") if ch.isprintable())


def provenance_header(set_id: str, name: str, url: str, license_: str) -> bytes:
    """P3 溯源头：来源/日期/许可跟随交付物；name/url/license 全消毒（防注释逃逸）。"""
    return (f"<!-- xizhi: {set_id}:{_clean_comment_text(name)} via "
            f"{_clean_comment_text(url)} @ {time.strftime('%Y-%m-%d')} "
            f"| license: {_clean_comment_text(license_)} -->\n").encode()


def _prepend_header(header: bytes, data: bytes) -> bytes:
    """SVG 带自有 <?xml 声明时，注释置于声明之后（否则产出非法 XML）。"""
    if data.startswith(b"<?xml"):
        end = data.find(b"?>")
        if end != -1:
            return data[:end + 2] + b"\n" + header + data[end + 2:]
    return header + data


def _safe_dest(out_dir: Path, fname: str) -> Path:
    """写盘前校验解析路径仍在 out_dir 内（防文件名携带 ..// 等逃逸）。"""
    dest = out_dir / fname
    if not dest.resolve().is_relative_to(out_dir.resolve()):
        raise SystemExit(f"[error] 非法文件名（路径逃逸）：{fname}")
    return dest


# P7：SVG 可携带脚本与外部引用，且 iconify 兜底可达任意第三方套件——落盘前做
# 归一化黑名单扫描（引号归一/去引号变体/空白与控制字符剔除/实体两轮解码），命中即
# 拒绝落盘并中止整批（安全红线，不属于可继续的批量失败）。
_SVG_EVENT_ATTR = re.compile(rb"\son[a-z]+\s*=", re.IGNORECASE)


def _svg_root_span(data: bytes):
    """线性定位首个 <svg 根标签（引号感知跳过引号内 '>'），返回 (start, end, tag)。
    交替正则方案在 <svg 重复流上实测二次复杂度（64KB 7.5s），改切片 O(n)。
    首个候选即终审：其后不存在能成功的候选（无 '>' 或引号未闭合），直接 None。"""
    i = data.find(b"<svg")
    if i == -1:
        return None
    j = i + 4
    n = len(data)
    while j < n:
        q = data[j:j + 1]
        if q == b">":
            return (i, j + 1, data[i:j + 1])
        if q in (b'"', b"'"):
            k = data.find(q, j + 1)
            if k == -1:
                return None
            j = k + 1
        else:
            j += 1
    return None
_SVG_BLOCK_PATTERNS = (
    b"<script", b"javascript:", b"vbscript:", b"data:text/html",
    b"href=http", b'href="http', b"url(http", b"href=//", b"url(//",
)


def scan_svg(data: bytes) -> list[str]:
    """返回命中的黑名单模式描述；空列表 = 通过。纯函数，确定性（规则5）。
    对抗归一化在先：空白/控制字符剔除、引号归一、去引号变体（url("http → url(http）、
    实体两轮解码——实测封堵单引号 href、url('http)、协议相对 href='//host、
    &#106;avascript:、jav\\tascript:、data:text/html 等混淆变体。"""
    low = data.lower()
    stripped = re.sub(rb"[\x00-\x20]+", b"", low).replace(b"'", b'"')
    hays = [low, stripped, stripped.replace(b'"', b"")]
    try:
        once = _html.unescape(stripped.decode("latin-1")).encode("latin-1", errors="replace")
        hays += [once, _html.unescape(once.decode("latin-1")).encode("latin-1", errors="replace")]
    except Exception:  # nosec B110 nosemgrep -- latin-1 往返不会失败；防御性兜底，安全检查绝不自身崩溃
        pass
    hits: list[str] = []
    for hay in hays:
        for p in _SVG_BLOCK_PATTERNS:
            if p in hay and p.decode() not in hits:
                hits.append(p.decode())
    if "on*=（事件属性）" not in hits and any(_SVG_EVENT_ATTR.search(h) for h in hays):
        hits.append("on*=（事件属性）")
    return hits


def _svg_security_guard(set_id: str, name: str, payload: bytes) -> bool:
    """P7 红线判定：命中打印详情返回 True（调用方显性中止整批）。"""
    hits = scan_svg(payload)
    if hits:
        emit(f"[security] {set_id}:{name} 命中黑名单 {hits}，拒绝落盘（供应链风险）。")
        emit("           改用官方一等套件，或人工审阅上游内容后再手动落地。")
        return True
    return False


def apply_color(color: str | None, data: bytes) -> tuple[bytes, bool]:
    """P9：--color 只替换 <svg> 根标签内的 currentColor，嵌套元素绝不改写
    （反例：mcp-universal-icons 全局正则剥掉嵌套 rect 尺寸、截断 stroke-width）。"""
    if not color:
        return data, False
    span = _svg_root_span(data)
    if not span or b"currentColor" not in span[2]:
        return data, False
    root = span[2].replace(b"currentColor", color.encode())
    return data[:span[0]] + root + data[span[1]:], True


def _sprite_symbol(set_id: str, name: str, data: bytes) -> bytes | None:
    """从单个 SVG 提取 <symbol>（viewBox + inner）；解析不出结构返回 None（调用方 warn）。"""
    t = re.sub(rb"^<\?xml[^>]*\?>\s*", b"", data.strip())
    span = _svg_root_span(t)
    if not span:
        return None
    root = span[2]
    vb = re.search(rb'viewBox=["\']([^"\']+)["\']', root)
    if vb:
        box = vb.group(1)
    else:
        w = re.search(rb'\bwidth="([\d.]+)"', root)
        h = re.search(rb'\bheight="([\d.]+)"', root)
        if not (w and h):
            return None
        box = b"0 0 " + w.group(1) + b" " + h.group(1)
    inner = re.sub(rb"</svg>\s*$", b"", t[span[1]:])
    sid = re.sub(r"[^A-Za-z0-9_.-]", "-", f"{set_id}:{name}")
    return b'<symbol id="%s" viewBox="%s">%s</symbol>' % (sid.encode(), box, inner)


def write_sprite(out_dir: Path, set_id: str, parts: list[bytes], skipped: list[str]):
    content = ((f'<!-- xizhi sprite: {set_id} @ {time.strftime("%Y-%m-%d")} -->\n'
                '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">').encode()
               + b"".join(parts) + b"</svg>\n")
    dest = out_dir / "sprite.svg"
    dest.write_bytes(content)
    print(f"[ok] {dest}  ({len(content)} bytes)  sprite（{len(parts)} 个 symbol）")
    for n in skipped:
        emit(f"[warn] sprite 跳过（解析不出 viewBox/结构，原文件保持不动）: {n}")


def _resolve_iconify_body(icons: dict, aliases: dict, key: str, depth: int = 0) -> dict | None:
    """iconify 别名链解包（parent 可指向 icon 或另一别名）；深度超限判为环/脏数据，显性拒绝。"""
    if depth > 5:
        raise SystemExit(f"[error] iconify 别名嵌套过深（疑似环）：{key}")
    if key in icons:
        return icons[key]
    a = (aliases or {}).get(key)
    if a:
        return _resolve_iconify_body(icons, aliases, a["parent"], depth + 1)
    return None


def iconify_json_to_svgs(prefix: str, data: dict) -> tuple[dict, list]:
    """合并端点与 @iconify-json 本地包共有的 JSON 形态 → ({icon: svg bytes}, not_found)。
    尺寸回退链：icon 级 → 集合级 → 24。"""
    icons, aliases = data.get("icons") or {}, data.get("aliases") or {}
    w_def, h_def = data.get("width") or 24, data.get("height") or 24
    out = {}
    for name in list(icons) + list(aliases):
        info = _resolve_iconify_body(icons, aliases, name)
        if info is None:
            continue
        w, h = info.get("width") or w_def, info.get("height") or h_def
        out[name] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
                     f'fill="currentColor">{info.get("body", "")}</svg>').encode()
    return out, list(data.get("not_found") or [])


def _find_iconify_json(prefix: str) -> Path | None:
    """P11：从 cwd 逐级向上找 node_modules/@iconify-json/<prefix>/icons.json。"""
    d = Path.cwd()
    for base in (d, *d.parents):
        cand = base / "node_modules" / "@iconify-json" / prefix / "icons.json"
        if cand.is_file():
            return cand
    return None


_ICONIFY_LOCAL_CACHE: dict[str, tuple] = {}  # prefix -> (mtime, {icon: svg})


def _iconify_local_svgs(prefix: str) -> dict | None:
    """本地 @iconify-json 包 → {icon: svg}；按 mtime 缓存（批量兜底免逐图标重解析）。"""
    f = _find_iconify_json(prefix)
    if f is None:
        return None
    try:
        mtime = f.stat().st_mtime
    except OSError:
        return None
    cached = _ICONIFY_LOCAL_CACHE.get(prefix)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        emit(f"[warn] 本地 {f} 解析失败（{e}），跳过本地兜底")
        return None
    if not isinstance(data, dict):
        emit(f"[warn] 本地 {f} 不是 JSON 对象，跳过本地兜底")
        return None
    svgs = iconify_json_to_svgs(prefix, data)[0]
    _ICONIFY_LOCAL_CACHE[prefix] = (mtime, svgs)
    return svgs


def _iconify_local_svg(prefix: str, icon: str) -> bytes | None:
    """在线失败时的本地兜底：从已安装的 @iconify-json 包组装 SVG（与合并端点同形态）。"""
    svgs = _iconify_local_svgs(prefix)
    return svgs.get(icon) if svgs else None


def _iconify_install_hint(prefix: str) -> str:
    return "" if _find_iconify_json(prefix) else f"；离线兜底：npm i -D @iconify-json/{prefix}"


def cmd_fetch(args) -> int:
    fmt = getattr(args, "format", None)
    if fmt is not None and fmt != "data-uri":
        raise SystemExit(f"[error] --format {fmt} 不支持（可选: data-uri）")
    names = split_names(args.name)
    s = SETS[args.set]
    version = validate_version(args, s, args.set)
    validate_color(getattr(args, "color", None))
    if args.set == "harmonyos":
        return _fetch_harmonyos_batch(args, names)
    if args.set == "iconify" and len(names) > 1:
        return _fetch_iconify_batch(args, names)
    return _fetch_standard(args, s, names, version)


def _fetch_harmonyos_batch(args, names: list[str]) -> int:
    ctx: dict = {}  # 字体解析与 wght 实例化跨名复用（性能实测 instancer ~0.9s/次）
    wrote = failed = 0
    for name in names:
        args.name = name
        try:
            _fetch_harmonyos(args, ctx)
            wrote += 1
        except SystemExit as e:
            if "fontTools" in str(e) or "pip install" in str(e):
                raise  # 配置错误中止整批，不逐图标重复报错（错误三层：配置≠批量失败）
            failed += 1
            emit(f"[fail] harmonyos:{name}: {e}")
    if failed:
        print(f"[summary] {failed} failed, {wrote} wrote")
        return 1
    return 0


def _fetch_iconify_batch(args, names: list[str]) -> int:
    """P1：按 prefix 分组走合并端点 /{prefix}.json?icons=a,b,c（含别名解包）。"""
    groups: dict[str, list] = {}
    for n in names:
        if ":" not in n:
            raise SystemExit(f"[error] iconify 批量名需 prefix:icon 格式（如 mdi:home）：{n}")
        p, icon = n.split(":", 1)
        groups.setdefault(p, []).append(icon)
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    wrote = failed = 0
    sprite_parts: list[bytes] = []
    sprite_skip: list[str] = []
    for prefix, icons in groups.items():
        url = f"https://api.iconify.design/{prefix}.json?icons=" + ",".join(icons)
        data = None
        try:
            data = parse_json(http_get(url), f"iconify 合并端点({prefix})")
            if not isinstance(data, dict):  # 未知 prefix 会返回裸文本 "404"
                emit(f"[warn] 合并端点返回非对象（{str(data)[:40]}），逐个尝试本地兜底 …")
                data = None
        except (SystemExit, ValueError) as e:
            emit(f"[warn] 合并端点失败（{e}），逐个尝试本地 @iconify-json/{prefix} …")
        svgs, missing = iconify_json_to_svgs(prefix, data) if data is not None else ({}, [])
        for icon in icons:
            full = f"{prefix}:{icon}"
            src = url
            svg = svgs.get(icon)
            if svg is None:
                svg = _iconify_local_svg(prefix, icon)
                if svg is not None:
                    src = f"local:node_modules/@iconify-json/{prefix}"  # 溯源写真实来源
                    emit(f"[info] {full} ← 本地 node_modules/@iconify-json/{prefix}")
            if svg is None:
                failed += 1
                reason = "上游返回 not_found" if icon in missing else "上游未返回"
                emit(f"[fail] {full}: {reason}{_iconify_install_hint(prefix)}")
                continue
            if _svg_security_guard("iconify", full, svg):
                print(f"[summary] 安全红线中止：{failed} failed, {wrote} wrote")
                return 1
            svg, _ = apply_color(getattr(args, "color", None), svg)
            fname = full.replace(":", "-").replace("/", "-").replace("\\", "-")
            if args.format == "data-uri":
                uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
                dest = _safe_dest(out_dir, fname + ".datauri.txt")
                dest.write_text(uri, encoding="ascii")
                print(f"[ok] {dest}  ({len(uri)} bytes)  ← {src}")
            else:
                payload = _prepend_header(
                    provenance_header("iconify", full, src, SETS["iconify"]["license"]), svg)
                dest = _safe_dest(out_dir, fname + ".svg")
                dest.write_bytes(payload)
                print(f"[ok] {dest}  ({len(payload)} bytes)  ← {src}")
            wrote += 1
            if args.sprite:
                sym = _sprite_symbol("iconify", full, svg)
                (sprite_parts.append(sym) if sym else sprite_skip.append(full))
    if args.sprite:
        write_sprite(out_dir, "iconify", sprite_parts, sprite_skip)
    if failed or len(names) > 1:
        print(f"[summary] {failed} failed, {wrote} wrote" if failed else f"[summary] {wrote} wrote")
    return 1 if failed else 0


def _fetch_standard(args, s: dict, names: list[str], version: str) -> int:
    if s["fetch"] is None:
        emit(f"[info] {args.set} 无脚本化下载通道（见 describe 输出与 {s['ref']}）。")
        return 0
    _validate_variants(s, args)
    if args.format == "data-uri" and s["ext"] != ".svg":
        raise SystemExit(f"[error] --format data-uri 仅支持 SVG 套件（{args.set} 产物是 {s['ext']}）")
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_asset = s["ext"] == ".svg"

    # 构建任务（共享 URL 构建）→ 线程池并行下载（I/O 密集）→ 按原序串行落盘（输出确定）
    tasks = []
    for name in names:
        url, stem = _build_fetch_url(args.set, s, name, args, version)
        tasks.append((name, url, stem))

    def _dl(t):
        name, url, stem = t
        try:
            return (name, url, stem, http_get(url, binary=True), None)
        except SystemExit as e:
            return (name, url, stem, None, str(e))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_dl, tasks))

    wrote = failed = 0
    sprite_parts: list[bytes] = []
    sprite_skip: list[str] = []
    for name, url, stem, data, err in results:
        if err is not None:
            local = None
            if args.set == "iconify":
                prefix, _icon = name.split(":", 1)
                local = _iconify_local_svg(prefix, name.split(":", 1)[1])
            if local is None:
                failed += 1
                extra = _iconify_install_hint(name.split(":", 1)[0]) if args.set == "iconify" else ""
                emit(f"[fail] {name}: {err}{extra}")
                continue
            data = local
            url = f"local:node_modules/@iconify-json/{name.split(':', 1)[0]}"  # 溯源写真实来源
            emit("[info] 在线通道失败，已改用本地 node_modules/@iconify-json 取图")
        if svg_asset and _svg_security_guard(args.set, name, data):
            print(f"[summary] 安全红线中止：{failed} failed, {wrote} wrote")
            return 1
        data, replaced = apply_color(getattr(args, "color", None), data)
        if getattr(args, "color", None) and svg_asset and not replaced and b"currentColor" in data:
            emit("[warn] currentColor 不在 <svg> 根标签，未改写（绝不全局替换）；"
                 "可用 CSS color 控制或手动替换")
        fname = stem.replace("/", "-").replace("\\", "-")
        if s["ext"] and not fname.endswith(s["ext"]):
            fname += s["ext"]
        if args.format == "data-uri":
            uri = "data:image/svg+xml;base64," + base64.b64encode(data).decode("ascii")
            dest = _safe_dest(out_dir, fname[:-len(s["ext"])] + ".datauri.txt")
            dest.write_text(uri, encoding="ascii")
            print(f"[ok] {dest}  ({len(uri)} bytes)  ← {url}")
            wrote += 1
            continue
        payload = _prepend_header(
            provenance_header(args.set, name, url, s["license"]), data) if svg_asset else data
        if svg_asset and _svg_security_guard(args.set, name, payload):
            # 复扫拼接体：防溯源注释被构造的 name/url 携带注入
            print(f"[summary] 安全红线中止：{failed} failed, {wrote} wrote")
            return 1
        dest = _safe_dest(out_dir, fname)
        dest.write_bytes(payload)
        print(f"[ok] {dest}  ({len(payload)} bytes)  ← {url}")
        wrote += 1
        if args.sprite and svg_asset:
            sym = _sprite_symbol(args.set, name, data)
            (sprite_parts.append(sym) if sym else sprite_skip.append(name))
    if args.sprite and svg_asset:
        write_sprite(out_dir, args.set, sprite_parts, sprite_skip)
    if failed or len(names) > 1:
        print(f"[summary] {failed} failed, {wrote} wrote" if failed else f"[summary] {wrote} wrote")
    if failed:
        return 1
    if args.set == "lordicon":
        print('用法: <lord-icon src="..." trigger="hover"></lord-icon>，player 见 references/lordicon.md')
    if args.set == "morphicons":
        print("用法: ESM import；框架集成（react/vue/svelte/element/astro）见 references/morphicons.md")
    return 0


# --------------------- doctor：通道健康巡检（P2，失败主动发现） ---------------------
# 代表图标只取有直接证据的名称（README/SKILL 示例或 2026-10 对标实测）；
# 无验证探针名的套件显性列出、只巡检索引通道，绝不猜名制造误报。
PROBE_ICONS = {
    "lucide": "house",           # README fetch 示例
    "material-symbols": "home",  # README fetch 示例
    "fluent": "home_24_regular",  # README search 示例
    "heroicons": "home",
    "tabler": "home",            # 2026-10 对标实测 tabler:home 存在
    "phosphor": "house",
    "feather": "home",
    "bootstrap": "house-door",   # README search 示例
    "mdi": "home",               # 2026-10 对标实测 mdi:home
    "octicons": "home-16",
    "radix": "home",
    "eva": "home-outline",
    "iconoir": "home",
    "simple-icons": "github",
    "lordicon": "lupuorrc",      # README fetch 示例 id
    "morphicons": "dom.js",      # README fetch 示例
    "iconify": "lucide:house",   # 2026-10 对标实测
}


PROBE_VARIANT_ICONS = {
    # iconoir solid 变体只有品牌图标（GitHub contents 实测无 home/user 等 UI 图标）
    ("iconoir", "style=solid"): "adobe-after-effects",
}


def build_probe_list(set_filter: str | None = None) -> list[dict]:
    """从注册表确定性生成探针清单：fetch 通道（代表图标 + 非默认变体逐变量探一枚）、
    名称索引、鸿蒙双通道、iconify 搜索与 P1 批量合并端点。"""
    probes: list[dict] = []
    for sid, s in SETS.items():
        if set_filter and sid != set_filter:
            continue
        if sid in PROBE_ICONS:
            probes.append({"label": f"{sid} fetch", "url": probe_url(sid, PROBE_ICONS[sid]),
                           "timeout": 10})
            # 变体探针（架构审查教训：phosphor 非默认字重通道死链而默认探针假绿）；
            # legacy 归一 choice（如 fill 的 "_fill1"/"fill1"）URL 相同，按 URL 去重
            seen_urls = {probes[-1]["url"]}
            for var, choices in (s.get("choices") or {}).items():
                d = (s.get("defaults") or {}).get(var)
                for val in choices:
                    if val == d:
                        continue
                    key = f"{var}={val}"
                    icon = PROBE_VARIANT_ICONS.get((sid, key), PROBE_ICONS[sid])
                    url = probe_url(sid, icon, {var: val})
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    probes.append({"label": f"{sid} fetch[{key}]", "timeout": 10, "url": url})
        kind = s["index"]["kind"]
        if kind in ("url-plain", "url-json-lucide"):
            probes.append({"label": f"{sid} index", "url": s["index"]["url"], "timeout": 10})
        elif kind == "url-flat-npm":
            probes.append({"label": f"{sid} index(npm registry)",
                           "url": f"https://registry.npmjs.org/{s['index']['pkg']}", "timeout": 10})
        elif kind == "iconify-search":
            probes.append({"label": f"{sid} search api",
                           "url": "https://api.iconify.design/collections?prefixes=lucide",
                           "timeout": 10})
        for cname, curl in (s.get("channels") or {}).items():
            probes.append({"label": f"{sid} {cname}", "url": curl, "timeout": 15, "light": True})
    if not set_filter or set_filter == "iconify":
        probes.append({"label": "iconify batch", "timeout": 10,
                       "url": "https://api.iconify.design/lucide.json?icons=house,bell"})
    return probes


def unprobed_fetch_sets() -> list[str]:
    """有 fetch 模板但无验证探针名的套件——doctor 显性列出而非静默跳过。"""
    return [sid for sid, s in SETS.items()
            if sid not in PROBE_ICONS and isinstance(s.get("fetch"), str)]


def _probe_url(url: str, timeout: int = 10, light: bool = False):
    """探针：常规通道复用 http_get（200 + HTML 软 200 校验）；大文件（字体等）
    先 HEAD 零下载，HEAD 不被支持回退 Range 单字节 GET。失败抛 SystemExit。"""
    if not light:
        http_get(url, timeout=timeout)
        return
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 nosemgrep -- 探针 URL 全部来自注册表白名单

            if resp.status == 200:
                return
    except SystemExit:
        raise
    except Exception:  # nosec B110 nosemgrep -- HEAD 不被支持属正常回退路径，Range 失败仍显性退出
        pass  # HEAD 不被支持/网络层报错 → 回退 Range GET 再验一次
    try:
        req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 nosemgrep -- 同上，注册表白名单

            if resp.status in (200, 206):
                return
            raise SystemExit(f"[error] HTTP {resp.status}: {url}")
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"[error] 探针失败 {url}: {e}")


def run_probes(probes: list[dict], probe_fn, workers: int = 8) -> tuple[list[str], int]:
    """逐探针计时执行（线程池并行——诊断命令恰在网络劣化时使用，串行实测最坏
    ~6.8 分钟；结果按清单原序打印保持输出确定）。probe_fn 失败抛 SystemExit 即判 ❌。"""
    def run(p):
        t0 = time.time()
        try:
            probe_fn(p["url"], timeout=p.get("timeout", 10), light=p.get("light", False))
            return (f"✅ {p['label']}  {time.time() - t0:.2f}s  {p['url']}", False)
        except SystemExit as e:
            return (f"❌ {p['label']}  {p['url']}\n     {e}", True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run, probes))
    return [r[0] for r in results], sum(1 for r in results if r[1])


def cmd_doctor(args) -> int:
    probes = build_probe_list(getattr(args, "set", None))
    print(f"[doctor] 巡检 {len(probes)} 个通道（短超时探针，非全量下载校验）:")
    lines, down = run_probes(probes, _probe_url)
    for l in lines:
        print(l)
    if not getattr(args, "set", None):
        skip = unprobed_fetch_sets()
        print(f"[doctor] 无验证探针名、仅巡检索引通道的套件: {'、'.join(skip) or '（无）'}")
    if down:
        print(f"[doctor] {down} channel(s) down —— 通道失效，请核对上游后更新注册表")
        return 1
    print(f"[doctor] 全部 {len(probes)} 个通道正常")
    return 0


# ------------------------------- sync：组件落地（P6） -------------------------------
# JSX 属性显式映射表：只重命名已知连字符属性，值一律不动；未映射属性原样保留
# （React 对透传的连字符属性按原样渲染）。反例教训：mcp-universal-icons 全局改值
# 剥掉嵌套 rect 尺寸、截断 stroke-width（issue #1 长期 open）。
_SYNC_JSX_ATTRS = {
    "class": "className",
    "stroke-width": "strokeWidth",
    "stroke-linecap": "strokeLinecap",
    "stroke-linejoin": "strokeLinejoin",
    "fill-rule": "fillRule",
    "clip-rule": "clipRule",
    "fill-opacity": "fillOpacity",
    "stroke-opacity": "strokeOpacity",
    "stop-color": "stopColor",
    "stop-opacity": "stopOpacity",
    "text-anchor": "textAnchor",
    "xlink:href": "xlinkHref",
}
_SYNC_FRAMEWORKS = ("react", "solid", "vue", "svelte", "svg")
# 生成模板上下文会解释花括号（JSX {} / Vue {{ }} / Svelte {}）——上游文本节点里的
# 花括号即代码注入面（安全审查 HIGH 实证：scan_svg 不查花括号，模板拼接后成为
# 可执行表达式）。含花括号的 SVG 只允许 --framework svg 原样落地。
_SYNC_TEMPLATE_FRAMEWORKS = ("react", "solid", "vue", "svelte")


def _jsx_attr_rename(svg: bytes, rename_class: bool) -> bytes:
    """线性扫描（按 '=' 切分、段尾短名匹配）——属性名正则方案对无 '=' 长段实测
    二次复杂度（1MB 157s）。只重命名已知连字符属性，值一律不动，未知属性原样保留。"""
    mapping = {k: v for k, v in _SYNC_JSX_ATTRS.items() if k != "class" or rename_class}

    def tail_name(seg: str) -> str:
        i, n = len(seg), 0
        while i > 0 and n < 64 and (seg[i - 1].isalnum() or seg[i - 1] in ":-"):
            i -= 1
            n += 1
        return seg[i:] if n else ""

    parts = svg.decode("utf-8", errors="replace").split("=")
    for idx in range(len(parts) - 1):  # 最后一段后面没有 '='，不处于属性名位置
        tail = tail_name(parts[idx])
        if tail and re.fullmatch(r"[A-Za-z][A-Za-z0-9:-]*", tail) and tail in mapping:
            parts[idx] = parts[idx][: len(parts[idx]) - len(tail)] + mapping[tail]
    return "=".join(parts).encode("utf-8")


def _jsx_root_spread(svg: bytes) -> bytes:
    """根标签注入 {...props}（唯一受控的结构改动；嵌套元素不碰）。"""
    span = _svg_root_span(svg)
    if not span:
        return svg
    i = span[1] - 1
    return svg[:i] + b" {...props}" + svg[i:]


def _component_name(set_id: str, name: str) -> str:
    return "Xizhi" + re.sub(r"[^A-Za-z0-9]+", " ", f"{set_id} {name}").title().replace(" ", "")


def _render_component(framework: str, set_id: str, name: str, svg: bytes) -> tuple[str, str]:
    """纯函数：SVG → (文件名, 组件文件内容)。输出契约由 test_xizhi_sync 钉死。
    marker 内 name 经 _clean_comment_text 消毒（防 vue/svelte 注释逃逸注入顶层
    script、react/solid 换行注入任意代码行——安全复审 N1）。"""
    comp = _component_name(set_id, name)
    marker = f"generated by xizhi ({set_id}:{_clean_comment_text(name)}) — rerun sync to update"
    if framework == "react":
        body = _jsx_root_spread(_jsx_attr_rename(svg, rename_class=True)).decode("utf-8")
        return (f"{comp}.tsx",
                f"// {marker}\n"
                f'import type {{ SVGProps }} from "react";\n\n'
                f"export function {comp}(props: SVGProps<SVGSVGElement>) {{\n"
                f"  return (\n    {body}\n  );\n}}\n")
    if framework == "solid":
        body = _jsx_root_spread(_jsx_attr_rename(svg, rename_class=False)).decode("utf-8")
        return (f"{comp}.tsx",
                f"// {marker}\n\n"
                f"export function {comp}(props: {{ class?: string }}) {{\n"
                f"  return (\n    {body}\n  );\n}}\n")
    if framework == "vue":
        return (f"{comp}.vue",
                f"<!-- {marker} -->\n<template>\n  "
                + svg.decode("utf-8", errors="replace") + "\n</template>\n")
    if framework == "svelte":
        return (f"{comp}.svelte",
                f"<!-- {marker} -->\n" + svg.decode("utf-8", errors="replace") + "\n")
    return (f"{name.replace(':', '-').replace('/', '-')}.svg",
            provenance_header(set_id, name, "sync", SETS[set_id]["license"]).decode()
            + svg.decode("utf-8", errors="replace"))


def cmd_sync(args) -> int:
    if args.framework not in _SYNC_FRAMEWORKS:
        raise SystemExit(f"[error] --framework {args.framework} 不支持，可选: {list(_SYNC_FRAMEWORKS)}")
    s = SETS[args.set]
    if args.set == "harmonyos":
        raise SystemExit("[error] sync 不适用于 harmonyos：代码内 $r('sys.symbol.*') 直引零资产，"
                         "SVG 需求用 fetch（见 references/harmonyos-symbol.md）")
    if s["fetch"] is None:
        raise SystemExit(f"[error] {args.set} 无脚本化下载通道，sync 不适用（见 {s['ref']}）")
    # 配置错误（非法变体/非法版本）在循环前显性中止，与 fetch 同层
    _validate_variants(s, args)
    version = validate_version(args, s, args.set)
    names = split_names(args.name)
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 与 fetch 同款并行模板：URL 构建期校验 → 线程池下载 → 按原序串行生成落盘
    tasks = []
    for name in names:
        url, _stem = _build_fetch_url(args.set, s, name, args, version)
        tasks.append((name, url))

    def _dl(t):
        name, url = t
        try:
            return (name, url, http_get(url, binary=True), None)
        except SystemExit as e:
            return (name, url, None, str(e))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_dl, tasks))

    wrote = failed = 0
    imports: list[str] = []
    for name, url, data, err in results:
        if err is not None:
            local = None
            if args.set == "iconify":
                prefix, icon = name.split(":", 1)
                local = _iconify_local_svg(prefix, icon)
            if local is None:
                failed += 1
                emit(f"[fail] {name}: {err}")
                continue
            data = local
            url = f"local:node_modules/@iconify-json/{name.split(':', 1)[0]}"
            emit("[info] 在线通道失败，已改用本地 node_modules/@iconify-json 取图")
        if args.framework in _SYNC_TEMPLATE_FRAMEWORKS and (b"{" in data or b"}" in data):
            emit(f"[security] {args.set}:{name} 含花括号（模板上下文代码注入面），拒绝生成组件。")
            emit("           改用 --framework svg 落原始资产，或人工清洗上游内容后重试。")
            print(f"[summary] 安全红线中止：{failed} failed, {wrote} wrote")
            return 1
        if _svg_security_guard(args.set, name, data):
            print(f"[summary] 安全红线中止：{failed} failed, {wrote} wrote")
            return 1
        fname, content = _render_component(args.framework, args.set, name, data)
        dest = _safe_dest(out_dir, fname)
        dest.write_text(content, encoding="utf-8")
        wrote += 1
        comp = _component_name(args.set, name)
        if args.framework in ("react", "solid"):
            imports.append(f'import {{ {comp} }} from "./{dest.stem}"')
        elif args.framework in ("vue", "svelte"):
            imports.append(f'import {comp} from "./{dest.name}"')
        else:
            imports.append(f'// 资产引用: ./{fname}（或按构建配置 import URL）')
        print(f"[ok] {dest}  组件 {comp}")
    if failed or len(names) > 1:
        print(f"[summary] {failed} failed, {wrote} wrote" if failed else f"[summary] {wrote} wrote")
    if failed:
        return 1
    if imports:
        print("import 语句:")
        for i in imports:
            print(f"  {i}")
    return 0


# ----------------------------- suggest：读项目实况选型（P5） -----------------------------
_REACT_ICONS_IMPORT = re.compile(r"""react-icons/([a-z0-9]+)""")
_SCAN_SRC_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte", ".astro"}
_PRUNE_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "vendor",
               ".venv", "venv", "__pycache__", "coverage", ".output", ".svelte-kit",
               ".turbo", ".parcel-cache", ".cache"}


def _react_icon_counts(root: Path, max_files: int = 2000) -> dict[str, int]:
    """扫源码里 react-icons/<sub> 的 import 次数（剪枝依赖目录，封顶防失控，截断显性提示）。"""
    counts: dict[str, int] = {}
    scanned = 0
    warned = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] not in _SCAN_SRC_EXTS:
                continue
            if scanned >= max_files:
                if not warned:
                    emit(f"[warn] 源文件超过 {max_files} 个，react-icons 用量统计截断"
                         "（不影响依赖名比对）")
                    warned = True
                continue
            scanned += 1
            try:
                text = (Path(dirpath) / fn).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in _REACT_ICONS_IMPORT.finditer(text):
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def scan_project(root: Path) -> list[tuple[str, int, str]]:
    """P5：读项目实况映射回 xizhi 套件——package.json 依赖 ∩ LIBRARY_HINTS、
    react-icons 子路径 import 计数、pubspec.yaml 行匹配。确定性规则（规则5）。
    返回 [(set_id, 计数, 依据)] 按计数降序。"""
    found: dict[str, int] = {}
    evid: dict[str, str] = {}

    def add(sid: str, n: int, why: str):
        found[sid] = found.get(sid, 0) + n
        evid.setdefault(sid, why)

    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            emit(f"[warn] package.json 解析失败（{e}），跳过依赖比对")
            data = {}
        deps: dict = {}
        for key in ("dependencies", "devDependencies"):
            deps.update(data.get(key) or {})
        for sid, hints in LIBRARY_HINTS.items():
            for h in hints:
                if h in deps:
                    add(sid, 1, f"依赖 {h}")
        if "react-icons" in deps:
            for sub, n in _react_icon_counts(root).items():
                sid = REACT_ICONS_SUBPATH.get(sub)
                if sid:
                    add(sid, n, f"import react-icons/{sub}")
    pubspec = root / "pubspec.yaml"
    if pubspec.is_file():
        try:
            lines = pubspec.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line in lines:
            for hint, sid in PUBSPEC_HINTS.items():
                if hint in line:
                    add(sid, 1, f"pubspec 依赖 {hint}")
    return sorted(((sid, n, evid[sid]) for sid, n in found.items()),
                  key=lambda kv: (-kv[1], kv[0]))


def cmd_suggest(args) -> int:
    root = Path(args.dir).resolve() if getattr(args, "dir", None) else Path.cwd()
    if not root.exists():
        raise SystemExit(f"[error] 目录不存在: {root}")
    findings = scan_project(root)
    if findings:
        print(f"[suggest] 项目实况（{root}）——检测到已装图标库，选型优先对齐现有依赖:")
        for sid, count, why in findings:
            s = SETS[sid]
            print(f"  {sid:<18} 检测到 {count} 处属于 {sid}"
                  f"（{s['label']}，{s['license']}）← {why}")
            print(f"{'':<18} → search --set {sid} --query <名称> 确认后"
                  f" fetch --set {sid} --name <名>")
    else:
        print(f"[suggest] {root} 未检测到已装图标库"
              "（比对 library_hints / react-icons / pubspec）。")
    print("按场景完整选型表 ↓")
    cmd_sets(args)
    return 0


def main():
    p = argparse.ArgumentParser(prog="xizhi.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sets", help="列出支持的图标套件").set_defaults(fn=cmd_sets)

    d = sub.add_parser("describe", help="套件通道详情")
    d.add_argument("--set", required=True, choices=SETS)
    d.set_defaults(fn=cmd_describe)

    q = sub.add_parser("search", help="套件内搜索图标名称（harmonyos 离线）")
    q.add_argument("--set", required=True, choices=SETS)
    q.add_argument("--query", required=True)
    q.add_argument("--limit", type=int, default=30)
    q.add_argument("--refresh", action="store_true", help="跳过缓存重建名称索引")
    q.set_defaults(fn=cmd_search)

    f = sub.add_parser("fetch", help="下载图标资产（--name 支持逗号批量）")
    f.add_argument("--set", required=True, choices=SETS)
    f.add_argument("--name", required=True,
                   help="图标名/文件名（先 search 确认）；多个用英文逗号分隔，如 house,bell")
    f.add_argument("--out", help="输出目录（默认 ./icons/）")
    f.add_argument("--version", help="钉版本号（如 0.511.0；仅含 {version} 槽位的 npm/jsdelivr 通道）")
    f.add_argument("--format", choices=["data-uri"],
                   help="输出适配（opt-in，默认原始落盘不改写）：data-uri=写 .datauri.txt")
    f.add_argument("--color", help="覆写 <svg> 根标签的 currentColor（如 '#f00'；绝不全局替换）")
    f.add_argument("--sprite", action="store_true",
                   help="SVG 批量额外产出 sprite.svg（<symbol> 单文件）")
    f.add_argument("--wght", type=int, help="harmonyos 可变字重 40-900（默认 400）")
    f.add_argument("--refresh", action="store_true", help="强制刷新缓存（harmonyos 字体/官方目录）")
    all_vars: dict[str, list] = {}
    for s in SETS.values():
        for var, choices in (s.get("choices") or {}).items():
            merged = all_vars.setdefault(var, [])
            for c in choices:
                if c not in merged:
                    merged.append(c)
    for var, choices in all_vars.items():
        f.add_argument(f"--{var}", help=f"可选: {choices}")
    f.set_defaults(fn=cmd_fetch)

    doc = sub.add_parser("doctor", help="通道健康巡检（短超时探针，失败非零退出）")
    doc.add_argument("--set", choices=SETS, help="只巡检指定套件")
    doc.set_defaults(fn=cmd_doctor)

    sy = sub.add_parser("sync", help="取图并生成为框架组件（幂等标记，重跑覆盖更新）")
    sy.add_argument("--framework", required=True, choices=list(_SYNC_FRAMEWORKS))
    sy.add_argument("--set", required=True, choices=SETS)
    sy.add_argument("--name", required=True, help="图标名（先 search 确认；逗号批量）")
    sy.add_argument("--out", help="组件输出目录（默认 ./icons/）")
    sy.add_argument("--version", help="钉版本号（同 fetch）")
    for var, choices in all_vars.items():
        sy.add_argument(f"--{var}", help=f"可选: {choices}")
    sy.set_defaults(fn=cmd_sync)

    sug = sub.add_parser("suggest", help="读项目实况（package.json/pubspec）推荐图标套件")
    sug.add_argument("--dir", help="项目根目录（默认当前目录）")
    sug.set_defaults(fn=cmd_suggest)

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
