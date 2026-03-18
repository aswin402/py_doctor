"""Custom rules for py_doctor (integrated in analyzers)."""
from py_doctor.rules import fastapi_rules      # noqa: F401
from py_doctor.rules import sqlalchemy_rules   # noqa: F401
from py_doctor.rules import pydantic_rules     # noqa: F401
from py_doctor.rules import structlog_rules    # noqa: F401