import argparse
import asyncio
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

    # Auto-fix stage
    if args.fix:
        with console.status("[bold yellow]Applying automatic fixes...[/bold yellow]"):
            subprocess.run(
                ["ruff", "check", project_path, "--fix", "--quiet"], 
                capture_output=True,
                check=False
            )
        console.print("[bold green]✓[/bold green] Auto-fixes applied\n")

    # Analysis stage
    with console.status("[bold cyan]Running analysis passes in parallel...[/bold cyan]"):
        diagnostics = await run_analysis(project_path, args, config)

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
    if args.score:
        # If running in CI pipeline score mode, just print the integer
        print(score)
    else:
        reporter = Reporter(verbose=args.verbose)
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

    if not args.no_md:
        reporter = Reporter(verbose=args.verbose)
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

    if not args.no_lint:
        tasks.append(LintRunner(project_path, config.ignore_rules).run())
    if not args.no_dead_code:
        tasks.append(DeadCodeRunner(project_path, config.ignore_files).run())
    if not args.no_types:
        tasks.append(TypeRunner(project_path, config.ignore_rules).run())
    if not args.no_security:
        tasks.append(DependencyRunner(project_path, config.ignore_rules).run())

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]


if __name__ == "__main__":
    main()