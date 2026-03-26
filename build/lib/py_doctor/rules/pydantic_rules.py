import ast
from .base_rule import BaseRule


class UnsafeFieldRule(BaseRule):
    rule_id = 'pydantic/unsafe-field'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Pydantic model
                is_pydantic = False
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if base.id in ('BaseModel', 'Model'):
                            is_pydantic = True
                            break
                
                if is_pydantic:
                    for child in node.body:
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    # Check for potentially unsafe field defaults
                                    if (isinstance(child.value, ast.Constant) and
                                        isinstance(child.value.value, str) and
                                        any(secret in target.id.upper() 
                                            for secret in ('PASSWORD', 'TOKEN', 'SECRET', 'KEY'))):
                                        diagnostics.append({
                                            'type': cls.severity,
                                            'rule': cls.rule_id,
                                            'location': f'{rel_path}:{child.lineno}',
                                            'description': f'Sensitive field {target.id} with default value — consider using SecretStr',
                                        })
        
        return diagnostics


class MissingValidatorRule(BaseRule):
    rule_id = 'pydantic/missing-validator'
    severity = 'WARN'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Pydantic model
                is_pydantic = False
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if base.id in ('BaseModel', 'Model'):
                            is_pydantic = True
                            break
                
                if is_pydantic:
                    fields = []
                    for child in node.body:
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    fields.append(target.id)
                    
                    # Check for email field without validator
                    for field in fields:
                        if 'email' in field.lower():
                            has_validator = False
                            for child in node.body:
                                if (isinstance(child, ast.FunctionDef) and
                                    any(dec.id == 'validator' for dec in child.decorator_list 
                                        if isinstance(dec, ast.Name))):
                                    has_validator = True
                                    break
                            
                            if not has_validator:
                                diagnostics.append({
                                    'type': cls.severity,
                                    'rule': cls.rule_id,
                                    'location': f'{rel_path}:{node.lineno}',
                                    'description': f'Email field {field} without validator — add EmailStr or custom validator',
                                })
        
        return diagnostics


class MissingFieldDefaultsRule(BaseRule):
    rule_id = 'pydantic/missing-field-defaults'
    severity = 'INFO'

    @classmethod
    def check(cls, tree: ast.Module, source: str, rel_path: str) -> list[dict]:
        diagnostics = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Pydantic model
                is_pydantic = False
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if base.id in ('BaseModel', 'Model'):
                            is_pydantic = True
                            break
                
                if is_pydantic:
                    for child in node.body:
                        if isinstance(child, ast.AnnAssign):
                            # Field without default value
                            if child.value is None:
                                if isinstance(child.target, ast.Name):
                                    diagnostics.append({
                                        'type': cls.severity,
                                        'rule': cls.rule_id,
                                        'location': f'{rel_path}:{child.lineno}',
                                        'description': f'Field {child.target.id} has no default value — will be required',
                                    })
        
        return diagnostics