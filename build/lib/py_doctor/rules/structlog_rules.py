import ast
from typing import Any

from .base_rule import BaseRule


class PrintInsteadLogRule(BaseRule):
    rule_id = "structlog/print-instead-of-log"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        skip_patterns = ["cli", "console", "reporter", "main", "__main__"]
        if any(pattern in rel_path.lower() for pattern in skip_patterns):
            return diagnostics

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{node.lineno}",
                        "description": "Use structlog logger instead of print() for structured logging",
                    }
                )
        return diagnostics


class MissingContextLoggingRule(BaseRule):
    rule_id = "structlog/missing-context"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                uses_logging = any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id in ("logger", "log", "structlog")
                    for child in ast.walk(node)
                )
                if uses_logging and node.args.args:
                    first_arg = node.args.args[0].arg
                    if first_arg not in ("self", "cls"):
                        binds_context = any(
                            isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Attribute)
                            and child.func.attr == "bind"
                            for child in ast.walk(node)
                        )
                        if not binds_context:
                            diagnostics.append(
                                {
                                    "type": cls.severity,
                                    "rule": cls.rule_id,
                                    "location": f"{rel_path}:{node.lineno}",
                                    "description": f"Logging without context in {node.name} — consider using logger.bind() to add request/user context",
                                }
                            )
        return diagnostics


class MissingExceptionLoggingRule(BaseRule):
    rule_id = "structlog/missing-exception"
    severity = "WARN"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                logs_exception = any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr in ("exception", "error")
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id in ("logger", "log")
                    for child in ast.walk(node)
                )
                if not logs_exception:
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{node.lineno}",
                            "description": "Exception caught but not logged — use logger.exception() to capture stack trace",
                        }
                    )
        return diagnostics
