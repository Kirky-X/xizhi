---
name: xizhi
description: "Icon asset routing skill: pick the right official icon set and fetch icons automatically. Trigger: 图标/icon/图标库/icon library/icon set/选图标/找图标/下载图标/icon 下载/SVG 图标/lucide/lucide-react/SymbolGlyph/sys.symbol/鸿蒙图标/HarmonyOS icon/lordicon/动效图标/animated icon/morphicons/图标变形/Material Symbols/Fluent icon/Heroicons/Tabler/Phosphor/Bootstrap Icons/AntD icons/feather icons/icon CDN. Covers set selection by project context (HarmonyOS→sys.symbol, shadcn/Tailwind→lucide, Material→Material Symbols, Microsoft→Fluent), offline icon-name search with synonym groups (anti-hallucination), batch SVG/Lottie download (comma multi-name, Iconify merged endpoint, sprite), version pinning with provenance/license headers, component generation (react/vue/svelte/solid), and channel health checks (doctor). Boundary: icon image generation→wudaozi; design system tokens→maliang; HarmonyOS syntax/engineering→hap-dev."
license: MIT
metadata:
  version: "0.1.1"
  author: "Kirky-X"
  repo: "https://github.com/Kirky-X/xizhi"
  tags: "icon, icon-library, lucide, harmonyos-symbol, symbolglyph, lordicon, morphicons, material-symbols, fluent-icons, heroicons, tabler, phosphor, bootstrap-icons, antd-icons, feather-icons, svg, lottie, asset-download, design-system, remix-icon, mdi-icons, ionicons, octicons, radix-icons, eva-icons, iconoir, simple-icons, iconify, free-commercial"
---

# XIZHI — 官方图标套件选型与自动下载

书圣王羲之：线条即图标。本 skill 解决两件事：**为当前项目选对图标套件** + **把图标资产自动拿下来**。

> **边界**：AI 生成图标图片 → wudaozi；设计系统/token → maliang；鸿蒙语法与工程问题 → hap-dev。本 skill 只管矢量图标资产的选型、检索、下载与集成。

## 第一步：选型（确定性查表，不要自由发挥）

| 项目/场景 | 套件（set id） | 理由 |
|---|---|---|
| **HarmonyOS / ArkTS** | `harmonyos` | 代码内 `$r()` 引用零下载自动跟随主题；SVG/官方字体亦可脚本化下载（官方目录含中文名搜名） |
| **iOS / macOS / watchOS 原生** | 系统 SF Symbols API（不设下载通道） | `Image(systemName:)` 零下载随系统分发，与鸿蒙 sys.symbol 同模式；Apple 许可明文禁止符号再分发/导出非 Apple 平台，无合法 fetch 通道；跨平台/Web 用 `lucide` 或 `phosphor`（见 references/mobile-native.md） |
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

项目里已装了图标库（package.json / pubspec.yaml）时，先跑 `suggest` 读实况对齐现有依赖，再查表：

```bash
python3 {SKILL_DIR}/scripts/xizhi.py suggest        # 检测已装依赖/react-icons 用量 → 推荐套件 + 下一步命令
```

## 第二步：查名称（写码前必做，防幻觉）

```bash
python3 {SKILL_DIR}/scripts/xizhi.py sets                          # 全部套件速览
python3 {SKILL_DIR}/scripts/xizhi.py search --set lucide --query house
python3 {SKILL_DIR}/scripts/xizhi.py search --set harmonyos --query 铃铛    # 官方目录支持中文名；离线降级 2761 名称 SDK 清单
python3 {SKILL_DIR}/scripts/xizhi.py describe --set material-symbols        # 套件通道/变体详情
```

- lucide 支持名称+tag 双匹配（旧名作为 tag 保留：搜 `home` 经 tag=home 命中 `house` 等图标；`matched as` 行标注首个 tag 命中名——实测为 birdhouse，fetch 用该实际名）
- harmonyos 双源：在线官方目录（579 图标，含中文名/unicode）+ 离线 SDK 清单（2761 名称），无网可用
- 同义词组自动扩展：搜 `铃铛`/`鈴鐺` 能命中 `bell`（简繁/中英别称，确定性查表，套件内作用域绝不跨套件改名）
- 搜不到 → 看输出的**近似名候选**（可直接 fetch）与**直链核验**；仍无则换套件，不要硬编名字

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
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set material-symbols --name home --style outlined --size 48 --grad grad200 --fill fill1
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lordicon --name lupuorrc      # Lottie JSON
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set morphicons --name dom.js      # 变形库 vanilla ESM
# 批量（逗号多值；iconify 自动走合并端点；逐条统计，任一失败 exit 1）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house,bell,compass --out ./assets/icons
# 批量打 sprite（单文件 <symbol> 集合，解析不出的图标显性跳过）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house,bell --sprite --out ./assets/icons
# 钉版本（可复现；SVG 产物自带溯源 + 许可注释；raw 分支/CDN id 通道不支持会显性拒绝）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --version 0.511.0
# 输出适配（opt-in，默认原始落盘绝不改写）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --format data-uri
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --color '#f00'   # 仅根标签 currentColor
# Web 框架组件化落地（react/solid/vue/svelte/svg；幂等标记，返回 import 语句）
python3 {SKILL_DIR}/scripts/xizhi.py sync --framework react --set lucide --name house --out ./components/xizhi
```

下载的 SVG `stroke="currentColor"`，颜色随 CSS `color`；SVG 产物头部带 `<!-- xizhi: 来源 @ 日期 | license -->` 溯源注释，`--version` 可钉版本复现。输出目录默认 `./icons/`，变体自动进文件名防覆盖。在线失败时 iconify 通道自动降级到项目内 `node_modules/@iconify-json/<prefix>` 本地包。鸿蒙之外的移动端（Flutter/Android/RN）集成见 `references/mobile-native.md`。

## 失败与降级

| 症状 | 处置 |
|---|---|
| fetch 404 | 名字错 → 回第二步 search 确认 |
| 请求失败/超时 | 网络问题不计入失败；确认代理后重试；jsdelivr 与 raw.githubusercontent 双通道在注册表内固化 |
| 通道疑似失效（上游改版） | `python3 xizhi.py doctor` 全量巡检（每周 CI 自动跑，失败自动开 issue）；`--set X` 只看单套件 |
| `harmonyos` SVG 报"需要 fontTools" | 一次性 `pip install fonttools`；或 `--name HMSymbol.ttf` 直下字体 |
| search 无结果 | 看输出的近似名候选；同义词/中文重试（鸿蒙支持中文名）；仍无则该套件没有此图标，换套件 |
| iconify 在线失败 | 自动降级项目内 `@iconify-json/<prefix>` 本地包；未装则提示 `npm i -D` 引导 |
| 脚本不可用 | 降级：按 references 里固化的 URL 模板直接 curl（规则5） |

## 内容安全（供应链边界）

- 每个落盘 SVG 都过**确定性黑名单扫描**（归一化后匹配：`<script`、`on*=` 事件属性、`javascript:`/`vbscript:` 伪协议、`data:text/html`、外部 `href`/`url()` 引用），命中即拒绝落盘并中止批次（exit 1，`[security]` 标注命中模式）；扫描仅覆盖 SVG 资产（lordicon 的 `.json`、morphicons 的 `.js` 为设计内的非 SVG 产物，不过黑名单）
- sync 组件生成额外拦截**花括号**（JSX/Vue/Svelte 模板上下文的代码注入面）；含花括号的 SVG 只能 `--framework svg` 原样落地
- 一等套件全部走官方上游；iconify 兜底可达任意第三方套件——搜索结果中非一等收录的 prefix 附警示，引入前人工审阅
- 产物头部带来源 URL + 日期 + 许可的溯源注释；要绝对稳定就 `--version` 钉版本或把 SVG 内联进源码

## 独立 CLI 用法（可脱离 agent 由人直接使用）

脚本零依赖（纯 Python 标准库），人类可直接命令行运行：

```bash
python3 scripts/xizhi.py sets                 # 选型速览
python3 scripts/xizhi.py suggest              # 读当前项目实况推荐套件
python3 scripts/xizhi.py search --set lucide --query home
python3 scripts/xizhi.py fetch --set lucide --name house,bell --out ./assets/icons
python3 scripts/xizhi.py doctor               # 通道健康巡检
```

## 按需深读（references/）

| 文件 | 何时读 |
|---|---|
| `references/lucide.md` | lucide 集成细节、命名更名史、CDN 用法 |
| `references/harmonyos-symbol.md` | 鸿蒙 SymbolGlyph/SymbolSpan 用法、找名三通道、素材下载 |
| `references/lordicon.md` | 动效图标：player、trigger、免费/付费边界、id 获取流程 |
| `references/morphicons.md` | 图标变形动画：各框架入口、stroke 型约束 |
| `references/official-web.md` | Material/Fluent/Heroicons/Tabler/Phosphor/Bootstrap/AntD/feather/remix/mdi/ionicons/octicons/radix/eva/iconoir/simple-icons 逐套细节（含许可变化警示） |
| `references/iconify.md` | 聚合兜底通道：跨库搜索/批量合并端点/本地降级/许可元数据与风险 |
| `references/mobile-native.md` | Flutter / Android / React Native 多栈落地（机械变换清单 + metro/vd-tool 配方） |
