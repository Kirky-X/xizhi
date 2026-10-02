#!/usr/bin/env python3
"""xizhi.py search 逻辑冒烟（离线）——排序/命中/降级全部不打网络。

钉死：exact > prefix > contains 排序与 limit、[miss] 退出码 1、
lordicon 无索引直接返回 0、harmonyos 双源搜索的离线降级路径。
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


def _search_args(query, limit=30, refresh=False):
    return SimpleNamespace(set="lucide", query=query, limit=limit, refresh=refresh)


class TestSearchRanking(unittest.TestCase):
    """build_names mock 成固定清单，只测 cmd_search 的纯排序/输出逻辑。"""

    NAMES = ["home", "home-ant", "Workhome", "homesmith", "cabin"]

    def _run(self, query, limit=30):
        with mock.patch.object(xizhi, "build_names", return_value=list(self.NAMES)), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(_search_args(query, limit))
        return rc, out.getvalue()

    def test_exact_first(self):
        rc, out = self._run("home")
        self.assertEqual(rc, 0)
        lines = [l for l in out.splitlines() if l.startswith("  ")]
        self.assertEqual(lines[0].split()[0], "home")  # exact 恒第一

    def test_ranking_order(self):
        rc, out = self._run("home")
        names = [l.split()[0] for l in out.splitlines() if l.startswith("  ")]
        # exact("home") > prefix("home-ant", "homesmith") > contains("Workhome")
        self.assertEqual(names, ["home", "home-ant", "homesmith", "Workhome"])

    def test_limit_applies_after_ranking(self):
        rc, out = self._run("home", limit=2)
        names = [l.split()[0] for l in out.splitlines() if l.startswith("  ")]
        self.assertEqual(names, ["home", "home-ant"])  # 截断的是排序后结果

    def test_miss_exits_1_with_hint(self):
        rc, out = self._run("zzz-no-such-icon")
        self.assertEqual(rc, 1)
        self.assertIn("[miss]", out)
        self.assertIn("换近义词", out)

    def test_case_insensitive(self):
        rc, _ = self._run("CABIN")
        self.assertEqual(rc, 0)

    def test_lucide_alias_tag_lines(self):
        # lucide 索引的别名行格式 "house\thome"：tag 命中要归到 tag_exact/taghits
        names = ["house\thome", "cabin"]
        with mock.patch.object(xizhi, "build_names", return_value=names), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(_search_args("home"))
        self.assertEqual(rc, 0)
        self.assertIn("tag=home", out.getvalue())


class TestNoIndexSets(unittest.TestCase):
    def test_none_kind_returns_0_with_hint(self):
        with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(SimpleNamespace(set="lordicon", query="loader",
                                                  limit=30, refresh=False))
        self.assertEqual(rc, 0)
        self.assertIn("无名称索引", out.getvalue())
        self.assertIn("lordicon.com", out.getvalue())


class TestHarmonyosSearch(unittest.TestCase):
    """双源搜索：官方目录（缓存）+ 离线 SDK 清单。CACHE_DIR 重定向到 tmp。"""

    def setUp(self):
        self._old_cache = xizhi.CACHE_DIR
        self.cache = Path(tempfile.mkdtemp(prefix="xizhi-hm-"))
        xizhi.CACHE_DIR = self.cache

    def tearDown(self):
        xizhi.CACHE_DIR = self._old_cache

    OFFICIAL = {
        "data": {
            "communication": [
                {"name": "phone", "name_cn": "电话", "unicode": "e601",
                 "support_version": "5.0.0", "category": "communication"},
                {"name": "mail", "name_cn": "邮件", "unicode": "e602",
                 "support_version": "5.0.0", "category": "communication"},
            ]
        }
    }

    def _sdk(self):
        return xizhi.build_names("harmonyos", refresh=False)

    def test_offline_fallback_uses_sdk_list(self):
        # 官方目录不可达（http_get 抛 SystemExit）且无缓存 → 降级纯 SDK 清单
        # 全程 mock http_get：不依赖本机是否真实联网（有网也不能走官方目录）
        args = SimpleNamespace(set="harmonyos", query="phone", limit=30, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=SystemExit("[error] offline")):
            self.assertIsNone(xizhi.harmonyos_official(refresh=False))
            with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
                rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 0)
        self.assertIn("离线 SDK 清单", out.getvalue())
        self.assertIn("phone", out.getvalue())

    def test_offline_fallback_miss_exits_1(self):
        with mock.patch.object(xizhi, "http_get",
                               side_effect=SystemExit("[error] offline")):
            args = SimpleNamespace(set="harmonyos", query="zzz-nothing",
                                   limit=30, refresh=False)
            with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
                rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 1)
        self.assertIn("[miss]", out.getvalue())

    def test_dual_source_with_official_cache(self):
        # 官方目录写入缓存（新鲜 TTL 内）→ 命中显示中文名/unicode，不再联网
        (self.cache / "harmonyos-name-map.json").write_text(
            json.dumps(self.OFFICIAL, ensure_ascii=False), encoding="utf-8")
        args = SimpleNamespace(set="harmonyos", query="电话", limit=30, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=AssertionError("缓存新鲜时不允许联网")):
            with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
                rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 0)
        outv = out.getvalue()
        self.assertIn("[官方] 电话", outv)
        self.assertIn("e601", outv)
        self.assertIn("[官方]", outv)

    def test_exact_hit_ranked_first(self):
        (self.cache / "harmonyos-name-map.json").write_text(
            json.dumps(self.OFFICIAL, ensure_ascii=False), encoding="utf-8")
        args = SimpleNamespace(set="harmonyos", query="mail", limit=30, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=AssertionError("缓存新鲜时不允许联网")):
            with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
                rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 0)
        first = [l for l in out.getvalue().splitlines() if l.startswith("  ")][0]
        self.assertEqual(first.split()[0], "mail")  # exact 插到最前


class TestIconifySearchOfflineGuard(unittest.TestCase):
    def test_iconify_search_hits_network_directly(self):
        # iconify 聚合搜索无离线路径——确认它会走 http_get（网络层，SKIPPED.md 记录）
        args = SimpleNamespace(set="iconify", query="home", limit=5, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=SystemExit("[error] offline")) as m:
            with self.assertRaises(SystemExit):
                xizhi.cmd_search(args)
        self.assertTrue(m.called)


class TestAliasExpansion(unittest.TestCase):
    """P4：ALIAS_GROUPS 同义词组（确定性查表）——只扩查询词，绝不跨套件改写名称。"""

    NAMES = ["bell", "house", "cabin"]

    def _run(self, query, names=None, set_id="lucide"):
        with mock.patch.object(xizhi, "build_names", return_value=list(names or self.NAMES)), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(SimpleNamespace(set=set_id, query=query,
                                                  limit=30, refresh=False))
        return rc, out.getvalue()

    def test_expand_query_terms(self):
        terms = xizhi.expand_query("铃铛")
        self.assertEqual(terms[0], "铃铛")  # 原词恒在最前
        self.assertIn("bell", terms)
        self.assertIn("鈴鐺", terms)  # 繁体覆盖

    def test_unmatched_query_returns_single_term(self):
        self.assertEqual(xizhi.expand_query("zzz"), ["zzz"])

    def test_alias_hit_via_expansion(self):
        rc, out = self._run("鈴鐺")  # 索引只有 bell，经同义词组命中
        self.assertEqual(rc, 0)
        self.assertIn("bell", out)
        self.assertIn("别名", out)

    def test_direct_hits_rank_before_alias_hits(self):
        rc, out = self._run("bell", names=["bell", "alarm"])
        self.assertEqual(rc, 0)
        first = [l for l in out.splitlines() if l.startswith("  ")][0]
        self.assertIn("bell", first)

    def test_alias_scope_never_rewrites_names(self):
        # 套件作用域纪律（Aria-Icons 全局别名致 404 的反例）：扩词只加查询，不改原词
        self.assertEqual(xizhi.expand_query("home")[0], "home")
        rc, out = self._run("home", names=["home"], set_id="tabler")
        self.assertEqual(rc, 0)
        self.assertNotIn("house", out)  # 索引没有就不出现改写名


class TestMissCandidates(unittest.TestCase):
    """P4：miss 前给近似名候选；P8：miss 附自取证直链。"""

    NAMES = ["home", "house", "horse", "cabin"]

    def _run(self, query, set_id="lucide"):
        with mock.patch.object(xizhi, "build_names", return_value=list(self.NAMES)), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(SimpleNamespace(set=set_id, query=query,
                                                  limit=30, refresh=False))
        return rc, out.getvalue()

    def test_close_matches_on_miss(self):
        rc, out = self._run("hose")  # 拼写近似 house
        self.assertEqual(rc, 1)
        self.assertIn("[miss]", out)
        self.assertIn("近似", out)
        self.assertIn("house", out)

    def test_miss_direct_url_hint(self):
        rc, out = self._run("zzz-none", set_id="lucide")
        self.assertEqual(rc, 1)
        self.assertIn("lucide-static@latest/icons/zzz-none.svg", out)  # 模板拼出的直链


class TestHitFooter(unittest.TestCase):
    """P8 matched as 溯源标注 + P1 批量下载提示。"""

    def _run(self, query, names):
        with mock.patch.object(xizhi, "build_names", return_value=names), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(SimpleNamespace(set="lucide", query=query,
                                                  limit=30, refresh=False))
        return rc, out.getvalue()

    def test_matched_as_on_tag_hit(self):
        rc, out = self._run("home", ["house\thome", "cabin"])
        self.assertEqual(rc, 0)
        self.assertIn("matched as", out)
        self.assertIn("house", out)
        self.assertIn("tag=home", out)  # 原有 tag 标注保留

    def test_batch_hint_on_hit(self):
        rc, out = self._run("home", ["home", "homesmith"])
        self.assertEqual(rc, 0)
        self.assertIn("批量", out)


class TestIconifyThirdPartyWarning(unittest.TestCase):
    """P7：iconify 兜底搜索中非一等收录的 prefix 附第三方上游警示。"""

    def test_third_party_prefix_flagged(self):
        search_payload = json.dumps({"icons": ["lucide:house", "someobs:thing"]}).encode()
        col_payload = json.dumps({"collections": {
            "lucide": {"license": {"title": "ISC"}},
            "someobs": {"license": {"title": "MIT"}}}}).encode()
        args = SimpleNamespace(set="iconify", query="house", limit=5, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=[search_payload, col_payload]), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 0)
        outv = out.getvalue()
        self.assertIn("someobs", outv)
        self.assertIn("一等收录", outv)  # 警示指向非收录套件


class TestHarmonyosAliasSearch(unittest.TestCase):
    """P4：鸿蒙繁体/别称经同义词组命中官方目录中文名。"""

    def setUp(self):
        self._old_cache = xizhi.CACHE_DIR
        xizhi.CACHE_DIR = Path(tempfile.mkdtemp(prefix="xizhi-hm-alias-"))
        (xizhi.CACHE_DIR / "harmonyos-name-map.json").write_text(json.dumps({
            "data": {"alerts": [{"name": "bell", "name_cn": "铃铛", "unicode": "f01d5",
                                 "support_version": "5.0.0", "category": "alerts"}]}
        }, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        xizhi.CACHE_DIR = self._old_cache

    def test_traditional_chinese_hits_official_entry(self):
        args = SimpleNamespace(set="harmonyos", query="鈴鐺", limit=30, refresh=False)
        with mock.patch.object(xizhi, "http_get",
                               side_effect=AssertionError("缓存新鲜时不允许联网")), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            rc = xizhi.cmd_search(args)
        self.assertEqual(rc, 0)
        self.assertIn("bell", out.getvalue())


if __name__ == "__main__":
    unittest.main()
