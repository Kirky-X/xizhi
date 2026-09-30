#!/usr/bin/env python3
"""xizhi.py CLI 冒烟（离线子进程）——--help / sets / describe / 无索引搜索。

只挑不打网络的子命令路径；在线通道（lucide 搜索、fetch 下载、iconify）
见 SKIPPED.md。XIZHI_CACHE 重定向，绝不碰真实缓存。
跑法：python3 -m pytest tests -q
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "xizhi.py"


def _run(*args):
    env = dict(os.environ)
    env["XIZHI_CACHE"] = tempfile.mkdtemp(prefix="xizhi-cli-test-")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60, env=env,
    )


class TestCliSmoke(unittest.TestCase):
    def test_help(self):
        r = _run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("sets", r.stdout)
        self.assertIn("search", r.stdout)
        self.assertIn("fetch", r.stdout)

    def test_no_subcommand_exits(self):
        r = _run()
        self.assertEqual(r.returncode, 2)  # argparse: required subcommand

    def test_sets_lists_registry(self):
        r = _run("sets")
        self.assertEqual(r.returncode, 0, r.stderr)
        for sid in ("lucide", "material-symbols", "harmonyos", "iconify"):
            self.assertIn(sid, r.stdout)

    def test_describe_web_set(self):
        r = _run("describe", "--set", "lucide")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lucide", r.stdout)
        self.assertIn("ISC", r.stdout)
        self.assertIn("https://", r.stdout)
        self.assertIn("references/lucide.md", r.stdout)

    def test_describe_harmonyos_shows_offline_index(self):
        r = _run("describe", "--set", "harmonyos")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("离线索引", r.stdout)
        # 离线索引计数来自 data 文件，必须 >2000（冒烟锚点）
        import re
        m = re.search(r"离线索引: (\d+) 个名称", r.stdout)
        self.assertIsNotNone(m)
        self.assertGreater(int(m.group(1)), 2000)

    def test_describe_invalid_set_exits(self):
        r = _run("describe", "--set", "no-such-set")
        self.assertEqual(r.returncode, 2)

    def test_search_none_index_set_offline_ok(self):
        # lordicon 无名称索引 → 打印挑选指引即返回 0，全程离线
        r = _run("search", "--set", "lordicon", "--query", "loader")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("无名称索引", r.stdout)
        self.assertIn("lordicon.com", r.stdout)

    def test_fetch_help_lists_variant_flags(self):
        r = _run("fetch", "--help")
        self.assertEqual(r.returncode, 0)
        for flag in ("--style", "--size", "--fill", "--variant", "--weight", "--wght"):
            self.assertIn(flag, r.stdout)


if __name__ == "__main__":
    unittest.main()
