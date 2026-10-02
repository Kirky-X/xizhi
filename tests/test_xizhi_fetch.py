#!/usr/bin/env python3
"""xizhi.py fetch URL 模板冒烟（离线）——http_get mock 掉，只验证模板组装与落盘命名。

钉死：{name} 替换、变体默认值不产生后缀、非默认变体加后缀防覆盖、
非法变体显性拒绝、eva fill 去 -outline、iconify prefix:name → 路径。
跑法：python3 -m pytest tests -q
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("XIZHI_CACHE", tempfile.mkdtemp(prefix="xizhi-cache-test-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import xizhi  # noqa: E402

FAKE_SVG = b"<svg/>"


def _fetch_args(set_id, name, out_dir, **vars_):
    """带全部变体属性的 args（未设置的为 None → 走 defaults）。"""
    fields = dict(set=set_id, name=name, out=str(out_dir),
                  style=None, size=None, fill=None,
                  variant=None, weight=None, wght=None,
                  version=None, format=None, color=None, sprite=False,
                  refresh=False)
    fields.update(vars_)
    return SimpleNamespace(**fields)


class FetchCase(unittest.TestCase):
    def _fetch(self, set_id, name, responses=None, **vars_):
        """跑 cmd_fetch，返回 (捕获的 URL 列表, 输出目录, stdout)。
        responses: None→恒返 FAKE_SVG；dict→按 URL 取；callable→(url)->bytes。"""
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        captured = []

        if responses is None:
            getter = lambda url, binary=False, timeout=30: FAKE_SVG  # noqa: E731
        elif isinstance(responses, dict):
            getter = lambda url, binary=False, timeout=30: responses[url]  # noqa: E731
        else:
            getter = responses

        def fake_http_get(url, binary=False, timeout=30):
            captured.append(url)
            return getter(url, binary, timeout)

        with mock.patch.object(xizhi, "http_get", side_effect=fake_http_get), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args(set_id, name, out_dir, **vars_))
        return rc, captured, out_dir, out.getvalue(), err.getvalue()


class TestPlainTemplates(FetchCase):
    def test_lucide_plain_name(self):
        rc, urls, out_dir, outv, errv = self._fetch("lucide", "house")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/house.svg"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["house.svg"])

    def test_feather(self):
        rc, urls, out_dir, _, errv = self._fetch("feather", "home")
        self.assertEqual(rc, 0)
        self.assertIn("feather-icons@latest/dist/icons/home.svg", urls[0])

    def test_iconify_prefix_colon_becomes_path(self):
        rc, urls, out_dir, _, errv = self._fetch("iconify", "mdi:home")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://api.iconify.design/mdi/home.svg"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["mdi-home.svg"])

    def test_lordicon_json_ext(self):
        rc, urls, out_dir, outv, errv = self._fetch("lordicon", "lupuorrc")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://cdn.lordicon.com/lupuorrc.json"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["lupuorrc.json"])
        self.assertIn("lord-icon", outv)  # 用法提示

    def test_morphicons_no_double_ext(self):
        rc, urls, out_dir, _, errv = self._fetch("morphicons", "dom.js")
        self.assertEqual(rc, 0)
        self.assertTrue(urls[0].endswith("/dist/dom.js"))
        self.assertEqual([p.name for p in out_dir.iterdir()], ["dom.js"])


class TestVariantDefaults(FetchCase):
    def test_tabler_default_style_no_suffix(self):
        rc, urls, out_dir, _, errv = self._fetch("tabler", "home")
        self.assertEqual(rc, 0)
        self.assertIn("/icons/outline/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])

    def test_tabler_non_default_style_gets_suffix(self):
        rc, urls, out_dir, _, errv = self._fetch("tabler", "home", style="filled")
        self.assertEqual(rc, 0)
        self.assertIn("/icons/filled/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_filled.svg"])

    def test_illegal_variant_rejected(self):
        with self.assertRaises(SystemExit) as cm:
            self._fetch("tabler", "home", style="bogus")
        self.assertIn("非法", str(cm.exception))

    def test_material_symbols_defaults(self):
        rc, urls, out_dir, _, errv = self._fetch("material-symbols", "home")
        self.assertEqual(rc, 0)
        self.assertEqual(
            urls[0],
            "https://raw.githubusercontent.com/google/material-design-icons/master/"
            "symbols/web/home/materialsymbolsrounded/home_24px.svg")
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])

    def test_material_symbols_fill_variant(self):
        rc, urls, out_dir, _, errv = self._fetch("material-symbols", "home", fill="_fill1")
        self.assertEqual(rc, 0)
        self.assertIn("home_fill1_24px.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_fill1.svg"])

    def test_heroicons_default_and_custom_variant(self):
        rc, urls, out_dir, _, errv = self._fetch("heroicons", "home")
        self.assertIn("/optimized/24/outline/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])
        rc, urls, out_dir, _, errv = self._fetch("heroicons", "home", variant="16/solid")
        self.assertIn("/optimized/16/solid/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_16-solid.svg"])

    def test_eva_fill_strips_outline_suffix(self):
        # eva 布局特例：fill 目录下无 -outline 后缀文件
        rc, urls, out_dir, _, errv = self._fetch("eva", "home-outline", style="fill")
        self.assertEqual(rc, 0)
        self.assertIn("/fill/svg/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_fill.svg"])


class TestBatchNames(FetchCase):
    """P1 批量 fetch：--name 逗号多值、去重、逐条统计、单条失败不中断批次。"""

    def test_name_comma_split_dedup_fetches_each(self):
        rc, urls, out_dir, outv, errv = self._fetch("lucide", "house, bell ,house")
        self.assertEqual(rc, 0)
        self.assertEqual(len(urls), 2)  # house 去重
        self.assertEqual(sorted(p.name for p in out_dir.iterdir()), ["bell.svg", "house.svg"])
        self.assertIn("2 wrote", outv)

    def test_batch_failure_does_not_abort_and_exits_1(self):
        def flaky(url, binary=False, timeout=30):
            if "bell" in url:
                raise SystemExit(f"[error] HTTP 404: {url}")
            return FAKE_SVG

        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        with mock.patch.object(xizhi, "http_get", side_effect=flaky), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args("lucide", "house,bell", out_dir))
        errv = err.getvalue()
        outv = out.getvalue()
        self.assertEqual(rc, 1)  # 有失败 → 显性非零
        self.assertIn("[fail] bell", errv)
        self.assertIn("1 failed, 1 wrote", outv)
        self.assertTrue((out_dir / "house.svg").is_file())  # 成功项已落盘
        self.assertFalse((out_dir / "bell.svg").exists())

    def test_empty_name_rejected(self):
        with self.assertRaises(SystemExit):
            self._fetch("lucide", " , ")

    def test_batch_size_cap(self):
        with self.assertRaises(SystemExit) as cm:
            self._fetch("lucide", ",".join(f"n{i}" for i in range(201)))
        self.assertIn("上限", str(cm.exception))


class TestVersionPin(FetchCase):
    """P3 可复现：--version 钉版本；默认 latest 行为不变；无版本概念的通道显性拒绝。"""

    def test_default_keeps_latest(self):
        rc, urls, _, _, errv = self._fetch("lucide", "house")
        self.assertEqual(rc, 0)
        self.assertIn("lucide-static@latest/icons/house.svg", urls[0])

    def test_version_substituted_into_url(self):
        rc, urls, _, _, errv = self._fetch("lucide", "house", version="0.511.0")
        self.assertEqual(rc, 0)
        self.assertIn("lucide-static@0.511.0/icons/house.svg", urls[0])

    def test_unversioned_channel_rejects_version(self):
        # heroicons 走 raw master 分支，无版本槽位
        with self.assertRaises(SystemExit) as cm:
            self._fetch("heroicons", "home", version="1.0.0")
        self.assertIn("--version", str(cm.exception))

    def test_version_invalid_chars_rejected(self):
        with self.assertRaises(SystemExit):
            self._fetch("lucide", "house", version="../etc")

    def test_no_template_has_floating_latest(self):
        # 迁移完备性：jsdelivr/npm 模板一律走 {version} 占位，禁止再硬编码 @latest
        for sid, s in xizhi.SETS.items():
            if isinstance(s.get("fetch"), str) and "cdn.jsdelivr.net/npm/" in s["fetch"]:
                self.assertIn("{version}", s["fetch"], sid)


class TestProvenanceHeader(FetchCase):
    """P3 溯源：SVG 产物注入 xizhi 头注释（来源/日期/许可），非 SVG 资产保持原样。"""

    def test_svg_gets_provenance_and_license(self):
        rc, urls, out_dir, _, errv = self._fetch("lucide", "house")
        self.assertEqual(rc, 0)
        content = (out_dir / "house.svg").read_bytes()
        self.assertTrue(content.startswith(b"<!-- xizhi: lucide:house via "))
        self.assertIn(b"license: ISC", content)
        self.assertIn(b"<svg/>", content)  # 原始内容完整保留在头注释之后

    def test_json_asset_untouched(self):
        rc, _, out_dir, _, errv = self._fetch("lordicon", "lupuorrc")
        self.assertEqual(rc, 0)
        self.assertEqual((out_dir / "lupuorrc.json").read_bytes(), FAKE_SVG)


class TestSafetyScan(FetchCase):
    """P7 供应链安全：SVG 落盘前黑名单扫描，命中拒绝落盘并中止批次。"""

    def test_scan_svg_patterns(self):
        self.assertEqual(xizhi.scan_svg(b"<svg><script>a</script></svg>"), ["<script"])
        self.assertTrue(any("on*" in h for h in xizhi.scan_svg(b'<svg onload="x"/>')))
        self.assertTrue(xizhi.scan_svg(b'<svg><a href="http://evil">x</a></svg>'))
        self.assertEqual(xizhi.scan_svg(b'<svg><rect fill="url(#g)"/></svg>'), [])  # 内部引用放行
        self.assertEqual(xizhi.scan_svg(b"<svg><path d='M0 0'/></svg>"), [])

    def test_poisoned_svg_rejected_and_aborts(self):
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        payload = b'<svg><script>alert(1)</script><rect stroke-width="2"/></svg>'
        with mock.patch.object(xizhi, "http_get", return_value=payload), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args("lucide", "evil,clean", out_dir))
        errv = err.getvalue()
        self.assertEqual(rc, 1)
        outv = out.getvalue()
        self.assertIn("[security]", errv)
        self.assertIn("<script", errv)
        self.assertFalse((out_dir / "evil.svg").exists())  # 拒绝落盘
        self.assertFalse((out_dir / "clean.svg").exists())  # 安全红线中止整批

    def test_clean_svg_passes_scan(self):
        rc, _, out_dir, _, errv = self._fetch("lucide", "house")
        self.assertEqual(rc, 0)
        self.assertTrue((out_dir / "house.svg").is_file())


class TestOutputAdapters(FetchCase):
    """P9 输出适配 opt-in：data-uri 编码与 --color 根标签受控替换，绝不全局改写。"""

    NESTED = (b'<svg xmlns="http://www.w3.org/2000/svg" stroke="currentColor" '
              b'width="24" height="24"><rect stroke-width="2" fill="currentColor"/></svg>')

    def test_data_uri_opt_in(self):
        import base64
        rc, _, out_dir, outv, errv = self._fetch("lucide", "house", format="data-uri")
        self.assertEqual(rc, 0)
        f = out_dir / "house.datauri.txt"
        self.assertTrue(f.is_file())
        content = f.read_text()
        self.assertTrue(content.startswith("data:image/svg+xml;base64,"))
        decoded = base64.b64decode(content.split(",", 1)[1])
        self.assertIn(b"<svg/>", decoded)  # 解码即原始（含溯源头的）SVG

    def test_data_uri_rejects_unknown_format(self):
        with self.assertRaises(SystemExit):
            self._fetch("lucide", "house", format="jsx")

    def test_color_rewrites_root_tag_only(self):
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        with mock.patch.object(xizhi, "http_get", return_value=self.NESTED), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO):
            rc = xizhi.cmd_fetch(_fetch_args("lucide", "house", out_dir, color="#f00"))
        errv = ""
        self.assertEqual(rc, 0)
        content = (out_dir / "house.svg").read_bytes()
        self.assertIn(b'<svg xmlns="http://www.w3.org/2000/svg" stroke="#f00"', content)
        # 嵌套元素的 currentColor 与 stroke-width 值原样保留（mcp-universal-icons 反例）
        self.assertIn(b'<rect stroke-width="2" fill="currentColor"/>', content)

    def test_color_without_root_currentcolor_warns_no_rewrite(self):
        svg = b'<svg xmlns="x"><path fill="currentColor"/></svg>'
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        with mock.patch.object(xizhi, "http_get", return_value=svg), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args("lucide", "house", out_dir, color="#f00"))
        errv = err.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("根标签", errv)
        self.assertIn(b'<path fill="currentColor"/>', (out_dir / "house.svg").read_bytes())


class TestIconifyBatch(FetchCase):
    """P1 iconify 合并端点：/{prefix}.json?icons=a,b,c + 多级别名解包 + not_found 显性失败。"""

    FIXTURE = {
        "prefix": "lucide",
        "width": 24, "height": 24,
        "icons": {"house": {"body": "<path d='M1'/>"}},
        "aliases": {"home": {"parent": "house"}},
        "not_found": ["zzz"],
    }

    def test_merged_endpoint_and_alias_unpack(self):
        fixture = json.dumps(self.FIXTURE).encode()
        rc, urls, out_dir, outv, errv = self._fetch(
            "iconify", "lucide:house,lucide:home",
            responses={"https://api.iconify.design/lucide.json?icons=house,home": fixture},
            sprite=True)
        self.assertEqual(rc, 0)
        self.assertEqual(len(urls), 1)
        self.assertIn("https://api.iconify.design/lucide.json?icons=house,home", urls[0])
        home = (out_dir / "lucide-home.svg").read_bytes()
        self.assertIn(b"<path d='M1'/>", home)  # 别名解包到 parent body
        self.assertIn(b'viewBox="0 0 24 24"', home)
        self.assertTrue((out_dir / "sprite.svg").is_file())
        self.assertIn(b'id="iconify-lucide-house"', (out_dir / "sprite.svg").read_bytes())

    def test_not_found_reported_as_fail_exit_1(self):
        rc, _, out_dir, outv, errv = self._fetch(
            "iconify", "lucide:house,lucide:zzz",
            responses={"https://api.iconify.design/lucide.json?icons=house,zzz":
                       json.dumps(self.FIXTURE).encode()})
        self.assertEqual(rc, 1)
        self.assertIn("[fail] lucide:zzz", errv)
        self.assertTrue((out_dir / "lucide-house.svg").is_file())

    def test_iconify_batch_requires_prefix_colon(self):
        with self.assertRaises(SystemExit) as cm:
            self._fetch("iconify", "house,home")
        self.assertIn("prefix:icon", str(cm.exception))

    def test_alias_cycle_rejected(self):
        cyc = {"prefix": "x", "icons": {"a": {"body": "<p/>"}},
               "aliases": {"b": {"parent": "c"}, "c": {"parent": "b"}}}
        with self.assertRaises(SystemExit) as cm:
            xizhi.iconify_json_to_svgs("x", cyc)
        self.assertIn("别名", str(cm.exception))

    def test_iconify_json_to_svgs_unit(self):
        svgs, missing = xizhi.iconify_json_to_svgs("lucide", self.FIXTURE)
        self.assertEqual(set(svgs), {"house", "home"})
        self.assertEqual(missing, ["zzz"])
        self.assertTrue(svgs["house"].startswith(b"<svg xmlns="))


class TestNodeModulesFallback(FetchCase):
    """P11 本地降级：在线失败时探测 node_modules/@iconify-json/<prefix>/icons.json。"""

    LOCAL_JSON = {"icons": {"house": {"body": "<path d='L'/>"}}, "width": 24, "height": 24}

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="xizhi-project-"))
        pkg = self.root / "node_modules" / "@iconify-json" / "lucide"
        pkg.mkdir(parents=True)
        (pkg / "icons.json").write_text(json.dumps(self.LOCAL_JSON), encoding="utf-8")
        self._old_cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._old_cwd)

    def test_online_failure_falls_back_to_local_package(self):
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))

        def offline(url, binary=False, timeout=30):
            raise SystemExit(f"[error] 请求失败 {url}: offline")

        with mock.patch.object(xizhi, "http_get", side_effect=offline), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args("iconify", "lucide:house", out_dir))
        errv = err.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("本地", errv)
        self.assertIn(b"<path d='L'/>", (out_dir / "lucide-house.svg").read_bytes())

    def test_no_local_package_gives_install_hint(self):
        import shutil
        shutil.rmtree(self.root / "node_modules")
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))

        def offline(url, binary=False, timeout=30):
            raise SystemExit(f"[error] 请求失败 {url}: offline")

        with mock.patch.object(xizhi, "http_get", side_effect=offline), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out, \
                mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            rc = xizhi.cmd_fetch(_fetch_args("iconify", "lucide:house", out_dir))
        errv = err.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn("npm i -D @iconify-json/lucide", errv)


class TestSprite(FetchCase):
    """P1 可选 --sprite：批量 SVG 包成 <symbol> 单文件，解析失败的图标显性跳过。"""

    def test_sprite_symbols_built_from_batch(self):
        svgs = {
            "a": b'<svg viewBox="0 0 24 24"><path d="A"/></svg>',
            "b": b'<svg viewBox="0 0 10 10"><circle r="1"/></svg>',
        }

        def getter(url, binary=False, timeout=30):
            return svgs[url.rsplit("/", 1)[1].split(".")[0]]

        rc, _, out_dir, outv, errv = self._fetch("lucide", "a,b", responses=getter, sprite=True)
        self.assertEqual(rc, 0)
        sprite = (out_dir / "sprite.svg").read_bytes()
        self.assertIn(b'<symbol id="lucide-a" viewBox="0 0 24 24"><path d="A"/></symbol>', sprite)
        self.assertIn(b'<symbol id="lucide-b" viewBox="0 0 10 10"><circle r="1"/></symbol>', sprite)

    def test_unparsable_svg_skipped_with_warn(self):
        svgs = {"a": b"<svg viewBox='0 0 24 24'><path/></svg>", "b": b"not a svg at all"}

        def getter(url, binary=False, timeout=30):
            return svgs[url.rsplit("/", 1)[1].split(".")[0]]

        rc, _, out_dir, outv, errv = self._fetch("lucide", "a,b", responses=getter, sprite=True)
        self.assertEqual(rc, 0)
        self.assertIn("[warn]", errv)
        sprite = (out_dir / "sprite.svg").read_bytes()
        self.assertIn(b"lucide-a", sprite)
        self.assertNotIn(b"lucide-b", sprite)



class TestGateFixes(FetchCase):
    """审查门禁修复回归：扫描强化 / 溯源消毒 / 路径逃逸围堵 / 下载上限 / phosphor 变体。"""

    def test_scan_hardened_variants(self):
        # 门禁实测穿透向量（实体编码/控制字符拆分/单引号/data URI），现已封堵
        self.assertTrue(xizhi.scan_svg(b'<svg><a href="&#106;&#97;vascript:x">y</a></svg>'))
        self.assertTrue(xizhi.scan_svg(b'<svg><a href="jav\tascript:x">y</a></svg>'))
        self.assertTrue(xizhi.scan_svg(b"<svg><a href='http://evil'>x</a></svg>"))
        self.assertTrue(xizhi.scan_svg(b'<svg><image href="data:text/html;base64,PHN2Zy8+"/></svg>'))
        self.assertTrue(xizhi.scan_svg(b"<svg><path fill='url(http://evil)'/></svg>"))
        # 安全复审 N2 补充向量：带引号 url('http) 与协议相对 href='//host
        self.assertTrue(xizhi.scan_svg(b'<svg><path style="fill:url(\'http://evil\')"/></svg>'))
        self.assertTrue(xizhi.scan_svg(b"<svg><a href='//evil.example'>x</a></svg>"))
        self.assertTrue(xizhi.scan_svg(b'<svg><path fill="url(//evil.example/x)"/></svg>'))
        self.assertEqual(xizhi.scan_svg(b'<svg xmlns="http://www.w3.org/2000/svg"/>'), [])

    def test_provenance_comment_injection_sanitized(self):
        # 双层防御：消毒层保证注释无法被 --> 提前闭合；复扫层拦截残留标记 → 显性拒绝
        rc, _, out_dir, outv, errv = self._fetch("lucide", "house--><script>alert(1)</script><!--")
        self.assertEqual(rc, 1)
        self.assertIn("[security]", errv)
        self.assertEqual(list(out_dir.iterdir()), [])

    def test_prepend_header_after_xml_decl(self):
        header = b"<!-- xizhi: t -->\n"
        out = xizhi._prepend_header(header, b'<?xml version="1.0"?><svg/>')
        self.assertTrue(out.startswith(b'<?xml version="1.0"?>'))
        self.assertIn(b"<!-- xizhi: t -->", out)
        self.assertEqual(xizhi._prepend_header(header, b"<svg/>"), header + b"<svg/>")

    def test_iconify_batch_traversal_contained(self):
        # 本地投毒包 icon 键带路径穿越 → 文件名消毒 + safe_dest，不逃逸 out_dir
        root = Path(tempfile.mkdtemp(prefix="xizhi-trav-"))
        pkg = root / "node_modules" / "@iconify-json" / "lucide"
        pkg.mkdir(parents=True)
        (pkg / "icons.json").write_text(json.dumps(
            {"icons": {"p/../../pwned": {"body": "<p/>"}}, "width": 24, "height": 24}),
            encoding="utf-8")
        old = os.getcwd()
        os.chdir(root)
        try:
            out_dir = Path(tempfile.mkdtemp(prefix="xizhi-trav-out-"))

            def offline(url, binary=False, timeout=30):
                raise SystemExit("[error] offline")

            with mock.patch.object(xizhi, "http_get", side_effect=offline), \
                    mock.patch("sys.stdout", new_callable=__import__("io").StringIO), \
                    mock.patch("sys.stderr", new_callable=__import__("io").StringIO):
                rc = xizhi.cmd_fetch(_fetch_args("iconify", "lucide:p/../../pwned,lucide:ok", out_dir))
        finally:
            os.chdir(old)
        self.assertEqual(rc, 1)  # lucide:ok 上游缺失 → 显性失败
        self.assertNotIn("pwned.svg", [p.name for p in root.iterdir()])  # 未逃逸到项目根
        self.assertIn("lucide-p-..-..-pwned.svg", [p.name for p in out_dir.iterdir()])

    def test_http_get_max_bytes_enforced(self):
        class R:
            status = 200

            def read(self, size=-1):
                return b"x" * 100

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: R()):
            with self.assertRaises(SystemExit) as cm:
                xizhi.http_get("https://x/y", binary=True, max_bytes=10)
        self.assertIn("上限", str(cm.exception))

    def test_phosphor_variant_url_and_name(self):
        # 上游命名（2.1.1 实测）：非 regular 字重带 -weight 后缀；regular 裸名
        rc, urls, out_dir, outv, errv = self._fetch("phosphor", "house", weight="fill")
        self.assertEqual(rc, 0)
        self.assertIn("/assets/fill/house-fill.svg", urls[0])
        self.assertIn("house_fill.svg", [p.name for p in out_dir.iterdir()])
        rc, urls, out_dir, outv, errv = self._fetch("phosphor", "house")
        self.assertIn("/assets/regular/house.svg", urls[0])
        self.assertIn("house.svg", [p.name for p in out_dir.iterdir()])

    def test_security_abort_prints_summary(self):
        svgs = {"house": FAKE_SVG, "evil": b"<svg><script>alert(1)</script></svg>"}

        def getter(url, binary=False, timeout=30):
            return svgs[url.rsplit("/", 1)[1].split(".")[0]]

        rc, _, out_dir, outv, errv = self._fetch("lucide", "house,evil", responses=getter)
        self.assertEqual(rc, 1)
        self.assertIn("安全红线中止：0 failed, 1 wrote", outv)  # 已写盘条目不丢统计
        self.assertFalse((out_dir / "evil.svg").exists())


class TestHarmonyosBatch(unittest.TestCase):
    """性能复审 HIGH 回归钉：ctx 复用后第 2 名起曾 UnboundLocalError（wght 未赋值）。
    用 fontTools 现造最小 TTF，全程离线（官方目录 mock 掉，走 None 降级）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import io
            from fontTools.fontBuilder import FontBuilder
            from fontTools.pens.ttGlyphPen import TTGlyphPen
        except ImportError:
            raise unittest.SkipTest("fontTools 未安装")

        def gpen():
            pen = TTGlyphPen(None)
            pen.moveTo((10, 10))
            pen.lineTo((500, 500))
            pen.lineTo((10, 500))
            pen.closePath()
            return pen.glyph()

        fb = FontBuilder(1000, isTTF=True)
        names = [".notdef", "house", "bell"]
        fb.setupGlyphOrder(names)
        fb.setupCharacterMap({0x68: "house", 0x62: "bell"})
        fb.setupGlyf({n: gpen() for n in names})
        fb.setupHorizontalMetrics({n: (600, 30) for n in names})
        fb.setupHorizontalHeader(ascent=800, descent=-200)
        fb.setupNameTable({"familyName": "XizhiTest", "styleName": "Regular"})
        fb.setupOS2(sTypoAscender=800, usWinAscent=800,
                    sTypoDescender=-200, usWinDescent=200)
        fb.setupPost()
        buf = io.BytesIO()
        fb.save(buf)
        cls.ttf = buf.getvalue()

    def test_batch_two_names_no_unbound(self):
        old = xizhi.CACHE_DIR
        xizhi.CACHE_DIR = Path(tempfile.mkdtemp(prefix="xizhi-hm-batch-"))
        (xizhi.CACHE_DIR / "HMSymbol.ttf").write_bytes(self.ttf)
        try:
            out_dir = Path(tempfile.mkdtemp(prefix="xizhi-hm-out-"))
            args = SimpleNamespace(set="harmonyos", name="ignored", out=str(out_dir),
                                   wght=None, refresh=False)

            def offline(url, binary=False, timeout=30):
                raise SystemExit("[error] offline")  # 官方目录不可达 → 降级 None

            with mock.patch.object(xizhi, "http_get", side_effect=offline), \
                    mock.patch("sys.stdout", new_callable=__import__("io").StringIO), \
                    mock.patch("sys.stderr", new_callable=__import__("io").StringIO):
                rc = xizhi._fetch_harmonyos_batch(args, ["house", "bell"])
            self.assertEqual(rc, 0)  # 修复前：第 2 名 UnboundLocalError（非 SystemExit 穿透）
            self.assertEqual(sorted(p.name for p in out_dir.iterdir()),
                             ["bell.svg", "house.svg"])
        finally:
            xizhi.CACHE_DIR = old


class TestRootSpanLinear(unittest.TestCase):
    """性能复审 MEDIUM 回归钉：<svg 重复流对抗输入上线性切片后须毫秒级。"""

    def test_adversarial_repeat_stream_fast_and_safe(self):
        import time
        blob = b"<svg" * 16384  # 64KB，无 '>'（旧交替正则实测 7.5s）
        t0 = time.time()
        self.assertIsNone(xizhi._svg_root_span(blob))
        elapsed = time.time() - t0
        self.assertLess(elapsed, 2.0)  # 线性实现 ~ms 级；2s 余量 100x

    def test_quoted_gt_handled(self):
        span = xizhi._svg_root_span(b'<svg title="a>b" width="24"><path/></svg>')
        self.assertEqual(span[2], b'<svg title="a>b" width="24">')
        self.assertEqual(span[1], len(b'<svg title="a>b" width="24">'))


if __name__ == "__main__":
    unittest.main()

