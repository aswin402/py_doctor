import asyncio
import hashlib
import os
import subprocess
import sys
from typing import Any, Optional

from py_doctor import json_utils


class DependencyRunner:
    def __init__(
        self,
        project_path: str,
        ignore_rules: list[str],
        use_cache: bool = True,
    ):
        self.project_path: str = project_path
        self.ignore_rules: list[str] = ignore_rules or []
        self.use_cache: bool = use_cache

    def _compute_manifest_hash(self) -> Optional[str]:
        hasher = hashlib.sha256()
        manifest_found = False
        manifest_files = [
            "uv.lock",
            "poetry.lock",
            "Pipfile.lock",
            "requirements.txt",
            "pyproject.toml",
        ]
        for name in manifest_files:
            file_path = os.path.join(self.project_path, name)
            if os.path.isfile(file_path):
                manifest_found = True
                try:
                    with open(file_path, "rb") as f:
                        hasher.update(name.encode("utf-8"))
                        hasher.update(f.read())
                except OSError:
                    pass
        if not manifest_found:
            return None
        hasher.update(sys.version.split()[0].encode("utf-8"))
        return hasher.hexdigest()

    async def run(self) -> list[dict[str, Any]]:
        manifest_hash = self._compute_manifest_hash() if self.use_cache else None
        cache_dir = os.path.join(self.project_path, ".pydoctor_cache")
        cache_file = (
            os.path.join(cache_dir, f"audit_{manifest_hash}.json") if manifest_hash else None
        )

        if cache_file and os.path.isfile(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json_utils.loads(f.read())
                return [d for d in cached_data if d.get("rule") not in self.ignore_rules]
            except Exception:
                pass

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
            data = json_utils.loads(result.stdout)
        except (json_utils.JSONDecodeError, Exception):
            return []

        all_diagnostics: list[dict[str, Any]] = []
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                rule_id = f"audit/{vuln.get('id', 'unknown')}"
                desc = (
                    f"{dep.get('name')} {dep.get('version')} is vulnerable: "
                    f"{vuln.get('description', '')[:100]}..."
                )
                fix = f"Upgrade to {', '.join(vuln.get('fix_versions', []))}"

                all_diagnostics.append(
                    {
                        "type": "ERR",
                        "rule": rule_id,
                        "location": "requirements.txt/pyproject.toml",
                        "description": f"{desc} -> {fix}",
                    }
                )

        if cache_file and all_diagnostics:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(json_utils.dumps(all_diagnostics))
            except Exception:
                pass

        return [d for d in all_diagnostics if d.get("rule") not in self.ignore_rules]
