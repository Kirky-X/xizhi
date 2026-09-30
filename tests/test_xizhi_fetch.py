#!/usr/bin/env python3
"""xizhi.py fetch URL 模板冒烟（离线）——http_get mock 掉，只验证模板组装与落盘命名。

钉死：{name} 替换、变体默认值不产生后缀、非默认变体加后缀防覆盖、
非法变体显性拒绝、eva fill 去 -outline、iconify prefix:name → 路径。
跑法：python3 -m pytest tests -q
"""
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
                  refresh=False)
    fields.update(vars_)
    return SimpleNamespace(**fields)


class FetchCase(unittest.TestCase):
    def _fetch(self, set_id, name, **vars_):
        """跑 cmd_fetch，返回 (捕获的 URL 列表, 输出目录, stdout)。"""
        out_dir = Path(tempfile.mkdtemp(prefix="xizhi-fetch-"))
        captured = []

        def fake_http_get(url, binary=False, timeout=30):
            captured.append(url)
            return FAKE_SVG

        with mock.patch.object(xizhi, "http_get", side_effect=fake_http_get), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_fetch(_fetch_args(set_id, name, out_dir, **vars_))
        return rc, captured, out_dir, out.getvalue()


class TestPlainTemplates(FetchCase):
    def test_lucide_plain_name(self):
        rc, urls, out_dir, outv = self._fetch("lucide", "house")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/house.svg"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["house.svg"])

    def test_feather(self):
        rc, urls, out_dir, _ = self._fetch("feather", "home")
        self.assertEqual(rc, 0)
        self.assertIn("feather-icons@latest/dist/icons/home.svg", urls[0])

    def test_iconify_prefix_colon_becomes_path(self):
        rc, urls, out_dir, _ = self._fetch("iconify", "mdi:home")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://api.iconify.design/mdi/home.svg"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["mdi-home.svg"])

    def test_lordicon_json_ext(self):
        rc, urls, out_dir, outv = self._fetch("lordicon", "lupuorrc")
        self.assertEqual(rc, 0)
        self.assertEqual(urls, ["https://cdn.lordicon.com/lupuorrc.json"])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["lupuorrc.json"])
        self.assertIn("lord-icon", outv)  # 用法提示

    def test_morphicons_no_double_ext(self):
        rc, urls, out_dir, _ = self._fetch("morphicons", "dom.js")
        self.assertEqual(rc, 0)
        self.assertTrue(urls[0].endswith("/dist/dom.js"))
        self.assertEqual([p.name for p in out_dir.iterdir()], ["dom.js"])


class TestVariantDefaults(FetchCase):
    def test_tabler_default_style_no_suffix(self):
        rc, urls, out_dir, _ = self._fetch("tabler", "home")
        self.assertEqual(rc, 0)
        self.assertIn("/icons/outline/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])

    def test_tabler_non_default_style_gets_suffix(self):
        rc, urls, out_dir, _ = self._fetch("tabler", "home", style="filled")
        self.assertEqual(rc, 0)
        self.assertIn("/icons/filled/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_filled.svg"])

    def test_illegal_variant_rejected(self):
        with self.assertRaises(SystemExit) as cm:
            self._fetch("tabler", "home", style="bogus")
        self.assertIn("非法", str(cm.exception))

    def test_material_symbols_defaults(self):
        rc, urls, out_dir, _ = self._fetch("material-symbols", "home")
        self.assertEqual(rc, 0)
        self.assertEqual(
            urls[0],
            "https://raw.githubusercontent.com/google/material-design-icons/master/"
            "symbols/web/home/materialsymbolsrounded/home_24px.svg")
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])

    def test_material_symbols_fill_variant(self):
        rc, urls, out_dir, _ = self._fetch("material-symbols", "home", fill="_fill1")
        self.assertEqual(rc, 0)
        self.assertIn("home_fill1_24px.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_fill1.svg"])

    def test_heroicons_default_and_custom_variant(self):
        rc, urls, out_dir, _ = self._fetch("heroicons", "home")
        self.assertIn("/optimized/24/outline/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home.svg"])
        rc, urls, out_dir, _ = self._fetch("heroicons", "home", variant="16/solid")
        self.assertIn("/optimized/16/solid/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_16-solid.svg"])

    def test_eva_fill_strips_outline_suffix(self):
        # eva 布局特例：fill 目录下无 -outline 后缀文件
        rc, urls, out_dir, _ = self._fetch("eva", "home-outline", style="fill")
        self.assertEqual(rc, 0)
        self.assertIn("/fill/svg/home.svg", urls[0])
        self.assertEqual([p.name for p in out_dir.iterdir()], ["home_fill.svg"])


if __name__ == "__main__":
    unittest.main()
