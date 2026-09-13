# Morphicons — 图标变形动画库

> Morphicons 不是图标集，是**图标 A↔图标 B 的弹簧物理变形动画库**（~7KB gzip，零依赖）。图标本体来自 lucide/tabler/heroicons 等 stroke 型套件。

## 适用场景

图标表达**状态切换**的瞬间，用变形代替生硬替换：

- menu ↔ close（汉堡按钮）
- play ↔ pause
- 月亮 ↔ 太阳（主题切换）
- 箭头方向翻转（排序/展开）

**不适用**：持续循环动画（loading 转圈 → lordicon）；图标静止展示（直接用 lucide）。

## 安装

```bash
npm install morphicons   # 实测 v1.7.1，exports: ./dom ./react ./vue ./svelte ./element ./astro ./react-native ./adapters
```

无构建工具的原型场景可拉单文件：

```bash
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set morphicons --name dom.js --out ./vendor
```

## 各框架用法

```tsx
// React
import { MorphIcon } from 'morphicons/react';
<MorphIcon from="menu" to="close" icons={{ menu: MenuIcon, close: CloseIcon }} />
```

```html
<!-- vanilla（ESM） -->
<script type="module">
  import { morph } from './vendor/dom.js';
  // 详见 https://www.morphicons.com 文档
</script>
```

Vue/Svelte/Astro/web component 入口同名规则（`morphicons/vue` 等）。完整 API（spring 参数、Procrustes 旋转等）见官网。

## 关键约束

1. **只吃 stroke 型图标**（lucide/tabler/heroicons 天然兼容；填充型如 Material filled 不适用）
2. 变形两端图标尽量同视觉重量（线数接近），效果才自然
3. 图标资产仍按各套件正常获取（lucide.md / official-web.md），morphicons 只负责动画层
