"""Shared AST inspection and traversal utilities for py_doctor rules."""

import ast
from typing import Optional

ROUTE_METHODS = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "api_route",
    "head",
    "options",
    "websocket",
}

DB_CALLER_NAMES = {
    "session",
    "db",
    "conn",
    "connection",
    "cursor",
    "client",
    "pool",
    "transaction",
    "engine",
    "async_session",
    "sync_session",
}

PYDANTIC_BASE_NAMES = {
    "BaseModel",
    "Model",
    "BaseSettings",
}


def annotate_parents(tree: ast.AST) -> None:
    """Recursively annotate each child node with a reference to its parent."""
    if getattr(tree, "_parent_annotated", False):
        return
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent  # type: ignore[attr-defined]
    tree._parent_annotated = True  # type: ignore[attr-defined]


def is_route_decorator(decorator: ast.AST) -> bool:
    """Check if decorator is a FastAPI / Starlette route decorator."""
    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
        return False
    return decorator.func.attr in ROUTE_METHODS


def is_pydantic_model(node: ast.AST) -> bool:
    """Check if a ClassDef inherits from a Pydantic model or settings base."""
    if not isinstance(node, ast.ClassDef):
        return False
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in PYDANTIC_BASE_NAMES:
            return True
        if isinstance(base, ast.Attribute) and base.attr in PYDANTIC_BASE_NAMES:
            return True
    return False


def is_db_caller(node: Optional[ast.AST]) -> bool:
    """Check if an expression refers to a database connection or session object."""
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id.lower() in DB_CALLER_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr.lower() in DB_CALLER_NAMES or is_db_caller(node.value)
    return False


def is_string_literal(node: ast.AST) -> bool:
    """Check if an AST node is a non-empty string literal (not an env template)."""
    return bool(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value
        and not node.value.startswith("${")
        and "os.environ" not in node.value
        and "os.getenv" not in node.value
    )
