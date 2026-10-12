import ast
import asyncio
import inspect
import json
import os
import subprocess
from typing import Any, Optional

from py_doctor.constants import DEFAULT_EXCLUDE_DIRS_STR, DEFAULT_SKIP_DIRS, RUFF_SELECT_FLAGS
from py_doctor.rules import (
    async_rules,
    base_rule,
    database_rules,
    fastapi_rules,
    pydantic_rules,
    sqlalchemy_rules,
    structlog_rules,
)
from py_doctor.rules.ast_utils import annotate_parents


class LintRunner:
    def __init__(
        self,
        project_path: str,
        ignore_rules: list[str],
        ignore_files: Optional[list[str]] = None,
    ):
        self.project_path: str = project_path
        self.ignore_rules: list[str] = ignore_rules or []
        self.ignore_files: list[str] = ignore_files or []
        self.custom_rules: list[Any] = []
        self._load_custom_rules()

    def _load_custom_rules(self) -> None:
        try:
            for module in [
                fastapi_rules,
                pydantic_rules,
                sqlalchemy_rules,
                structlog_rules,
                async_rules,
                database_rules,
            ]:
                for _name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, base_rule.BaseRule)
                        and obj is not base_rule.BaseRule
                        and hasattr(obj, "check")
                    ):
                        self.custom_rules.append(obj)
        except Exception:
            pass

    async def run(self) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        ruff_diags = await self._run_ruff()
        diagnostics.extend(ruff_diags)
        custom_diags = await self._run_custom_rules()
        diagnostics.extend(custom_diags)

        return [d for d in diagnostics if d.get("rule", "") not in self.ignore_rules]

    async def _run_ruff(self) -> list[dict[str, Any]]:
        result: Optional[subprocess.CompletedProcess] = None

        exclude_dirs = DEFAULT_EXCLUDE_DIRS_STR
        if self.ignore_files:
            exclude_dirs = f"{exclude_dirs},{','.join(self.ignore_files)}"

        cmd_args = [
            "check",
            self.project_path,
            "--output-format=json",
            "--quiet",
            "--select",
            RUFF_SELECT_FLAGS,
            "--exclude",
            exclude_dirs,
        ]

        for base_cmd in (["uv", "run", "ruff"], ["ruff"]):
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    base_cmd + cmd_args,
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=30,
                )
                if result is not None and (result.returncode == 0 or result.stdout.strip()):
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

        if result is None or not result.stdout.strip():
            return []

        try:
            issues = json.loads(result.stdout)
        except (json.JSONDecodeError, Exception):
            return []

        diagnostics: list[dict[str, Any]] = []
        for issue in issues:
            abs_path = issue.get("filename", "")
            try:
                file_path = os.path.relpath(abs_path, self.project_path)
            except ValueError:
                file_path = abs_path

            if any(skip in file_path for skip in [".venv", "venv", "env", "__pycache__"]):
                continue

            row = issue.get("location", {}).get("row", 0)
            code = issue.get("code", "unknown")
            message = issue.get("message", "")

            # Adjust severity based on Ruff rule codes
            if code.startswith(("E9", "F8", "F9", "S", "B")):
                sev = "ERR"
            elif code.startswith(("E", "F", "W", "UP", "SIM", "RUF")):
                sev = "WARN"
            else:
                sev = "INFO"

            diagnostics.append(
                {
                    "type": sev,
                    "rule": f"ruff/{code}",
                    "location": f"{file_path}:{row}",
                    "description": message,
                }
            )
        return diagnostics

    async def _run_custom_rules(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._sync_run_custom_rules)

    def _sync_run_custom_rules(self) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(self.project_path):
            filtered_dirs: list[str] = [
                d for d in dirs if not d.startswith(".") and d not in DEFAULT_SKIP_DIRS
            ]
            dirs[:] = filtered_dirs

            for filename in files:
                if not filename.endswith(".py"):
                    continue
                filepath = os.path.join(root, filename)
                try:
                    rel_path = os.path.relpath(filepath, self.project_path)
                except ValueError:
                    rel_path = filepath

                if any(ig.rstrip("/") in rel_path for ig in self.ignore_files):
                    continue

                skip_file = filename == "__init__.py"
                try:
                    with open(filepath, encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)

                    # Annotate parent on AST nodes for rules that rely on tree context
                    annotate_parents(tree)

                    for rule_class in self.custom_rules:
                        if skip_file and "import" in getattr(rule_class, "rule_id", ""):
                            continue
                        try:
                            diags = rule_class.check(tree, source, rel_path)
                            diagnostics.extend(diags)
                        except Exception:
                            pass
                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue
        return diagnostics
