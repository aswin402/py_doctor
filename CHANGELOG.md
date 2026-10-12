# Changelog

## 2.0.2 (2026-10-12)

### Fixed & Improved
- **False-Positive Traps Eliminated**:
  - `database/transaction-management`: Eliminated false positives on benign Python `dict.update()` and `list.insert()` calls by verifying callers are database/session instances (`is_db_caller`).
  - `sqlalchemy/n-plus-one`: Eliminated false positives on in-memory dictionary lookups (`cache.get(...)`) inside loops.
  - `sqlalchemy/missing-index`: Upgraded to inspect both AST Names and Attributes, adding full support for modern SQLAlchemy 2.0 `mapped_column` alongside legacy `Column` and `db.Column`.
  - `database/missing-pool-config`: Excluded SQLite databases (`sqlite:///...`) which do not support pool size configurations in SQLAlchemy.
  - `fastapi/hardcoded-secret` & `pydantic/unsafe-field`: Removed generic `"KEY"` substring pattern and introduced `SAFE_KEY_EXCLUSIONS` (`CACHE_KEY`, `PRIMARY_KEY`, `PUBLIC_KEY`, `SORT_KEY`) to prevent false alarms on non-secret keys.
  - `vulture/dead-code`: Switched regex parser to greedy path matching to reliably support Windows drive letter paths (`C:\...`).
  - `ProjectDetector`: Extended version specifier regex to support Poetry caret (`^`) and PEP 440 compatible release (`~=`) syntax.

### Architecture & Reusability
- **New Shared AST Utilities ([`ast_utils.py`](py_doctor/rules/ast_utils.py))**:
  - Centralized shared AST node inspection functions: `annotate_parents`, `is_route_decorator`, `is_pydantic_model`, `is_db_caller`, and `is_string_literal`.
  - Deduplicated route decorator detection across multiple FastAPI rule checks.
- **Centralized Scorer Constants**:
  - Moved hardcoded score penalties and rule category sets into `constants.py` for consistent maintenance and testing.
- **True Concurrency & Performance**:
  - Replaced blocking synchronous subprocess execution in all runners (`lint_runner`, `type_runner`, `dead_code_runner`, `dependency_runner`, `project_detector`, `cli`) with non-blocking `asyncio.to_thread` execution under `asyncio.gather`.
  - Offloaded AST parsing and report file IO to worker threads.
- **CLI Alias**:
  - Registered `py-doctor` entry point alias in `pyproject.toml` alongside `py_doctor`.

### Testing & Verification
- Added 9 comprehensive unit test suites in `tests/test_rules.py` covering all new rules and false-positive guards.
- Expanded test suite from 33 to 42 tests passing with 100% test pass rate, 0 Ruff errors, and 0 Mypy type errors.

## 2.0.1 (2026-10-12)

### Added
- **New Diagnostic Rules**:
  - `fastapi/insecure-cors`: Detects wildcard origins (`allow_origins=["*"]`) combined with `allow_credentials=True` in `CORSMiddleware`, which violates Fetch CORS standards and introduces security risks.
  - `fastapi/mutable-default-argument`: Catches mutable default arguments (`list = []`, `dict = {}`) in route handlers that cause memory corruption and state leakage across concurrent requests.
  - `fastapi/invalid-route-path`: Flags route paths missing leading slashes (`@app.get("users")`) or containing duplicate slashes (`@app.get("//users")`).
  - `fastapi/bare-except-swallow`: Detects empty exception handlers silently swallowing errors with `pass` or `...`.
  - `database/n-plus-one-query`: Detects database query execution (`.execute()`, `.scalars()`, `fetchall()`) inside loops.
- **Reporting & CLI**:
  - Added `--format html` option generating self-contained, interactive, dark-themed HTML health reports.
  - Added `--output <path>` flag to save reports directly to a specified destination file.
  - Added `--threshold <N>` CLI override flag for custom pass/fail gates in CI and command lines.
  - Formatted top priority fixes with file location and indented actionable suggestions matching terminal demo.
- **Async & Performance**:
  - Expanded `SyncInAsyncRouteRule` and `BlockingIOInAsyncRule` to detect blocking `requests.get/post()` and `subprocess.run()` calls in async handlers, recommending `httpx.AsyncClient` or `asyncio.to_thread`.
  - Added lazy module attribute resolution in `py_doctor/__init__.py` to eliminate `runpy` `RuntimeWarning`.

### Testing
- Expanded test suite to 33 passing unit tests with 100% Ruff compliance.

## 1.0.0 (2024-10-01)

- Initial release
- FastAPI-specific AST lint rules
- Parallel ruff/mypy/bandit/vulture analysis
- Exact flutter_doctor-style terminal UI
- NEEDEDFIX.md generation
