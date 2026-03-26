import ast
from typing import Any

from py_doctor.constants import SECRET_PATTERNS

from .base_rule import BaseRule


class UnsafeFieldRule(BaseRule):
    rule_id = "pydantic/unsafe-field"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                is_pydantic = any(
                    isinstance(base, ast.Name) and base.id in ("BaseModel", "Model")
                    for base in node.bases
                )
                if is_pydantic:
                    for child in node.body:
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    if (
                                        isinstance(child.value, ast.Constant)
                                        and isinstance(child.value.value, str)
                                        and any(
                                            secret in target.id.upper()
                                            for secret in SECRET_PATTERNS
                                        )
                                    ):
                                        diagnostics.append(
                                            {
                                                "type": cls.severity,
                                                "rule": cls.rule_id,
                                                "location": f"{rel_path}:{child.lineno}",
                                                "description": f"Sensitive field {target.id} with default value — consider using SecretStr",
                                            }
                                        )
        return diagnostics


class MissingValidatorRule(BaseRule):
    rule_id = "pydantic/missing-validator"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                is_pydantic = any(
                    isinstance(base, ast.Name) and base.id in ("BaseModel", "Model")
                    for base in node.bases
                )
                if is_pydantic:
                    fields = []
                    for child in node.body:
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    fields.append(target.id)

                    for field in fields:
                        if "email" in field.lower():
                            has_validator = any(
                                isinstance(child, ast.FunctionDef)
                                and any(
                                    isinstance(dec, ast.Name) and dec.id == "validator"
                                    for dec in child.decorator_list
                                )
                                for child in node.body
                            )
                            if not has_validator:
                                diagnostics.append(
                                    {
                                        "type": cls.severity,
                                        "rule": cls.rule_id,
                                        "location": f"{rel_path}:{node.lineno}",
                                        "description": f"Email field {field} without validator — add EmailStr or custom validator",
                                    }
                                )
        return diagnostics


class MissingFieldDefaultsRule(BaseRule):
    rule_id = "pydantic/missing-field-defaults"
    severity = "INFO"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                is_pydantic = any(
                    isinstance(base, ast.Name) and base.id in ("BaseModel", "Model")
                    for base in node.bases
                )
                if is_pydantic:
                    for child in node.body:
                        if (
                            isinstance(child, ast.AnnAssign)
                            and child.value is None
                            and isinstance(child.target, ast.Name)
                        ):
                            diagnostics.append(
                                {
                                    "type": cls.severity,
                                    "rule": cls.rule_id,
                                    "location": f"{rel_path}:{child.lineno}",
                                    "description": f"Field {child.target.id} has no default value — will be required",
                                }
                            )
        return diagnostics
