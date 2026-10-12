from typing import Any

from py_doctor.constants import (
    CRITICAL_RULES,
    CRITICAL_WEIGHT,
    DEAD_CODE_WEIGHT,
    DEPENDENCY_WEIGHT,
    ERROR_WEIGHT,
    SECURITY_RULES,
    SECURITY_WEIGHT,
    WARNING_WEIGHT,
)


def calculate_score(
    errors: int,
    warnings: int,
    dead_code: int,
    critical_issues: int = 0,
    security_issues: int = 0,
    dependency_issues: int = 0,
) -> int:
    """Calculate health score with weighted penalties"""
    penalty = (
        errors * ERROR_WEIGHT
        + warnings * WARNING_WEIGHT
        + dead_code * DEAD_CODE_WEIGHT
        + critical_issues * CRITICAL_WEIGHT
        + security_issues * SECURITY_WEIGHT
        + dependency_issues * DEPENDENCY_WEIGHT
    )
    score = 100 - penalty
    return max(0, min(100, score))


def categorize_issues(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    """Categorize issues by severity and type"""
    categories: dict[str, int] = {
        "errors": 0,
        "warnings": 0,
        "dead_code": 0,
        "critical": 0,
        "security": 0,
        "dependencies": 0,
    }

    for d in diagnostics:
        issue_type = d.get("type", "")
        rule = d.get("rule", "")

        if issue_type == "ERR":
            categories["errors"] += 1
        elif issue_type == "WARN":
            categories["warnings"] += 1
        elif issue_type == "DEAD":
            categories["dead_code"] += 1

        if any(cr in rule for cr in CRITICAL_RULES):
            categories["critical"] += 1
        if any(sr in rule for sr in SECURITY_RULES):
            categories["security"] += 1
        if rule.startswith("audit/"):
            categories["dependencies"] += 1

    return categories
