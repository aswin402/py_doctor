"""Centralized constants for py_doctor to avoid hardcoded values."""

DEFAULT_IGNORE_RULES = [
    "bandit/B404",
    "bandit/B603",
    "bandit/B607",
    "bandit/B110",
    "bandit/B112",
]

DEFAULT_SKIP_DIRS = {
    "venv",
    "env",
    "__pycache__",
    ".venv",
    "node_modules",
    "migrations",
    "alembic",
    "tests",
    "test",
    "build",
    "dist",
    "eggs",
    ".eggs",
    "py_doctor.egg-info",
    ".git"
}

# Used by CLI tools like ruff
DEFAULT_EXCLUDE_DIRS_STR = ",".join(DEFAULT_SKIP_DIRS)

# Used by Vulture
VULTURE_EXCLUDE_DIRS = ",".join(f"*{d}*" for d in DEFAULT_SKIP_DIRS)

# Aggressive Ruff rules: Flake8, Bugbear, Comprehensions, Pyupgrade, Simplify, Bandit, Return, Unused Args, Eradicate
RUFF_SELECT_FLAGS = "E,F,W,I,B,C4,UP,SIM,RUF,S,PT,RET,ARG,ERA"

SECRET_PATTERNS = (
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "API_KEY",
    "PRIVATE_KEY",
    "JWT_SECRET",
    "SALT",
    "KEY",
    "ACCESS_KEY",
    "SECRET_KEY",
)