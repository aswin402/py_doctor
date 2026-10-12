import ast
from typing import Any

from py_doctor.constants import SAFE_KEY_EXCLUSIONS, SECRET_PATTERNS

from .ast_utils import annotate_parents, is_pydantic_model
from .base_rule import BaseRule


class UnsafeFieldRule(BaseRule):
    rule_id = "pydantic/unsafe-field"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and is_pydantic_model(node):
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
                            name_upper = name.upper()
                            if any(
                                safe == name_upper
                                or name_upper.endswith(f"_{safe}")
                                or name_upper.startswith(f"{safe}_")
                                for safe in SAFE_KEY_EXCLUSIONS
                            ):
                                continue
                            if any(secret in name_upper for secret in SECRET_PATTERNS):
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
            if isinstance(node, ast.ClassDef) and is_pydantic_model(node):
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
            if isinstance(node, ast.ClassDef) and is_pydantic_model(node):
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


class PydanticV1ValidatorRule(BaseRule):
    rule_id = "pydantic/v1-deprecated-validator"
    severity = "WARN"
    description = "Deprecated Pydantic v1 @validator or @root_validator used — upgrade to @field_validator or @model_validator in Pydantic v2"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []

        file_imports_pydantic = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any("pydantic" in alias.name for alias in node.names):
                    file_imports_pydantic = True
            elif isinstance(node, ast.ImportFrom) and node.module and ("pydantic" in node.module):
                file_imports_pydantic = True

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            is_model = is_pydantic_model(node) or file_imports_pydantic

            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                for dec in child.decorator_list:
                    dec_name = cls._get_decorator_name(dec)
                    if dec_name == "validator" and is_model:
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{dec.lineno}",
                                "description": (
                                    "Deprecated @validator used (Pydantic v1) — use @field_validator in Pydantic v2"
                                ),
                                "suggestion": "Replace @validator(...) with @field_validator(...) and ensure @classmethod is used",
                            }
                        )
                    elif dec_name == "root_validator" and is_model:
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{dec.lineno}",
                                "description": (
                                    "Deprecated @root_validator used (Pydantic v1) — use @model_validator in Pydantic v2"
                                ),
                                "suggestion": "Replace @root_validator(...) with @model_validator(mode='before' | 'after')",
                            }
                        )

        return diagnostics

    @staticmethod
    def _get_decorator_name(dec: ast.AST) -> str:
        if isinstance(dec, ast.Name):
            return dec.id
        if isinstance(dec, ast.Attribute):
            return dec.attr
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                return dec.func.id
            if isinstance(dec.func, ast.Attribute):
                return dec.func.attr
        return ""


PYDANTIC_DUMP_KWARGS = {
    "exclude_unset",
    "exclude_none",
    "exclude_defaults",
    "by_alias",
    "exclude",
    "include",
    "mode",
}


class PydanticV1DumpRule(BaseRule):
    rule_id = "pydantic/v1-deprecated-dump"
    severity = "WARN"
    description = "Legacy Pydantic v1 .dict() method used — deprecated in Pydantic v2 in favor of .model_dump()"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []

        file_imports_pydantic = False
        pydantic_classes: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any("pydantic" in alias.name for alias in node.names):
                    file_imports_pydantic = True
            elif isinstance(node, ast.ImportFrom) and node.module and ("pydantic" in node.module):
                file_imports_pydantic = True
            elif isinstance(node, ast.ClassDef) and is_pydantic_model(node):
                pydantic_classes.add(node.name)

        annotate_parents(tree)

        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "dict"
            ):
                continue

            has_pydantic_kwarg = any(
                kw.arg in PYDANTIC_DUMP_KWARGS for kw in node.keywords if kw.arg
            )
            is_pydantic_call = has_pydantic_kwarg

            if not is_pydantic_call:
                caller = node.func.value
                # 1. self.dict() inside a Pydantic model class
                if isinstance(caller, ast.Name) and caller.id == "self":
                    curr: Any = getattr(node, "parent", None)
                    while curr is not None:
                        if isinstance(curr, ast.ClassDef):
                            if is_pydantic_model(curr) or curr.name in pydantic_classes:
                                is_pydantic_call = True
                            break
                        curr = getattr(curr, "parent", None)

                # 2. caller is a known Pydantic model variable or parameter
                elif isinstance(caller, ast.Name) and file_imports_pydantic:
                    name_lower = caller.id.lower()
                    if name_lower in (
                        "model",
                        "schema",
                        "payload",
                        "item_in",
                        "user_in",
                        "data_in",
                    ) or name_lower.endswith(("_model", "_schema", "_in", "_payload")):
                        is_pydantic_call = True
                    else:
                        # Check enclosing function parameter annotations
                        curr = getattr(node, "parent", None)
                        while curr is not None:
                            if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                for arg in curr.args.args + curr.args.kwonlyargs:
                                    if arg.arg == caller.id and arg.annotation:
                                        ann = ast.unparse(arg.annotation)
                                        if ann in pydantic_classes or any(
                                            ann.endswith(sfx)
                                            for sfx in (
                                                "Model",
                                                "Schema",
                                                "In",
                                                "Request",
                                                "Create",
                                                "Update",
                                            )
                                        ):
                                            is_pydantic_call = True
                                break
                            curr = getattr(curr, "parent", None)

            if is_pydantic_call:
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{node.lineno}",
                        "description": cls.description,
                        "suggestion": "Replace .dict(...) with .model_dump(...)",
                    }
                )

        return diagnostics
