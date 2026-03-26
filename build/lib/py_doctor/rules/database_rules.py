import ast
from typing import Any

from .base_rule import BaseRule


class MissingConnectionPoolRule(BaseRule):
    rule_id = "database/missing-connection-pool"
    severity = "ERR"
    description = "Direct database connection without connection pool - performance issue"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if cls._is_direct_connection(node):
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                        "description": cls.description,
                        "suggestion": "Use create_async_pool() for asyncpg or create_engine() with pool for SQLAlchemy",
                    }
                )
            if cls._is_missing_pool_config(node):
                diagnostics.append(
                    {
                        "type": "WARN",
                        "rule": "database/missing-pool-config",
                        "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                        "description": "Database pool not configured with optimal settings",
                        "suggestion": "Configure pool_size=20, max_overflow=10 for production",
                    }
                )
        return diagnostics

    @staticmethod
    def _is_direct_connection(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "connect"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncpg"
        )

    @staticmethod
    def _is_missing_pool_config(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            return False
        return node.func.id in ("create_async_engine", "create_engine") and not any(
            kw.arg in ("pool_size", "max_overflow") for kw in node.keywords
        )


class ConnectionLeakRule(BaseRule):
    rule_id = "database/connection-leak"
    severity = "ERR"
    description = "Potential connection leak - more acquires than releases"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                acquires = sum(1 for child in ast.walk(node) if cls._is_acquire(child))
                releases = sum(1 for child in ast.walk(node) if cls._is_release(child))
                if acquires > releases:
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                            "description": cls.description,
                            "suggestion": f"Ensure each acquire() has matching release() - missing {acquires - releases} release(s)",
                        }
                    )
        return diagnostics

    @staticmethod
    def _is_acquire(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "acquire"
        )

    @staticmethod
    def _is_release(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "release"
        )


class TransactionManagementRule(BaseRule):
    rule_id = "database/transaction-management"
    severity = "ERR"
    description = "Missing transaction management - potential data inconsistency"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_write = cls._has_write_operation(node)
                has_transaction = cls._has_transaction(node)
                if has_write and not has_transaction:
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                            "description": cls.description,
                            "suggestion": "Use async with db.begin(): for atomic transactions",
                        }
                    )
        return diagnostics

    @staticmethod
    def _has_write_operation(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in ("insert", "update", "delete", "execute")
            ):
                return True
        return False

    @staticmethod
    def _has_transaction(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.With):
                for item in child.items:
                    if (
                        isinstance(item.context_expr, ast.Call)
                        and isinstance(item.context_expr.func, ast.Attribute)
                        and item.context_expr.func.attr == "begin"
                    ):
                        return True
        return False


class SlowQueryDetectionRule(BaseRule):
    rule_id = "database/slow-query"
    severity = "WARN"
    description = "Potential slow query without limit or pagination"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and cls._is_select_query(node)
                and not cls._has_limit(node)
            ):
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                        "description": cls.description,
                        "suggestion": "Add .limit() or pagination to prevent loading all rows",
                    }
                )
        return diagnostics

    @staticmethod
    def _is_select_query(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return False
        return node.func.attr in ("select", "query", "execute") and "select" in str(node).lower()

    @staticmethod
    def _has_limit(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        return any("limit" in str(kw).lower() for kw in node.keywords)