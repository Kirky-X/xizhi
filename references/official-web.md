# 其他官方 Web 图标套件

> 各套件按需查阅对应小节；下载/搜名统一走 `scripts/xizhi.py`。所有 URL 模式与许可 2026-09-14 实测/核验。

速查：

| set | 官方 | 许可 | fetch 示例 |
|---|---|---|---|
| material-symbols | Google | Apache-2.0 | `fetch --set material-symbols --name home [--style rounded\|outlined\|sharp] [--size 20\|24\|40\|48] [--fill _fill1]` |
| fluent | Microsoft | MIT | `fetch --set fluent --name home_24_regular` |
| heroicons | Tailwind Labs | MIT | `fetch --set heroicons --name home [--variant 24/outline\|24/solid\|20/solid\|16/solid]` |
| tabler | Tabler | MIT | `fetch --set tabler --name home [--style outline\|filled]` |
| phosphor | Phosphor | MIT | `fetch --set phosphor --name house [--weight thin\|light\|regular\|bold\|fill\|duotone]` |
| remix | Remix Design | Remix Icon License v1.0（商用 ✓ 署名可选，禁单独售卖） | `fetch --set remix --name "Buildings/home-2-line"`（名称带分类前缀） |
| mdi | Pictogrammers | Pictogrammers Free License（Apache-2.0 基底，商用 ✓） | `fetch --set mdi --name home`（7400+） |
| ionicons | Ionic | MIT | `fetch --set ionicons --name home-outline`（也含 home/home-sharp） |
| octicons | GitHub | MIT | `fetch --set octicons --name home-16`（名称带尺寸后缀） |
| radix | Radix UI | MIT | `fetch --set radix --name cube`（~330 个，15px 视觉优化） |
| eva | Akveo | MIT | `fetch --set eva --name home-outline [--style outline\|fill]`（fill 自动去 -outline 后缀） |
| iconoir | Iconoir | MIT | `fetch --set iconoir --name home [--style regular\|solid]` |
| simple-icons | Simple Icons | CC0-1.0（品牌 logo 受商标法约束） | `fetch --set simple-icons --name github` |
| feather | Feather | MIT | `fetch --set feather --name home`（287 个，停更，新项目用 lucide） |
| bootstrap | Bootstrap | MIT | `fetch --set bootstrap --name house-door` |
| antd | Ant Design | MIT | `fetch --set antd --name home [--style outlined\|filled\|twotone]` |

## 2026-09 新增套件要点

- **Remix Icon**：⚠️ 2026-01 起 Apache-2.0 换为自定义 Remix Icon License v1.0——商用明确允许、署名可选，唯一红线是"把图标包单独售卖"；名称带分类目录前缀（search 结果照抄即可）
- **MDI (Pictogrammers)**：与 Google 官方 material-symbols 是两回事（社区集），量大（7400+）适合兜底细分需求
- **Simple Icons**：品牌 logo 单色版；CC0 但**商标权不受 CC0 影响**——对外产品中展示第三方品牌 logo 仍需遵守各品牌商标政策
- **css.gg 曾评估但被排除**：v2.1.2 起许可改为禁止修改/禁止复刻/强制署名，不再宽松，勿引入

## Material Symbols（Google 官方）

- **可变字体四轴**：FILL（0/1 线↔面）、wght（100-700）、GRAD（-25/0/200）、opsz（20/24/40/48）——网页用 Google Fonts CSS 引字体，SVG 场景用本脚本
- 命名 snake_case：`home`、`arrow_back`、`search`
- 名称索引 = 官方 codepoints（`search --set material-symbols` 自动拉取缓存）
- 字体引入：

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" />
<span class="material-symbols-rounded">home</span>
```

- React 项目用 `material-symbols` npm 包或 `@mui/icons-material`（MUI 生态自带）

## Fluent UI System Icons（Microsoft 官方）

- **名称自带尺寸与风格后缀**：`{name}_{size}_{style}`，如 `home_24_regular`、`alert_20_filled`
- 尺寸 20/24/28/32/48；风格 regular/filled
- `search --set fluent --query home_24` 可按前缀过滤
- React 用 `@fluentui/react-icons`（npm，官方）

## Heroicons（Tailwind Labs 官方）

- 仅 ~300 精选图标，4 变体：`24/outline`、`24/solid`、`20/solid`、`16/solid`
- Tailwind 项目气质最搭；shadcn/ui 项目仍用 lucide（默认依赖）
- React 用 `@heroicons/react`：`import { HomeIcon } from '@heroicons/react/24/outline'`

## Tabler Icons

- 5000+ 全开源（MIT），outline/filled 双风格，stroke-width 可调（包内提供 1~2.5 细分文件）
- React 用 `@tabler/icons-react`；Vue 用 `@tabler/icons-vue`

## Phosphor Icons

- 同一图标 6 字重（thin/light/regular/bold/fill/duotone），适合需要排版层级的项目
- React 用 `@phosphor-icons/react`

## Bootstrap Icons

- Bootstrap 生态；SVG + icon font 双通道
- 字体引入：`<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@latest/font/bootstrap-icons.min.css">` + `<i class="bi bi-house-door"></i>`

## Ant Design Icons

- AntD/蚂蚁系中后台；outlined/filled/twotone
- React 用 `@ant-design/icons`（`<HomeOutlined />`）；组件名 = PascalCase + 风格后缀

## 选型兜底规则

1. 项目已锁设计系统（MUI/Fluent/AntD/Bootstrap）→ 跟系统自带图标走
2. 无约束 → lucide
3. 图标量/细分度不够再考虑 tabler/phosphor
4. 同一项目**禁止混用多套**（视觉不统一是图标第一大忌）
