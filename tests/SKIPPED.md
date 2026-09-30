# xizhi tests/SKIPPED.md — 冒烟套件未覆盖项及原因

原则：③涉及真实网络/外部二进制的路径不写假测试。以下全部为在线通道，
脚本内已 mock 边界（`http_get`）验证过 URL 组装与显性失败契约，真实
HTTP IO 不进入离线套件。

## 在线名称索引（search --set ... 的联网路径）

| 未覆盖路径 | 位置 | 原因 |
| --- | --- | --- |
| lucide tags.json 双索引构建 | `scripts/xizhi.py` `build_names` kind=url-json-lucide | 需下载 cdn.jsdelivr.net 真实 tags.json；组装/缓存逻辑已 mock 验证 |
| material-symbols codepoints 索引 | 同上 kind=url-plain | 需下载 raw.githubusercontent.com codepoints 文件 |
| fluent/heroicons/tabler/phosphor/feather/bootstrap/antd/remix/mdi/ionicons/octicons/radix/eva/iconoir/simple-icons flat 索引 | 同上 kind=url-flat-npm | 依赖 jsdelivr/GitHub flat API 真实响应 + `npm_latest` registry 查询 |
| iconify 聚合搜索 / collections 许可元数据 | `_search_iconify` | 纯在线功能，无离线路径（已测：联网前显性失败） |

## 在线下载

| 未覆盖路径 | 位置 | 原因 |
| --- | --- | --- |
| `fetch --set <set> --name <n>` 真实下载 | `cmd_fetch` 内 `http_get(u, binary=True)` | 下载真实 SVG/JSON 资产需外网；模板组装与落盘命名已 mock 全覆盖（tests/test_xizhi_fetch.py） |
| harmonyos HMSymbol.ttf 字体下载 | `_fetch_harmonyos` 字体分支 | 数 MB 字体下载；且 SVG 字形生成依赖可选包 fontTools（离线环境不保证安装） |
| harmonyos SVG 字形渲染（fontTools instancer/SVGPathPen） | `_fetch_harmonyos` 主体 | 需 fontTools + 已缓存字体，属外部依赖而非脚本逻辑 |

## 实测口径

文档声称"所有 URL 模式 2026-09-14 实测 200"属在线事实，无法离线复验；
冒烟套件只保证：模板组装正确、通道失效时**显性报错**（HTML 探测/非 200/
网络异常均 SystemExit，tests/test_xizhi_infra.py）。
