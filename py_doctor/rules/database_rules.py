import ast
from typing import Any

from .ast_utils import annotate_parents, is_db_caller
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


class MissingPoolConfigRule(BaseRule):
    rule_id = "database/missing-pool-config"
    severity = "WARN"
    description = "Database pool not configured with optimal settings"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if cls._is_missing_pool_config(node):
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                        "description": cls.description,
                        "suggestion": "Configure pool_size=20, max_overflow=10 for production",
                    }
                )
        return diagnostics

    @staticmethod
    def _is_missing_pool_config(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))):
            return False
        func_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        if func_name not in ("create_async_engine", "create_engine"):
            return False
        # SQLite does not support pool_size/max_overflow (raises ArgumentError in SQLAlchemy)
        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.startswith("sqlite")
        ):
            return False
        for kw in node.keywords:
            if (
                kw.arg == "url"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
                and kw.value.value.startswith("sqlite")
            ):
                return False
        return not any(kw.arg in ("pool_size", "max_overflow") for kw in node.keywords)


class ConnectionLeakRule(BaseRule):
    rule_id = "database/connection-leak"
    severity = "ERR"
    description = "Potential connection leak - more acquires than releases"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        annotate_parents(tree)

        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                acquires = sum(
                    1
                    for child in ast.walk(node)
                    if cls._is_acquire(child) and not cls._is_in_context_manager(child)
                )
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
    def _is_in_context_manager(node: ast.AST) -> bool:
        parent = getattr(node, "parent", None)
        if isinstance(parent, ast.withitem):
            return True
        grandparent = getattr(parent, "parent", None)
        return isinstance(grandparent, (ast.With, ast.AsyncWith))

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
                val = getattr(child.func, "value", None)
                if is_db_caller(val):
                    return True
        return False

    @staticmethod
    def _has_transaction(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, (ast.With, ast.AsyncWith)):
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
        annotate_parents(tree)

        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                parent = getattr(node, "parent", None)
                # Only check the outermost call in an expression or assignment to avoid duplicate alerts on sub-calls
                if isinstance(parent, (ast.Attribute, ast.Call)):
                    continue
                segment = ast.get_source_segment(source, node)
                if not segment:
                    continue
                if cls._is_select_query(node, segment) and not cls._has_limit(node, segment):
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
    def _is_select_query(node: ast.AST, segment: str) -> bool:
        seg_lower = segment.lower()
        if "select(" in seg_lower:
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("all", "fetch", "fetchall")
        ):
            val = getattr(node.func, "value", None)
            if (
                isinstance(val, ast.Call)
                and isinstance(getattr(val, "func", None), ast.Attribute)
                and getattr(val.func, "attr", None) in ("query", "filter", "where")
            ):
                return True
            if is_db_caller(val):
                return True
        return False

    @staticmethod
    def _has_limit(node: ast.AST, segment: str) -> bool:
        seg_lower = segment.lower()
        return any(
            term in seg_lower
            for term in (".limit(", "limit=", "offset=", "first()", "one()", "slice(", "paginate")
        )


class NPlusOneQueryRule(BaseRule):
    rule_id = "database/n-plus-one-query"
    severity = "WARN"
    description = (
        "Database query executed inside a loop - potential N+1 query performance bottleneck"
    )

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                for child in ast.walk(node):
                    if child is node:
                        continue
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                        attr_name = child.func.attr
                        if attr_name in (
                            "execute",
                            "scalars",
                            "scalar",
                            "fetch",
                            "fetchall",
                            "fetchrow",
                        ):
                            val = getattr(child.func, "value", None)
                            if is_db_caller(val) or attr_name in ("fetchall", "fetchrow"):
                                diagnostics.append(
                                    {
                                        "type": cls.severity,
                                        "rule": cls.rule_id,
                                        "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                        "description": cls.description,
                                        "suggestion": "Batch queries using IN clauses, eager loading (selectinload/joinedload), or query outside loop",
                                    }
                                )
                                break
        return diagnostics
