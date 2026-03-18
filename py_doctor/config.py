import json
import os


import sys
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]

DEFAULT_IGNORE_RULES = [
    'bandit/B404',  # subprocess import warning — expected in CLI
    'bandit/B603',  # subprocess call — expected in CLI
    'bandit/B607',  # partial executable path — expected in CLI
    'bandit/B110',  # try/except/pass — sometimes intentional
    'bandit/B112',  # try/except/continue — sometimes intentional
]

class Config:
    def __init__(self,
                 lint: bool = True,
                 dead_code: bool = True,
                 types: bool = True,
                 security: bool = True,
                 ignore_rules: Optional[list[str]] = None,
                 ignore_files: Optional[list[str]] = None):
        self.lint = lint
        self.dead_code = dead_code
        self.types = types
        self.security = security
        self.ignore_rules = DEFAULT_IGNORE_RULES + (ignore_rules or [])
        self.ignore_files = ignore_files or []

    @classmethod
    def load(cls, project_path: str) -> 'Config':
        # try py_doctor.config.json first
        json_path = os.path.join(project_path, 'py_doctor.config.json')
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
            ignore = data.get('ignore', {})
            return cls(
                lint=data.get('lint', True),
                dead_code=data.get('deadCode', True),
                types=data.get('types', True),
                security=data.get('security', True),
                ignore_rules=ignore.get('rules', []),
                ignore_files=ignore.get('files', []),
            )

        # try pyproject.toml [tool.py_doctor]
        toml_path = os.path.join(project_path, 'pyproject.toml')
        if os.path.exists(toml_path) and tomllib:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
            cfg = data.get('tool', {}).get('py_doctor', {})
            if cfg:
                ignore = cfg.get('ignore', {})
                return cls(
                    lint=cfg.get('lint', True),
                    dead_code=cfg.get('dead_code', True),
                    types=cfg.get('types', True),
                    security=cfg.get('security', True),
                    ignore_rules=ignore.get('rules', []),
                    ignore_files=ignore.get('files', []),
                )

        return cls()
