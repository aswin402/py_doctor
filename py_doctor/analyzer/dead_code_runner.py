import os
import re
import subprocess
from typing import Any, Optional

from py_doctor.constants import VULTURE_EXCLUDE_DIRS

class DeadCodeRunner:
    def __init__(self, project_path: str, ignore_files: list[str]):
        self.project_path: str = project_path
        self.ignore_files: list[str] = ignore_files or []

    async def run(self) -> list[dict[str, Any]]:
        result: Optional[subprocess.CompletedProcess] = None
        
        # Vulture will find unused functions, classes, and variables
        cmd_args = [
            self.project_path,
            "--min-confidence", "70",
            "--exclude", VULTURE_EXCLUDE_DIRS
        ]

        for base_cmd in (["uv", "run", "vulture"], ["vulture"]):
            try:
                result = subprocess.run(
                    base_cmd + cmd_args, capture_output=True, text=True, cwd=self.project_path, timeout=30
                )
                if result.stdout.strip():
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

        if result is None or not result.stdout.strip():
            return []

        diagnostics: list[dict[str, Any]] = []
        
        # Parse Vulture's output format: "file.py:line: message"
        pattern = re.compile(r"^(.*?):(\d+):\s+(.*)$")
        
        for line in result.stdout.splitlines():
            match = pattern.match(line.strip())
            if match:
                file_path, line_no, message = match.groups()
                
                # Make path relative
                try:
                    rel_path = os.path.relpath(file_path, self.project_path)
                except ValueError:
                    rel_path = file_path
                
                # Skip user ignored files
                if any(ig.rstrip("/") in rel_path for ig in self.ignore_files):
                    continue
                
                sub_type = "UNUSED IMPORT" if "import" in message else "UNUSED"

                diagnostics.append({
                    "type": "DEAD",
                    "subType": sub_type,
                    "location": f"{rel_path}:{line_no}",
                    "description": message,
                    "rule": "vulture/dead-code"
                })

        return diagnostics