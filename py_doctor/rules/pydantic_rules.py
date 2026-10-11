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
                        field_names = []
                        val = None
                        if isinstance(child, ast.Assign):
                            field_names = [t.id for t in child.targets if isinstance(t, ast.Name)]
                            val = child.value
                        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                            field_names = [child.target.id]
                            val = child.value

                        if (
                            val
                            and isinstance(val, ast.Constant)
                            and isinstance(val.value, str)
                            and bool(val.value)
                        ):
                            for name in field_names:
                                if any(secret in name.upper() for secret in SECRET_PATTERNS):
                                    diagnostics.append(
                                        {
                                            "type": cls.severity,
                                            "rule": cls.rule_id,
                                            "location": f"{rel_path}:{child.lineno}",
                                            "description": f"Sensitive field {name} with default value — consider using SecretStr",
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
                    # Collect validator decorator targets/names
                    has_validator = any(
                        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and any(
                            (
                                isinstance(dec, ast.Name)
                                and dec.id in ("validator", "field_validator", "model_validator")
                            )
                            or (
                                isinstance(dec, ast.Call)
                                and isinstance(dec.func, ast.Name)
                                and dec.func.id in ("validator", "field_validator", "model_validator")
                            )
                            for dec in child.decorator_list
                        )
                        for child in node.body
                    )

                    for child in node.body:
                        field_name = ""
                        is_email_str = False
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name) and "email" in target.id.lower():
                                    field_name = target.id
                        elif (
                            isinstance(child, ast.AnnAssign)
                            and isinstance(child.target, ast.Name)
                            and "email" in child.target.id.lower()
                        ):
                            field_name = child.target.id
                            if (
                                isinstance(child.annotation, ast.Name)
                                and child.annotation.id == "EmailStr"
                            ) or (
                                isinstance(child.annotation, ast.Attribute)
                                and child.annotation.attr == "EmailStr"
                            ):
                                is_email_str = True

                        if field_name and not is_email_str and not has_validator:
                            diagnostics.append(
                                {
                                    "type": cls.severity,
                                    "rule": cls.rule_id,
                                    "location": f"{rel_path}:{child.lineno}",
                                    "description": f"Email field {field_name} without validator — add EmailStr or custom validator",
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
