import asyncio
import json
import os
import re
import subprocess
import sys
from typing import Any, Optional

from py_doctor.constants import DEFAULT_SKIP_DIRS


class ProjectDetector:
    def __init__(self, project_path: str):
        self.project_path: str = project_path
        self.python_version: str = ""
        self.fastapi_version: str = ""
        self.sqlalchemy_version: str = ""
        self.packages: dict[str, str] = {}
        self.source_file_count: int = 0
        self.has_alembic: bool = False
        self.has_structlog: bool = False
        self.has_pydantic: bool = False
        self.has_asyncpg: bool = False

    async def detect(self) -> None:
        await asyncio.gather(
            self._detect_python_version(),
            self._detect_packages(),
            self._count_source_files(),
        )

    async def _detect_python_version(self) -> None:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.python_version = result.stdout.strip().replace("Python ", "")
        except Exception:
            self.python_version = "unknown"

    async def _detect_packages(self) -> None:
        package_data: Optional[list[dict[str, Any]]] = None
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["uv", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                cwd=self.project_path,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                package_data = json.loads(result.stdout)
        except Exception:
            pass

        if not package_data:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-m", "pip", "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    package_data = json.loads(result.stdout)
            except Exception:
                pass

        if package_data:
            self.packages = {
                p["name"].lower(): p["version"]
                for p in package_data
                if isinstance(p, dict) and "name" in p and "version" in p
            }
            self.fastapi_version = self.packages.get("fastapi", "")
            self.sqlalchemy_version = self.packages.get("sqlalchemy", "")
            self.has_alembic = "alembic" in self.packages
            self.has_structlog = "structlog" in self.packages
            self.has_pydantic = "pydantic" in self.packages
            self.has_asyncpg = "asyncpg" in self.packages

        self._detect_from_config_files()

    def _detect_from_config_files(self) -> None:
        content = ""
        toml_path = os.path.join(self.project_path, "pyproject.toml")
        req_path = os.path.join(self.project_path, "requirements.txt")

        if os.path.exists(toml_path):
            try:
                with open(toml_path, encoding="utf-8") as f:
                    content = f.read().lower()
            except (OSError, UnicodeDecodeError):
                pass
        elif os.path.exists(req_path):
            try:
                with open(req_path, encoding="utf-8") as f:
                    content = f.read().lower()
            except (OSError, UnicodeDecodeError):
                pass

        if not content:
            return

        if "fastapi" in content and not self.fastapi_version:
            m = re.search(r'fastapi[>=<!~^\s"\']+([0-9][0-9.]*)', content)
            self.fastapi_version = m.group(1) if m else "detected"

        if "sqlalchemy" in content and not self.sqlalchemy_version:
            m = re.search(r'sqlalchemy[>=<!~^\s"\']+([0-9][0-9.]*)', content)
            self.sqlalchemy_version = m.group(1) if m else "detected"

        if "alembic" in content:
            self.has_alembic = True
        if "structlog" in content:
            self.has_structlog = True
        if "pydantic" in content:
            self.has_pydantic = True
        if "asyncpg" in content:
            self.has_asyncpg = True

    async def _count_source_files(self) -> None:
        count = 0

        for _root, dirs, files in os.walk(self.project_path):
            filtered_dirs: list[str] = [
                d for d in dirs if not d.startswith(".") and d not in DEFAULT_SKIP_DIRS
            ]
            dirs[:] = filtered_dirs

            for f in files:
                if f.endswith(".py"):
                    count += 1

        self.source_file_count = count
