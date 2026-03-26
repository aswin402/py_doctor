import json
import os
import subprocess
from typing import Any, Optional


class TypeRunner:
    def __init__(self, project_path: str, ignore_rules: list[str]):
        self.project_path: str = project_path
        self.ignore_rules: list[str] = ignore_rules or []

    async def run(self) -> list[dict[str, Any]]:
        result: Optional[subprocess.CompletedProcess] = None
        for cmd in (
            [
                "uv",
                "run",
                "mypy",
                self.project_path,
                "--output=json",
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
            [
                "mypy",
                self.project_path,
                "--output=json",
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
        ):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, cwd=self.project_path, timeout=30
                )
                if result.stdout.strip():
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        else:
            return []

        diagnostics: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                issue = json.loads(line)
                try:
                    file_path = os.path.relpath(issue.get("file", ""), self.project_path)
                except ValueError:
                    file_path = issue.get("file", "")

                line_no = issue.get("line", 0)
                message = issue.get("message", "")
                severity = issue.get("severity", "error")
                code = issue.get("error_code", "type-error")

                if f"mypy/{code}" in self.ignore_rules:
                    continue

                diagnostics.append(
                    {
                        "type": "ERR" if severity == "error" else "WARN",
                        "rule": f"mypy/{code}",
                        "location": f"{file_path}:{line_no}",
                        "description": message,
                    }
                )
            except (json.JSONDecodeError, Exception):
                continue
        return diagnostics
