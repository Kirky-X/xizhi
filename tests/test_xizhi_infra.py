#!/usr/bin/env python3
"""xizhi.py HTTP 基础设施与缓存冒烟（离线）——显性失败契约 + 缓存 TTL。

钉死：非 200 / HTML 响应 / 网络异常都显性 SystemExit（绝不静默）、
cached_names 在 TTL 内命中缓存（builder 只跑一次）、过期重建。
跑法：python3 -m pytest tests -q
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

os.environ.setdefault("XIZHI_CACHE", tempfile.mkdtemp(prefix="xizhi-cache-test-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import xizhi  # noqa: E402


class _FakeResp:
    def __init__(self, status=200, payload=b"ok"):
        self.status = status
        self._p = payload

    def read(self, size=-1):  # size 参数对齐 http_get 的 max_bytes 读取上限
        return self._p if size < 0 else self._p[:size]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestHttpGetContract(unittest.TestCase):
    """规则12：失败必须显性化——通道失效要报出来，不许静默返回垃圾。"""

    def test_ok_text(self):
        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: _FakeResp(200, b"hello")):
            self.assertEqual(xizhi.http_get("https://x/y"), "hello")

    def test_ok_binary(self):
        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: _FakeResp(200, b"\x89PNG")):
            self.assertEqual(xizhi.http_get("https://x/y", binary=True), b"\x89PNG")

    def test_non_200_exits(self):
        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: _FakeResp(404)):
            with self.assertRaises(SystemExit) as cm:
                xizhi.http_get("https://x/y")
            self.assertIn("404", str(cm.exception))

    def test_html_response_exits(self):
        # 通道失效最常见症状：返回了 HTML 而非 SVG/JSON
        html = b"<!doctype html><html><body>404 page</body></html>"
        with mock.patch.object(xizhi.urllib.request, "urlopen",
                               lambda req, timeout=None: _FakeResp(200, html)):
            with self.assertRaises(SystemExit) as cm:
                xizhi.http_get("https://x/y")
            self.assertIn("HTML", str(cm.exception))

    def test_network_error_exits(self):
        def refuse(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(xizhi.urllib.request, "urlopen", refuse):
            with self.assertRaises(SystemExit) as cm:
                xizhi.http_get("https://x/y")
            self.assertIn("请求失败", str(cm.exception))

    def test_loopback_refused_exits_without_mock(self):
        # 真实 socket 层：连本机保留端口（服务未监听）→ 立即拒绝，不依赖外网
        with self.assertRaises(SystemExit) as cm:
            xizhi.http_get("http://127.0.0.1:1/x", timeout=3)
        self.assertIn("请求失败", str(cm.exception))


class TestCachedNames(unittest.TestCase):
    def setUp(self):
        self._old = xizhi.CACHE_DIR
        xizhi.CACHE_DIR = Path(tempfile.mkdtemp(prefix="xizhi-cache-"))

    def tearDown(self):
        xizhi.CACHE_DIR = self._old

    def test_builder_called_once_within_ttl(self):
        calls = []

        def builder():
            calls.append(1)
            return ["a", "b"]

        self.assertEqual(xizhi.cached_names("unit-test-key", builder), ["a", "b"])
        self.assertEqual(xizhi.cached_names("unit-test-key", builder), ["a", "b"])
        self.assertEqual(len(calls), 1)  # 第二次走缓存文件
        # 缓存文件落在重定向后的 CACHE_DIR，不污染真实 ~/.cache
        self.assertTrue((xizhi.CACHE_DIR / "unit-test-key.txt").is_file())

    def test_expired_cache_rebuilds(self):
        calls = []

        def builder():
            calls.append(len(calls))
            return [f"n{len(calls)}"]

        xizhi.cached_names("ttl-key", builder)
        # 把缓存文件 mtime 拨回到 TTL 之外
        cp = xizhi.CACHE_DIR / "ttl-key.txt"
        old = time.time() - (xizhi.CACHE_TTL + 3600)
        os.utime(cp, (old, old))
        self.assertEqual(xizhi.cached_names("ttl-key", builder), ["n2"])
        self.assertEqual(len(calls), 2)

    def test_keys_are_isolated(self):
        self.assertEqual(xizhi.cached_names("k1", lambda: ["x"]), ["x"])
        self.assertEqual(xizhi.cached_names("k2", lambda: ["y"]), ["y"])


class TestHarmonyosOfficialCache(unittest.TestCase):
    def setUp(self):
        self._old = xizhi.CACHE_DIR
        xizhi.CACHE_DIR = Path(tempfile.mkdtemp(prefix="xizhi-hmcache-"))

    def tearDown(self):
        xizhi.CACHE_DIR = self._old

    def test_downloads_then_serves_from_cache(self):
        payload = {"data": {"cat": [{"name": "cat", "name_cn": "猫",
                                     "unicode": "e123"}]}}

        def fake_http_get(url, binary=False, timeout=30):
            return json.dumps(payload).encode()

        with mock.patch.object(xizhi, "http_get", side_effect=fake_http_get) as m:
            first = xizhi.harmonyos_official(refresh=False)
            self.assertEqual(m.call_count, 1)
            second = xizhi.harmonyos_official(refresh=False)
        self.assertEqual(m.call_count, 1)  # 第二次读缓存文件，不再下载
        self.assertEqual(first, second)
        self.assertEqual(first["cat"][0]["name_cn"], "猫")
        self.assertTrue((xizhi.CACHE_DIR / "harmonyos-name-map.json").is_file())

    def test_refresh_bypasses_cache(self):
        with mock.patch.object(xizhi, "http_get",
                               return_value=b'{"data": {}}') as m:
            xizhi.harmonyos_official(refresh=True)
            xizhi.harmonyos_official(refresh=True)
        self.assertEqual(m.call_count, 2)  # --refresh 每次都强制下载


if __name__ == "__main__":
    unittest.main()
