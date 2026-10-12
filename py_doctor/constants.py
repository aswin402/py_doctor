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
    ".git",
    ".pydoctor_cache",
}

# Used by CLI tools like ruff
DEFAULT_EXCLUDE_DIRS_STR = ",".join(DEFAULT_SKIP_DIRS)

# Used by Vulture
VULTURE_EXCLUDE_DIRS = ",".join(f"*{d}*" for d in DEFAULT_SKIP_DIRS)

# Aggressive Ruff rules: Flake8, Bugbear, Comprehensions, Pyupgrade, Simplify, Bandit, Return, Unused Args, Eradicate, Async
RUFF_SELECT_FLAGS = "E,F,W,I,B,C4,UP,SIM,RUF,S,PT,RET,ARG,ERA,ASYNC"

SECRET_PATTERNS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "API_KEY",
    "PRIVATE_KEY",
    "JWT_SECRET",
    "SALT",
    "ACCESS_KEY",
    "SECRET_KEY",
    "AUTH_KEY",
    "ENCRYPTION_KEY",
    "SIGNING_KEY",
)

SAFE_KEY_EXCLUSIONS = {
    "PRIMARY_KEY",
    "FOREIGN_KEY",
    "CACHE_KEY",
    "SORT_KEY",
    "PUBLIC_KEY",
    "PARTITION_KEY",
    "ROUTING_KEY",
    "DICT_KEY",
    "ITEM_KEY",
    "IDEMPOTENCY_KEY",
    "SEARCH_KEY",
}

# Penalty weights for health score calculation
ERROR_WEIGHT = 3
WARNING_WEIGHT = 1
DEAD_CODE_WEIGHT = 1
CRITICAL_WEIGHT = 10
SECURITY_WEIGHT = 5
DEPENDENCY_WEIGHT = 15

CRITICAL_RULES = [
    "fastapi/hardcoded-secret",
    "fastapi/insecure-cors",
    "fastapi/mutable-default-argument",
    "sqlalchemy/missing-session-close",
    "database/connection-leak",
    "async/missing-await",
    "fastapi/sync-in-async-route",
    "async/blocking-io",
    "fastapi/background-task-db-session",
]

SECURITY_RULES = [
    "bandit/",
    "ruff/S",
    "fastapi/hardcoded-secret",
    "fastapi/insecure-cors",
    "pydantic/unsafe-field",
]
