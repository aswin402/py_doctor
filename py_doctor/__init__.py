"""
py_doctor - Advanced FastAPI project health diagnostic tool
"""

__version__ = "2.0.5"
__author__ = "aswin"
__description__ = "Comprehensive FastAPI project health checker with advanced error detection"


def __getattr__(name: str):
    if name in ("main", "get_version"):
        from py_doctor import cli

        return getattr(cli, name)
    raise AttributeError(f"module 'py_doctor' has no attribute '{name}'")


__all__ = ["main", "get_version", "__version__"]
