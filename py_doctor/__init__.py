"""
py_doctor - Advanced FastAPI project health diagnostic tool
"""

__version__ = "2.0.0"
__author__ = "aswin"
__description__ = "Comprehensive FastAPI project health checker with advanced error detection"

from py_doctor.cli import get_version, main

__all__ = ["main", "get_version", "__version__"]
