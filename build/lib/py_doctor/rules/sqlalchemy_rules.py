import ast
from .base_rule import BaseRule


class MissingSessionCloseRule(BaseRule):
    rule_id = 'sqlalchemy/missing-session-close'
    severity = 'ERR'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                session_created = False
                session_closed = False
                
                for child in ast.walk(node):
                    # Check for session creation
                    if (isinstance(child, ast.Assign) and
                        isinstance(child.value, ast.Call) and
                        isinstance(child.value.func, ast.Name) and
                        child.value.func.id in ('Session', 'sessionmaker')):
                        session_created = True
                    
                    # Check for session.close() or session.commit()
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr in ('close', 'commit', 'rollback')):
                        session_closed = True
                
                if session_created and not session_closed:
                    diagnostics.append({
                        'type': cls.severity,
                        'rule': cls.rule_id,
                        'location': f'{rel_path}:{node.lineno}',
                        'description': 'Database session created but never closed — potential connection leak',
                    })
        
        return diagnostics


class NoSessionScopeRule(BaseRule):
    rule_id = 'sqlalchemy/no-session-scope'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if session is passed as parameter
                has_session_param = False
                for arg in node.args.args:
                    if arg.arg in ('session', 'db', 'db_session'):
                        has_session_param = True
                        break
                
                # If no session param but uses session, it might be global
                uses_session = False
                for child in ast.walk(node):
                    if (isinstance(child, ast.Name) and 
                        child.id in ('session', 'db', 'db_session')):
                        uses_session = True
                        break
                
                if uses_session and not has_session_param:
                    diagnostics.append({
                        'type': cls.severity,
                        'rule': cls.rule_id,
                        'location': f'{rel_path}:{node.lineno}',
                        'description': 'Using global session — pass session as parameter for better testability',
                    })
        
        return diagnostics


class MissingAsyncQueryRule(BaseRule):
    rule_id = 'sqlalchemy/missing-async-query'
    severity = 'ERR'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    # Check for sync query methods in async functions
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        child.func.attr in ('execute', 'query', 'filter', 'all', 'first') and
                        not isinstance(child.func.value, ast.Await)):
                        
                        # Check if it's a SQLAlchemy query
                        if (isinstance(child.func.value, ast.Name) and 
                            child.func.value.id in ('session', 'db', 'Session')):
                            diagnostics.append({
                                'type': cls.severity,
                                'rule': cls.rule_id,
                                'location': f'{rel_path}:{child.lineno}',
                                'description': f'Sync query method {child.func.attr}() in async function — use async version (await session.execute())',
                            })
        
        return diagnostics