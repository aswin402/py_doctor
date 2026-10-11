import json
import os
import tempfile
import unittest

from py_doctor.config import Config


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config()
        self.assertTrue(cfg.lint)
        self.assertTrue(cfg.dead_code)
        self.assertTrue(cfg.types)
        self.assertTrue(cfg.security)
        self.assertEqual(cfg.threshold, 75)
        self.assertIn("bandit/B404", cfg.ignore_rules)

    def test_load_from_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "py_doctor.config.json")
            data = {
                "lint": False,
                "deadCode": True,
                "types": True,
                "security": False,
                "threshold": 85,
                "ignore": {
                    "rules": ["custom/rule-1"],
                    "files": ["tests/"],
                },
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            cfg = Config.load(tmpdir)
            self.assertFalse(cfg.lint)
            self.assertTrue(cfg.dead_code)
            self.assertFalse(cfg.security)
            self.assertEqual(cfg.threshold, 85)
            self.assertIn("custom/rule-1", cfg.ignore_rules)
            self.assertIn("tests/", cfg.ignore_files)

    def test_load_from_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "pyproject.toml")
            toml_content = """
[tool.py_doctor]
lint = true
dead_code = false
types = true
security = true
threshold = 90

[tool.py_doctor.ignore]
rules = ["ruff/E501"]
files = ["docs/"]
"""
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(toml_content)

            cfg = Config.load(tmpdir)
            self.assertTrue(cfg.lint)
            self.assertFalse(cfg.dead_code)
            self.assertEqual(cfg.threshold, 90)
            self.assertIn("ruff/E501", cfg.ignore_rules)
            self.assertIn("docs/", cfg.ignore_files)


if __name__ == "__main__":
    unittest.main()
