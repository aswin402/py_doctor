import ast
import json
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any


class LintRunner:
    def __init__(self, project_path: str, ignore_rules: list):
        self.project_path = project_path
        self.ignore_rules = ignore_rules
        # Import custom rules properly
        self._load_custom_rules()

    def _load_custom_rules(self):
        """Load all custom rules from the rules directory"""
        self.custom_rules = []
        try:
            from py_doctor.rules import base_rule
            from py_doctor.rules import fastapi_rules
            from py_doctor.rules import sqlalchemy_rules
            from py_doctor.rules import pydantic_rules
            from py_doctor.rules import structlog_rules
            
            # Collect all rule classes that inherit from BaseRule
            import inspect
            import sys
            
            for module in [fastapi_rules, sqlalchemy_rules, pydantic_rules, structlog_rules]:
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        hasattr(obj, 'check') and 
                        hasattr(obj, 'rule_id') and
                        obj.rule_id):
                        self.custom_rules.append(obj)
        except Exception as e:
            print(f"Warning: Could not load custom rules: {e}")

    async def run(self) -> list[dict]:
        diagnostics = []
        ruff_diags = await self._run_ruff()
        diagnostics.extend(ruff_diags)
        custom_diags = await self._run_custom_rules()
        diagnostics.extend(custom_diags)
        return [d for d in diagnostics
                if d['rule'] not in self.ignore_rules]

    async def _run_ruff(self) -> list[dict]:
        result = None
        exclude_dirs = 'build,dist,.eggs,py_doctor.egg-info,.venv,venv,env,__pycache__'
        
        for cmd in (
            ['uv', 'run', 'ruff', 'check', self.project_path,
             '--output-format=json', '--quiet',
             '--exclude', exclude_dirs],
            ['ruff', 'check', self.project_path,
             '--output-format=json', '--quiet',
             '--exclude', exclude_dirs],
        ):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    cwd=self.project_path,
                    timeout=30
                )
                if result.returncode == 0 or result.stdout.strip():
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if result is None or not result.stdout.strip():
            return []

        try:
            issues = json.loads(result.stdout)
        except Exception:
            return []

        diagnostics = []
        for issue in issues:
            abs_path = issue.get('filename', '')
            try:
                file_path = os.path.relpath(abs_path, self.project_path)
            except ValueError:
                file_path = abs_path
            
            # Skip venv files
            if any(skip in file_path for skip in ['.venv', 'venv', 'env', '__pycache__']):
                continue
                
            row = issue.get('location', {}).get('row', 0)
            code = issue.get('code', 'unknown')
            message = issue.get('message', '')
            
            # Determine severity based on ruff's severity
            severity = issue.get('fix', {}).get('applicability', '')
            if code.startswith(('E9', 'F8', 'F9')) or severity == 'unsafe':
                sev = 'ERR'
            elif code.startswith(('E', 'F')):
                sev = 'WARN'
            else:
                sev = 'INFO'
                
            diagnostics.append({
                'type': sev,
                'rule': f'ruff/{code}',
                'location': f'{file_path}:{row}',
                'description': message,
            })
        return diagnostics

    async def _run_custom_rules(self) -> list[dict]:
        diagnostics = []
        skip_dirs = {
            'venv', 'env', '__pycache__', '.venv',
            'build', 'dist', 'eggs', '.eggs', 'py_doctor.egg-info',
            'migrations', 'alembic', 'tests', 'test', 'node_modules'
        }
        
        for root, dirs, files in os.walk(self.project_path):
            # Filter directories
            dirs[:] = [d for d in dirs 
                       if not d.startswith('.')
                       and d not in skip_dirs]
            
            for filename in files:
                if not filename.endswith('.py'):
                    continue
                    
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.project_path)
                
                # Skip __init__.py for some checks
                skip_file = filename == '__init__.py'
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        source = f.read()
                    
                    tree = ast.parse(source, filename=filepath)
                    
                    # Apply each custom rule
                    for rule_class in self.custom_rules:
                        # Skip certain files for specific rules
                        if skip_file and 'import' in rule_class.rule_id:
                            continue
                            
                        try:
                            diags = rule_class.check(tree, source, rel_path)
                            diagnostics.extend(diags)
                        except Exception as e:
                            # Silently continue on rule errors
                            pass
                            
                except (SyntaxError, UnicodeDecodeError):
                    continue
                except Exception:
                    continue
                    
        return diagnostics