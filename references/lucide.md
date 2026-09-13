# Lucide — Web 默认图标套件

> 优先读 SKILL.md 的选型表确认 lucide 是正确选择；本文档是 lucide 的落地细节。

## 定位

- 1500+（实测 1834）线性 stroke 图标，24×24、stroke-width 2，风格统一、覆盖面最广
- Feather Icons 的社区继任者（feather 已停更，新项目一律用 lucide）
- shadcn/ui 默认图标库；React/Vue/Svelte/Angular/Solid/Preact 全家桶
- ISC 许可（早期 MIT，现行 ISC，均可商用）

## 命名规范（防幻觉关键）

- 名称一律 **kebab-case**：`arrow-left`、`chevron-right`、`house`
- ⚠️ `home` 已更名 **`house`**（tags 里保留 home 别名，`search --set lucide --query home` 能通过 tag 命中 house）——同理 `save`→`floppy-disk` 等老 feather 名多有更名，**写代码前先 search**
- 组件名 = PascalCase：`house` → `<House />`
- 浏览全部图标：https://lucide.dev/icons

## 三种落地方式

### 1. 框架包（推荐，项目内使用）

```bash
npm install lucide-react        # React / Next.js
npm install lucide-vue-next     # Vue 3（Vue 2 用 lucide-vue）
npm install lucide-svelte       # Svelte
npm install lucide              # vanilla JS / Astro 等
```

```tsx
// React
import { House, Settings, Menu } from 'lucide-react';
<Menu size={20} strokeWidth={1.5} className="text-neutral-500" />
```

### 2. 静态 SVG（零依赖，按需下载）

```bash
python3 {SKILL_DIR}/scripts/xizhi.py search --set lucide --query house
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --out ./assets/icons
```

下载的 SVG 默认 `stroke="currentColor"`，颜色随 CSS `color` 走，可直接 inline 或 `<img>` 引用。

### 3. CDN 全量脚本（原型/demo 快速用）

```html
<script src="https://unpkg.com/lucide@latest"></script>
<i data-lucide="house"></i>
<script>lucide.createIcons();</script>
```

## 变体调节

- **尺寸**：框架包 `size` 属性；静态 SVG 改 `width/height`（viewBox 24 不变）
- **粗细**：`strokeWidth`（1/1.5/2/2.5）；lucide-static 也提供 `house-1.5px.svg` 等细笔画文件？——不提供，粗细只有框架包/SVG stroke 属性可调
- **绝对定位变体**：带 `-absolute` 后缀（如 `arrow-left-absolute`）用于角标定位

## 常见坑

1. **名字记错是最高频失败**：先 `search` 再写码；404 说明名字不对
2. React 里 `import { Home }` 报 undefined → 已更名 `House`
3. Next.js App Router 里超大图标树用 dynamic import 或改用静态 SVG，避免打包体积膨胀
4. 需要"菜单↔关闭"这类**变形动画** → 配合 morphicons（见 morphicons.md），lucide 是 stroke 型天然兼容
