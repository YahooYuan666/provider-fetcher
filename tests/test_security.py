import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provider_fetcher import fetch
from provider_fetcher.fetch import safe_target


class SafeTargetTests(unittest.TestCase):
    def test_allows_http_and_https(self):
        self.assertEqual(safe_target("https://api.example.com/v1/models"), "https://api.example.com/v1/models")
        self.assertEqual(safe_target("http://127.0.0.1:7863/v1/models"), "http://127.0.0.1:7863/v1/models")

    def test_blocks_non_http_schemes(self):
        for url in ("file:///C:/Users/x/favorites.json", "gopher://x", "ftp://x/y"):
            with self.assertRaises(ValueError):
                safe_target(url)

    def test_blocks_cloud_metadata(self):
        with self.assertRaises(ValueError):
            safe_target("http://169.254.169.254/latest/meta-data/")
        with self.assertRaises(ValueError):
            safe_target("http://metadata.google.internal/computeMetadata/v1/")

    def test_private_targets_allowed_by_default(self):
        # 本地网关是本工具的正当场景，默认必须放行
        self.assertEqual(safe_target("http://127.0.0.1:7863/v1/models"), "http://127.0.0.1:7863/v1/models")

    def test_strict_mode_blocks_loopback_but_not_public(self):
        with patch.dict(os.environ, {"PROVIDER_FETCHER_ALLOW_PRIVATE": "0"}):
            with patch.object(fetch.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 7863))]):
                with self.assertRaises(ValueError):
                    safe_target("http://127.0.0.1:7863/v1/models")

    def test_proxy_fake_ip_range_is_not_treated_as_private(self):
        # Clash 等代理把公网域名解析到 198.18.0.0/15，收紧模式不能误伤
        with patch.dict(os.environ, {"PROVIDER_FETCHER_ALLOW_PRIVATE": "0"}):
            with patch.object(fetch.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("198.18.0.7", 443))]):
                self.assertEqual(
                    safe_target("https://api.example.com/v1/models"), "https://api.example.com/v1/models"
                )


class GetJsonGuardTests(unittest.TestCase):
    def test_get_json_refuses_before_any_request(self):
        # 守卫要在发请求之前生效：拦住后不得触达 urlopen
        with patch.object(fetch.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(ValueError):
                fetch._get_json("file:///etc/passwd", "sk-test", 5)
        urlopen.assert_not_called()

    def test_metadata_target_refused_before_request(self):
        with patch.object(fetch.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(ValueError):
                fetch._get_json("http://169.254.169.254/latest/meta-data/", "sk-test", 5)
        urlopen.assert_not_called()


class CatalogUrlGuardTests(unittest.TestCase):
    def test_rejects_non_https_or_foreign_host(self):
        from provider_fetcher import catalog

        with self.assertRaises(ValueError):
            catalog._assert_public_https("http://models.dev/api.json")
        with self.assertRaises(ValueError):
            catalog._assert_public_https("https://evil.example/api.json")

    def test_rejects_loopback_resolution(self):
        from provider_fetcher import catalog

        with patch.object(catalog.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                catalog._assert_public_https("https://models.dev/api.json")

    def test_allows_proxy_fake_ip_range(self):
        from provider_fetcher import catalog

        fake = [(2, 1, 6, "", ("198.18.0.179", 443))]
        with patch.object(catalog.socket, "getaddrinfo", return_value=fake):
            catalog._assert_public_https("https://models.dev/api.json")

    def test_refresh_uses_pinned_constant(self):
        from provider_fetcher import catalog

        # refresh 内部固定写死上游，不读任何外部输入
        import inspect

        src = inspect.getsource(catalog.Catalog.refresh)
        self.assertIn("https://models.dev/api.json", src)
        self.assertNotIn("CATALOG_URL", src)


if __name__ == "__main__":
    unittest.main()