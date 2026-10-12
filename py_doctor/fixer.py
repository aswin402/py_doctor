"""
Autonomous AST-guided code fixer for py_doctor.

Automatically repairs safe, unambiguous anti-patterns:
- fastapi/invalid-route-path (missing leading slash or duplicate slashes)
- pydantic/v1-deprecated-validator (@validator -> @field_validator, @root_validator -> @model_validator)
- pydantic/v1-deprecated-dump (.dict() -> .model_dump() on Pydantic models)
"""

import ast
import contextlib
import os
import re
from typing import Optional

from py_doctor.constants import DEFAULT_SKIP_DIRS
from py_doctor.rules.ast_utils import is_pydantic_model, is_route_decorator
from py_doctor.rules.pydantic_rules import PYDANTIC_DUMP_KWARGS


class ProjectFixer:
    """Detects and automatically fixes safe anti-patterns across a project codebase."""

    def __init__(self, project_path: str, ignore_files: Optional[list[str]] = None):
        self.project_path: str = os.path.abspath(project_path)
        self.ignore_files: list[str] = ignore_files or []

    def fix_all(self) -> dict[str, int]:
        """Runs all registered AST-guided fixers on project files."""
        stats = {
            "fixed_route_paths": 0,
            "fixed_validators": 0,
            "fixed_dumps": 0,
            "total_files_modified": 0,
        }

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in DEFAULT_SKIP_DIRS]

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

                try:
                    with open(filepath, encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

                new_source = source
                modified = False

                # 1. Fix invalid route paths
                routes_fixed, new_source = self.fix_route_paths(new_source, tree)
                if routes_fixed > 0:
                    stats["fixed_route_paths"] += routes_fixed
                    modified = True
                    with contextlib.suppress(Exception):
                        tree = ast.parse(new_source, filename=filepath)

                # 2. Fix deprecated Pydantic v1 validators
                validators_fixed, new_source = self.fix_pydantic_validators(new_source, tree)
                if validators_fixed > 0:
                    stats["fixed_validators"] += validators_fixed
                    modified = True
                    with contextlib.suppress(Exception):
                        tree = ast.parse(new_source, filename=filepath)

                # 3. Fix deprecated Pydantic v1 .dict() calls
                dumps_fixed, new_source = self.fix_pydantic_dumps(new_source, tree)
                if dumps_fixed > 0:
                    stats["fixed_dumps"] += dumps_fixed
                    modified = True

                if modified:
                    stats["total_files_modified"] += 1
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_source)

        return stats

    @classmethod
    def fix_route_paths(cls, source: str, tree: ast.Module) -> tuple[int, str]:
        """Repairs routes with missing leading slashes or duplicate slashes."""
        fixes = 0
        replacements: list[tuple[str, str]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for dec in node.decorator_list:
                if not is_route_decorator(dec) or not isinstance(dec, ast.Call):
                    continue

                path_str = None
                if (
                    dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)
                ):
                    path_str = dec.args[0].value
                else:
                    for kw in dec.keywords:
                        if (
                            kw.arg == "path"
                            and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                        ):
                            path_str = kw.value.value
                            break

                if path_str is not None:
                    target_cleaned = None
                    if not path_str.startswith("/"):
                        target_cleaned = f"/{path_str}"
                    elif "//" in path_str:
                        target_cleaned = "/" + "/".join(filter(None, path_str.split("/")))

                    if target_cleaned and target_cleaned != path_str:
                        replacements.append((path_str, target_cleaned))
                        fixes += 1

        new_source = source
        for old_path, new_path in replacements:
            # Replace occurrences surrounded by single or double quotes
            new_source = re.sub(
                rf'(["\']){re.escape(old_path)}\1',
                rf"\g<1>{new_path}\g<1>",
                new_source,
            )

        return fixes, new_source

    @classmethod
    def fix_pydantic_validators(cls, source: str, tree: ast.Module) -> tuple[int, str]:
        """Converts @validator to @field_validator and @root_validator to @model_validator."""
        fixes = 0
        has_v1_validator = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and is_pydantic_model(node):
                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for dec in child.decorator_list:
                        dec_name = ""
                        if isinstance(dec, ast.Name):
                            dec_name = dec.id
                        elif isinstance(dec, ast.Attribute):
                            dec_name = dec.attr
                        elif isinstance(dec, ast.Call):
                            if isinstance(dec.func, ast.Name):
                                dec_name = dec.func.id
                            elif isinstance(dec.func, ast.Attribute):
                                dec_name = dec.func.attr

                        if dec_name in ("validator", "root_validator"):
                            has_v1_validator = True
                            fixes += 1

        if not has_v1_validator:
            return 0, source

        new_source = source
        # Replace decorators
        new_source = re.sub(r"@validator\b", "@field_validator", new_source)
        new_source = re.sub(r"@root_validator\b", "@model_validator", new_source)

        # Update imports from pydantic
        # e.g., from pydantic import BaseModel, validator -> from pydantic import BaseModel, field_validator
        new_source = re.sub(r"\bvalidator\b", "field_validator", new_source)
        new_source = re.sub(r"\broot_validator\b", "model_validator", new_source)

        return fixes, new_source

    @classmethod
    def fix_pydantic_dumps(cls, source: str, tree: ast.Module) -> tuple[int, str]:
        """Converts deprecated .dict(...) calls into .model_dump(...)."""
        fixes = 0
        file_imports_pydantic = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any("pydantic" in alias.name for alias in node.names):
                    file_imports_pydantic = True
            elif isinstance(node, ast.ImportFrom) and node.module and ("pydantic" in node.module):
                file_imports_pydantic = True

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dict"
            ):
                has_pydantic_kwarg = any(
                    kw.arg in PYDANTIC_DUMP_KWARGS for kw in node.keywords if kw.arg
                )
                is_self = isinstance(node.func.value, ast.Name) and node.func.value.id == "self"

                if has_pydantic_kwarg or (is_self and file_imports_pydantic):
                    fixes += 1

        if fixes == 0:
            return 0, source

        new_source = source
        # Replace self.dict( -> self.model_dump(
        new_source = re.sub(r"\bself\.dict\(", "self.model_dump(", new_source)

        # Replace .dict( with pydantic kwargs
        for kw in PYDANTIC_DUMP_KWARGS:
            pattern = rf"\.dict\(([^)]*?{kw}\s*=)"
            new_source = re.sub(pattern, r".model_dump(\1", new_source)

        return fixes, new_source
