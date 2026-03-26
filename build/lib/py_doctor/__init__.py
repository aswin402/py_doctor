"""py_doctor - Diagnose FastAPI projects like flutter_doctor."""
"""
py_doctor - FastAPI project health diagnostic tool
"""

__version__ = "1.0.1"
__author__ = "py_doctor"
__description__ = "Diagnose and fix your FastAPI project health"

from py_doctor.cli import main, get_version, __version__

__all__ = ['main', 'get_version', '__version__']