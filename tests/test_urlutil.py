import unittest

from provider_fetcher.urlutil import models_url_candidates, normalize_base_url


class UrlUtilTests(unittest.TestCase):
    def test_root_adds_v1_and_models_fallback(self):
        self.assertEqual(
            models_url_candidates("https://api.example.com"),
            [
                "https://api.example.com/v1/models",
                "https://api.example.com/models",
            ],
        )

    def test_versioned_path_only_appends_models(self):
        self.assertEqual(
            models_url_candidates("https://api.example.com/v1/"),
            ["https://api.example.com/v1/models"],
        )

    def test_strips_chat_completions_suffix(self):
        self.assertEqual(
            normalize_base_url("https://gw.example.com/coding/v1/chat/completions"),
            "https://gw.example.com/coding/v1",
        )
        self.assertEqual(
            models_url_candidates("https://gw.example.com/coding/v1/chat/completions"),
            ["https://gw.example.com/coding/v1/models"],
        )

    def test_keeps_subpath_prefix(self):
        self.assertEqual(
            models_url_candidates("https://gw.example.com/api/paas/v4"),
            ["https://gw.example.com/api/paas/v4/models"],
        )

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_base_url("  ")


if __name__ == "__main__":
    unittest.main()
