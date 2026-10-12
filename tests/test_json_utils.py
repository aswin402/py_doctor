import datetime
import os
import tempfile
import unittest
from unittest.mock import patch

from py_doctor import json_utils


class TestJsonUtils(unittest.TestCase):
    def test_loads_string_and_bytes(self):
        payload = {"name": "py_doctor", "version": "2.0.2", "active": True, "count": 42}
        json_str = '{"name": "py_doctor", "version": "2.0.2", "active": true, "count": 42}'
        json_bytes = json_str.encode("utf-8")

        self.assertEqual(json_utils.loads(json_str), payload)
        self.assertEqual(json_utils.loads(json_bytes), payload)

    def test_dumps_and_dumps_bytes(self):
        payload = {"b": 2, "a": 1}
        dumped = json_utils.dumps(payload)
        self.assertIn('"a"', dumped)
        self.assertIn('"b"', dumped)

        dumped_sorted = json_utils.dumps(payload, sort_keys=True)
        self.assertTrue(dumped_sorted.index('"a"') < dumped_sorted.index('"b"'))

        dumped_indented = json_utils.dumps(payload, indent=True)
        self.assertIn("\n", dumped_indented)

        bytes_val = json_utils.dumps_bytes(payload)
        self.assertIsInstance(bytes_val, bytes)
        self.assertEqual(json_utils.loads(bytes_val), payload)

    def test_load_and_write_file(self):
        data = {"rules": ["fastapi/insecure-cors", "async/blocking-io"], "score": 95}
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.json")
            json_utils.write_file(file_path, data, indent=True)
            self.assertTrue(os.path.exists(file_path))

            loaded = json_utils.load_file(file_path)
            self.assertEqual(loaded, data)

    def test_invalid_json_raises_decode_error(self):
        with self.assertRaises(json_utils.JSONDecodeError):
            json_utils.loads("{not valid json: true,")

    def test_datetime_serialization(self):
        now = datetime.datetime(2026, 10, 12, 12, 0, 0)
        data = {"timestamp": now}
        dumped = json_utils.dumps(data)
        self.assertIn("2026-10-12", dumped)

    def test_fallback_to_stdlib_json(self):
        # Verify seamless fallback behavior when orjson is disabled/missing
        payload = {"fallback": True, "items": [1, 2, 3]}
        with (
            patch.object(json_utils, "HAS_ORJSON", False),
            patch.object(json_utils, "orjson", None),
        ):
            dumped = json_utils.dumps(payload, indent=True, sort_keys=True)
            self.assertIn('"fallback": true', dumped)
            loaded = json_utils.loads(dumped)
            self.assertEqual(loaded, payload)

            loaded_bytes = json_utils.loads(dumped.encode("utf-8"))
            self.assertEqual(loaded_bytes, payload)


if __name__ == "__main__":
    unittest.main()
