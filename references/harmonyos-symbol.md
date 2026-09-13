# HarmonyOS Symbol — 鸿蒙官方图标

> 鸿蒙项目里图标的**唯一正确首选**。与 hap-dev 的分工：图标选型与名称查询用本 skill；ArkTS 语法/工程问题走 hap-dev。

## 两条使用路线

### 路线 A：代码内引用（零下载，鸿蒙开发默认）

系统内置 2000+ Symbol 图标（sys.symbol 资源），代码内直接 `$r()` 引用：

```typescript
// 独立图标
SymbolGlyph($r('sys.symbol.house'))
  .fontSize(24)
  .fontColor('#333333')

// 富文本内嵌（bell_fill 是填充变体；很多图标有 _fill 后缀的实心版）
Text() {
  SymbolSpan($r('sys.symbol.bell_fill'))
}
```

- 自动跟随系统主题（深色模式/强调色）；是字体图标，`fontSize`/`fontColor` 直接调节
- 卡片/元服务同样可用；无版权负担（随系统分发）

⚠️ 不要在 ArkTS 里手写 SVG 路径或引第三方 SVG 当图标——sys.symbol 覆盖不到时才考虑自备资源。

### 路线 B：脚本化下载 SVG/字体（mockup、设计稿、文档、Web 展示）

官网 SPA 的数据通道已逆向实测（2026-09-14），**可完全脚本化**：

| 资产 | URL（实测 200） | 内容 |
|---|---|---|
| 官方目录 | `https://developer.huawei.com/allianceCmsResource/resource/HUAWEI_Developer_VUE/template/resources/hm-symbol/name_map_new.json` | 579 图标：name/name_cn 中文名/unicode/support_version/category |
| 符号字体 | 同目录 `HMSymbol.ttf`（4.2MB） | 可变字体 wght 40-900，4837 字形（含 SDK 全量 2761 名称 + 2091 扩展符号） |
| 动画图层配置 | 同目录 `layer_config.json` | 官网动画参数（spring 曲线等），做高保真动效还原用 |

```bash
# 中英文/名称模糊搜名（官方目录含中文名，如 设置→gearshape；离线时降级 SDK 清单）
python3 {SKILL_DIR}/scripts/xizhi.py search --set harmonyos --query 铃铛
python3 {SKILL_DIR}/scripts/xizhi.py search --set harmonyos --query house

# 生成 SVG（fontTools 从字体提取字形，fill=currentColor；--wght 40-900 可变字重）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name airplane_fill --out ./assets/icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name house --wght 700 --out ./assets/icons

# 直接拿官方字体（DevEco/设计工具用）
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name HMSymbol.ttf --out ./fonts
```

SVG 生成需要 `pip install fonttools`（唯一可选依赖，报错会明确提示）；字体与目录自动缓存到 `~/.cache/xizhi/`，`--refresh` 强制更新。

## 查名称（写码前必做，防幻觉）

优先级：① `search --set harmonyos`（官方目录+SDK 清单双源）→ ② DevEco Studio 内置 Symbol 面板 → ③ 官网可视化浏览（点击图标复制名称）：https://developer.huawei.com/consumer/cn/design/harmonyos-symbol

- 命名风格混合：`house`、`bell_fill`、`chevron_left`、`gearshape`（不是 settings）、`AI_search`（大写开头）
- ⚠️ 与 Web 套件名不对齐（`gearshape` ≠ `gear`），**写码前必须 search 确认**

## 边界

- 位图系统图标（`sys.media.*`）属系统 UI 专用，业务图标用 sys.symbol
- SymbolGlyph 完整属性（renderingStrategy/动效等）：https://developer.huawei.com/consumer/cn/doc/harmonyos-references/ts-basic-components-symbolglyph
- 官网 SVG 下载是前端 fontkit 渲染（非静态文件），本 skill 用 fontTools 复刻同管线，字重/字形与官网一致
