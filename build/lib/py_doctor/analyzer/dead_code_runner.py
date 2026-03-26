import os
import ast
from pathlib import Path
from typing import Set, List, Dict


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
        unused_imports = await self._find_unused_imports()
        diagnostics.extend(unused_imports)
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
        import_structures = {}  # Store import relationships

        for filepath in py_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source: str = f.read()
                tree = ast.parse(source)
                imports = self._extract_imports(tree)
                all_imported_names.update(imports)
                import_structures[filepath] = imports
            except Exception:
                continue

        for filepath in py_files:
            rel = os.path.relpath(filepath, self.project_path)

            basename = os.path.basename(filepath)
            if basename in (
                'main.py', 'app.py', 'wsgi.py', 'asgi.py',
                'settings.py', 'config.py', 'conftest.py',
                'celery.py', 'worker.py', 'cli.py', '__init__.py'
            ):
                continue

            if any(ig.rstrip('/') in rel for ig in self.ignore_files):
                continue

            # Check if file is imported
            module_name = Path(filepath).stem
            module_path = rel.replace(os.sep, '.').replace('.py', '')
            module_path_parts = module_path.split('.')
            
            is_imported = False
            
            # Check various import patterns
            for imported in all_imported_names:
                # Direct import
                if imported == module_name or imported == module_path:
                    is_imported = True
                    break
                
                # Import from module
                if '.' in imported:
                    if imported.split('.')[0] == module_name:
                        is_imported = True
                        break
                
                # Check for relative imports
                if module_path_parts and module_path_parts[-1] in imported:
                    is_imported = True
                    break

            if not is_imported:
                diagnostics.append({
                    'type': 'DEAD',
                    'subType': 'UNUSED FILE',
                    'description': rel,
                })

        return diagnostics

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    imports.add(name)
                    # Add the base module name as well
                    if '.' in name:
                        imports.add(name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    # Add the base module name
                    if '.' in node.module:
                        imports.add(node.module.split('.')[0])
                for alias in node.names:
                    if alias.name != '*':
                        imports.add(alias.name)
        return imports

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
                if f.endswith('.py'):
                    filepath = os.path.join(root, f)
                    rel_path = os.path.relpath(filepath, self.project_path)
                    by_name.setdefault(f, []).append(rel_path)
                    
        for name, paths in by_name.items():
            if len(paths) > 1:
                diagnostics.append({
                    'type': 'DEAD',
                    'subType': 'DUPLICATE',
                    'description': f'{name}: {" ≈ ".join(paths)}',
                })
        return diagnostics

    async def _find_unused_imports(self) -> list[dict]:
        """Find unused imports in Python files"""
        diagnostics = []
        skip_dirs = {
            'venv', 'env', '__pycache__', '.venv', 'node_modules',
            'migrations', 'alembic', 'tests', 'test',
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
                    
                    tree = ast.parse(source)
                    imports = self._get_imports(tree)
                    used_names = self._get_used_names(tree)
                    
                    for import_name, import_line in imports:
                        # Check if the imported name is used
                        if import_name not in used_names:
                            diagnostics.append({
                                'type': 'DEAD',
                                'subType': 'UNUSED IMPORT',
                                'description': f'{rel_path}:{import_line} — import {import_name} not used',
                            })
                            
                except Exception:
                    continue
                    
        return diagnostics

    def _get_imports(self, tree: ast.AST) -> List[tuple[str, int]]:
        """Extract all imported names with line numbers"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name.split('.')[0], node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != '*':
                        imports.append((alias.name, node.lineno))
        return imports

    def _get_used_names(self, tree: ast.AST) -> Set[str]:
        """Extract all names used in the file"""
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                used_names.add(node.attr)
        return used_names