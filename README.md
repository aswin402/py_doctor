# py_doctor

Diagnose and fix your FastAPI project health — Python equivalent of [flutter_doctor](https://github.com/millionco/react-doctor).

One command scans your codebase for errors, warnings, dead code, and vulnerable dependencies, then outputs a **0–100 health score** with a beautiful `rich` terminal UI and generates a `NEEDEDFIX.md` file you can paste directly into any AI agent to auto-fix all issues.

```bash
py_doctor . --verbose
```

```text
  ❯ py_doctor . --verbose

  Detecting project...
  ✓ Python 3.12.3 · FastAPI 0.110.0 · SQLAlchemy 2.0.25
  ✓ Alembic detected · structlog detected · 34 source files

  ✓ Analysis complete

  ────────────────────────────────────────────────────────────────────────────

  ERRORS (2)

   ERR   fastapi/missing-await          app/routes/users.py:42
         db.execute() called without await — returns coroutine not result

   ERR   fastapi/hardcoded-secret       app/core/config.py:7
         SECRET_KEY hardcoded in source — use env var

  WARNINGS (2)

   WARN  fastapi/missing-response-model app/routes/users.py:15
         Route missing response_model — leaks internal fields

   WARN  ruff/F401                      app/services/email.py:3
         asyncio imported but unused

  ────────────────────────────────────────────────────────────────────────────

  DEAD CODE

   DEAD  UNUSED           app/utils/legacy_auth.py:12
         unused function 'legacy_login' (60% confidence)

  ────────────────────────────────────────────────────────────────────────────

  ╭───────────────────────────────────────────────────────────────────────────╮
  │                                                                           │
  │  71        HEALTH SCORE                                                   │
  │            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━──────────────────     │
  │  Needs work  2 errors  2 warnings  1 dead code  34 files scanned          │
  │                                                                           │
  ╰───────────────────────────────────────────────────────────────────────────╯

  Top priority fixes:
  → Fix fastapi/missing-await — crashes with coroutine never awaited
  → Fix fastapi/hardcoded-secret — secret visible in source code

  📄 NEEDEDFIX.md generated

  Run py_doctor . --fix to auto-fix with AI · --diff main for PR mode
```

---

## What it checks

### 🚨 Errors & Security
| Engine | Description |
|--------|-------------|
| **FastAPI AST** | Missing `await` on DB calls, blocking I/O in async routes, hardcoded secrets. |
| **SQLAlchemy AST** | Missing session closures (connection leaks), sync queries in async functions. |
| **Ruff (`E`, `F`, `S`, `B`)** | Syntax errors, undefined names, likely bugs, and static security vulnerabilities (via built-in `flake8-bandit`). |
| **mypy** | Type mismatches that cause runtime `TypeError` or `AttributeError` crashes. |
| **pip-audit** | Scans `requirements.txt` / `pyproject.toml` against the PyPA advisory database for packages with known CVEs. |

### ⚠️ Warnings & Improvements
| Engine | Description |
|--------|-------------|
| **FastAPI AST** | Routes missing `response_model` (leaks internal data), missing status codes. |
| **Pydantic AST** | Unsafe default fields, missing validators for sensitive fields like email. |
| **Ruff (`W`, `UP`, `SIM`, `RUF`)** | Outdated Python syntax, code simplifications, unused imports, and style warnings. |

### 💀 Dead Code (via Vulture)
Finds unused functions, classes, variables, and unreachable code with high confidence to help you trim bundle size and cognitive load.

---

## Scoring
The health score starts at `100` and deducts points based on severity:
```
score = 100 - (errors × 3) - (warnings × 1) - (dead_code × 1) - (critical × 10) - (security × 5) - (dependencies × 15)
```

| Score | Label | CI exit code |
|-------|-------|-------------|
| ≥ 75 | Great | 0 |
| 50–74 | Needs work | 1 |
| < 50 | Critical | 1 |

---

## Installation

### Recommended — clone and install (no venv needed)
```bash
git clone https://github.com/yourname/py_doctor
cd py_doctor
./tool/activate.sh
```

This installs `py_doctor` globally via `uv tool` and symlinks it to `/usr/local/bin/py_doctor` so it works from any directory instantly.

### Requirements
- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (installed automatically by `activate.sh` if missing)

---

## Usage
```bash
py_doctor .                        # scan current directory
py_doctor . --fix                  # auto-fix safe formatting/linting errors first
py_doctor . --verbose              # show description per rule
py_doctor . --format json          # output structured JSON (for integrations)
py_doctor . --score                # print score only (for CI)
py_doctor . --no-lint              # skip Ruff lint pass
py_doctor . --no-dead-code         # skip Vulture dead code detection
py_doctor . --no-types             # skip Mypy type checking
py_doctor . --no-security          # skip Pip-audit dependency vulnerability scan
py_doctor . --no-md                # skip NEEDEDFIX.md generation
py_doctor --version                # show version
```

---

## NEEDEDFIX.md — AI agent workflow

Every scan generates `NEEDEDFIX.md` in your project root containing:
- Every error with **why it crashes** and **exact code fix**
- Warnings grouped by rule with **how to fix** instructions
- Dead code with **action to take**

Paste the contents directly to Cursor, GitHub Copilot, or any AI agent:
```text
Read NEEDEDFIX.md and fix all issues in order.
Fix errors first, then warnings, then dead code.
```

*(Add `NEEDEDFIX.md` to your `.gitignore`)*

---

## Config

Create `py_doctor.config.json` in your project root to override defaults:
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

Or configure it inside your existing `pyproject.toml`:
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

## CI/CD — GitHub Actions

Automatically block Pull Requests that degrade your project's health score.

Create `.github/workflows/py_doctor.yml`:
```yaml
name: py_doctor health check

on:
  pull_request:
    branches: [ main ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: |
          uv venv
          uv pip install .

      - name: Run py_doctor
        # Exits with code 1 (failing the PR) if score drops below threshold
        run: uv run py_doctor . --score --no-md
```

---

## Project structure
```
py_doctor/
├── py_doctor/
│   ├── __init__.py
│   ├── cli.py                    # entry point, argparse, orchestration
│   ├── config.py                 # JSON/TOML config loader
│   ├── constants.py              # centralized string literals and patterns
│   ├── reporter.py               # rich terminal UI + NEEDEDFIX.md generation
│   ├── scorer.py                 # weighted 0–100 score formula
│   ├── analyzer/
│   │   ├── project_detector.py   # detect Python/FastAPI versions, file count
│   │   ├── lint_runner.py        # aggressive Ruff + custom FastAPI AST rules
│   │   ├── dead_code_runner.py   # Vulture integration and output parsing
│   │   ├── type_runner.py        # mypy JSON output parser
│   │   └── dependency_runner.py  # pip-audit vulnerability scanning
│   └── rules/
│       ├── fastapi_rules.py      # FastAPI-specific rule definitions
│       ├── sqlalchemy_rules.py   # SQLAlchemy async rules
│       ├── pydantic_rules.py     # Pydantic model rules
│       └── structlog_rules.py    # logging rules
├── pyproject.toml
└── README.md
```

---

## How it works
```text
py_doctor . --verbose
      ↓
Config.load()          reads py_doctor.config.json or pyproject.toml
      ↓
ProjectDetector        detects Python version, FastAPI, SQLAlchemy from pyproject.toml
      ↓
asyncio.gather()       runs 4 passes in parallel:
  ├── LintRunner       ruff (E, F, B, S, UP, SIM) + custom AST rules
  ├── DeadCodeRunner   vulture --min-confidence 70
  ├── TypeRunner       mypy --output=json
  └── DependencyRunner pip-audit -f json
      ↓
Scorer                 100 - penalties (errors, critical, vulnerabilities)
      ↓
Reporter               renders UI via `rich`
      ↓
NEEDEDFIX.md           writes markdown report with AI-ready fix instructions
```

---

## License

MIT
```

