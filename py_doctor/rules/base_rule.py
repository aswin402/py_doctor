import ast
class BaseRule:
    """Base class for custom rules."""
    rule_id: str = ''
    severity: str = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        return []
