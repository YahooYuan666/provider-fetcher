import json
import tempfile
import unittest
from pathlib import Path

from provider_fetcher import opencode_write
from provider_fetcher.opencode_write import load_jsonc, preview, write_config


CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "provider": {
        "relay-example": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "relay.example",
            "options": {"baseURL": "https://relay.example/v1", "apiKey": "sk-test-key-123456"},
            "models": {"gpt-5.4": {"name": "GPT-5.4", "limit": {"context": 1050000, "output": 128000}}},
        }
    },
}

EXISTING = """{
  // 用户自己的注释，必须原样保留
  "$schema": "https://opencode.ai/config.json",
  "shell": "powershell",

  /* 块注释也要留住 */
  "permissions": [
    { "action": "shell", "resource": "git push *", "effect": "ask" }
  ],
  "provider": {
    "other-relay": {
      "name": "别人的供应商",
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "https://other.example/v1" },
      "models": { "some-model": { "name": "Some" } }
    }
  }
}
"""


class JsoncTests(unittest.TestCase):
    def test_strips_comments_but_keeps_strings(self):
        text = '{\n// 注释\n"a": "http://x//y", /* b */ "c": 1\n}'
        doc = json.loads(opencode_write._strip_jsonc(text))
        self.assertEqual(doc["a"], "http://x//y")
        self.assertEqual(doc["c"], 1)

    def test_load_jsonc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            doc = load_jsonc(path)
            self.assertEqual(doc["shell"], "powershell")
            self.assertIn("other-relay", doc["provider"])


class WriteConfigTests(unittest.TestCase):
    def test_merge_preserves_user_content_and_replaces_own_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            result = write_config(CONFIG, path=path)
            text = path.read_text(encoding="utf-8")

            # 原有段落原样保留（含注释）
            self.assertIn("// 用户自己的注释", text)
            self.assertIn("/* 块注释也要留住 */", text)
            self.assertEqual(json.loads(opencode_write._strip_jsonc(text))["shell"], "powershell")
            # 别人的 provider 不受影响
            doc = json.loads(opencode_write._strip_jsonc(text))
            self.assertIn("other-relay", doc["provider"])
            self.assertIn("relay-example", doc["provider"])
            self.assertEqual(result["action"], "并入已有 provider 段")

    def test_same_provider_id_is_replaced_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            write_config(CONFIG, path=path)
            # 第二次导出只带一个不同的模型：同名 provider 应整体替换
            second = {
                "$schema": "https://opencode.ai/config.json",
                "provider": {
                    "relay-example": {
                        "npm": "@ai-sdk/openai-compatible",
                        "name": "relay.example",
                        "options": {"baseURL": "https://relay.example/v1"},
                        "models": {"brand-new-model": {"name": "Brand New"}},
                    }
                },
            }
            result = write_config(second, path=path)
            doc = json.loads(opencode_write._strip_jsonc(path.read_text(encoding="utf-8")))
            self.assertEqual(result["action"], "替换同名 provider")
            models = doc["provider"]["relay-example"]["models"]
            self.assertIn("brand-new-model", models)
            # 旧模型不该残留
            self.assertNotIn("gpt-5.4", models)
            # provider 只出现一次，别人的 provider 仍在
            self.assertIn("other-relay", doc["provider"])

    def test_backup_created_before_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            result = write_config(CONFIG, path=path)
            backup = Path(result["backup"])
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), EXISTING)

    def test_creates_file_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "opencode.jsonc"
            result = write_config(CONFIG, path=path)
            self.assertTrue(path.exists())
            self.assertEqual(result["backup"], "")
            self.assertEqual(result["action"], "新建配置文件")

    def test_no_tmp_file_left_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            write_config(CONFIG, path=path)
            leftovers = [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_requires_provider_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            with self.assertRaises(ValueError):
                write_config({"provider": {}}, path=path)

    def test_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opencode.jsonc"
            path.write_text(EXISTING, encoding="utf-8")
            before = path.read_text(encoding="utf-8")
            info = preview(CONFIG, path=path)
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertTrue(info["existed"])
            self.assertEqual(info["path"], str(path))


if __name__ == "__main__":
    unittest.main()