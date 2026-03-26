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
                        decorator.func.attr in ('get', 'post', 'put', 'delete', 'patch', 'api_route')):
                        has_response_model = any(
                            kw.arg == 'response_model' for kw in decorator.keywords
                        )
                        if not has_response_model:
                            diagnostics.append({
                                'type': cls.severity,
                                'rule': cls.rule_id,
                                'location': f'{rel_path}:{node.lineno}',
                                'description': 'Route missing response_model — leaks internal fields and breaks API contract',
                            })
        return diagnostics


class SyncInAsyncRouteRule(BaseRule):
    rule_id = 'fastapi/sync-in-async-route'
    severity = 'ERR'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check for blocking calls in async functions
                for child in ast.walk(node):
                    # time.sleep()
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr == 'sleep' and
                        isinstance(child.func.value, ast.Name) and
                        child.func.value.id == 'time'):
                        diagnostics.append({
                            'type': cls.severity,
                            'rule': cls.rule_id,
                            'location': f'{rel_path}:{child.lineno}',
                            'description': 'time.sleep() blocks event loop — use await asyncio.sleep()',
                        })
                    
                    # Synchronous database calls
                    elif (isinstance(child, ast.Call) and
                          isinstance(child.func, ast.Attribute) and
                          'execute' in child.func.attr and
                          not isinstance(child.func.value, ast.Await)):
                        # Check if this is a SQLAlchemy sync call in async function
                        for parent in ast.walk(node):
                            if (isinstance(parent, ast.Assign) and
                                isinstance(parent.value, ast.Call)):
                                # Heuristic: likely sync SQLAlchemy call
                                diagnostics.append({
                                    'type': cls.severity,
                                    'rule': cls.rule_id,
                                    'location': f'{rel_path}:{child.lineno}',
                                    'description': f'Potential blocking call {child.func.attr}() in async route — use async version',
                                })
        return diagnostics


class HardcodedSecretRule(BaseRule):
    rule_id = 'fastapi/hardcoded-secret'
    severity = 'ERR'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        secret_patterns = [
            'SECRET', 'PASSWORD', 'TOKEN', 'API_KEY', 
            'PRIVATE_KEY', 'JWT_SECRET', 'SALT', 'KEY'
        ]
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_upper = target.id.upper()
                        if any(pattern in name_upper for pattern in secret_patterns):
                            # Check if value is a string literal
                            if (isinstance(node.value, ast.Constant) and
                                    isinstance(node.value.value, str) and
                                    node.value.value and
                                    not node.value.value.startswith('${')):
                                
                                # Skip if it's an environment variable reference
                                if node.value.value.startswith('os.environ') or '$' in node.value.value:
                                    continue
                                    
                                diagnostics.append({
                                    'type': cls.severity,
                                    'rule': cls.rule_id,
                                    'location': f'{rel_path}:{node.lineno}',
                                    'description': f'Hardcoded secret in {target.id} — use env var or secrets manager',
                                })
        return diagnostics


class MissingStatusCodeRule(BaseRule):
    rule_id = 'fastapi/missing-status-code'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and
                        isinstance(decorator.func, ast.Attribute) and
                        decorator.func.attr in ('post', 'put', 'delete', 'patch')):
                        has_status_code = any(
                            kw.arg == 'status_code' for kw in decorator.keywords
                        )
                        if not has_status_code:
                            diagnostics.append({
                                'type': cls.severity,
                                'rule': cls.rule_id,
                                'location': f'{rel_path}:{node.lineno}',
                                'description': 'Route missing status_code — use appropriate HTTP status codes',
                            })
        return diagnostics


class MissingDependencyInjectionRule(BaseRule):
    rule_id = 'fastapi/missing-di'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for direct database instantiation
                for child in ast.walk(node):
                    if (isinstance(child, ast.Assign) and
                        isinstance(child.value, ast.Call) and
                        isinstance(child.value.func, ast.Name) and
                        child.value.func.id in ('Session', 'sessionmaker')):
                        diagnostics.append({
                            'type': cls.severity,
                            'rule': cls.rule_id,
                            'location': f'{rel_path}:{child.lineno}',
                            'description': 'Direct database session creation in route — use FastAPI dependency injection',
                        })
        return diagnostics