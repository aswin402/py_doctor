import ast
from .base_rule import BaseRule

class MissingResponseModelRule(BaseRule):
    rule_id = 'fastapi/missing-response-model'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and
                        isinstance(decorator.func, ast.Attribute) and
                        decorator.func.attr in ('get','post','put','delete','patch')):
                        has_response_model = any(
                            kw.arg == 'response_model' for kw in decorator.keywords
                        )
                        if not has_response_model:
                            diagnostics.append({
                                'type': cls.severity,
                                'rule': cls.rule_id,
                                'location': f'{rel_path}:{node.lineno}',
                                'description': 'Route missing response_model — leaks internal fields',
                            })
        return diagnostics

# Additional FastAPI rules stub
class SyncInAsyncRouteRule(BaseRule):
    rule_id = 'fastapi/sync-in-async-route'
    severity = 'ERR'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        # impl similar to lint_runner AST
        return []
