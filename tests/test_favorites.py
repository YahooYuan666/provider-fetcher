import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provider_fetcher import favorites


class FavoriteCredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fav_path = self.root / "favorites.json"
        self.last_path = self.root / "last-fetch.json"
        self.patchers = [
            patch.object(favorites, "favorites_path", lambda: self.fav_path),
            patch.object(favorites, "last_fetch_path", lambda: self.last_path),
        ]
        for item in self.patchers:
            item.start()

    def tearDown(self):
        for item in self.patchers:
            item.stop()
        self.tmp.cleanup()

    def test_upsert_saves_url_and_key_once(self):
        favorites.upsert_credential("https://api.example.com/v1", "sk-test-key-123456")
        favorites.upsert_credential("https://api.example.com/v1/", "sk-test-key-123456")
        items = favorites.load_favorites()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["base_url"], "https://api.example.com/v1")
        self.assertEqual(items[0]["api_key"], "sk-test-key-123456")

    def test_public_list_masks_key(self):
        favorites.upsert_credential("https://api.example.com/v1", "sk-test-key-123456")
        public = favorites.public_favorites()
        self.assertEqual(len(public), 1)
        self.assertNotIn("api_key", public[0])
        self.assertEqual(public[0]["api_key_masked"], "sk-t…3456")
        raw = json.loads(self.fav_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["items"][0]["api_key"], "sk-test-key-123456")

    def test_old_model_rows_are_ignored(self):
        self.fav_path.write_text(
            json.dumps(
                {
                    "items": [
                        {"id": "grok-4.6", "base_url": "https://api.example.com/v1", "context": 1}
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(favorites.load_favorites(), [])

    def test_mask_short_key(self):
        self.assertEqual(favorites.mask_api_key("abcd"), "a…d")

    def test_find_credential_detects_saved_combo(self):
        favorites.upsert_credential("https://api.example.com/v1", "sk-test-key-123456")
        found = favorites.find_credential("https://api.example.com/v1/", "sk-test-key-123456")
        missing = favorites.find_credential("https://api.example.com/v1", "sk-other-key-000000")
        self.assertIsNotNone(found)
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
