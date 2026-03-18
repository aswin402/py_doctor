import subprocess
import json
import os

class TypeRunner:
    def __init__(self, project_path: str, ignore_rules: list):
        self.project_path = project_path
        self.ignore_rules = ignore_rules

    async def run(self) -> list[dict]:
        for cmd in (
            ['uv', 'run', 'mypy', self.project_path,
             '--output=json', '--ignore-missing-imports',
             '--no-error-summary'],
            ['mypy', self.project_path,
             '--output=json', '--ignore-missing-imports',
             '--no-error-summary'],
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
        else:
            return []

        diagnostics = []
        for line in result.stdout.splitlines():
            try:
                issue = json.loads(line)
                file_path = os.path.relpath(
                    issue.get('file', ''), self.project_path)
                line_no = issue.get('line', 0)
                message = issue.get('message', '')
                severity = issue.get('severity', 'error')
                code = issue.get('error_code', 'type-error')
                if f'mypy/{code}' in self.ignore_rules:
                    continue
                diagnostics.append({
                    'type': 'ERR' if severity == 'error' else 'WARN',
                    'rule': f'mypy/{code}',
                    'location': f'{file_path}:{line_no}',
                    'description': message,
                })
            except Exception:
                continue
        return diagnostics
