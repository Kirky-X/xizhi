# Lordicon — 动效图标（Lottie 动画）

> 静态图标用 lucide 等套件；**需要"会动的图标"**（loading、微交互反馈、空状态引导、onboarding）才走 Lordicon。

## 定位

- 47000+ 动画图标，**免费 + 付费混排**（免费约 1300+，商用条款以官网为准）
- 格式：Lottie JSON（矢量动画）、GIF、SVG 等；Web 首选 JSON
- 本质是 Lottie 动画，任何 Lottie 播放器都能放，官方 web component 最省事

## 使用方式（Web Component，官方推荐）

```html
<!-- 1. 播放器（jsDelivr 实测可用） -->
<script src="https://cdn.jsdelivr.net/npm/@lordicon/element@2.3.1/lib/index.js"></script>

<!-- 2. 图标：trigger 控制播放时机 -->
<lord-icon
  src="https://cdn.lordicon.com/lupuorrc.json"
  trigger="hover"
  colors="primary:#121331,secondary:#08a88a"
  style="width:64px;height:64px">
</lord-icon>
```

trigger 可选：`hover` / `click` / `loop` / `loop-on-hover` / `in`（进入视口）/ `boomerang` 等，详见 https://lordicon.com/docs/web

## 获取图标（无公开名称索引，必须官网挑）

Lordicon 没有可脚本枚举的名称清单，图标 id 是短随机串（如 `lupuorrc`）：

1. 到 https://lordicon.com 搜索（如 "loading"），用 **Free** 筛选器只看免费图标
2. 打开图标页 → 复制 CDN 链接（形如 `https://cdn.lordicon.com/<id>.json`）→ 取 `<id>`
3. 下载到本地：

```bash
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lordicon --name lupuorrc --out ./assets/icons
```

agent 辅助流程：让用户在官网挑好给 id，或 WebFetch 图标页拿 id；**不要瞎编 id**。

## 本地化用法（推荐生产环境）

```html
<lord-icon src="/assets/icons/lupuorrc.json" trigger="hover"></lord-icon>
```

## 常见坑

1. CDN 直链跨域没问题，但生产环境建议自托管 JSON（可用性+隐私）
2. 付费图标下载会带水印/受限——认准 Free 筛选
3. `colors` 只影响图标里标记为 primary/secondary 的图层，不是所有图标都支持换色
4. React 里可用 `@lordicon/react`（官方包），或直接用 web component
