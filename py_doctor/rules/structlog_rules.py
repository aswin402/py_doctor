import ast
from .base_rule import BaseRule


class PrintInsteadLogRule(BaseRule):
    rule_id = 'structlog/print-instead-of-log'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        # Skip files that are CLI tools where print is acceptable
        skip_patterns = ['cli', 'console', 'reporter', 'main', '__main__']
        if any(pattern in rel_path.lower() for pattern in skip_patterns):
            return diagnostics
        
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Name) and
                node.func.id == 'print'):
                diagnostics.append({
                    'type': cls.severity,
                    'rule': cls.rule_id,
                    'location': f'{rel_path}:{node.lineno}',
                    'description': 'Use structlog logger instead of print() for structured logging',
                })
        
        return diagnostics


class MissingContextLoggingRule(BaseRule):
    rule_id = 'structlog/missing-context'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if function uses logging
                uses_logging = False
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        isinstance(child.func.value, ast.Name) and
                        child.func.value.id in ('logger', 'log', 'structlog')):
                        uses_logging = True
                        break
                
                if uses_logging:
                    # Check if function binds context
                    binds_context = False
                    for child in ast.walk(node):
                        if (isinstance(child, ast.Call) and
                            isinstance(child.func, ast.Attribute) and
                            child.func.attr == 'bind'):
                            binds_context = True
                            break
                    
                    if not binds_context and node.args.args:
                        # Check if first argument is self/cls
                        first_arg = node.args.args[0].arg
                        if first_arg not in ('self', 'cls'):
                            # Suggest adding context
                            diagnostics.append({
                                'type': cls.severity,
                                'rule': cls.rule_id,
                                'location': f'{rel_path}:{node.lineno}',
                                'description': f'Logging without context in {node.name} — consider using logger.bind() to add request/user context',
                            })
        
        return diagnostics


class MissingExceptionLoggingRule(BaseRule):
    rule_id = 'structlog/missing-exception'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if exception handler logs the exception
                logs_exception = False
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr in ('exception', 'error') and
                        isinstance(child.func.value, ast.Name) and
                        child.func.value.id in ('logger', 'log')):
                        logs_exception = True
                        break
                
                if not logs_exception:
                    diagnostics.append({
                        'type': cls.severity,
                        'rule': cls.rule_id,
                        'location': f'{rel_path}:{node.lineno}',
                        'description': 'Exception caught but not logged — use logger.exception() to capture stack trace',
                    })
        
        return diagnostics