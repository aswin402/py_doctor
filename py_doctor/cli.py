import argparse
import asyncio
import json
import os
import subprocess
import sys
from typing import Any

from rich.console import Console

from py_doctor.analyzer.dead_code_runner import DeadCodeRunner
from py_doctor.analyzer.dependency_runner import DependencyRunner
from py_doctor.analyzer.lint_runner import LintRunner
from py_doctor.analyzer.project_detector import ProjectDetector
from py_doctor.analyzer.type_runner import TypeRunner
from py_doctor.config import Config
from py_doctor.reporter import Reporter
from py_doctor.scorer import calculate_score, categorize_issues

__version__ = "2.0.0"
__author__ = "aswin"
__description__ = "Diagnose and fix your FastAPI project health"


def get_version() -> str:
    return f"py_doctor version {__version__}"


def get_git_diff_files(project_path: str, ref: str) -> set[str]:
    """Retrieve set of modified or added python files relative to a git reference."""
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", ref],
            capture_output=True,
            text=True,
            cwd=project_path,
            check=False,
        )
        if res.returncode == 0:
            files = set()
            for line in res.stdout.splitlines():
                clean = line.strip()
                if clean.endswith(".py"):
                    files.add(os.path.normpath(clean))
            return files
    except Exception:
        pass
    return set()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="py_doctor",
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=get_version(),
        help="Show the version of py_doctor and exit",
    )

    parser.add_argument("path", nargs="?", default=".", help="Project path to scan")
    parser.add_argument("--verbose", action="store_true", help="Show detailed descriptions for each issue")
    parser.add_argument("--score", action="store_true", help="Print only the final score (useful for CI/CD)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe linting and formatting errors before scoring")
    parser.add_argument("--no-lint", action="store_true", help="Skip Ruff linting pass")
    parser.add_argument("--no-dead-code", action="store_true", help="Skip Vulture dead code detection")
    parser.add_argument("--no-types", action="store_true", help="Skip Mypy type checking")
    parser.add_argument("--no-security", action="store_true", help="Skip Pip-audit dependency vulnerability scan")
    parser.add_argument("--no-md", action="store_true", help="Skip generating NEEDEDFIX.md")
    parser.add_argument("--format", choices=["terminal", "json"], default="terminal")
    parser.add_argument(
        "--diff",
        nargs="?",
        const="HEAD",
        default=None,
        help="Scan only files changed in git diff against ref (e.g. --diff main)",
    )

    args = parser.parse_args()
    asyncio.run(run(args))


async def run(args: argparse.Namespace) -> None:
    project_path = os.path.normpath(os.path.abspath(args.path))
    if not os.path.isdir(project_path):
        print(f"Error: Directory not found: {project_path}", file=sys.stderr)
        sys.exit(1)

    config = Config.load(project_path)
    detector = ProjectDetector(project_path)
    await detector.detect()

    console = Console()

    format_opt = getattr(args, "format", "terminal")
    score_opt = getattr(args, "score", False)
    fix_opt = getattr(args, "fix", False)
    diff_opt = getattr(args, "diff", None)
    no_md_opt = getattr(args, "no_md", False)
    verbose_opt = getattr(args, "verbose", False)

    is_quiet_mode = score_opt or format_opt == "json"

    # Auto-fix stage
    if fix_opt:
        if not is_quiet_mode:
            with console.status("[bold yellow]Applying automatic fixes...[/bold yellow]"):
                subprocess.run(
                    ["ruff", "check", project_path, "--fix", "--quiet"],
                    capture_output=True,
                    check=False,
                )
            console.print("[bold green]✓[/bold green] Auto-fixes applied\n")
        else:
            subprocess.run(
                ["ruff", "check", project_path, "--fix", "--quiet"],
                capture_output=True,
                check=False,
            )

    # Analysis stage
    if not is_quiet_mode:
        with console.status("[bold cyan]Running analysis passes in parallel...[/bold cyan]"):
            diagnostics = await run_analysis(project_path, args, config)
    else:
        diagnostics = await run_analysis(project_path, args, config)

    # Filter diagnostics for PR / diff mode if requested
    if diff_opt:
        diff_files = get_git_diff_files(project_path, diff_opt)
        diagnostics = [
            d
            for d in diagnostics
            if any(
                os.path.normpath(d.get("location", "").split(":")[0]).endswith(df)
                or df.endswith(os.path.normpath(d.get("location", "").split(":")[0]))
                for df in diff_files
            )
        ]
        detector.source_file_count = len(diff_files)

    categorized = categorize_issues(diagnostics)
    score = calculate_score(
        errors=categorized["errors"],
        warnings=categorized["warnings"],
        dead_code=categorized["dead_code"],
        critical_issues=categorized.get("critical", 0),
        security_issues=categorized.get("security", 0),
        dependency_issues=categorized.get("dependencies", 0),
    )

    # Reporting stage
    if format_opt == "json":
        output = {
            "score": score,
            "threshold": config.threshold,
            "categories": categorized,
            "diagnostics": diagnostics,
            "project": {
                "python_version": detector.python_version,
                "fastapi_version": detector.fastapi_version,
                "sqlalchemy_version": detector.sqlalchemy_version,
                "source_file_count": detector.source_file_count,
            },
        }
        print(json.dumps(output, indent=2))
    elif score_opt:
        # If running in CI pipeline score mode, just print the integer
        print(score)
    else:
        reporter = Reporter(verbose=verbose_opt)
        await reporter.generate_report(
            diagnostics=diagnostics,
            detector=detector,
            score=score,
            errors=categorized["errors"],
            warnings=categorized["warnings"],
            dead_code=categorized["dead_code"],
            file_count=detector.source_file_count,
            threshold=config.threshold,
        )

    if not no_md_opt and format_opt != "json":
        reporter = Reporter(verbose=verbose_opt)
        await reporter.generate_markdown_report(
            project_path=project_path,
            diagnostics=diagnostics,
            detector=detector,
            score=score,
            errors=categorized["errors"],
            warnings=categorized["warnings"],
            dead_code=categorized["dead_code"],
            file_count=detector.source_file_count,
            threshold=config.threshold,
        )

    # Fail the CI build if the score drops below the configured threshold
    if score < config.threshold:
        sys.exit(1)


async def run_analysis(
    project_path: str, args: argparse.Namespace, config: Config
) -> list[dict[str, Any]]:
    tasks: list[Any] = []

    if not getattr(args, "no_lint", False):
        tasks.append(LintRunner(project_path, config.ignore_rules, config.ignore_files).run())
    if not getattr(args, "no_dead_code", False):
        tasks.append(DeadCodeRunner(project_path, config.ignore_files).run())
    if not getattr(args, "no_types", False):
        tasks.append(TypeRunner(project_path, config.ignore_rules).run())
    if not getattr(args, "no_security", False):
        tasks.append(DependencyRunner(project_path, config.ignore_rules).run())

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]


if __name__ == "__main__":
    main()
