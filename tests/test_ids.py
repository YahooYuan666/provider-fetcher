import unittest

from provider_fetcher.ids import (
    collapse_minor_version,
    lookup_candidates,
    strip_namespace_prefix,
    strip_routing_suffixes,
)


class IdNormalizationTests(unittest.TestCase):
    def test_strip_fast_and_preview(self):
        self.assertEqual(strip_routing_suffixes("grok-3-mini-fast"), "grok-3-mini")
        self.assertEqual(strip_routing_suffixes("grok-imagine-video-1.5-preview"), "grok-imagine-video-1.5")

    def test_collapse_image_minor_version(self):
        self.assertEqual(collapse_minor_version("gpt-image-2.5-flare"), "gpt-image-2-flare")
        self.assertEqual(collapse_minor_version("grok-3-mini"), "")

    def test_lookup_candidates_include_preview_and_family(self):
        aliases = lookup_candidates("gpt-image-2.5-flare")
        self.assertIn("gpt-image-2.5", aliases)
        self.assertIn("gpt-image-2", aliases)

    def test_date_stamp_suffix_is_strippable(self):
        # 网关线路日期戳，不是模型的一部分
        self.assertEqual(strip_routing_suffixes("deepseek-v4-pro-202606"), "deepseek-v4-pro")


class NamespacePrefixTests(unittest.TestCase):
    def test_colon_namespace(self):
        self.assertEqual(strip_namespace_prefix("cn:glm-5.3"), "glm-5.3")
        self.assertEqual(strip_namespace_prefix("cn:deepseek-v4-flash"), "deepseek-v4-flash")

    def test_slash_namespace(self):
        self.assertEqual(strip_namespace_prefix("global/zai_glm-5.3-flash"), "glm-5.3-flash")

    def test_underscore_vendor_prefix(self):
        self.assertEqual(
            strip_namespace_prefix("tdpsk_deepseek-v4-pro-202606"), "deepseek-v4-pro-202606"
        )
        self.assertEqual(strip_namespace_prefix("zaicoding_glm-5.3"), "glm-5.3")

    def test_refuses_when_bare_name_is_not_model_like(self):
        # 剥完既无产品词也无版本号就不冒险：auto/openclaw 是聚合路由入口
        self.assertEqual(strip_namespace_prefix("zai_auto"), "")
        self.assertEqual(strip_namespace_prefix("openclaw"), "")

    def test_leaves_clean_ids_untouched(self):
        self.assertEqual(strip_namespace_prefix("glm-5.3-flash"), "")
        self.assertEqual(strip_namespace_prefix("gpt-5.4"), "")

    def test_lookup_candidates_include_bare_name(self):
        self.assertIn("deepseek-v4-flash", lookup_candidates("cn:deepseek-v4-flash"))
        self.assertIn("glm-5.3", lookup_candidates("cn:glm-5.3"))
        self.assertIn("deepseek-v4-pro", lookup_candidates("tdpsk_deepseek-v4-pro-202606"))


if __name__ == "__main__":
    unittest.main()
