import subprocess
import json
import os

class SecurityRunner:
    def __init__(self, project_path: str, ignore_rules: list):
        self.project_path = project_path
        self.ignore_rules = ignore_rules

    async def run(self) -> list[dict]:
        for cmd in (
            ['uv', 'run', 'bandit', '-r', self.project_path,
             '-f', 'json', '-q',
             '--exclude', '.venv,venv,env,migrations,.git'],
            ['bandit', '-r', self.project_path,
             '-f', 'json', '-q',
             '--exclude', '.venv,venv,env,migrations,.git'],
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

        try:
            data = json.loads(result.stdout)
        except Exception:
            return []

        diagnostics = []
        for issue in data.get('results', []):
            file_path = os.path.relpath(
                issue.get('filename', ''), self.project_path)
            line_no = issue.get('line_number', 0)
            severity = issue.get('issue_severity', 'LOW')
            test_id = issue.get('test_id', '')
            text = issue.get('issue_text', '')
            rule = f'bandit/{test_id}'
            if rule in self.ignore_rules:
                continue
            diagnostics.append({
                'type': 'ERR' if severity == 'HIGH' else 'WARN',
                'rule': rule,
                'location': f'{file_path}:{line_no}',
                'description': text,
            })
        return diagnostics
