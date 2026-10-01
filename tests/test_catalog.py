import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from provider_fetcher import catalog
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
                "structured_output": True,
                "reasoning": True,
                "reasoning_options": [
                    {"type": "effort", "values": ["none", "low", "medium", "high", "xhigh"]}
                ],
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
                "structured_output": True,
                "reasoning": True,
                "reasoning_options": [
                    {"type": "effort", "values": ["low", "medium", "high", "max"]},
                    {"type": "budget_tokens", "min": 1024},
                ],
            }
        },
    },
    "zai": {
        "id": "zai",
        "models": {
            "glm-5.2": {
                "id": "glm-5.2",
                "limit": {"context": 204800, "output": 131072},
                "modalities": {"input": ["text"], "output": ["text"]},
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["high", "max"]}],
                "interleaved": {"field": "reasoning_content"},
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
    "302ai": {
        "id": "302ai",
        "models": {
            "glm-5.3": {
                "id": "glm-5.3",
                "limit": {"context": 1000000, "output": 131072},
                "modalities": {"input": ["text"], "output": ["text"]},
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["low", "high", "max"]}],
                "interleaved": {"field": "reasoning_content"},
            }
        },
    },
    "opencode": {
        "id": "opencode",
        "models": {
            "big-pickle": {
                "id": "big-pickle",
                "limit": {"context": 200000, "input": 160000, "output": 32000},
                "modalities": {"input": ["text"], "output": ["text"]},
                "reasoning": True,
                "cost": {"input": 0, "output": 0},
            },
            "glm-5.3": {
                "id": "glm-5.3",
                "limit": {"context": 1000000, "output": 131072},
                "modalities": {"input": ["text"], "output": ["text"]},
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["low", "high", "max"]}],
                "interleaved": {"field": "reasoning_content"},
                "tool_call": True,
                "structured_output": True,
                "cost": {"input": 1.4, "output": 4.4},
            },
            "mimo-v2.5-free": {
                "id": "mimo-v2.5-free",
                "limit": {"context": 200000, "output": 32000},
                "modalities": {"input": ["text", "image", "audio", "video"], "output": ["text"]},
                "reasoning": True,
                "cost": {"input": 0, "output": 0},
            },
            "no-cost-model": {
                "id": "no-cost-model",
                "limit": {"context": 128000, "output": 8192},
                "modalities": {"input": ["text"], "output": ["text"]},
            },
            "output-only-nonzero-free": {
                "id": "output-only-nonzero-free",
                "limit": {"context": 128000, "output": 8192},
                "modalities": {"input": ["text"], "output": ["text"]},
                "cost": {"input": 0, "output": 3},
            },
            "retired-free-model": {
                "id": "retired-free-model",
                "limit": {"context": 200000, "output": 32000},
                "modalities": {"input": ["text"], "output": ["text"]},
                "cost": {"input": 0, "output": 0},
                "status": "deprecated",
            },
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

    def test_reasoning_levels_and_structured_output_extracted(self):
        hit = self.catalog.lookup("gpt-5.3-codex")
        self.assertEqual(hit.reasoning_levels, ["none", "low", "medium", "high", "xhigh"])
        self.assertIs(hit.reasoning_capable, True)
        self.assertIs(hit.structured_output, True)
        self.assertIsNone(hit.reasoning_budget_min)
        self.assertIsNone(hit.interleaved_field)

    def test_budget_tokens_extracted_alongside_effort(self):
        hit = self.catalog.lookup("claude-opus-4-6")
        self.assertEqual(hit.reasoning_levels, ["low", "medium", "high", "max"])
        self.assertEqual(hit.reasoning_budget_min, 1024)

    def test_interleaved_field_extracted(self):
        hit = self.catalog.lookup("glm-5.2")
        self.assertEqual(hit.reasoning_levels, ["high", "max"])
        self.assertEqual(hit.interleaved_field, "reasoning_content")

    def test_missing_reasoning_fields_stay_unknown(self):
        hit = self.catalog.lookup("grok-3-mini")
        self.assertEqual(hit.reasoning_levels, [])
        self.assertIsNone(hit.reasoning_capable)
        self.assertIsNone(hit.structured_output)

    def test_unmatched_has_empty_reasoning(self):
        hit = self.catalog.lookup("my-alias-gpt")
        self.assertEqual(hit.reasoning_levels, [])
        self.assertIsNone(hit.reasoning_capable)
        self.assertIsNone(hit.structured_output)

    def test_provider_hint_prefers_official_mirror(self):
        # 无提示时 302ai 副本按字母序胜出；提示 opencode 后官方镜像压过一切副本
        plain = self.catalog.lookup("glm-5.3")
        self.assertEqual(plain.catalog_provider, "302ai")
        hinted = self.catalog.lookup("glm-5.3", provider_hint="opencode")
        self.assertEqual(hinted.catalog_provider, "opencode")
        self.assertEqual(hinted.cost, {"input": 1.4, "output": 4.4})
        self.assertIs(hinted.tool_call, True)
        # 提示命中的是网关自己的目录，不再标注"中转副本"
        self.assertNotIn("无官方实验室条目", " ".join(hinted.notes))
        self.assertNotEqual(hinted.catalog_provider, plain.catalog_provider)

    def test_hint_ignores_absent_provider(self):
        hit = self.catalog.lookup("grok-3-mini", provider_hint="opencode")
        self.assertEqual(hit.catalog_provider, "xai")

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

    def test_zen_rows_free_first_with_score(self):
        rows = enrich_models(
            "https://opencode.ai/zen/v1",
            [{"id": "glm-5.3"}, {"id": "big-pickle"}, {"id": "mimo-v2.5-free"}],
            self.catalog,
        )
        by_id = {row["id"]: row for row in rows}
        self.assertTrue(by_id["big-pickle"]["free"])
        self.assertTrue(by_id["mimo-v2.5-free"]["free"])
        self.assertFalse(by_id["glm-5.3"]["free"])
        # 免费模型置顶（组内按评分降序），非免费排后
        self.assertEqual([row["id"] for row in rows], ["mimo-v2.5-free", "big-pickle", "glm-5.3"])
        # 评分：1M 上下文 40 + 输出 16 + 推理满档 15 + 工具 15 + 结构化 4 = 90
        self.assertEqual(by_id["glm-5.3"]["score"], 90)
        self.assertTrue(0 <= by_id["big-pickle"]["score"] <= 100)

    def test_free_matches_opencode_desktop_rule(self):
        # 官方规则：provider=opencode 且（无 cost 或 cost.input===0）。
        # 输出价非 0 也算免费；完全没有 cost 字段也算免费；-free 后缀不算依据。
        rows = enrich_models(
            "https://opencode.ai/zen/v1",
            [
                {"id": "big-pickle"},
                {"id": "glm-5.3"},
                {"id": "mimo-v2.5-free"},
                {"id": "grok-4.6"},
                {"id": "no-cost-model"},
                {"id": "output-only-nonzero-free"},
                {"id": "retired-free-model"},
            ],
            self.catalog,
        )
        by_id = {row["id"]: row for row in rows}
        # cost {input:0,output:0} -> 免费
        self.assertTrue(by_id["big-pickle"]["free"])
        # cost {input:1.4,output:4.4} -> 不免费
        self.assertFalse(by_id["glm-5.3"]["free"])
        # 非 opencode 目录来源（xai 官方条目）即使有推理能力也不免费
        self.assertFalse(by_id["grok-4.6"]["free"])
        # 官方规则把「没有 cost 字段」也当免费
        self.assertTrue(by_id["no-cost-model"]["free"])
        # 官方规则只看 input，output 非 0 仍是免费
        self.assertTrue(by_id["output-only-nonzero-free"]["free"])
        # 目录标记 deprecated 的免费模型不再算免费（Zen 已下架，桌面版也不列）
        self.assertFalse(by_id["retired-free-model"]["free"])


class RefreshCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "models-dev-api.json"
        patcher = patch.object(catalog, "catalog_cache_path", lambda: self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_refresh_writes_cache_without_tmp_leftover(self):
        payload = {"openai": {"models": {"gpt-5.4": {"limit": {"context": 1050000}}}}}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with patch.object(catalog.urllib.request, "urlopen", return_value=response):
            envelope = Catalog.refresh()
        data = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertEqual(data["providers"], payload)
        self.assertEqual(envelope["providers"], payload)
        self.assertFalse(Path(str(self.cache) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
