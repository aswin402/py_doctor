# py_doctor Fixes TODO

Status: 🚀 In Progress

## Steps (7 total):

### 1. ✅ Understand files [COMPLETED]

Read cli.py, dead_code_runner.py, lint_runner.py, reporter.py, config.py, base_rule.py, NEEDEDFIX.md

### 2. ✅ Create TODO.md [COMPLETED]

### 3. ✅ Fix dead_code_runner.py [COMPLETED]

- Enhance ImportFrom collection (path_version matching)
- Fix source: str = f.read()
- Type by_name: dict[str, list[str]]

### 4. ✅ Fix lint_runner.py [COMPLETED]

### 5. 🔧 Fix config.py [COMPLETED]

- Add skip_print_check for reporter/cli files

### 5. ✅ Fix config.py [COMPLETED]

### 6. ✅ Fix reporter.py [COMPLETED]

- Replace generate_markdown_report entirely
- Add 5 helper functions (\_err_why etc.)
- Fix imports, f-string escapes

### 7. 🧪 Test fixes

- uv pip install -e .
- py_doctor . --verbose
- ✅ Expect: 0 dead_code (cli.py detected), better NEEDEDFIX.md, no print warns in reporter, bandit ignored

### 7. ✅ Test fixes [COMPLETED]
