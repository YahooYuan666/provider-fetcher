import unittest

from provider_fetcher.catalog import Catalog
from provider_fetcher.fetch import parse_model_list
from provider_fetcher.service import enrich_models


SAMPLE = {
    "xai": {
        "id": "xai",
        "models": {
            "grok-4.6": {
                "id": "grok-4.6",
                "name": "Grok 4.6",
                "limit": {"context": 500000, "output": 500000},
                "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
            },
            "grok-imagine-image": {
                "id": "grok-imagine-image",
                "name": "Grok Imagine Image",
                "limit": {"context": 0, "output": 0},
                "modalities": {"input": ["text"], "output": ["image"]},
            },
            "grok-imagine-video-1.5": {
                "id": "grok-imagine-video-1.5",
                "limit": {"context": 1024, "output": 0},
                "modalities": {"input": ["text", "image", "audio", "pdf"], "output": ["video"]},
            },
            "grok-3-mini": {
                "id": "grok-3-mini",
                "limit": {"context": 131072, "output": 8192},
                "modalities": {"input": ["text"], "output": ["text"]},
            },
        },
    },
    "google": {
        "id": "google",
        "models": {
            "gemini-3-flash-preview": {
                "id": "gemini-3-flash-preview",
                "limit": {"context": 1048576, "output": 65536},
                "modalities": {"input": ["text", "image", "video", "audio", "pdf"], "output": ["text"]},
            },
            "gemini-3.1-pro-preview": {
                "id": "gemini-3.1-pro-preview",
                "limit": {"context": 1048576, "output": 65536},
                "modalities": {"input": ["text", "image", "video", "audio", "pdf"], "output": ["text"]},
            },
            "gemini-3.1-flash-image": {
                "id": "gemini-3.1-flash-image",
                "limit": {"context": 65536, "output": 65536},
                "modalities": {"input": ["text", "image"], "output": ["image"]},
            },
            "gemini-3.6-flash": {
                "id": "gemini-3.6-flash",
                "limit": {"context": 1048576, "output": 65536},
                "modalities": {"input": ["text", "image", "video", "audio", "pdf"], "output": ["text"]},
            },
            "gemini-3.8-flash": {
                "id": "gemini-3.8-flash",
                "limit": {"context": 1048576, "output": 65536},
                "modalities": {"input": ["text", "image", "video", "audio", "pdf"], "output": ["text"]},
            },
        },
    },
    "openai": {
        "id": "openai",
        "models": {
            "gpt-image-2": {
                "id": "gpt-image-2",
                "limit": {"context": 0, "output": 0},
                "modalities": {"input": ["text", "image"], "output": ["image"]},
            },
            "gpt-5.3-codex": {
                "id": "gpt-5.3-codex",
                "limit": {"context": 400000, "output": 128000},
                "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
            },
            "gpt-5.3-codex-spark": {
                "id": "gpt-5.3-codex-spark",
                "limit": {"context": 128000, "output": 32000},
                "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
            },
        },
    },
    "anthropic": {
        "id": "anthropic",
        "models": {
            "claude-opus-4-6": {
                "id": "claude-opus-4-6",
                "limit": {"context": 1000000, "output": 128000},
                "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
            }
        },
    },
    "neon": {
        "id": "neon",
        "models": {
            "gemini-3-flash": {
                "id": "gemini-3-flash",
                "limit": {"context": 1048576, "output": 65536},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            }
        },
    },
    "openrouter": {
        "id": "openrouter",
        "models": {
            "x-ai/grok-4.6": {
                "id": "x-ai/grok-4.6",
                "limit": {"context": 500000, "output": 450000},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            }
        },
    },
    "vercel": {
        "id": "vercel",
        "models": {
            "openai/gpt-image-2.5-flare": {
                "id": "openai/gpt-image-2.5-flare",
                "limit": {},
                "modalities": {"input": ["text"], "output": ["text"]},
            }
        },
    },
    "helicone": {
        "id": "helicone",
        "models": {
            "grok-3-mini": {
                "id": "grok-3-mini",
                "limit": {"context": 131072, "output": 131072},
                "modalities": {"input": ["text"], "output": ["text"]},
            }
        },
    },
}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(SAMPLE, fetched_at="test")

    def test_official_entry_wins_over_relay_copy(self):
        hit = self.catalog.lookup("x-ai/grok-4.6")
        self.assertEqual(hit.context, 500000)
        self.assertEqual(hit.max_output, 500000)
        self.assertEqual(hit.inputs, ["text", "image", "pdf"])
        self.assertEqual(hit.catalog_provider, "xai")
        self.assertIn("models.dev/xai", hit.source)

    def test_unmatched_stays_empty(self):
        hit = self.catalog.lookup("my-alias-gpt")
        self.assertFalse(hit.matched)
        self.assertIsNone(hit.context)
        self.assertEqual(hit.inputs, ["text"])

    def test_image_model_kept(self):
        hit = self.catalog.lookup("grok-imagine-image")
        self.assertEqual(hit.kind, "image")

    def test_parse_openai_list(self):
        models = parse_model_list(
            {"object": "list", "data": [{"id": "grok-4.6"}, {"id": "grok-imagine-video"}]}
        )
        self.assertEqual([item["id"] for item in models], ["grok-4.6", "grok-imagine-video"])

    def test_gemini_routing_suffix_uses_google_preview(self):
        hit = self.catalog.lookup("gemini-3.1-pro-high")
        self.assertTrue(hit.matched)
        self.assertEqual(hit.catalog_provider, "google")
        self.assertEqual(hit.catalog_id, "gemini-3.1-pro-preview")
        self.assertEqual(hit.context, 1048576)
        self.assertIn("gemini-3.1-pro-preview", " ".join(hit.notes))

    def test_gemini_flash_prefers_google_over_neon(self):
        hit = self.catalog.lookup("gemini-3-flash")
        self.assertEqual(hit.catalog_provider, "google")
        self.assertEqual(hit.catalog_id, "gemini-3-flash-preview")

    def test_gemini_flash_high_maps_to_base(self):
        hit = self.catalog.lookup("gemini-3.6-flash-high")
        self.assertEqual(hit.catalog_id, "gemini-3.6-flash")
        self.assertEqual(hit.catalog_provider, "google")

    def test_does_not_map_flash_to_image_variant(self):
        hit = self.catalog.lookup("gemini-3.1-flash")
        self.assertFalse(hit.matched)

    def test_claude_thinking_maps_to_base(self):
        hit = self.catalog.lookup("claude-opus-4-6-thinking")
        self.assertEqual(hit.catalog_id, "claude-opus-4-6")
        self.assertEqual(hit.catalog_provider, "anthropic")

    def test_fast_suffix_maps_to_base(self):
        hit = self.catalog.lookup("grok-3-mini-fast")
        self.assertEqual(hit.catalog_id, "grok-3-mini")
        self.assertEqual(hit.catalog_provider, "xai")

    def test_preview_suffix_maps_to_base_media_model(self):
        hit = self.catalog.lookup("grok-imagine-video-1.5-preview")
        self.assertEqual(hit.catalog_id, "grok-imagine-video-1.5")
        self.assertEqual(hit.kind, "video")

    def test_image_variant_collapses_to_official_family(self):
        hit = self.catalog.lookup("gpt-image-2.5-flare")
        self.assertEqual(hit.catalog_provider, "openai")
        self.assertEqual(hit.catalog_id, "gpt-image-2")
        self.assertEqual(hit.kind, "image")

    def test_exact_spark_beats_parent_codex(self):
        hit = self.catalog.lookup("gpt-5.3-codex-spark")
        self.assertEqual(hit.catalog_id, "gpt-5.3-codex-spark")
        self.assertEqual(hit.context, 128000)

    def test_enrich_keeps_video_and_image(self):
        rows = enrich_models(
            "https://api.x.ai/v1",
            [{"id": "grok-4.6"}, {"id": "grok-imagine-image"}, {"id": "custom-video"}],
            self.catalog,
        )
        kinds = {row["id"]: row["kind"] for row in rows}
        self.assertEqual(kinds["grok-4.6"], "chat")
        self.assertEqual(kinds["grok-imagine-image"], "image")
        self.assertEqual(kinds["custom-video"], "video")


if __name__ == "__main__":
    unittest.main()
