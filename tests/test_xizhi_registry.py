#!/usr/bin/env python3
"""xizhi.py SETS 注册表一致性冒烟（离线）——查找表是唯一的路由事实源（规则5）。

钉死：fetch 模板含 {name}、ref 文档存在、defaults ⊆ choices、
harmonyos 离线索引可解析、fetch None 仅 harmonyos 一家。
跑法：python3 -m pytest tests -q
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 必须在 import xizhi 之前重定向缓存目录，绝不碰真实 ~/.cache/xizhi
os.environ.setdefault("XIZHI_CACHE", tempfile.mkdtemp(prefix="xizhi-cache-test-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import xizhi  # noqa: E402

SKILL_ROOT = Path(xizhi.SKILL_ROOT)
VALID_INDEX_KINDS = {
    "local-file", "url-plain", "url-flat-npm", "url-json-lucide",
    "iconify-search", "none",
}


class TestSetsRegistry(unittest.TestCase):
    def test_registry_not_empty(self):
        self.assertGreaterEqual(len(xizhi.SETS), 20)

    def test_required_fields_present(self):
        for sid, s in xizhi.SETS.items():
            with self.subTest(set=sid):
                self.assertTrue(s.get("label"), sid)
                self.assertTrue(s.get("desc"), sid)
                self.assertTrue(s.get("license"), sid)
                self.assertTrue(s.get("when"), sid)
                self.assertIn("fetch", s)
                self.assertTrue(s.get("ext"), sid)
                self.assertIn(s["index"]["kind"], VALID_INDEX_KINDS)
                self.assertTrue(s.get("ref"), sid)

    def test_fetch_template_has_name_placeholder(self):
        # 除 harmonyos（专用字体通道，fetch=None）外，模板都必须含 {name}
        for sid, s in xizhi.SETS.items():
            if sid == "harmonyos":
                self.assertIsNone(s["fetch"], sid)
                self.assertIn("channels", s, sid)
            else:
                self.assertIsInstance(s["fetch"], str, sid)
                self.assertIn("{name}", s["fetch"], sid)
                self.assertTrue(s["fetch"].startswith("https://"), sid)

    def test_ref_documents_exist(self):
        for sid, s in xizhi.SETS.items():
            self.assertTrue((SKILL_ROOT / s["ref"]).is_file(),
                            f"{sid}: {s['ref']} 不存在")

    def test_defaults_are_subset_of_choices(self):
        for sid, s in xizhi.SETS.items():
            defaults = s.get("defaults") or {}
            choices = s.get("choices") or {}
            self.assertEqual(set(defaults), set(choices),
                             f"{sid}: defaults 与 choices 键不一致")
            for var, val in defaults.items():
                self.assertIn(val, choices[var], f"{sid}.{var}={val}")

    def test_flat_npm_index_fields(self):
        for sid, s in xizhi.SETS.items():
            idx = s["index"]
            if idx["kind"] == "url-flat-npm":
                self.assertTrue(idx.get("pkg"), sid)
                self.assertTrue(idx["sub"].startswith("/"), sid)
                self.assertTrue(idx["suffix"].startswith("."), sid)

    def test_endpoints_are_https(self):
        for sid, s in xizhi.SETS.items():
            if isinstance(s.get("fetch"), str):
                self.assertTrue(s["fetch"].startswith("https://"), sid)
            for url in (s.get("channels") or {}).values():
                self.assertTrue(url.startswith("https://"), sid)


class TestHarmonyosLocalIndex(unittest.TestCase):
    def test_index_file_parseable(self):
        names = xizhi.build_names("harmonyos", refresh=False)
        self.assertIsInstance(names, list)
        self.assertGreater(len(names), 2000)  # SDK 清单 2761 个
        self.assertTrue(all(n and not n.startswith("#") for n in names))
        self.assertIn("phone", names)  # 抽样锚点（真实存在的名称）
        self.assertIn("arrow_bounce_right", names)

    def test_unknown_index_kind_exits(self):
        broken = dict(xizhi.SETS["lucide"])
        broken["index"] = {"kind": "bogus-kind"}
        old = xizhi.SETS["lucide"]
        xizhi.SETS["lucide"] = broken
        try:
            with self.assertRaises(SystemExit):
                xizhi.build_names("lucide", refresh=False)
        finally:
            xizhi.SETS["lucide"] = old


if __name__ == "__main__":
    unittest.main()
