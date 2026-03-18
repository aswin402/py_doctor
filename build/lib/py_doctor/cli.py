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

def main():
    parser = argparse.ArgumentParser(
        prog='py_doctor',
        description='Diagnose and fix your FastAPI project health'
    )
    parser.add_argument('path', nargs='?', default='.',
        help='Project path to scan (default: current directory)')
    parser.add_argument('--verbose', '-v', action='store_true',
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

    args = parser.parse_args()
    asyncio.run(run(args))

async def run(args):
    project_path = os.path.normpath(os.path.abspath(args.path))

    if not os.path.isdir(project_path):
        print(f'Error: Directory not found: {project_path}',
              file=sys.stderr)
        sys.exit(1)

    # load config
    config = Config.load(project_path)

    # detect project
    detector = ProjectDetector(project_path)
    await detector.detect()
    print(f'Project detected: Python {detector.python_version}')

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
        print(json.dumps({
            'score': score,
            'errors': errors,
            'warnings': warnings,
            'dead_code': dead,
            'files': file_count,
            'diagnostics': diagnostics
        }, indent=2))
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
