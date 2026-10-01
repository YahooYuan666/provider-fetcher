import unittest

from provider_fetcher.opencode import OPENCODE_PATHS, build_opencode_config, provider_slug


ROWS = [
    {
        "id": "gpt-5.4",
        "display_name": "GPT 5.4",
        "context": 1050000,
        "max_output": 128000,
        "kind": "chat",
        "reasoning_capable": True,
        "reasoning_levels": ["none", "low", "medium", "high", "xhigh"],
        "tool_call": True,
    },
    {
        "id": "glm-5.2",
        "display_name": "GLM 5.2",
        "context": 204800,
        "max_output": 131072,
        "kind": "chat",
        "reasoning_capable": True,
        "interleaved_field": "reasoning_content",
    },
    {
        "id": "mystery-model",
        "display_name": "mystery-model",
        "context": None,
        "max_output": 128000,
        "kind": "chat",
    },
    {
        "id": "gpt-image-2",
        "display_name": "GPT Image 2",
        "kind": "image",
        "context": None,
        "max_output": None,
    },
]


class ProviderSlugTests(unittest.TestCase):
    def test_slug_from_host(self):
        self.assertEqual(provider_slug("https://relay.example/v1"), "relay-example")

    def test_slug_with_port(self):
        self.assertEqual(provider_slug("https://api.example.com:8443/v1"), "api-example-com-8443")


class BuildConfigTests(unittest.TestCase):
    def test_structure_with_key(self):
        config = build_opencode_config("https://relay.example/v1", "sk-test-key-123456", ROWS)
        self.assertEqual(config["$schema"], "https://opencode.ai/config.json")
        provider = config["provider"]["relay-example"]
        self.assertEqual(provider["npm"], "@ai-sdk/openai-compatible")
        self.assertEqual(provider["options"]["baseURL"], "https://relay.example/v1")
        self.assertEqual(provider["options"]["apiKey"], "sk-test-key-123456")
        self.assertEqual(config["model"], "relay-example/gpt-5.4")

    def test_models_mapping(self):
        config = build_opencode_config("https://relay.example/v1", "sk-test-key-123456", ROWS)
        models = config["provider"]["relay-example"]["models"]
        self.assertEqual(set(models), {"gpt-5.4", "glm-5.2", "mystery-model"})
        self.assertEqual(models["gpt-5.4"]["limit"], {"context": 1050000, "output": 128000})
        self.assertIs(models["gpt-5.4"]["reasoning"], True)
        self.assertIs(models["gpt-5.4"]["tool_call"], True)
        self.assertEqual(models["glm-5.2"]["interleaved"], {"field": "reasoning_content"})
        # context 或 output 缺失时整体省略 limit（schema 双必填）
        self.assertNotIn("limit", models["mystery-model"])
        self.assertNotIn("reasoning", models["mystery-model"])

    def test_variants_from_reasoning_levels(self):
        config = build_opencode_config("https://relay.example/v1", "sk-test-key-123456", ROWS)
        models = config["provider"]["relay-example"]["models"]
        self.assertEqual(
            models["gpt-5.4"]["variants"],
            {
                "none": {"reasoningEffort": "none"},
                "low": {"reasoningEffort": "low"},
                "medium": {"reasoningEffort": "medium"},
                "high": {"reasoningEffort": "high"},
                "xhigh": {"reasoningEffort": "xhigh"},
            },
        )
        # 无档位数据的模型不写 variants
        self.assertNotIn("variants", models["glm-5.2"])
        self.assertNotIn("variants", models["mystery-model"])

    def test_env_placeholder_when_key_missing(self):
        config = build_opencode_config("https://relay.example/v1", "  ", ROWS)
        options = config["provider"]["relay-example"]["options"]
        self.assertEqual(options["apiKey"], "{env:RELAY_EXAMPLE_API_KEY}")

    def test_non_chat_skipped_and_default_model(self):
        config = build_opencode_config("https://relay.example/v1", "sk-test-key-123456", ROWS)
        models = config["provider"]["relay-example"]["models"]
        self.assertNotIn("gpt-image-2", models)

    def test_no_models_omits_default_model(self):
        config = build_opencode_config("https://relay.example/v1", "sk-test-key-123456", [])
        provider = config["provider"]["relay-example"]
        self.assertEqual(provider["models"], {})
        self.assertNotIn("model", config)

    def test_base_url_required(self):
        with self.assertRaises(ValueError):
            build_opencode_config("", "sk-test-key-123456", ROWS)

    def test_normalizes_malformed_base_url(self):
        config = build_opencode_config("https://relay.example/v1/chat/completions", "sk-test-key-123456", [])
        options = config["provider"]["relay-example"]["options"]
        self.assertEqual(options["baseURL"], "https://relay.example/v1")

    def test_paths_cover_three_platforms(self):
        labels = [item["label"] for item in OPENCODE_PATHS["items"]]
        self.assertEqual(labels, ["Windows", "WSL", "macOS"])
        self.assertTrue(all(".config/opencode" in item["value"] or "opencode" in item["value"] for item in OPENCODE_PATHS["items"]))


if __name__ == "__main__":
    unittest.main()
