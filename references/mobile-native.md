# 移动原生多栈落地 — Flutter / Android / React Native

> 鸿蒙项目不走本文件：代码内 `SymbolGlyph($r('sys.symbol.*'))` 直引零下载，见 `harmonyos-symbol.md`。
> 原则：**统一 SVG 输出（fetch 原始落盘 + 溯源头）→ 每栈一节机械变换 → 确定性校验命令**。
> 不手改路径数据、不目测对齐；每栈只写可机械执行的规则。

## 0. 统一取图

```bash
# 原始 SVG 落盘（含 xizhi 溯源头注释 + 许可标注；--version 可钉版本）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house,bell --out ./assets/icons
```

Web 框架（react/solid/vue/svelte）优先用 `sync` 子命令直接生成组件（幂等标记，返回 import 语句）：

```bash
python3 {SKILL_DIR}/scripts/xizhi.py sync --framework react --set lucide --name house --out ./components/xizhi
```

## 1. Flutter

**资产落位**：fetch 到 `assets/icons/`，`pubspec.yaml` 声明：

```yaml
flutter:
  assets:
    - assets/icons/
```

**渲染**（`flutter pub add flutter_svg`）：

```dart
import 'package:flutter_svg/flutter_svg.dart';
SvgPicture.asset('assets/icons/house.svg',
    width: 24, height: 24,
    colorFilter: const ColorFilter.mode(Color(0xFF333333), BlendMode.srcIn))
```

- SVG 内 `fill="currentColor"` 由 `colorFilter` 统一接管（等价 Web 的 CSS color）
- **校验**：`flutter analyze && flutter pub get`（构建期显性报错）

## 2. Android 原生（VectorDrawable）

**落位**：`res/drawable/`（文件名小写下划线：`ic_house.xml`）。

**变换**（SVG ≠ VD，需转换）：

- Android Studio：`New → Vector Asset → Local file` 选 SVG（交互式，逐个）
- 命令行批量：`$ANDROID_HOME/tools/bin/vd-tool -c -d <输入目录> -o res/drawable/`

**兼容性检查清单**（机械核对，命中任一条先改 SVG 再转）：

- [ ] 无 `<script>`/外部引用（xizhi 安全扫描已拦截，源头即净）
- [ ] 无 `<text>`、滤镜（`<filter>`）、蒙版（`<mask>`）——VD 不支持
- [ ] 渐变用 `<gradient>` 内联（aapt 生成），不引外部资源

**着色**：`android:tint` + `ImageViewCompat.setImageTintList`（等价 currentColor）。
**校验**：`./gradlew :app:assembleDebug`（aapt 编译错误显性失败）。

## 3. React Native

**依赖**（`npm i react-native-svg react-native-svg-transformer`）+ metro 配置（官方配方，逐字）：

```js
// metro.config.js
const { getDefaultConfig } = require("@react-native/metro-config");
const { assetExts, sourceExts } = getDefaultConfig().resolver;

module.exports = {
  transformer: {
    babelTransformerPath: require.resolve("react-native-svg-transformer"),
    getTransformOptions: async () => ({
      transform: { experimentalImportSupport: false, inlineRequires: true },
    }),
  },
  resolver: {
    assetExts: assetExts.filter((ext) => ext !== "svg"),
    sourceExts: [...sourceExts, "svg"],
  },
};
```

**使用**：fetch 到 `assets/svg/` 后 TS 声明 + import（transformer 把 SVG 变组件）：

```ts
// declarations.d.ts
declare module "*.svg" {
  import React from "react";
  import { SvgProps } from "react-native-svg";
  const content: React.FC<SvgProps>;
  export default content;
}
```

```tsx
import House from "./assets/svg/house.svg";
<House width={24} height={24} color="#333" />
```

**校验**：`npx tsc --noEmit` + `npx react-native build-android`（或对应平台构建）。

## 4. 版式纪律（跨栈）

- 一个项目一套图标（与 SKILL.md 铁律一致）；动效层另用 lordicon/morphicons
- `--version` 钉版本 + 溯源头注释让素材可审计；要绝对稳定就把 SVG 内联进源码
- 选哪个套件不确定时先跑 `suggest`（读 package.json / pubspec.yaml 实况）
