import asyncio
import json
import os
import subprocess
from typing import Any, Optional


class DependencyRunner:
    def __init__(self, project_path: str, ignore_rules: list[str]):
        self.project_path: str = project_path
        self.ignore_rules: list[str] = ignore_rules or []

    async def run(self) -> list[dict[str, Any]]:
        # pip-audit needs a requirements.txt or pyproject.toml to scan accurately
        req_path = os.path.join(self.project_path, "requirements.txt")
        toml_path = os.path.join(self.project_path, "pyproject.toml")

        target_args = []
        if os.path.exists(req_path):
            target_args = ["-r", req_path]
        elif os.path.exists(toml_path):
            target_args = ["-l"]  # Local environment scan if pyproject exists
        else:
            return []  # Nothing to scan against

        result: Optional[subprocess.CompletedProcess] = None
        for base_cmd in (["uv", "run", "pip-audit"], ["pip-audit"]):
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    base_cmd + target_args + ["-f", "json"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=45,
                )
                if result is not None and result.stdout.strip():
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        else:
            return []

        if result is None or not result.stdout.strip():
            return []

        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, Exception):
            return []

        diagnostics: list[dict[str, Any]] = []
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                rule_id = f"audit/{vuln.get('id', 'unknown')}"
                if rule_id in self.ignore_rules:
                    continue

                desc = f"{dep.get('name')} {dep.get('version')} is vulnerable: {vuln.get('description', '')[:100]}..."
                fix = f"Upgrade to {', '.join(vuln.get('fix_versions', []))}"

                diagnostics.append(
                    {
                        "type": "ERR",
                        "rule": rule_id,
                        "location": "requirements.txt/pyproject.toml",
                        "description": f"{desc} -> {fix}",
                    }
                )
        return diagnostics
