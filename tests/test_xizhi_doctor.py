#!/usr/bin/env python3
"""xizhi.py doctor 巡检冒烟（离线）——探针清单构建与三态判定的纯逻辑。

钉死：探针清单覆盖 fetch/index/鸿蒙双通道/批量合并端点、
--set 过滤、run_probes 的 ✅/❌ 统计与退出码、light 探针 HEAD→Range 回退。
真实网络探针不打（SKIPPED.md 记录），跑法：python3 -m pytest tests -q
"""
import io
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("XIZHI_CACHE", tempfile.mkdtemp(prefix="xizhi-cache-test-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import xizhi  # noqa: E402


class TestProbeList(unittest.TestCase):
    def test_probe_list_covers_key_channels(self):
        probes = xizhi.build_probe_list()
        labels = {p["label"] for p in probes}
        self.assertIn("lucide fetch", labels)
        self.assertIn("harmonyos name_map", labels)
        self.assertIn("harmonyos font", labels)
        self.assertIn("iconify batch", labels)  # P1 批量合并端点也在巡检范围
        self.assertTrue(any("index" in l for l in labels))

    def test_probe_list_set_filter(self):
        probes = xizhi.build_probe_list("lucide")
        self.assertTrue(probes)
        self.assertTrue(all("lucide" in p["label"] for p in probes))

    def test_probe_urls_are_https(self):
        for p in xizhi.build_probe_list():
            self.assertTrue(p["url"].startswith("https://"), p["label"])

    def test_unprobed_fetch_sets_listed(self):
        # 无验证探针名的套件显性列出（只巡检索引），不静默跳过
        unprobed = xizhi.unprobed_fetch_sets()
        self.assertIn("remix", unprobed)
        self.assertNotIn("lucide", unprobed)
        self.assertNotIn("harmonyos", unprobed)  # fetch=None 不属于此列


class TestRunProbes(unittest.TestCase):
    def test_all_up(self):
        probes = [{"label": "a", "url": "https://a", "timeout": 1}]
        lines, down = xizhi.run_probes(probes, lambda url, timeout=10, light=False: None)
        self.assertEqual(down, 0)
        self.assertIn("✅", lines[0])

    def test_down_counted_and_reported(self):
        probes = [{"label": "a", "url": "https://a"}, {"label": "b", "url": "https://b"}]

        def probe(url, timeout=10, light=False):
            if url == "https://b":
                raise SystemExit("[error] HTTP 404")

        lines, down = xizhi.run_probes(probes, probe)
        self.assertEqual(down, 1)
        joined = "\n".join(lines)
        self.assertIn("❌", joined)
        self.assertIn("404", joined)


class TestCmdDoctor(unittest.TestCase):
    def test_exit_1_when_down(self):
        probes = [{"label": "x", "url": "https://x"}]
        with mock.patch.object(xizhi, "build_probe_list", return_value=probes), \
                mock.patch.object(xizhi, "_probe_url", side_effect=SystemExit("[error] down")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = xizhi.cmd_doctor(SimpleNamespace(set=None))
        self.assertEqual(rc, 1)
        self.assertIn("1 channel(s) down", out.getvalue())

    def test_exit_0_when_all_up(self):
        probes = [{"label": "x", "url": "https://x"}]
        with mock.patch.object(xizhi, "build_probe_list", return_value=probes), \
                mock.patch.object(xizhi, "_probe_url", return_value=None), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = xizhi.cmd_doctor(SimpleNamespace(set=None))
        self.assertEqual(rc, 0)
        self.assertIn("正常", out.getvalue())

    def test_unprobed_sets_printed_not_silent(self):
        with mock.patch.object(xizhi, "build_probe_list", return_value=[]), \
                mock.patch.object(xizhi, "_probe_url", return_value=None), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            xizhi.cmd_doctor(SimpleNamespace(set=None))
        self.assertIn("remix", out.getvalue())  # 无探针名套件显性列出


class TestProbeLight(unittest.TestCase):
    """light 探针（大文件零下载）：HEAD 200 直接过；HEAD 被拒回退 Range 单字节 GET。"""

    class _R:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def test_head_200_passes_without_download(self):
        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: self._R(200)):
            xizhi._probe_url("https://big/font.ttf", timeout=5, light=True)

    def test_head_405_falls_back_to_range_get(self):
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.get_method())
            return self._R(405) if req.get_method() == "HEAD" else self._R(206)

        with mock.patch.object(xizhi.urllib.request, "urlopen", urlopen):
            xizhi._probe_url("https://big/font.ttf", timeout=5, light=True)
        self.assertEqual(calls, ["HEAD", "GET"])

    def test_both_refused_exits(self):
        def urlopen(req, timeout=None):
            return self._R(403)

        with mock.patch.object(xizhi.urllib.request, "urlopen", urlopen):
            with self.assertRaises(SystemExit):
                xizhi._probe_url("https://big/font.ttf", timeout=5, light=True)


class TestGateFixes(unittest.TestCase):
    """门禁修复回归：常量表一致性 + doctor 变体探针（phosphor 死链假绿教训）。"""

    def test_probe_icons_keys_subset_of_sets(self):
        self.assertTrue(set(xizhi.PROBE_ICONS) <= set(xizhi.SETS))

    def test_known_iconify_prefixes_subset_of_sets(self):
        self.assertTrue(xizhi._KNOWN_ICONIFY_PREFIXES <= set(xizhi.SETS))

    def test_variant_probes_cover_non_defaults(self):
        probes = xizhi.build_probe_list()
        by = {p["label"]: p["url"] for p in probes}
        self.assertIn("phosphor fetch[weight=fill]", by)
        self.assertIn("house-fill.svg", by["phosphor fetch[weight=fill]"])  # 上游 2.1.1 命名
        self.assertIn("iconoir fetch[style=solid]", by)
        self.assertIn("adobe-after-effects", by["iconoir fetch[style=solid]"])  # solid 只有品牌图标
        self.assertIn("material-symbols fetch[fill=fill1]", by)
        self.assertNotIn("material-symbols fetch[fill=_fill1]", by)  # legacy 归一后按 URL 去重

    def test_run_probes_preserves_order_under_parallelism(self):
        probes = [{"label": f"p{i}", "url": f"https://x/{i}"} for i in range(20)]

        def probe(url, timeout=10, light=False):
            return None  # 全部健康；顺序仍须与清单一致

        lines, down = xizhi.run_probes(probes, probe)
        self.assertEqual(down, 0)
        self.assertEqual([f"p{i}" for i in range(20)],
                         [l.split()[1] for l in lines])


if __name__ == "__main__":
    unittest.main()
