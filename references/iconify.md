# Iconify — 聚合兜底通道（200,000+ 图标）

> **何时用**：已收录套件都找不到想要的图标时，用 iconify 跨 150+ 套件全库搜；它也覆盖本 skill 未直接收录的套件（IconPark 字节系、flag 国旗、devicon 技术栈 logo、fluent-emoji、solar、mynaui 等）。

## API（全部实测 200，公开免鉴权）

```bash
# 跨库搜索（响应 icons 列表 + collections 许可元数据，本 skill 会自动展示）
python3 {SKILL_DIR}/scripts/xizhi.py search --set iconify --query flame --limit 20

# 按 prefix:icon 下载 SVG
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set iconify --name icon-park-outline:home --out ./icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set iconify --name flag:cn-4x3 --out ./icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set iconify --name devicon:python --out ./icons

# 批量（合并端点一次取回，别名自动解包，逐条 saved/failed 统计）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set iconify --name lucide:house,lucide:bell,lucide:compass --out ./icons
```

原始 API：

- 搜索：`https://api.iconify.design/search?query=<词>&limit=<N>`（**只支持英文关键词**）
- 下载：`https://api.iconify.design/<prefix>/<icon>.svg`（单个）；批量 `https://api.iconify.design/<prefix>.json?icons=a,b,c`（返回 icons/aliases JSON，由 xizhi 组装 SVG 并解包 `home→house` 类别名，不解包会直接 miss）
- 元数据：`https://api.iconify.design/collections?prefixes=<a,b,c>` → license.title/spdx

## 批量与离线降级

- 批量 fetch 走合并端点（单次上限 200 个，单条失败不中断批次，结尾显性统计并 exit 1）
- **离线兜底**：在线失败时自动探测项目的 `node_modules/@iconify-json/<prefix>/icons.json`，命中直接本地组装；未安装则提示 `npm i -D @iconify-json/<prefix>`
- 每个落盘 SVG 均经过**内容安全黑名单扫描**（`<script`、事件属性、`javascript:`、外部引用——命中拒绝落盘）并带 `<!-- xizhi: ... -->` 溯源头

## 许可风险提示（重要）

- iconify 的许可是**各来源套件的快照元数据，可能滞后**（实测例：`ri` 显示 Apache 2.0，实际 RemixIcon 已于 2026-01 改为自定义许可）。商用前以套件官方仓库的 LICENSE 为准
- search 结果中**不在 xizhi 一等收录的 prefix 会附第三方上游警示**（iconify 镜像，非官方通道），引入前自行审阅许可与内容
- 用 iconify 引入新套件前，先确认该套件许可；确认后可考虑把它升级为一等公民收录（改 scripts/xizhi.py 的 SETS）

## 与一等套件的分工

1. 项目主套件 → 一等公民（SKILL.md 选型表），风格/变体/许可都可控
2. 主套件缺图 → `search --set iconify` 找哪个套件有 → 评估是否单独引一个图标（注意别破坏风格统一）
3. 特殊品类（国旗 flag:、技术栈 devicon:、品牌 simple-icons、emoji fluent-emoji:/noto:）→ iconify 直取
