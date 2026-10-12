# Changelog

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
