import ast
from typing import Any

from py_doctor.constants import SECRET_PATTERNS
from .base_rule import BaseRule


class MissingResponseModelRule(BaseRule):
    rule_id = "fastapi/missing-response-model"
    severity = "WARN"
    description = "Route missing response_model - leaks internal fields and breaks API contract"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if cls._is_route_decorator(decorator) and not cls._has_response_model(
                        decorator
                    ):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{node.lineno}",
                                "description": cls.description,
                                "suggestion": "Add response_model=YourResponseModel to decorator",
                            }
                        )
        return diagnostics

    @staticmethod
    def _is_route_decorator(decorator: ast.AST) -> bool:
        return (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in ("get", "post", "put", "delete", "patch", "api_route")
        )

    @staticmethod
    def _has_response_model(decorator: ast.AST) -> bool:
        if not isinstance(decorator, ast.Call):
            return False
        return any(kw.arg == "response_model" for kw in decorator.keywords)


class SyncInAsyncRouteRule(BaseRule):
    rule_id = "fastapi/sync-in-async-route"
    severity = "ERR"
    description = "Blocking call in async route blocks the entire event loop"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if cls._is_time_sleep(child):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": "Replace time.sleep() with await asyncio.sleep()",
                            }
                        )
        return diagnostics

    @staticmethod
    def _is_time_sleep(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        )


class HardcodedSecretRule(BaseRule):
    rule_id = "fastapi/hardcoded-secret"
    severity = "ERR"
    description = "Hardcoded secret in source code - security risk"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_upper = target.id.upper()
                        if any(
                            pattern in name_upper for pattern in SECRET_PATTERNS
                        ) and cls._is_string_literal(node.value):
                            diagnostics.append(
                                {
                                    "type": cls.severity,
                                    "rule": cls.rule_id,
                                    "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                                    "description": cls.description,
                                    "suggestion": f"Move {target.id} to environment variable using pydantic-settings",
                                }
                            )
        return diagnostics

    @staticmethod
    def _is_string_literal(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and bool(node.value)
            and not node.value.startswith("${")
            and "os.environ" not in node.value
        )