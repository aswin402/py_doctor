import asyncio
import os
import sys
import subprocess
import json

class ProjectDetector:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.python_version = ''
        self.fastapi_version = ''
        self.sqlalchemy_version = ''
        self.packages: dict = {}
        self.source_file_count = 0
        self.has_alembic = False
        self.has_structlog = False
        self.has_pydantic = False
        self.has_asyncpg = False

    async def detect(self):
        await asyncio.gather(
            self._detect_python_version(),
            self._detect_packages(),
            self._count_source_files(),
        )

    async def _detect_python_version(self):
        try:
            result = subprocess.run(
                [sys.executable, '--version'],
                capture_output=True, text=True
            )
            self.python_version = result.stdout.strip().replace('Python ', '')
        except Exception:
            self.python_version = 'unknown'

    async def _detect_packages(self):
        # Try uv first (fastest), then pip as fallback
        package_data = None

        # Method 1: uv pip list (works in uv projects)
        try:
            result = subprocess.run(
                ['uv', 'pip', 'list', '--format=json'],
                capture_output=True, text=True,
                cwd=self.project_path
            )
            if result.returncode == 0 and result.stdout.strip():
                package_data = json.loads(result.stdout)
        except Exception:
            pass

        # Method 2: current python pip list
        if not package_data:
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'list', '--format=json'],
                    capture_output=True, text=True,
                    cwd=self.project_path
                )
                if result.returncode == 0 and result.stdout.strip():
                    package_data = json.loads(result.stdout)
            except Exception:
                pass

        if package_data:
            self.packages = {
                p['name'].lower(): p['version']
                for p in package_data
            }
            self.fastapi_version = self.packages.get('fastapi', '')
            self.sqlalchemy_version = self.packages.get('sqlalchemy', '')
            self.has_alembic = 'alembic' in self.packages
            self.has_structlog = 'structlog' in self.packages
            self.has_pydantic = 'pydantic' in self.packages
            self.has_asyncpg = 'asyncpg' in self.packages

        # Always also read config files directly
        # more reliable than pip list for uv projects
        self._detect_from_config_files()

    def _detect_from_config_files(self):
        import re
        content = ''

        # read pyproject.toml first
        toml_path = os.path.join(self.project_path, 'pyproject.toml')
        req_path = os.path.join(self.project_path, 'requirements.txt')

        if os.path.exists(toml_path):
            with open(toml_path) as f:
                content = f.read().lower()
        elif os.path.exists(req_path):
            with open(req_path) as f:
                content = f.read().lower()

        if not content:
            return

        if 'fastapi' in content and not self.fastapi_version:
            m = re.search(r'fastapi[>=<!\s"\']+([0-9][0-9.]*)', content)
            self.fastapi_version = m.group(1) if m else 'detected'
        if 'sqlalchemy' in content and not self.sqlalchemy_version:
            m = re.search(r'sqlalchemy[>=<!\s"\']+([0-9][0-9.]*)', content)
            self.sqlalchemy_version = m.group(1) if m else 'detected'
        if 'alembic' in content:
            self.has_alembic = True
        if 'structlog' in content:
            self.has_structlog = True
        if 'pydantic' in content:
            self.has_pydantic = True
        if 'asyncpg' in content:
            self.has_asyncpg = True

    async def _count_source_files(self):
        count = 0
        for root, dirs, files in os.walk(self.project_path):
            # skip hidden dirs and venv
            dirs[:] = [d for d in dirs if not d.startswith('.')
                      and d not in ('venv', 'env', '__pycache__',
                                    '.venv', 'node_modules', 'migrations')]
            for f in files:
                if f.endswith('.py'):
                    count += 1
        self.source_file_count = count
