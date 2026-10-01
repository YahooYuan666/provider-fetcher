import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provider_fetcher import zen_probe
from provider_fetcher.zen_probe import classify, probe_models


class ClassifyTests(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(classify(200, ""), "ok")

    def test_client_only_free_tier(self):
        self.assertEqual(
            classify(403, "Error from provider (Console): OpenCode's free tier can only be used from within"),
            "client_only",
        )

    def test_upstream_unavailable(self):
        self.assertEqual(
            classify(400, "Error from provider (Console): Upstream request failed: Model is unavailable."),
            "unavailable",
        )

    def test_missing_key(self):
        self.assertEqual(classify(400, "Missing API key."), "auth")
        self.assertEqual(classify(401, "nope"), "auth")

    def test_server_error(self):
        self.assertEqual(classify(500, "Internal server error"), "error")

    def test_not_found(self):
        self.assertEqual(classify(404, "not found"), "unavailable")


class ProbeModelsTests(unittest.TestCase):
    def test_reports_every_model(self):
        calls = []

        def fake(base_url, api_key, model_id):
            calls.append((base_url, api_key, model_id))
            if model_id == "space-bunny-free":
                return "ok", ""
            return "client_only", "OpenCode's free tier can only be used from within"

        with patch.object(zen_probe, "_probe_once", side_effect=fake):
            report = probe_models("https://opencode.ai/zen/v1", "public", ["space-bunny-free", "big-pickle"], delay=0)

        self.assertEqual(report["probed"], 2)
        self.assertTrue(report["results"]["space-bunny-free"]["usable"])
        self.assertEqual(report["results"]["space-bunny-free"]["label"], "外部可调用")
        # 仅限客户端：不是不可用，只是外部直连被拒
        self.assertEqual(report["results"]["big-pickle"]["status"], "client_only")
        self.assertFalse(report["results"]["big-pickle"]["usable"])
        self.assertEqual(calls[0][0], "https://opencode.ai/zen/v1")

    def test_caps_probe_count(self):
        with patch.object(zen_probe, "_probe_once", return_value=("ok", "")) as probe:
            report = probe_models("https://opencode.ai/zen/v1", "public", [f"m{i}" for i in range(60)], delay=0)
        self.assertEqual(report["probed"], zen_probe.MAX_PROBES)
        self.assertEqual(probe.call_count, zen_probe.MAX_PROBES)

    def test_requires_base_url(self):
        with self.assertRaises(ValueError):
            probe_models("", "public", ["m"], delay=0)


class ReportPersistenceTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "zen-probe.json"
            payload = {"base_url": "https://opencode.ai/zen/v1", "results": {"m": {"status": "ok"}}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch("provider_fetcher.paths.zen_probe_path", return_value=path):
                self.assertEqual(zen_probe.load_report()["results"]["m"]["status"], "ok")

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nope.json"
            with patch("provider_fetcher.paths.zen_probe_path", return_value=path):
                self.assertEqual(zen_probe.load_report(), {})

    def test_corrupt_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with patch("provider_fetcher.paths.zen_probe_path", return_value=path):
                self.assertEqual(zen_probe.load_report(), {})


if __name__ == "__main__":
    unittest.main()
