#!/usr/bin/env python3
"""xizhi.py — 官方图标套件统一检索/下载 CLI（书圣王羲之：线条即图标）

子命令:
  sets                          列出支持的套件与选型摘要
  search --set S --query Q     在套件内按名称(+别名/tag)搜索图标（harmonyos 离线）
  fetch --set S --name N [...] 下载图标资产到 ./icons/（或 --out 指定目录）
  describe --set S             打印套件详细通道信息（URL 模板/许可/变体）

设计约束: 纯 Python 标准库（urllib），跨平台，无 pip 依赖。
所有 URL 模式均于 2026-09-14 实测 200。失败显性退出（exit 1），绝不静默。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; xizhi-skill/0.1)"}
CACHE_DIR = Path(os.environ.get("XIZHI_CACHE", Path.home() / ".cache" / "xizhi"))
CACHE_TTL = 7 * 24 * 3600  # 名称索引缓存 7 天

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
        "fetch": "https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{name}.svg",
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
                  "symbols/web/{name}/materialsymbols{style}/{name}{fill}_{size}px.svg"),
        "defaults": {"style": "rounded", "size": "24", "fill": ""},
        "choices": {"style": ["outlined", "rounded", "sharp"], "size": ["20", "24", "40", "48"],
                    "fill": ["", "_fill1"]},
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
        "fetch": "https://cdn.jsdelivr.net/npm/@fluentui/svg-icons@latest/icons/{name}.svg",
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
        "fetch": "https://cdn.jsdelivr.net/npm/@tabler/icons@latest/icons/{style}/{name}.svg",
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
        "fetch": "https://cdn.jsdelivr.net/npm/@phosphor-icons/core@latest/assets/{weight}/{name}.svg",
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
        "fetch": "https://cdn.jsdelivr.net/npm/feather-icons@latest/dist/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "feather-icons", "sub": "/dist/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "bootstrap": {
        "label": "Bootstrap Icons",
        "desc": "2000+ 图标，Bootstrap 官方，含字体/SVG 两种用法",
        "license": "MIT",
        "when": "Bootstrap 生态",
        "fetch": "https://cdn.jsdelivr.net/npm/bootstrap-icons@latest/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "bootstrap-icons", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "antd": {
        "label": "Ant Design Icons",
        "desc": "AntD 官方；outlined/filled/twotone 三风格",
        "license": "MIT",
        "when": "AntD / 蚂蚁系中后台生态",
        "fetch": ("https://cdn.jsdelivr.net/npm/@ant-design/icons-svg@latest/"
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
        "fetch": "https://cdn.jsdelivr.net/npm/morphicons@latest/dist/{name}",
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
        "fetch": "https://cdn.jsdelivr.net/npm/remixicon@latest/icons/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "remixicon", "sub": "/icons/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "mdi": {
        "label": "Material Design Icons (Pictogrammers)",
        "desc": "社区维护的单体最大集之一（7400+），非 Google 官方 Material Symbols",
        "license": "Pictogrammers Free License（Apache-2.0 基底，GPL 友好，可商用）",
        "when": "Material Symbols 覆盖不到的细分图标；量优先",
        "fetch": "https://cdn.jsdelivr.net/npm/@mdi/svg@latest/svg/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "@mdi/svg", "sub": "/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "ionicons": {
        "label": "Ionicons (Ionic)",
        "desc": "Ionic 官方，1300+，outline/filled/sharp 三风格，移动端气质",
        "license": "MIT",
        "when": "Ionic/Capacitor 生态；移动 App 风格 Web 页",
        "fetch": "https://cdn.jsdelivr.net/npm/ionicons@latest/dist/svg/{name}.svg",
        "ext": ".svg",
        "index": {"kind": "url-flat-npm", "pkg": "ionicons", "sub": "/dist/svg/", "suffix": ".svg"},
        "ref": "references/official-web.md",
    },
    "octicons": {
        "label": "Octicons (GitHub)",
        "desc": "GitHub 官方图标，名称自带尺寸后缀（如 home-16/home-24）",
        "license": "MIT",
        "when": "GitHub 风格界面/文档、开发者工具",
        "fetch": "https://cdn.jsdelivr.net/npm/@primer/octicons@latest/build/svg/{name}.svg",
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
        "fetch": "https://cdn.jsdelivr.net/npm/eva-icons@latest/{style}/svg/{name}.svg",
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
        "fetch": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{name}.svg",
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
        "desc": "鸿蒙官方图标：代码内 $r 引用零下载；SVG/字体可脚本化下载（官方 name_map + HMSymbol.ttf，4837 字形实测）",
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
def http_get(url: str, binary: bool = False, timeout: int = 30):
    """GET 并校验 HTTP 200 与内容类型，失败抛 SystemExit（规则12：禁止静默）。"""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise SystemExit(f"[error] HTTP {resp.status}: {url}")
            data = resp.read()
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


def npm_latest(pkg: str) -> str:
    url = f"https://registry.npmjs.org/{urllib.request.quote(pkg, safe='@/')}"
    return json.loads(http_get(url))["dist-tags"]["latest"]


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


# ------------------------------- 名称索引构建 -------------------------------
def harmonyos_official(refresh: bool) -> list[dict] | None:
    """官方 name_map_new.json（name/name_cn/unicode/support_version/category）。
    缓存 7 天；下载失败且有旧缓存时用旧缓存；全无网络时返回 None（调用方降级离线清单）。"""
    cp = CACHE_DIR / "harmonyos-name-map.json"
    if refresh or not cp.exists() or time.time() - cp.stat().st_mtime > CACHE_TTL:
        url = SETS["harmonyos"]["channels"]["name_map"]
        try:
            data = json.loads(http_get(url))
            cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except SystemExit:
            if not cp.exists():
                print("[warn] 官方目录下载失败且无缓存，降级离线 SDK 清单（无中文名/unicode）")
                return None
    return json.loads(cp.read_text(encoding="utf-8"))["data"]


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
        tags = json.loads(http_get(idx["url"]))

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
            data = json.loads(http_get(base, timeout=60))
            names = [f["name"][len(sub):][:-len(suffix)]
                     for f in data.get("files", [])
                     if f["name"].startswith(sub) and f["name"].endswith(suffix)]
            if not names:
                raise SystemExit(f"[error] {pkg} flat 列表为空，通道可能变化")
            return names
        key = f"{set_id}-{idx['sub'].strip('/').replace('/', '_')}"
        return cached_names(key, build) if not refresh else build()
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
        _search_harmonyos(args, names)
        return 0
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
        print(f"[miss] '{args.query}' 在 {args.set} 中无匹配。")
        print("       换近义词重试；或用 --refresh 刷新索引；或换套件（sets 看全表）。")
        return 1
    print(f"[hit] {args.set}: {len(hits)} 个匹配（上限 {args.limit}）:")
    for name, note in hits:
        print(f"  {name}  {note}")
    return 0


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
        print(f"[miss] '{q}' 无匹配。换近义词（中文名亦可，如 飞机/设置/铃铛）；或 --refresh 刷新官方目录。")
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
    data = json.loads(http_get(
        f"https://api.iconify.design/search?query={q}&limit={args.limit}"))
    icons = data.get("icons", [])
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
        col = json.loads(http_get(
            "https://api.iconify.design/collections?prefixes=" + ",".join(prefixes)))
        # ?prefixes= 响应按 prefix 直接作键；无参数版才嵌在 collections 字段下
        infos = col.get("collections") if isinstance(col.get("collections"), dict) else col
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
    print("注意：许可以各套件官方仓库为准（iconify 元数据可能滞后，如 ri 已于 2026-01 改新许可）。")
    return 0


def _fetch_harmonyos(args) -> int:
    """harmonyos 专用通道：官方 name_map + HMSymbol.ttf（可变字体 wght 40-900）
    → fontTools 提取字形路径生成 SVG；--name HMSymbol.ttf 则直接下载字体。"""
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.name.lower().endswith(".ttf"):
        data = http_get(SETS["harmonyos"]["channels"]["font"], binary=True, timeout=120)
        dest = out_dir / "HMSymbol.ttf"
        dest.write_bytes(data)
        print(f"[ok] {dest}  ({len(data)} bytes)  官方符号字体（可变轴 wght 40-900，4837 字形）")
        return 0
    try:
        from fontTools.ttLib import TTFont
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.boundsPen import BoundsPen
    except ImportError:
        raise SystemExit("[error] SVG 生成需要 fontTools（一次性）：pip install fonttools；"
                         "或先 fetch --set harmonyos --name HMSymbol.ttf 拿字体用 DevEco/设计工具自取")
    font_path = CACHE_DIR / "HMSymbol.ttf"
    if args.refresh or not font_path.exists():
        data = http_get(SETS["harmonyos"]["channels"]["font"], binary=True, timeout=120)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        font_path.write_bytes(data)
    font = TTFont(str(font_path))
    wght = getattr(args, "wght", None)
    if wght is not None and wght != 400:
        from fontTools.varLib.instancer import instantiateVariableFont
        instantiateVariableFont(font, {"wght": wght}, inplace=True)
    cmap = font.getBestCmap()
    # 名称 → unicode：先查官方目录（含 _fill 等全部），再退字体字形名直查
    official = harmonyos_official(False) or {}
    unicode_map = {ic["name"]: ic["unicode"] for icons in official.values() for ic in icons}
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
    dest = out_dir / f"{args.name}{suffix}{SETS['harmonyos']['ext']}"
    dest.write_text(svg, encoding="utf-8")
    note = f"官方目录: {unicode_map[args.name]}" if args.name in unicode_map else "来自字体扩展字形"
    print(f"[ok] {dest}  ({dest.stat().st_size} bytes)  {note}")
    print("     鸿蒙代码内引用无需此文件：SymbolGlyph($r('sys.symbol.<name>'))")
    return 0


def cmd_fetch(args):
    s = SETS[args.set]
    if args.set == "iconify":
        args.name = args.name.replace(":", "/")  # prefix:icon → API 路径 prefix/icon
    if args.set == "eva" and getattr(args, "style", None) == "fill":
        # eva 布局：outline/svg/home-outline.svg vs fill/svg/home.svg（无 -outline 后缀）
        args.name = re.sub(r"-outline$", "", args.name)
    if args.set == "harmonyos":
        return _fetch_harmonyos(args)
    if s["fetch"] is None:
        print(f"[info] {args.set} 无脚本化下载通道（见 describe 输出与 {s['ref']}）。")
        return 0
    url = s["fetch"]
    variant_parts = []
    for var, choices in (s.get("choices") or {}).items():
        val = getattr(args, var.replace("/", "_").replace("-", "_"), None) or s.get("defaults", {}).get(var, "")
        if val and val not in choices:
            raise SystemExit(f"[error] --{var}={val} 非法，可选: {choices}")
        if val and val != s.get("defaults", {}).get(var, ""):
            variant_parts.append(val.strip("_").replace("/", "-"))
        url = url.replace("{%s}" % var, val)
    url = re.sub(r"\{(?!name\})\w+\}", "", url)  # 未提供的可选变量清空（如 fill）
    urls = [(args.name, url.replace("{name}", args.name))]
    out_dir = Path(args.out or Path.cwd() / "icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    for label, u in urls:
        data = http_get(u, binary=True)
        fname = label.replace("/", "-")
        if variant_parts and fname == args.name:  # 变体后缀防同名覆盖
            fname += "_" + "_".join(variant_parts)
        if s["ext"] and not fname.endswith(s["ext"]):
            fname += s["ext"]
        dest = out_dir / fname
        dest.write_bytes(data)
        print(f"[ok] {dest}  ({len(data)} bytes)  ← {u}")
    if args.set == "lordicon":
        print('用法: <lord-icon src="..." trigger="hover"></lord-icon>，player 见 references/lordicon.md')
    if args.set == "morphicons":
        print("用法: ESM import；框架集成（react/vue/svelte/element/astro）见 references/morphicons.md")
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

    f = sub.add_parser("fetch", help="下载图标资产")
    f.add_argument("--set", required=True, choices=SETS)
    f.add_argument("--name", required=True, help="图标名/文件名（先 search 确认）")
    f.add_argument("--out", help="输出目录（默认 ./icons/）")
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

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
