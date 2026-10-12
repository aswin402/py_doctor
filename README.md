<div align="center">

<a href="https://github.com/aswin402/py_doctor">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-animated.svg">
    <img src="assets/logo-animated.svg" alt="py_doctor logo" width="96" height="96" />
  </picture>
</a>

# py_doctor

<h3>FastAPI Project Health Diagnostic &amp; AI Remediation Engine</h3>

<p><em>The automated health checker for Python &amp; FastAPI — deep AST static analysis, instant 0–100 health scoring, and AI-ready remediation prompts.</em></p>

[![Release](https://img.shields.io/github/v/release/aswin402/py_doctor?style=flat&color=10B981&label=release)](https://github.com/aswin402/py_doctor/releases)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)
[![Managed by uv](https://img.shields.io/badge/Managed%20by-uv-DE5FE9?style=flat&logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Linted with Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tested with pytest](https://img.shields.io/badge/Tested%20with-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white)](https://pytest.org)
[![GitHub issues](https://img.shields.io/github/issues/aswin402/py_doctor?style=flat)](https://github.com/aswin402/py_doctor/issues)

<br/>

<a href="#-overview">Overview</a> •
<a href="#-installation--quick-start-with-uv">Install with uv</a> •
<a href="#-diagnostic-rules-catalog">Rules Catalog</a> •
<a href="#-ai-agent-workflow-neededfixmd">AI Workflow</a> •
<a href="#-cli-reference">CLI Reference</a> •
<a href="#-configuration">Configuration</a> •
<a href="#-cicd--github-actions">CI/CD &amp; Pre-commit</a> •
<a href="#-architecture">Architecture</a>

</div>

---

## ⚡ Overview

**py_doctor** is an open-source static health diagnostic CLI and automated code doctor tailored specifically for FastAPI backends.

Standard linters detect syntax bugs and formatting, but miss runtime pitfalls unique to FastAPI, SQLAlchemy, and modern asynchronous architectures. `py_doctor` performs deep AST inspection across your codebase to detect silent bugs, unawaited coroutines, database connection leaks, missing response models, and hardcoded secrets—scoring your project from **0 to 100** and exporting a structured `NEEDEDFIX.md` action plan ready for instant AI auto-fixing.

<br/>

<div align="center">
  <img src="assets/demo.gif" alt="py_doctor real-time terminal diagnostics demo" width="100%" />
</div>

<br/>

<details>
<summary><b>Click to expand raw terminal text output</b></summary>

```text
  ❯ py_doctor . --verbose

  Detecting project...
  ✓ Python 3.12.3 · FastAPI 0.110.0 · SQLAlchemy 2.0.25
  ✓ Alembic detected · structlog detected · 34 source files

  ✓ Analysis complete (0.34s)

  ────────────────────────────────────────────────────────────────────────────

  ERRORS (2)

   ERR   fastapi/missing-await          app/routes/users.py:42
         db.execute() called without await — returns coroutine not result

   ERR   fastapi/hardcoded-secret       app/core/config.py:7
         SECRET_KEY hardcoded in source — load from environment

  WARNINGS (2)

   WARN  fastapi/missing-response-model app/routes/users.py:15
         Route missing response_model — leaks internal fields

   WARN  ruff/F401                      app/services/email.py:3
         asyncio imported but unused

  ────────────────────────────────────────────────────────────────────────────

  DEAD CODE (1)

   DEAD  UNUSED           app/utils/legacy_auth.py:12
         unused function 'legacy_login' (60% confidence)

  ────────────────────────────────────────────────────────────────────────────

  ╭───────────────────────────────────────────────────────────────────────────╮
  │                                                                           │
  │  71        HEALTH SCORE                                                   │
  │            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
  │  Needs work  2 errors  2 warnings  1 dead code  34 files scanned          │
  │                                                                           │
  ╰───────────────────────────────────────────────────────────────────────────╯

  Top priority fixes:
  → Fix fastapi/missing-await: app/routes/users.py:42
    ↳ Suggestion: await the call: await db.execute(...)
  → Fix fastapi/hardcoded-secret: app/core/config.py:7
    ↳ Suggestion: Load secret from environment variable (e.g. os.getenv or pydantic-settings)

  📄 NEEDEDFIX.md generated

  Run py_doctor . --fix to auto-fix with AI · --diff main for PR mode
```
</details>

---

## 🎯 Key Highlights

- **FastAPI-First AST Analysis**: Deep static analysis targeting framework-specific antipatterns that generic linters miss.
- **Unified 0–100 Health Score**: Transparent weighted score formula designed for pull request gates and automated quality enforcement.
- **AI-Agent Remediation (`NEEDEDFIX.md`)**: Automatically exports a prioritized task list with exact line numbers, cause explanations, and code fix suggestions for Cursor, Claude Code, Copilot, or Antigravity.
- **Git Diff Mode (`--diff [REF]`)**: Only scan lines and files modified in the active branch for lightning-fast pre-commit and CI verification.
- **Concurrent Engine Dispatch**: Parallel execution across Ruff, Mypy, Vulture, Pip-Audit, and custom AST visitors via `asyncio`.
- **Zero Config Required**: Automatically auto-detects installed framework versions, virtual environments, and project structures.

---

## 📦 Installation & Quick Start with uv

Astral's [`uv`](https://docs.astral.sh/uv/) is the fastest way to install and run `py_doctor`. You can run it on demand without installing, install it globally as a standalone CLI tool, or add it to your project.

### 1. Run Instantly with `uvx` (Zero Installation)
Run `py_doctor` directly on any project without installing anything permanently:

```bash
uvx --from git+https://github.com/aswin402/py_doctor.git py_doctor .
```

### 2. Global CLI Install with `uv tool` (Recommended)
Install `py_doctor` globally so the `py_doctor` command is available in your terminal from any directory:

```bash
uv tool install git+https://github.com/aswin402/py_doctor.git
```

Now run anywhere:
```bash
py_doctor . --verbose
```

To update to the latest version later:
```bash
uv tool upgrade py_doctor
```

### 3. Add to Your Project with `uv add`
If your project is managed with `uv`, add `py_doctor` as a development dependency:

```bash
uv add --dev git+https://github.com/aswin402/py_doctor.git
```

Then run it inside your project environment:
```bash
uv run py_doctor .
```

### 4. Install in Active Virtual Environment with `uv pip`
If you are inside an activated virtual environment:

```bash
uv pip install git+https://github.com/aswin402/py_doctor.git
```

### 5. Automated Setup Script
You can also clone the repository and run the automated activation script, which sets up `uv` and links `py_doctor` to your `/usr/local/bin`:

```bash
git clone https://github.com/aswin402/py_doctor.git
cd py_doctor
./tool/activate.sh
```

---

<details>
<summary><b>Non-uv alternatives (pip / pipx)</b></summary>

```bash
# Global run with pipx:
pipx run --spec git+https://github.com/aswin402/py_doctor.git py_doctor .

# Global install with pipx:
pipx install git+https://github.com/aswin402/py_doctor.git

# Traditional pip install into active venv:
pip install git+https://github.com/aswin402/py_doctor.git
```
</details>

---

## 🔍 Why py_doctor?

| Capability | Generic Linters (Ruff / Flake8) | Type Checkers (Mypy) | **py_doctor** |
| :--- | :--- | :--- | :--- |
| **FastAPI Route Semantics** | Syntax & basic formatting only | Signatures only | Identifies route data leakage, missing models, and unawaited operations |
| **Database & ORM Safety** | None | Limited | Catches connection leaks, unclosed sessions, and unbounded slow queries |
| **Health Metric** | Binary pass / fail | Binary pass / fail | Single unified **0–100 score** with customizable gating thresholds |
| **AI Remediation Handoff** | Raw console output | Unstructured error dump | Structured `NEEDEDFIX.md` action plan tailored for coding agents |
| **Multi-Engine Concurrency** | Single tool pass | Single tool pass | Orchestrates 5 static, type, dead-code, and security passes concurrently |

---

## 📚 Diagnostic Rules Catalog

### 1. FastAPI & Async AST Rules

#### `fastapi/missing-await`
- **Severity**: `ERROR` (-3 pts)
- **Problem**: Calling an asynchronous database operation or async client without `await` returns an un-awaited coroutine object instead of executing the operation.
```python
# ❌ Bad: returns a coroutine; query never executes
result = db.execute(select(User))

# ✅ Good: coroutine awaited and executed
result = await db.execute(select(User))
```

#### `fastapi/sync-in-async-route`
- **Severity**: `ERROR` (-3 pts)
- **Problem**: Blocking synchronous calls (e.g. `time.sleep()`, synchronous `requests.get()`) inside an `async def` handler freeze the entire event loop, blocking all concurrent user requests.
```python
# ❌ Bad: blocks the whole ASGI worker
@app.get("/items")
async def get_items():
    time.sleep(2)
    return {"status": "ok"}

# ✅ Good: non-blocking async execution
@app.get("/items")
async def get_items():
    await asyncio.sleep(2)
    return {"status": "ok"}
```

#### `fastapi/hardcoded-secret`
- **Severity**: `ERROR` (-3 pts)
- **Problem**: Storing API keys, JWT tokens, or credentials directly in source code risks exposing secrets in version control.
```python
# ❌ Bad: hardcoded secret in source
SECRET_KEY: str = "super-secret-key-12345"

# ✅ Good: loaded securely from environment
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
```

#### `fastapi/missing-response-model`
- **Severity**: `WARNING` (-1 pt)
- **Problem**: Endpoints returning raw ORM models without `response_model` or type annotations can accidentally leak sensitive internal database columns (e.g., password hashes, internal IDs).
```python
# ❌ Bad: may leak internal model fields
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return await db_get_user(user_id)

# ✅ Good: explicit response model filtering
@app.get("/users/{user_id}", response_model=UserPublic)
async def get_user(user_id: int):
    return await db_get_user(user_id)
```

---

### 2. Database & SQLAlchemy AST Rules

#### `sqlalchemy/missing-async-query`
- **Severity**: `ERROR` (-3 pts)
- **Problem**: Calling legacy synchronous SQLAlchemy 1.x Query methods (`db.query()`, `.all()`) inside async routes triggers blocking socket I/O.
```python
# ❌ Bad: blocking synchronous ORM query
users = db.query(User).filter(User.active == True).all()

# ✅ Good: modern SQLAlchemy 2.0 async execution
result = await session.execute(select(User).where(User.active == True))
users = result.scalars().all()
```

#### `database/connection-leak`
- **Severity**: `ERROR` (-3 pts)
- **Problem**: Raw connection acquisition without context management leaks pool connections under load, resulting in pool exhaustion.
```python
# ❌ Bad: connection may leak if exception occurs
conn = await engine.connect()
await conn.execute(...)

# ✅ Good: connection safely returned to pool automatically
async with engine.connect() as conn:
    await conn.execute(...)
```

#### `database/slow-query`
- **Severity**: `WARNING` (-1 pt)
- **Problem**: Executing queries without `.limit()` or pagination on tables that grow over time can lead to memory spikes and database bottlenecks.
```python
# ❌ Bad: unbounded full-table scan
users = await session.scalars(select(User)).all()

# ✅ Good: bounded query with pagination
users = await session.scalars(select(User).limit(50).offset(page * 50)).all()
```

---

### 3. Pydantic & Logging Rules

#### `pydantic/unsafe-field`
- **Severity**: `WARNING` (-1 pt)
- **Problem**: Storing sensitive credentials in plain `str` fields causes secrets to be printed in plain text during logging, repr output, or validation error dumps.
```python
# ❌ Bad: raw string appears in plain text in logs and stack traces
class AuthRequest(BaseModel):
    token: str

# ✅ Good: Pydantic SecretStr masks value automatically
from pydantic import SecretStr

class AuthRequest(BaseModel):
    token: SecretStr
```

#### `structlog/print-instead-of-log`
- **Severity**: `WARNING` (-1 pt)
- **Problem**: Using `print()` instead of structured logging prevents log aggregation, trace correlation, and JSON structured log parsing in production.
```python
# ❌ Bad: unformatted stdout output
print(f"User {user_id} authenticated")

# ✅ Good: structured log with contextual key-value pairs
logger.info("user_authenticated", user_id=user_id)
```

---

## 📊 Scoring Methodology

Health scores start at **100** and are penalized according to finding severity:

$$\text{Score} = 100 - (\text{Errors} \times 3) - (\text{Warnings} \times 1) - (\text{Dead Code} \times 1) - (\text{Critical} \times 10) - (\text{Security} \times 5) - (\text{Dependencies} \times 15)$$

| Health Range | Status | Meaning | CI Exit Code |
| :--- | :--- | :--- | :--- |
| **75 – 100** | 🟢 **Great** | High code health; approved for merge | `0` (Success) |
| **50 – 74** | 🟡 **Needs Work** | Fixes recommended; review before release | `1` (Failure) |
| **0 – 49** | 🔴 **Critical** | Major stability or security risks detected | `1` (Failure) |

---

## 🤖 AI Agent Workflow (`NEEDEDFIX.md`)

Running `py_doctor` automatically generates a structured `NEEDEDFIX.md` in the project root. This document is formatted specifically for immediate consumption by AI agents like Cursor, Claude Code, Copilot, or Antigravity.

````markdown
# Project Health Fix List (py_doctor)

Health Score: 71 / 100 (Threshold: 75)
Generated: 2026-10-12 14:00:00

## Priority Fixes (Critical & Errors)
1. **fastapi/missing-await** at `app/routes/users.py:42`
   - Description: db.execute() called without await — returns coroutine not result
   - Suggested Action: await the call: await db.execute(...)

2. **fastapi/hardcoded-secret** at `app/core/config.py:7`
   - Description: SECRET_KEY hardcoded in source
   - Suggested Action: Load secret from environment variable (e.g. os.getenv or pydantic-settings)
````

### Quick Agent Prompt
Copy and paste this instruction into your AI coding assistant:
```text
Read NEEDEDFIX.md and fix all reported issues in order of priority.
After completing the fixes, run `py_doctor . --score` to ensure the project health score satisfies the threshold.
```

*(Recommendation: Add `NEEDEDFIX.md` to your `.gitignore` file).*

---

## 💻 CLI Reference

```bash
# Basic scan of the current directory
py_doctor .

# Detailed verbose report with file paths and remediation tips
py_doctor . --verbose

# Scan only files modified in the active git branch against main
py_doctor . --diff origin/main

# Machine-readable JSON output (ideal for dashboards and custom tools)
py_doctor . --format json

# Print score only (for bash scripts and simple CI gates)
py_doctor . --score

# Automatically apply safe Ruff lint and format fixes before scoring
py_doctor . --fix

# Selectively disable specific analyzers
py_doctor . --no-lint          # Disable Ruff linting
py_doctor . --no-dead-code     # Disable Vulture dead code detection
py_doctor . --no-types         # Disable Mypy type checks
py_doctor . --no-security      # Disable pip-audit CVE vulnerability scans
py_doctor . --no-md            # Prevent writing NEEDEDFIX.md to disk
```

### Complete Flag Options

| Flag | Type | Description |
| :--- | :--- | :--- |
| `path` | `Positional` | Target directory to scan (defaults to `.`). |
| `--verbose` | `Flag` | Displays detailed rule descriptions and specific remediation suggestions. |
| `--diff [REF]` | `Optional` | Limits analysis to `.py` files changed relative to Git ref (e.g. `main` or `HEAD~1`). |
| `--format` | `Choice` | Output format: `terminal` (Rich UI) or `json` (machine-readable). |
| `--score` | `Flag` | Outputs only the integer health score (0–100) and suppresses terminal styling. |
| `--fix` | `Flag` | Executes safe automatic Ruff fixes before analyzing. |
| `--no-lint` | `Flag` | Skips Ruff and custom AST visitor passes. |
| `--no-dead-code` | `Flag` | Skips Vulture dead-code detection. |
| `--no-types` | `Flag` | Skips Mypy static type checking. |
| `--no-security` | `Flag` | Skips pip-audit dependency vulnerability scanning. |
| `--no-md` | `Flag` | Prevents creation of the `NEEDEDFIX.md` file. |
| `--version` | `Flag` | Prints the installed `py_doctor` version. |

---

## ⚙️ Configuration

Configure custom thresholds and exclusion lists with `py_doctor.config.json` in your project root:

```json
{
  "lint": true,
  "deadCode": true,
  "types": true,
  "security": true,
  "threshold": 80,
  "ignore": {
    "rules": [
      "ruff/E501",
      "audit/CVE-2023-XXXX"
    ],
    "files": [
      "migrations/",
      "tests/",
      "alembic/"
    ]
  }
}
```

Or configure directly inside your existing `pyproject.toml`:

```toml
[tool.py_doctor]
lint = true
dead_code = true
types = true
security = true
threshold = 80

[tool.py_doctor.ignore]
rules = ["ruff/E501", "audit/CVE-2023-XXXX"]
files = ["migrations/", "tests/", "alembic/"]
```

---

## 🔄 CI/CD & Pre-commit

### GitHub Actions Workflow
Block pull requests that degrade project health score below your threshold:

```yaml
name: Health Check

on:
  pull_request:
    branches: [ main ]

jobs:
  py-doctor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install py_doctor
        run: uv tool install git+https://github.com/aswin402/py_doctor.git

      - name: Run py_doctor PR Diff Scan
        run: py_doctor . --diff origin/main --no-md
```

### Pre-commit Integration
Add `py_doctor` to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/aswin402/py_doctor
    rev: v2.0.0
    hooks:
      - id: py-doctor
        name: py_doctor health check
        entry: py_doctor . --diff HEAD --no-md
        language: python
        types: [python]
        pass_filenames: false
```

---

## 🏗️ Architecture

```
py_doctor CLI
     │
     ├── 1. Config.load()          (Loads py_doctor.config.json or pyproject.toml)
     ├── 2. ProjectDetector        (Identifies Python, FastAPI, SQLAlchemy, Alembic)
     │
     ├── 3. asyncio.gather() [Parallel Analysis Dispatch]
     │       ├── LintRunner        (Ruff lint/security + Custom AST Rule Visitors)
     │       ├── DeadCodeRunner    (Vulture dead code confidence analysis)
     │       ├── TypeRunner        (Mypy static type checking)
     │       └── DependencyRunner  (Pip-audit PyPA CVE vulnerability scanner)
     │
     ├── 4. Scorer                 (Calculates weighted 0–100 health index)
     ├── 5. Reporter               (Renders Rich terminal UI or JSON stream)
     └── 6. NEEDEDFIX.md           (Generates prioritized AI agent remediation file)
```

---

## 🧪 Testing & Development

Run the full automated test suite (25 unit and integration tests):

```bash
# Run tests with pytest
pytest -v

# Or run tests using Python standard library
python -m unittest discover tests

# Lint codebase and tests
ruff check py_doctor/ tests/
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
