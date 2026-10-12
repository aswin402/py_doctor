import os
import tempfile
import unittest
from unittest.mock import patch

from py_doctor import json_utils
from py_doctor.analyzer.dependency_runner import DependencyRunner


class TestDependencyRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_compute_manifest_hash_with_no_manifests(self):
        runner = DependencyRunner(self.project_path, [])
        self.assertIsNone(runner._compute_manifest_hash())

    def test_compute_manifest_hash_changes_with_manifest_content(self):
        runner = DependencyRunner(self.project_path, [])
        req_path = os.path.join(self.project_path, "requirements.txt")

        with open(req_path, "w", encoding="utf-8") as f:
            f.write("fastapi==0.100.0\n")
        h1 = runner._compute_manifest_hash()
        self.assertIsNotNone(h1)

        with open(req_path, "w", encoding="utf-8") as f:
            f.write("fastapi==0.115.0\n")
        h2 = runner._compute_manifest_hash()
        self.assertIsNotNone(h2)
        self.assertNotEqual(h1, h2)

    def test_cache_round_trip_and_speed(self):
        runner = DependencyRunner(self.project_path, [])
        req_path = os.path.join(self.project_path, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("fastapi==0.100.0\n")

        manifest_hash = runner._compute_manifest_hash()
        self.assertIsNotNone(manifest_hash)

        cache_dir = os.path.join(self.project_path, ".pydoctor_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"audit_{manifest_hash}.json")

        dummy_diags = [
            {
                "type": "ERR",
                "rule": "audit/PYSEC-2024-TEST",
                "location": "requirements.txt/pyproject.toml",
                "description": "fastapi 0.100.0 is vulnerable",
            }
        ]
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(json_utils.dumps(dummy_diags))

        # runner should read directly from cache without executing subprocess
        with patch("asyncio.to_thread") as mock_exec:
            import asyncio

            result = asyncio.run(runner.run())
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["rule"], "audit/PYSEC-2024-TEST")
            mock_exec.assert_not_called()

        # runner with ignore_rules should filter cached results
        runner_ignored = DependencyRunner(self.project_path, ["audit/PYSEC-2024-TEST"])
        import asyncio

        filtered = asyncio.run(runner_ignored.run())
        self.assertEqual(len(filtered), 0)


if __name__ == "__main__":
    unittest.main()
