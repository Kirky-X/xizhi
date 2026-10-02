# Xizhi — Official Icon Set Routing & Auto-Download Skill

[![GitHub Release](https://img.shields.io/github/v/release/Kirky-X/xizhi?style=flat-square)](https://github.com/Kirky-X/xizhi/releases) [![GitHub License](https://img.shields.io/github/license/Kirky-X/xizhi?style=flat-square)](LICENSE) [![Sets](https://img.shields.io/badge/icon%20sets-21-blue?style=flat-square)](#-supported-sets)

> Icon asset skill for AI agents: deterministically pick the right official icon set by project context → anti-hallucination name search (offline/online) → scripted auto-download. 21 first-class sets (licenses individually verified) plus Iconify 200k aggregate fallback; HarmonyOS sys.symbol referenced in code with zero downloads; web sets via dual jsDelivr/GitHub channels.

English | [中文](README.md)

## ✨ Features

- **Deterministic 21-set routing table** (licenses individually verified, tracking 2026 changes: RemixIcon new license commercial-OK, css.gg new license excluded): HarmonyOS→`sys.symbol`, shadcn/Tailwind→lucide, Material→Material Symbols, Microsoft→Fluent, animated→lordicon/morphicons… table-driven routing, no free-styling (deterministic logic stays in lookup tables, not the model); `suggest` subcommand reads project reality (package.json/pubspec.yaml/react-icons usage) to align with existing dependencies
- **Anti-hallucination name search**: lucide dual name+tag index (resolves renames like `home`→`house` with a `matched as` note); **synonym-group expansion** (simplified/traditional Chinese & English aliases via curated lookup, e.g. `铃铛`→`bell`, strictly suite-scoped — never rewrites names across sets); close-name candidates + direct-URL verification on miss; **HarmonyOS dual-source index** — official catalog of 579 icons (with Chinese names/unicode) + offline SDK full list of 2,761 names, works without network
- **Batch download & provenance**: comma-separated multi-name fetch (Iconify merged endpoint with automatic alias unpacking; per-item stats, one failure never aborts the batch); `--sprite` packs a `<symbol>` sheet; `--version` pins reproducible downloads; every SVG carries provenance + license headers; `--format data-uri` / `--color` output adapters (opt-in, root-tag-only rewrite — never global)
- **Supply-chain safety**: deterministic blocklist scan before writing any SVG (`<script`/event handlers/`javascript:`/external refs) — hits refuse to land and abort the batch; iconify search results from non-first-party prefixes carry a review warning
- **HarmonyOS full pipeline**: in-code `SymbolGlyph($r('sys.symbol.*'))` with zero downloads; SVG needs served by the reverse-engineered official channel — `name_map_new.json` catalog + `HMSymbol.ttf` variable font (wght 40-900, 4,837 glyphs), rendered via fontTools with the same pipeline as the website's frontend fontkit
- **Multi-stack delivery**: `sync` subcommand generates react/solid/vue/svelte components (idempotent markers, returns import statements); mechanical checklists for Flutter/Android/RN in `references/mobile-native.md`
- **Channel health checks**: `doctor` subcommand probes every registry channel with short timeouts; `.github/workflows/health.yml` runs it weekly in CI and auto-files an issue on failure — breakage is discovered proactively, not on first user failure
- **Animated icon options**: lordicon (Lottie JSON via CDN) + morphicons (spring-physics morphing library for stroke icons)
- **Zero pip dependencies**: pure Python stdlib (urllib), cross-platform; 7-day local cache for name indexes, `--refresh` to force; usable as a standalone CLI by humans without an agent
- **Explicit failures**: invalid variants / 404 / broken channels / HTML soft-200 / poisoned SVGs all error out with exit 1 — never silent (pinned by 140+ offline tests)

```mermaid
flowchart TD
    A["User needs icons"] --> B{"Project type?"}
    B -->|HarmonyOS/ArkTS| H["sys.symbol<br/>offline search + $r reference (zero download)"]
    B -->|shadcn/Tailwind| L["lucide"]
    B -->|Material/Android| M["material-symbols"]
    B -->|Microsoft/Fluent| F["fluent"]
    B -->|AntD/Bootstrap ecosystem| E["antd / bootstrap"]
    B -->|Animation needed| D["lordicon (loop) <br/>morphicons (state morph)"]
    H & L & M & F & E & D --> S["xizhi.py search to confirm names"]
    S --> T["xizhi.py fetch download / npm package integration"]
```

## 📦 Supported Sets

| set | Library | License | Positioning |
| --- | ------- | ------- | ----------- |
| `harmonyos` | HarmonyOS Symbol | Bundled with OS | HarmonyOS first choice; zero-download in-code refs; SVG/font scriptable (official catalog with Chinese names) |
| `lucide` | Lucide | ISC | Web default; 1,834 icons; shadcn/ui default |
| `remix` | Remix Icon | Remix Icon License v1.0 | 3,200+; commercial ✓ attribution optional (2026-01 new license) |
| `mdi` | Material Design Icons (Pictogrammers) | Pictogrammers Free License | Largest single community set, 7,400+ |
| `ionicons` | Ionicons (Ionic) | MIT | Ionic official, mobile feel |
| `octicons` | Octicons (GitHub) | MIT | GitHub official, dev-tool style |
| `radix` | Radix Icons | MIT | Radix UI official, minimal curation |
| `eva` | Eva Icons (Akveo) | MIT | Soft rounded, outline/fill |
| `iconoir` | Iconoir | MIT | New-gen linear set, 1,500+ |
| `simple-icons` | Simple Icons | CC0-1.0 | Brand/tech logos (trademarks still apply) |
| `iconify` | Iconify aggregate | Per source set | 200k+ / 150+ sets fallback incl. flags/dev/emoji |
| `material-symbols` | Material Symbols (Google) | Apache-2.0 | Material/Android official; variable-font 4 axes |
| `fluent` | Fluent UI System Icons (Microsoft) | MIT | Microsoft official; size/style suffixes in names |
| `heroicons` | Heroicons (Tailwind Labs) | MIT | Tailwind ecosystem (non-shadcn projects) |
| `antd` | Ant Design Icons | MIT | AntD / Ant ecosystem admin UIs |
| `bootstrap` | Bootstrap Icons | MIT | Bootstrap ecosystem |
| `phosphor` | Phosphor | MIT | 6 weights / duotone typographic system |
| `tabler` | Tabler Icons | MIT | 5,000+ icons, breadth play |
| `lordicon` | Lordicon | Site terms | Lottie animated icons (free + premium) |
| `morphicons` | Morphicons | MIT | Icon morphing animation library (not an icon set) |
| `feather` | Feather Icons | MIT | Legacy compatibility (unmaintained) |

## 🚀 Quick Start

```bash
# 1. Set overview / channel details
python3 {SKILL_DIR}/scripts/xizhi.py sets
python3 {SKILL_DIR}/scripts/xizhi.py describe --set material-symbols

# 2. Search names (mandatory before coding; harmonyos official catalog supports Chinese, offline falls back to SDK list)
python3 {SKILL_DIR}/scripts/xizhi.py search --set lucide --query home        # tag hits renamed house
python3 {SKILL_DIR}/scripts/xizhi.py search --set harmonyos --query bell     # official: bell · unicode F01D5

# 3. Download (optional variants auto-appended to filename; comma batches; provenance + license headers)
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --out ./assets/icons
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house,bell,compass --out ./assets/icons   # batch
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house,bell --sprite --out ./assets/icons  # sprite sheet
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lucide --name house --version 0.511.0                   # pinned version
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set material-symbols --name home --style outlined --size 48 --grad grad200 --fill fill1
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set lordicon --name lupuorrc    # Lottie JSON
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set harmonyos --name house --wght 700 --out ./assets/icons  # official font rendered SVG
python3 {SKILL_DIR}/scripts/xizhi.py fetch --set iconify --name icon-park-outline:home --out ./assets/icons # aggregate fallback

# 4. Engineering (as needed)
python3 {SKILL_DIR}/scripts/xizhi.py suggest                                                # recommend sets from project reality
python3 {SKILL_DIR}/scripts/xizhi.py sync --framework react --set lucide --name house       # generate components
python3 {SKILL_DIR}/scripts/xizhi.py doctor                                                 # channel health check
```

HarmonyOS code references system built-ins directly (no download needed):

```typescript
SymbolGlyph($r('sys.symbol.house')).fontSize(24).fontColor('#333')
```

## 🧪 Tests & Verification

All data verified via real network tests on 2026-09-14:

- Full fetch regression across sets: all downloads/generations succeed ✓ (including harmonyos SVG generation, font download, and iconify aggregate)
- Search across all sets: exact/tag/prefix/contains four-tier ranking ✓ (lucide `home`→`house`, fluent `home_24_regular`, bootstrap `house-door`, harmonyos Chinese 设置→`gearshape`)
- Error paths: invalid variant / 404 / no match all exit 1 explicitly ✓
- HarmonyOS channel reverse-engineered and verified: website SPA (`hm-symbol.js`) → data files `name_map_new.json` (579 icons) + `HMSymbol.ttf` (4,837 glyphs, 579/579 unicode hits; covers 2,746/2,761 of the SDK list); SVG rendered by fontTools from the font (same pipeline as the site's frontend fontkit)
- Anti-hallucination effectiveness: `gear`/`settings` absent from the HarmonyOS list (correct name `gearshape`); SDK list extracted from [webabcd/HarmonyDemo IconDemo.ets](https://github.com/webabcd/HarmonyDemo/blob/main/entry/src/main/ets/pages/resource/IconDemo.ets)
- **2026-10 benchmark enhancements** (batch fetch / provenance / safety scan / doctor / suggest / sync — 11 recommendations): pinned by 140 offline tests (`python3 -m pytest tests -q`); the Iconify merged endpoint and `home→house` alias behavior re-verified against api.iconify.design; channel availability continuously monitored by the weekly doctor CI

```bash
# Offline test suite
python3 -m pytest tests -q
# Regression (networked environment)
python3 scripts/xizhi.py sets && python3 scripts/xizhi.py search --set harmonyos --query house
python3 scripts/xizhi.py fetch --set lucide --name house --out /tmp/icons
python3 scripts/xizhi.py doctor
```

## 📁 Layout

```
xizhi/
├── SKILL.md                       # Entry: routing table + 3-step workflow
├── scripts/xizhi.py               # Unified CLI (sets/search/fetch/doctor/sync/suggest/describe)
├── data/harmonyos-symbols.txt     # Offline list of 2,761 sys.symbol names
├── .github/workflows/
│   ├── release.yml                # tag-triggered packaging & release
│   └── health.yml                 # weekly channel doctor (auto-issue on failure)
└── references/
    ├── lucide.md                  # Integration, rename history, CDN
    ├── harmonyos-symbol.md        # SymbolGlyph usage & 3 name-lookup channels
    ├── lordicon.md                # Animated icons: player/trigger/id workflow
    ├── morphicons.md              # Morph animation: framework entries/stroke constraint
    ├── official-web.md            # Material/Fluent/Heroicons/Tabler/Phosphor/Bootstrap/AntD/feather etc.
    ├── iconify.md                 # Aggregate fallback: batch endpoint/local fallback/license risks
    └── mobile-native.md           # Flutter/Android/RN multi-stack delivery checklists
```

## 📜 License

[MIT](LICENSE) © 2026 Kirky-X🌠
