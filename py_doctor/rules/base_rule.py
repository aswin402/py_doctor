import ast
from typing import Any


class BaseRule:
    """Base class for all custom rules"""

    rule_id: str = ""
    severity: str = "WARN"
    description: str = ""

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict[str, Any]]:
        """Check the AST for violations"""
        return []

    @classmethod
    def get_help(cls) -> str:
        """Get help text for this rule"""
        return cls.description
