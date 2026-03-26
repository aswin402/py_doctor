import json
import os
import sys
from typing import Optional

from py_doctor.constants import DEFAULT_IGNORE_RULES

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

class Config:
    def __init__(
        self,
        lint: bool = True,
        dead_code: bool = True,
        types: bool = True,
        security: bool = True,
        ignore_rules: Optional[list[str]] = None,
        ignore_files: Optional[list[str]] = None,
        custom_rules: Optional[list[str]] = None,
        severity_mapping: Optional[dict[str, str]] = None,
        threshold: int = 75,
    ):
        self.lint = lint
        self.dead_code = dead_code
        self.types = types
        self.security = security
        self.ignore_rules = DEFAULT_IGNORE_RULES + (ignore_rules or [])
        self.ignore_files = ignore_files or []
        self.custom_rules = custom_rules or []
        self.severity_mapping = severity_mapping or {}
        self.threshold = threshold

    @classmethod
    def load(cls, project_path: str, config_file: Optional[str] = None) -> "Config":
        """Load configuration from file"""
        if config_file and os.path.exists(config_file):
            return cls._load_from_file(config_file)

        json_path = os.path.join(project_path, "py_doctor.config.json")
        if os.path.exists(json_path):
            return cls._load_from_file(json_path)

        toml_path = os.path.join(project_path, "pyproject.toml")
        if os.path.exists(toml_path) and tomllib is not None:
            return cls._load_from_toml(toml_path)

        return cls()

    @classmethod
    def _load_from_file(cls, filepath: str) -> "Config":
        """Load config from JSON file"""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            ignore = data.get("ignore", {})
            return cls(
                lint=data.get("lint", True),
                dead_code=data.get("deadCode", data.get("dead_code", True)),
                types=data.get("types", True),
                security=data.get("security", True),
                ignore_rules=ignore.get("rules", []),
                ignore_files=ignore.get("files", []),
                custom_rules=data.get("customRules", []),
                severity_mapping=data.get("severityMapping", {}),
                threshold=data.get("threshold", 75),
            )
        except Exception as e:
            print(f"Warning: Could not load config from {filepath}: {e}", file=sys.stderr)
            return cls()

    @classmethod
    def _load_from_toml(cls, filepath: str) -> "Config":
        """Load config from TOML file"""
        try:
            with open(filepath, "rb") as f:
                data = tomllib.load(f)
            cfg = data.get("tool", {}).get("py_doctor", {})
            if cfg:
                ignore = cfg.get("ignore", {})
                return cls(
                    lint=cfg.get("lint", True),
                    dead_code=cfg.get("dead_code", True),
                    types=cfg.get("types", True),
                    security=cfg.get("security", True),
                    ignore_rules=ignore.get("rules", []),
                    ignore_files=ignore.get("files", []),
                    custom_rules=cfg.get("custom_rules", []),
                    severity_mapping=cfg.get("severity_mapping", {}),
                    threshold=cfg.get("threshold", 75),
                )
        except Exception as e:
            print(f"Warning: Could not load config from {filepath}: {e}", file=sys.stderr)
        return cls()
