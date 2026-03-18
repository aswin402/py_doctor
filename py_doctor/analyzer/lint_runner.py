import ast
import json
import os
import subprocess


class LintRunner:
    def __init__(self, project_path: str, ignore_rules: list):
        self.project_path = project_path
        self.ignore_rules = ignore_rules

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
        for cmd in (
            ['uv', 'run', 'ruff', 'check', self.project_path,
             '--output-format=json', '--quiet',
             '--exclude', 'build,dist,.eggs,py_doctor.egg-info,.venv,venv,env'],
            ['ruff', 'check', self.project_path,
             '--output-format=json', '--quiet',
             '--exclude', 'build,dist,.eggs,py_doctor.egg-info,.venv,venv,env'],
        ):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    cwd=self.project_path
                )
                if result.stdout.strip():
                    break
            except FileNotFoundError:
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
            if file_path.startswith('.venv') or file_path.startswith('venv'):
                continue
            row = issue.get('location', {}).get('row', 0)
            code = issue.get('code', 'unknown')
            message = issue.get('message', '')
            sev = 'ERR' if code.startswith(('E9', 'F8', 'F9')) else 'WARN'
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
        }
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs
                       if not d.startswith('.')
                       and d not in skip_dirs]
            for filename in files:
                if not filename.endswith('.py'):
                    continue
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.project_path)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        source = f.read()
                    tree = ast.parse(source, filename=filepath)
                    diags = self._check_file(tree, rel_path)
                    diagnostics.extend(diags)
                except SyntaxError:
                    continue
                except Exception:
                    continue
        return diagnostics

    def _check_file(self, tree, rel_path) -> list[dict]:
        diagnostics = []

        skip_print = any(name in rel_path for name in (
            'reporter', 'cli', 'main', 'app',
            'console', 'terminal', 'output', 'display',
        ))

        for node in ast.walk(tree):
            # fastapi/sync-in-async-route
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call) and
                            isinstance(child.func, ast.Attribute) and
                            child.func.attr == 'sleep' and
                            isinstance(child.func.value, ast.Name) and
                            child.func.value.id == 'time'):
                        diagnostics.append({
                            'type': 'ERR',
                            'rule': 'fastapi/sync-in-async-route',
                            'location': f'{rel_path}:{child.lineno}',
                            'description': 'time.sleep() blocks event loop — use await asyncio.sleep()',
                        })

            # fastapi/missing-response-model
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and
                            isinstance(decorator.func, ast.Attribute) and
                            decorator.func.attr in (
                                'get', 'post', 'put', 'delete', 'patch')):
                        has_response_model = any(
                            kw.arg == 'response_model'
                            for kw in decorator.keywords
                        )
                        if not has_response_model:
                            diagnostics.append({
                                'type': 'WARN',
                                'rule': 'fastapi/missing-response-model',
                                'location': f'{rel_path}:{node.lineno}',
                                'description': 'Route missing response_model — leaks internal fields',
                            })

            # structlog/print-instead-of-log
            if not skip_print:
                if (isinstance(node, ast.Call) and
                        isinstance(node.func, ast.Name) and
                        node.func.id == 'print'):
                    diagnostics.append({
                        'type': 'WARN',
                        'rule': 'structlog/print-instead-of-log',
                        'location': f'{rel_path}:{node.lineno}',
                        'description': 'Use structlog logger instead of print()',
                    })

            # fastapi/hardcoded-secret
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_upper = target.id.upper()
                        if any(kw in name_upper for kw in (
                            'SECRET', 'PASSWORD', 'TOKEN',
                            'API_KEY', 'PRIVATE_KEY',
                        )):
                            if (isinstance(node.value, ast.Constant) and
                                    isinstance(node.value.value, str)):
                                diagnostics.append({
                                    'type': 'ERR',
                                    'rule': 'fastapi/hardcoded-secret',
                                    'location': f'{rel_path}:{node.lineno}',
                                    'description': f'Hardcoded secret in {target.id} — use env var',
                                })

        return diagnostics