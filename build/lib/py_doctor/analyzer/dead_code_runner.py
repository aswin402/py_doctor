import os
import ast
from pathlib import Path


class DeadCodeRunner:
    def __init__(self, project_path: str, ignore_files: list):
        self.project_path = project_path
        self.ignore_files = ignore_files

    async def run(self) -> list[dict]:
        diagnostics = []
        unused_files = await self._find_unused_files()
        diagnostics.extend(unused_files)
        duplicates = await self._find_duplicates()
        diagnostics.extend(duplicates)
        return diagnostics

    async def _find_unused_files(self) -> list[dict]:
        diagnostics = []
        py_files = []

        skip_dirs = {
            'venv', 'env', '__pycache__', '.venv', 'node_modules',
            'migrations', 'alembic', 'tests', 'test',
            'build', 'dist', 'eggs', '.eggs', 'py_doctor.egg-info',
        }

        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs
                       if not d.startswith('.')
                       and d not in skip_dirs]
            for f in files:
                if f.endswith('.py') and f != '__init__.py':
                    py_files.append(os.path.join(root, f))

        all_imported_names = set()

        for filepath in py_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source: str = f.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.name
                            all_imported_names.add(name)
                            parts = name.split('.')
                            for i in range(1, len(parts) + 1):
                                all_imported_names.add('.'.join(parts[:i]))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            all_imported_names.add(node.module)
                            parts = node.module.split('.')
                            for i in range(1, len(parts) + 1):
                                all_imported_names.add('.'.join(parts[:i]))
                            path_version = node.module.replace('.', os.sep)
                            all_imported_names.add(path_version)
                            all_imported_names.add(parts[-1])
                        for alias in node.names:
                            all_imported_names.add(alias.name)
            except Exception:
                continue

        for filepath in py_files:
            rel = os.path.relpath(filepath, self.project_path)

            basename = os.path.basename(filepath)
            if basename in (
                'main.py', 'app.py', 'wsgi.py', 'asgi.py',
                'settings.py', 'config.py', 'conftest.py',
                'celery.py', 'worker.py', 'cli.py',
            ):
                continue

            if any(ig.rstrip('/') in rel for ig in self.ignore_files):
                continue

            stem = Path(filepath).stem
            rel_no_ext = rel.replace(os.sep, '.').replace('.py', '')
            rel_as_path = rel.replace('.py', '')

            possible = {stem, rel_no_ext, rel_as_path}
            parts = rel_no_ext.split('.')
            for i in range(len(parts)):
                possible.add('.'.join(parts[i:]))
            path_parts = rel_as_path.split(os.sep)
            for i in range(len(path_parts)):
                possible.add(os.sep.join(path_parts[i:]))
                possible.add('.'.join(path_parts[i:]))

            is_imported = bool(possible & all_imported_names)

            if not is_imported:
                diagnostics.append({
                    'type': 'DEAD',
                    'subType': 'UNUSED FILE',
                    'description': rel,
                })

        return diagnostics

    async def _find_duplicates(self) -> list[dict]:
        diagnostics = []
        skip_dirs = {
            'venv', 'env', '__pycache__', '.venv', 'node_modules',
            'migrations', 'alembic', 'tests', 'test',
            'build', 'dist', 'eggs', '.eggs', 'py_doctor.egg-info',
        }
        by_name: dict[str, list[str]] = {}
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs
                       if not d.startswith('.')
                       and d not in skip_dirs]
            for f in files:
                if f.endswith('.py') and f != '__init__.py':
                    filepath = os.path.join(root, f)
                    by_name.setdefault(f, []).append(
                        os.path.relpath(filepath, self.project_path))
        for paths in by_name.values():
            if len(paths) > 1:
                diagnostics.append({
                    'type': 'DEAD',
                    'subType': 'DUPLICATE',
                    'description': ' ≈ '.join(paths),
                })
        return diagnostics