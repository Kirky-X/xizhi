---
name: xizhi
description: "Icon asset routing skill: pick the right official icon set and fetch icons automatically. Trigger: 图标/icon/图标库/icon library/icon set/选图标/找图标/下载图标/icon 下载/SVG 图标/lucide/lucide-react/SymbolGlyph/sys.symbol/鸿蒙图标/HarmonyOS icon/lordicon/动效图标/animated icon/morphicons/图标变形/Material Symbols/Fluent icon/Heroicons/Tabler/Phosphor/Bootstrap Icons/AntD icons/feather icons/icon CDN. Covers set selection by project context (HarmonyOS→sys.symbol, shadcn/Tailwind→lucide, Material→Material Symbols, Microsoft→Fluent), offline icon-name search (anti-hallucination), and scripted download of individual SVG/Lottie assets. Boundary: icon image generation→wudaozi; design system tokens→maliang; HarmonyOS syntax/engineering→hap-dev."
license: MIT
---

# XIZHI — 官方图标套件选型与自动下载

书圣王羲之：线条即图标。本 skill 解决两件事：**为当前项目选对图标套件** + **把图标资产自动拿下来**。

> **边界**：AI 生成图标图片 → wudaozi；设计系统/token → maliang；鸿蒙语法与工程问题 → hap-dev。本 skill 只管矢量图标资产的选型、检索、下载与集成。

## 第一步：选型（确定性查表，不要自由发挥）

| 项目/场景 | 套件（set id） | 理由 |
|---|---|---|
| **HarmonyOS / ArkTS** | `harmonyos` | 代码内 `$r()` 引用零下载自动跟随主题；SVG/官方字体亦可脚本化下载（官方目录含中文名搜名） |
| Web 无设计系统约束 | `lucide` | 覆盖最广、风格统一，事实标准 |
| shadcn/ui / 大多数 React+Tailwind 模板 | `lucide` | 已是默认依赖 |
| Google / Material Design / Android | `material-symbols` | 官方配套，可变字体四轴 |
| Microsoft / Windows / Fluent 生态 | `fluent` | 官方配套 |
| Tailwind 生态（非 shadcn） | `heroicons` 或 `lucide` | Tailwind Labs 官方 |
| AntD / 蚂蚁系中后台 | `antd` | 组件库同源 |
| Bootstrap | `bootstrap` | 组件库同源 |
| 需要多字重/双色调排版层级 | `phosphor` | 6 字重体系 |
| 图标量要求极大（5000+） | `tabler` 或 `mdi` | 数量优先（mdi 7400+） |
| 国内风格 / Remix 生态 | `remix` | 3200+ line/fill（⚠️ 2026-01 新许可：商用 ✓ 署名可选） |
| 品牌/技术栈 logo | `simple-icons` | CC0，3200+ 单色 logo |
| 开发者工具 / GitHub 风格 | `octicons` | GitHub 官方 |
| Ionic / 移动端风格 | `ionicons` | Ionic 官方 |
| 极简工具型 UI | `radix` | Radix UI 官方，克制精选 |
| 柔和圆润风格 | `eva` 或 `iconoir` | MIT，新生代线性集 |
| **图标要"动"**（loading/微交互/空状态） | `lordicon` | Lottie 动画图标 |
| **图标状态切换动画**（menu↔close） | `morphicons` + 上述 stroke 套件 | 变形动画库，不是图标集 |
| 老项目已在用 feather | `feather` | 兼容维护（停更，勿新引入） |
| **以上都没有 → 全库兜底** | `iconify` | 200k+ 聚合搜索/下载，含国旗/技术栈/emoji 等特殊品类 |

铁律：**一个项目只用一套图标**（动效层 lordicon/morphicons 除外）；用户点名要某套则用户优先。

## 第二步：查名称（写码前必做，防幻觉）

```bash
python3 {SKILL_DIR}/scripts/xizhi.py sets                          # 全部套件速览
python3 {SKILL_DIR}/scripts/xizhi.py search --set lucide --query house
python3 {SKILL_DIR}/scripts/xizhi.py search --set harmonyos --query 铃铛    # 官方目录支持中文名；离线降级 2761 名称 SDK 清单
python3 {SKILL_DIR}/scripts/xizhi.py describe --set material-symbols        # 套件通道/变体详情
```

- lucide 支持名称+tag 双匹配（搜 `home` 能命中已更名的 `house`）
- harmonyos 双源：在线官方目录（579 图标，含中文名/unicode）+ 离线 SDK 清单（2761 名称），无网可用
- 搜不到 → 换近义词（鸿蒙可试中文名）→ `--refresh` → 换套件，不要硬编名字

## 第三步：落地

### A. 鸿蒙（代码内零下载 + SVG 可下载）

```typescript
SymbolGlyph($r('sys.symbol.house')).fontSize(24).fontColor('#333')   // 业务代码首选
```

```bash
# 需要 SVG 素材（mockup/设计稿/文档）时，官方字体渲染，--wght 40-900 可变字重
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name house --out ./assets/icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name HMSymbol.ttf --out ./fonts
```

### B. Web 框架（包管理器集成）

```bash
npm install lucide-react    # 包名速查：lucide-vue-next / lucide-svelte / lucide
```

### C. 静态资产按需下载

```bash
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --out ./assets/icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set material-symbols --name home --style outlined --size 48 --fill _fill1
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lordicon --name lupuorrc      # Lottie JSON
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set morphicons --name dom.js      # 变形库 vanilla ESM
```

下载的 SVG `stroke="currentColor"`，颜色随 CSS `color`。输出目录默认 `./icons/`，变体自动进文件名防覆盖。

## 失败与降级

| 症状 | 处置 |
|---|---|
| fetch 404 | 名字错 → 回第二步 search 确认 |
| 请求失败/超时 | 网络问题不计入失败；确认代理后重试；jsdelivr 与 raw.githubusercontent 双通道在注册表内固化 |
| `harmonyos` SVG 报"需要 fontTools" | 一次性 `pip install fonttools`；或 `--name HMSymbol.ttf` 直下字体 |
| search 无结果 | 换近义词；lucide 用 tag 语义词试；harmonyos 试中文名；仍无则该套件没有此图标，换套件 |
| 脚本不可用 | 降级：按 references 里固化的 URL 模板直接 curl（规则23） |

## 按需深读（references/）

| 文件 | 何时读 |
|---|---|
| `references/lucide.md` | lucide 集成细节、命名更名史、CDN 用法 |
| `references/harmonyos-symbol.md` | 鸿蒙 SymbolGlyph/SymbolSpan 用法、找名三通道、素材下载 |
| `references/lordicon.md` | 动效图标：player、trigger、免费/付费边界、id 获取流程 |
| `references/morphicons.md` | 图标变形动画：各框架入口、stroke 型约束 |
| `references/official-web.md` | Material/Fluent/Heroicons/Tabler/Phosphor/Bootstrap/AntD/feather/remix/mdi/ionicons/octicons/radix/eva/iconoir/simple-icons 逐套细节（含许可变化警示） |
| `references/iconify.md` | 聚合兜底通道：跨库搜索/prefix:icon 下载/许可元数据与风险 |
