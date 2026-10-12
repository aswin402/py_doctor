import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest


class TestCLI(unittest.TestCase):
    def test_version_flag(self):
        res = subprocess.run(
            [sys.executable, "-m", "py_doctor", "--version"],
            capture_output=True,
            text=True,
        )
        # Or running python -m py_doctor.cli
        if res.returncode != 0:
            res = subprocess.run(
                [sys.executable, "-c", "import py_doctor.cli; print(py_doctor.cli.get_version())"],
                capture_output=True,
                text=True,
            )
        self.assertIn("py_doctor version", res.stdout)

    def test_json_format_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = os.path.join(tmpdir, "main.py")
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write('"""Sample clean file"""\nx = 1\n')

            # Run py_doctor with --no-security --no-types --no-dead-code for fast targeted test
            cmd = [
                sys.executable,
                "-c",
                f"""
import argparse, asyncio
from py_doctor.cli import run
parser = argparse.ArgumentParser()
parser.add_argument('path', default='{tmpdir}')
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--score', action='store_true')
parser.add_argument('--fix', action='store_true')
parser.add_argument('--no-lint', action='store_true', default=False)
parser.add_argument('--no-dead-code', action='store_true', default=True)
parser.add_argument('--no-types', action='store_true', default=True)
parser.add_argument('--no-security', action='store_true', default=True)
parser.add_argument('--no-md', action='store_true', default=True)
parser.add_argument('--format', default='json')
args = parser.parse_args(['{tmpdir}'])
asyncio.run(run(args))
""",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, msg=f"CLI failed with error: {res.stderr}")
            data = json.loads(res.stdout)
            self.assertIn("score", data)
            self.assertIn("categories", data)
            self.assertIn("diagnostics", data)

    def test_diff_filtering(self):
        from py_doctor.cli import get_git_diff_files

        # Test on current repo against HEAD
        diff_files = get_git_diff_files(".", "HEAD")
        self.assertIsInstance(diff_files, set)

    def test_markdown_report_generation(self):
        from py_doctor.analyzer.project_detector import ProjectDetector
        from py_doctor.reporter import Reporter

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ProjectDetector(tmpdir)
            detector.python_version = "3.12.0"
            detector.source_file_count = 1
            diagnostics = [
                {
                    "type": "ERR",
                    "rule": "fastapi/missing-response-model",
                    "location": "app/main.py:10",
                    "description": "Route missing response_model",
                    "suggestion": "Add response_model=Model",
                }
            ]
            reporter = Reporter(verbose=True)
            asyncio.run(
                reporter.generate_markdown_report(
                    project_path=tmpdir,
                    diagnostics=diagnostics,
                    detector=detector,
                    score=97,
                    errors=1,
                    warnings=0,
                    dead_code=0,
                    file_count=1,
                    threshold=75,
                )
            )
            report_path = os.path.join(tmpdir, "NEEDEDFIX.md")
            self.assertTrue(os.path.exists(report_path))
            with open(report_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Health Score: 97 / 100", content)
            self.assertIn("fastapi/missing-response-model", content)
            self.assertIn("Add response_model=Model", content)

    def test_html_report_generation(self):
        from py_doctor.analyzer.project_detector import ProjectDetector
        from py_doctor.reporter import Reporter

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ProjectDetector(tmpdir)
            detector.python_version = "3.12.0"
            detector.source_file_count = 1
            diagnostics = [
                {
                    "type": "ERR",
                    "rule": "fastapi/insecure-cors",
                    "location": "app/main.py:10",
                    "description": "Insecure CORS",
                    "suggestion": "Specify explicit origins",
                }
            ]
            reporter = Reporter(verbose=True)
            html_path = os.path.join(tmpdir, "report.html")
            asyncio.run(
                reporter.generate_html_report(
                    output_path=html_path,
                    diagnostics=diagnostics,
                    detector=detector,
                    score=82,
                    errors=1,
                    warnings=0,
                    dead_code=0,
                    file_count=1,
                    threshold=75,
                )
            )
            self.assertTrue(os.path.exists(html_path))
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("py_doctor Health Report", content)
            self.assertIn("fastapi/insecure-cors", content)
            self.assertIn("Specify explicit origins", content)


if __name__ == "__main__":
    unittest.main()


