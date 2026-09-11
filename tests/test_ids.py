import unittest

from provider_fetcher.ids import collapse_minor_version, lookup_candidates, strip_routing_suffixes


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


if __name__ == "__main__":
    unittest.main()
