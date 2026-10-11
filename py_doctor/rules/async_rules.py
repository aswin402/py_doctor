import ast
from typing import Any

from .base_rule import BaseRule


class MissingAwaitRule(BaseRule):
    rule_id = "async/missing-await"
    severity = "ERR"
    description = "Missing await on coroutine - coroutine will not execute"

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        # Ensure parent annotations exist even if check() is called standalone
        if not getattr(tree, "_parent_annotated", False):
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    child.parent = parent
            tree._parent_annotated = True

        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if cls._is_awaitable_call(child) and not cls._is_awaited(child):
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": f"Add await before {cls._get_call_name(child)}",
                            }
                        )
        return diagnostics

    @staticmethod
    def _is_awaitable_call(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return False

        attr = node.func.attr
        if attr in ("fetch", "fetchrow", "fetchval", "fetchall", "execute", "executemany"):
            return True

        # HTTP client or async db session calls
        if attr in ("get", "post", "put", "delete", "patch"):
            val = getattr(node.func, "value", None)
            if isinstance(val, ast.Name):
                return val.id.lower() in ("client", "session", "async_session", "httpx", "http", "http_client", "db")
            if isinstance(val, ast.Attribute):
                return val.attr.lower() in ("client", "session", "async_session", "httpx", "http", "http_client", "db")
            return False

        return False

    @staticmethod
    def _is_awaited(node: ast.AST) -> bool:
        parent = getattr(node, "parent", None)
        if isinstance(parent, (ast.Await, ast.AsyncWith)):
            return True
        if isinstance(parent, ast.Call):
            func = getattr(parent, "func", None)
            if isinstance(func, ast.Attribute) and func.attr in ("gather", "create_task", "wait", "shield"):
                return True
            if isinstance(func, ast.Name) and func.id in ("create_task", "gather"):
                return True
        return False

    @staticmethod
    def _get_call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            return node.func.attr
        return "call"


class BlockingIOInAsyncRule(BaseRule):
    rule_id = "async/blocking-io"
    severity = "ERR"
    description = "Blocking I/O operation in async function - blocks event loop"

    BLOCKING_FUNCTIONS = {
        "open": "file I/O",
        "time.sleep": "sleep",
        "os.system": "system call",
        "subprocess.run": "subprocess",
    }

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if cls._is_blocking_call(child):
                        operation = cls._get_operation_name(child)
                        diagnostics.append(
                            {
                                "type": cls.severity,
                                "rule": cls.rule_id,
                                "location": f"{rel_path}:{getattr(child, 'lineno', 1)}",
                                "description": cls.description,
                                "suggestion": f"Use async alternative for {operation} or run in executor: await asyncio.to_thread(...)",
                            }
                        )
        return diagnostics

    @classmethod
    def _is_blocking_call(cls, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if isinstance(node.func, ast.Name) and node.func.id in cls.BLOCKING_FUNCTIONS:
            return True
        return bool(
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
            and node.func.attr == "sleep"
        )

    @classmethod
    def _get_operation_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return cls.BLOCKING_FUNCTIONS.get(node.func.id, node.func.id)
        return "I/O operation"
