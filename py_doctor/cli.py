import argparse
import asyncio
import sys
import os
from py_doctor.analyzer.project_detector import ProjectDetector
from py_doctor.analyzer.lint_runner import LintRunner
from py_doctor.analyzer.dead_code_runner import DeadCodeRunner
from py_doctor.analyzer.type_runner import TypeRunner
from py_doctor.analyzer.security_runner import SecurityRunner
from py_doctor.reporter import Reporter
from py_doctor.scorer import calculate_score
from py_doctor.config import Config
from py_doctor.rules.fastapi_rules import *      # noqa: F401, F403
from py_doctor.rules.sqlalchemy_rules import *   # noqa: F401, F403
from py_doctor.rules.pydantic_rules import *     # noqa: F401, F403
from py_doctor.rules.structlog_rules import *    # noqa: F401, F403

# Version information
__version__ = "1.0.1"
__author__ = "aswin"
__description__ = "Diagnose and fix your FastAPI project health"


def get_version():
    """Return version string with optional details"""
    return f"py_doctor version {__version__}"


def print_version():
    """Print version information"""
    print(get_version())
    print(f"Python: {sys.version.split()[0]}")
    print(f"Author: {__author__}")
    print(f"Description: {__description__}")


def main():
    parser = argparse.ArgumentParser(
        prog='py_doctor',
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py_doctor .                    # Scan current directory
  py_doctor ./myproject          # Scan specific project
  py_doctor . --verbose          # Show detailed output
  py_doctor . --score            # Output only score for CI
  py_doctor . --diff main        # Scan only changed files vs main
  py_doctor . --no-lint          # Skip linting pass
  py_doctor . --format json      # JSON output for tools
  py_doctor --version             # Show version
  py_doctor -v                    # Show version (short)
        """
    )
    
    parser.add_argument('path', nargs='?', default='.',
        help='Project path to scan (default: current directory)')
    
    # Version argument (mutually exclusive with other operations)
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument('--version', '-V', action='store_true',
        help='Show version information and exit')
    version_group.add_argument('-v', '--verbose-version', action='store_true',
        help='Show detailed version information and exit')
    
    parser.add_argument('--verbose', action='store_true',
        help='Show file:line per rule')
    parser.add_argument('--score', action='store_true',
        help='Output score only for CI')
    parser.add_argument('--no-lint', action='store_true',
        help='Skip lint pass')
    parser.add_argument('--no-dead-code', action='store_true',
        help='Skip dead code detection')
    parser.add_argument('--no-types', action='store_true',
        help='Skip mypy type checking')
    parser.add_argument('--no-security', action='store_true',
        help='Skip bandit security scan')
    parser.add_argument('--no-md', action='store_true',
        help='Skip NEEDEDFIX.md generation')
    parser.add_argument('--diff', metavar='BRANCH',
        help='Scan only files changed vs branch')
    parser.add_argument('--format', choices=['terminal', 'json'],
        default='terminal', help='Output format')
    parser.add_argument('--config', '-c', metavar='FILE',
        help='Path to config file (pyproject.toml or py_doctor.config.json)')

    args = parser.parse_args()
    
    # Handle version flags
    if args.version:
        print_version()
        sys.exit(0)
    
    if args.verbose_version:
        print_version()
        print(f"\nDependencies:")
        try:
            import importlib.metadata
            deps = ['ruff', 'mypy', 'bandit', 'ast', 'structlog']
            for dep in deps:
                try:
                    version = importlib.metadata.version(dep)
                    print(f"  {dep}: {version}")
                except:
                    print(f"  {dep}: not installed")
        except Exception:
            print("  Could not determine dependency versions")
        sys.exit(0)
    
    asyncio.run(run(args))


async def run(args):
    project_path = os.path.normpath(os.path.abspath(args.path))

    if not os.path.isdir(project_path):
        print(f'Error: Directory not found: {project_path}',
              file=sys.stderr)
        sys.exit(1)

    # load config with optional custom config file
    config = Config.load(project_path, args.config)

    # detect project
    detector = ProjectDetector(project_path)
    await detector.detect()
    
    # Print detection info in verbose mode
    if args.verbose and not args.score and args.format == 'terminal':
        print(f'Project detected: Python {detector.python_version}')
        if detector.fastapi_version:
            print(f'FastAPI: {detector.fastapi_version}')
        if detector.sqlalchemy_version:
            print(f'SQLAlchemy: {detector.sqlalchemy_version}')
        print()

    # run all analysis in parallel
    diagnostics = await run_analysis(project_path, args, config)

    # calculate score
    errors = sum(1 for d in diagnostics if d['type'] == 'ERR')
    warnings = sum(1 for d in diagnostics if d['type'] == 'WARN')
    dead = sum(1 for d in diagnostics if d['type'] == 'DEAD')
    file_count = detector.source_file_count
    score = calculate_score(errors, warnings, dead)

    # score only mode for CI
    if args.score:
        print(score)
        sys.exit(1 if score < 75 else 0)

    # json format
    if args.format == 'json':
        import json
        output = {
            'version': __version__,
            'score': score,
            'errors': errors,
            'warnings': warnings,
            'dead_code': dead,
            'files': file_count,
            'diagnostics': diagnostics
        }
        print(json.dumps(output, indent=2))
        sys.exit(1 if score < 75 else 0)

    # generate terminal report
    reporter = Reporter(verbose=args.verbose)
    await reporter.generate_report(
        diagnostics=diagnostics,
        detector=detector,
        score=score,
        errors=errors,
        warnings=warnings,
        dead_code=dead,
        file_count=file_count
    )

    # generate NEEDEDFIX.md
    if not args.no_md:
        await reporter.generate_markdown_report(
            project_path=project_path,
            diagnostics=diagnostics,
            detector=detector,
            score=score,
            errors=errors,
            warnings=warnings,
            dead_code=dead,
            file_count=file_count
        )
        print(f'\n\033[90m📄 NEEDEDFIX.md → {project_path}/NEEDEDFIX.md\033[0m')

    sys.exit(1 if score < 75 else 0)


async def run_analysis(project_path, args, config):
    tasks = []

    if not args.no_lint:
        tasks.append(LintRunner(project_path, config.ignore_rules).run())
    if not args.no_dead_code:
        tasks.append(DeadCodeRunner(project_path, config.ignore_files).run())
    if not args.no_types:
        tasks.append(TypeRunner(project_path, config.ignore_rules).run())
    if not args.no_security:
        tasks.append(SecurityRunner(project_path, config.ignore_rules).run())

    if not tasks:
        return []

    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]


if __name__ == '__main__':
    main()