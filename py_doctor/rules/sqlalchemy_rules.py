import ast
from typing import Any

from .base_rule import BaseRule


class MissingSessionCloseRule(BaseRule):
    rule_id = "sqlalchemy/missing-session-close"
    severity = "ERR"
    description = "Database session created but never closed - connection leak"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                session_created = any(cls._is_session_creation(child) for child in ast.walk(node))
                session_closed = any(cls._is_session_close(child) for child in ast.walk(node))
                if session_created and not session_closed:
                    diagnostics.append(
                        {
                            "type": cls.severity,
                            "rule": cls.rule_id,
                            "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                            "description": cls.description,
                            "suggestion": "Use context manager: with Session() as session: or ensure session.close()",
                        }
                    )
        return diagnostics

    @staticmethod
    def _is_session_creation(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ("Session", "sessionmaker")
        )

    @staticmethod
    def _is_session_close(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("close", "commit", "rollback")
        )


class MissingAsyncQueryRule(BaseRule):
    rule_id = "sqlalchemy/missing-async-query"
    severity = "ERR"
    description = "Sync query method in async function - blocks event loop"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        if not getattr(tree, "_parent_annotated", False):
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    child.parent = parent
            tree._parent_annotated = True

        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if cls._is_sync_query(child):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": f"Use await session.execute() instead of {getattr(getattr(child, 'func', None), 'attr', '')}()",
                            }
                        )
        return diagnostics

    @staticmethod
    def _is_sync_query(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return False
        attr = node.func.attr
        # In SQLAlchemy 2.0 AsyncSession, `await session.execute(...)` is the standard async pattern.
        # It is only a blocking sync query if execute() is called without await,
        # or if legacy 1.x Query methods (.query, .filter, .all, .first) are used on db/session.
        if attr == "execute":
            parent = getattr(node, "parent", None)
            return not isinstance(parent, ast.Await)
        if attr in ("query", "all", "first"):
            val = getattr(node.func, "value", None)
            if isinstance(val, ast.Name) and val.id.lower() in ("db", "session", "sync_session"):
                return True
            if (
                isinstance(val, ast.Call)
                and isinstance(getattr(val, "func", None), ast.Attribute)
                and getattr(val.func, "attr", None) in ("query", "filter")
            ):
                return True
        return False


class NPlusOneQueryRule(BaseRule):
    rule_id = "sqlalchemy/n-plus-one"
    severity = "WARN"
    description = "Potential N+1 query in loop - use eager loading"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.For, ast.While))
                and cls._has_query_in_loop(node)
                and not cls._has_eager_loading(tree)
            ):
                diagnostics.append(
                    {
                        "type": cls.severity,
                        "rule": cls.rule_id,
                        "location": f"{rel_path}:{getattr(node, 'lineno', 1)}",
                        "description": cls.description,
                        "suggestion": "Use joinedload() or selectinload() for relationships",
                    }
                )
        return diagnostics

    @staticmethod
    def _has_query_in_loop(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in ("execute", "query", "get", "filter")
            ):
                return True
        return False

    @staticmethod
    def _has_eager_loading(tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("joinedload", "selectinload")
            ):
                return True
        return False


class MissingIndexRule(BaseRule):
    rule_id = "sqlalchemy/missing-index"
    severity = "INFO"
    description = "Column likely needs index for performance"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if cls._is_sqlalchemy_model(node):
                # We know node is an ast.ClassDef because of the check
                for child in node.body:  # type: ignore
                    if cls._is_column_definition(child):
                        column_name = cls._get_column_name(child)
                        if not cls._has_index(child) and cls._needs_index(column_name):
                            diagnostics.append(
                                {
                                    "type": cls.severity,
                                    "rule": cls.rule_id,
                                    "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                    "description": cls.description,
                                    "suggestion": f"Add index=True to {column_name} column definition",
                                }
                            )
        return diagnostics

    @staticmethod
    def _is_sqlalchemy_model(node: ast.AST) -> bool:
        if not isinstance(node, ast.ClassDef):
            return False
        return any(
            isinstance(base, ast.Name) and base.id in ("Base", "Model") for base in node.bases
        )

    @staticmethod
    def _is_column_definition(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ("Column", "db.Column")
        )

    @staticmethod
    def _get_column_name(node: ast.AST) -> str:
        if isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return ""

    @staticmethod
    def _has_index(node: ast.AST) -> bool:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            return False
        if not node.value.keywords:
            return False
        return any(
            kw.arg == "index" and isinstance(kw.value, ast.Constant) and kw.value.value
            for kw in node.value.keywords
        )

    @staticmethod
    def _needs_index(column_name: str) -> bool:
        return any(
            term in column_name.lower()
            for term in ("_id", "email", "username", "slug", "created_at", "updated_at")
        )
