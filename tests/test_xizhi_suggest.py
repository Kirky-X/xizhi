#!/usr/bin/env python3
"""xizhi.py suggest 项目实况选型冒烟（离线）——确定性依赖扫描，无模型参与（规则5）。

钉死：package.json 依赖 ∩ library_hints、react-icons 子路径 import 计数、
pubspec.yaml 行匹配、node_modules 剪枝、注册表一致性、命令输出。
跑法：python3 -m pytest tests -q
"""
import io
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


class TestScanProject(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="xizhi-suggest-"))

    def _pkg(self, deps):
        (self.root / "package.json").write_text(
            json.dumps({"dependencies": deps}), encoding="utf-8")

    def test_package_json_dep_and_react_icons_imports(self):
        self._pkg({"lucide-react": "^0.511.0", "react-icons": "^5.0.0"})
        src = self.root / "src"
        src.mkdir()
        (src / "App.tsx").write_text(
            'import { A } from "react-icons/lu";\n'
            'import { B } from "react-icons/lu";\n'
            'import { C } from "react-icons/md";\n', encoding="utf-8")
        findings = xizhi.scan_project(self.root)
        by = {sid: (count, why) for sid, count, why in findings}
        self.assertEqual(by["lucide"][0], 3)  # 依赖 1（lucide-react）+ import 2（react-icons/lu）
        self.assertEqual(by["material-symbols"][0], 1)  # react-icons/md
        self.assertEqual(findings[0][0], "lucide")  # 按用量降序

    def test_pubspec_yaml_line_match(self):
        (self.root / "pubspec.yaml").write_text(
            "dependencies:\n  material_symbols_icons: ^2.0.0\n", encoding="utf-8")
        findings = xizhi.scan_project(self.root)
        self.assertEqual([sid for sid, _, _ in findings], ["material-symbols"])

    def test_no_matches_empty(self):
        self.assertEqual(xizhi.scan_project(self.root), [])

    def test_node_modules_pruned(self):
        self._pkg({"react-icons": "^5.0.0"})
        nm = self.root / "node_modules" / "x"
        nm.mkdir(parents=True)
        (nm / "chunk.js").write_text('from "react-icons/lu"' * 10, encoding="utf-8")
        findings = xizhi.scan_project(self.root)
        by = {sid: count for sid, count, _ in findings}
        self.assertNotIn("lucide", by)  # node_modules 内的 import 不计用量

    def test_broken_package_json_warns_not_crashes(self):
        (self.root / "package.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(xizhi.scan_project(self.root), [])


class TestRegistryConsistency(unittest.TestCase):
    def test_react_icons_subpath_targets_exist(self):
        self.assertTrue(set(xizhi.REACT_ICONS_SUBPATH.values()) <= set(xizhi.SETS))

    def test_pubspec_hint_targets_exist(self):
        self.assertTrue(set(xizhi.PUBSPEC_HINTS.values()) <= set(xizhi.SETS))

    def test_library_hints_keys_exist(self):
        self.assertTrue(set(xizhi.LIBRARY_HINTS) <= set(xizhi.SETS))
        for sid, hints in xizhi.LIBRARY_HINTS.items():
            self.assertTrue(hints, sid)
            self.assertTrue(all(isinstance(h, str) and h for h in hints), sid)


class TestCmdSuggest(unittest.TestCase):
    def test_hits_printed_with_next_command(self):
        root = Path(tempfile.mkdtemp(prefix="xizhi-suggest-"))
        (root / "package.json").write_text(
            json.dumps({"dependencies": {"lucide-react": "^0.511.0"}}), encoding="utf-8")
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = xizhi.cmd_suggest(SimpleNamespace(dir=str(root)))
        self.assertEqual(rc, 0)
        outv = out.getvalue()
        self.assertIn("lucide", outv)
        self.assertIn("search --set lucide", outv)  # 命中即给下一步命令（闭环）
        self.assertIn("按场景", outv)  # 完整选型表仍附在后

    def test_no_hits_falls_back_to_sets_table(self):
        root = Path(tempfile.mkdtemp(prefix="xizhi-suggest-"))
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = xizhi.cmd_suggest(SimpleNamespace(dir=str(root)))
        self.assertEqual(rc, 0)
        self.assertIn("lucide", out.getvalue())  # cmd_sets 兜底表格

    def test_missing_dir_exits(self):
        with self.assertRaises(SystemExit):
            xizhi.cmd_suggest(SimpleNamespace(dir="/no/such/dir-xizhi"))


if __name__ == "__main__":
    unittest.main()
