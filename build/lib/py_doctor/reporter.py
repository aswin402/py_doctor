import os
import sys
import asyncio

# Real ANSI escape constants — never use \\x1b or \\033 as strings
ESC = '\x1b'
R   = f'{ESC}[0m'
RED    = f'{ESC}[31m'
GREEN  = f'{ESC}[32m'
YELLOW = f'{ESC}[33m'
CYAN   = f'{ESC}[36m'
GRAY   = f'{ESC}[90m'
BOLD   = f'{ESC}[1m'
WHITE  = f'{ESC}[97m'
GRAY1  = f'{ESC}[90;1m'
B97    = f'{ESC}[1;97m'
BGRED  = f'{ESC}[41;97m'
BGYEL  = f'{ESC}[43;30m'
BGBLU  = f'{ESC}[44;97m'
PURPLE = f'{ESC}[35m'


class Reporter:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.use_color = sys.stdout.isatty() or sys.stderr.isatty()

    def _c(self, code: str, text: str) -> str:
        if not self.use_color:
            return text
        return f'{code}{text}{R}'

    async def generate_report(self, diagnostics, detector,
                              score, errors, warnings,
                              dead_code, file_count):
        self._print_command()
        self._print_detection(detector)
        await self._print_header()
        self._print_lint_diagnostics(diagnostics)
        self._print_dead_code_diagnostics(diagnostics)
        self._print_health_score(score, errors, warnings,
                                 dead_code, file_count)
        self._print_priority_fixes(diagnostics)
        self._print_footer()

    def _print_command(self):
        print(self._c(CYAN, '  ❯ py_doctor . --verbose'))
        print()

    def _print_detection(self, detector):
        print('Detecting project...')
        parts = [f'Python {detector.python_version}']
        if detector.fastapi_version:
            parts.append(f'FastAPI {detector.fastapi_version}')
        if detector.sqlalchemy_version:
            parts.append(f'SQLAlchemy {detector.sqlalchemy_version}')
        sep = self._c(GRAY, ' · ')
        line1 = self._c(GREEN, '✓ ') + sep.join(parts)
        print(f'  {line1}')

        extras = []
        if detector.has_alembic:
            extras.append('Alembic detected')
        if detector.has_structlog:
            extras.append('structlog detected')
        if detector.has_asyncpg:
            extras.append('asyncpg detected')
        extras.append(f'{detector.source_file_count} source files')
        line2 = self._c(GREEN, '✓ ') + self._c(GRAY, ' · ').join(extras)
        print(f'  {line2}')
        print()

    async def _print_header(self):
        print('Running analysis passes in parallel...')
        await self._print_spinner()
        print(self._c(GREEN, '✓ Analysis complete'))
        print()
        print(self._c(GRAY, '─' * 76))

    async def _print_spinner(self):
        frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        for i in range(20):
            sys.stderr.write(f'\r{frames[i % len(frames)]} Lint · Types · Security · Dead code')
            sys.stderr.flush()
            await asyncio.sleep(0.1)
        sys.stderr.write('\r' + ' ' * 60 + '\r')
        sys.stderr.flush()

    def _print_lint_diagnostics(self, diagnostics):
        lints = [d for d in diagnostics if d['type'] in ('ERR', 'WARN')]
        if not lints:
            return
        print()
        print(self._c(GRAY1, 'LINT DIAGNOSTICS'))
        print()
        for d in lints[:15]:
            if d['type'] == 'ERR':
                tag = f'{BGRED} ERR {R}'
            else:
                tag = f'{BGYEL} WARN {R}'
            rule = self._c(CYAN, d['rule'])
            loc = self._c(GRAY, d.get('location', ''))
            pad = max(2, 76 - 6 - len(d['rule']) - len(d.get('location', '')))
            print(f'{tag}  {rule}{" " * pad}{loc}')
            if self.verbose and d.get('description'):
                print(f'       {self._c(GRAY, d["description"])}')
            print()
        print(self._c(GRAY, '─' * 76))
        print()

    def _print_dead_code_diagnostics(self, diagnostics):
        deads = [d for d in diagnostics if d['type'] == 'DEAD']
        if not deads:
            return
        print(self._c(GRAY1, 'DEAD CODE'))
        print()
        for d in deads:
            sub = d.get('subType', 'UNKNOWN').ljust(16).upper()
            desc = d.get('description', '')
            tag = f'{BGBLU} DEAD {R}'
            print(f'{tag}  {self._c(GRAY, sub)}{self._c(PURPLE, desc)}')
            print()
        print(self._c(GRAY, '─' * 76))
        print()

    def _print_health_score(self, score, errors, warnings,
                            dead_code, file_count):
        color = GREEN if score >= 75 else YELLOW if score >= 50 else RED
        label = 'Great' if score >= 75 else 'Needs work' if score >= 50 else 'Critical'

        filled = round(score / 100 * 48)
        empty = 48 - filled
        bar = self._c(color, '━' * filled) + self._c(GRAY, '─' * empty)

        W = 77
        inner = W - 2

        top    = '╭' + '─' * inner + '╮'
        blank  = '│' + ' ' * inner + '│'
        bottom = '╰' + '─' * inner + '╯'

        score_str = str(score)
        score_colored = f'{BOLD}{color}{score_str}{R}'
        score_line = (
            '│  ' +
            score_colored +
            '        ' +
            self._c(GRAY, 'HEALTH SCORE') +
            ' ' * max(0, inner - 2 - len(score_str) - 8 - 12) +
            '│'
        )

        bar_indent = ' ' * 13
        bar_trail = ' ' * max(0, inner - 13 - 48)
        bar_line = '│' + bar_indent + bar + bar_trail + '│'

        stats_raw = (f'{errors} errors  {warnings} warnings  '
                     f'{dead_code} dead code  {file_count} files scanned')
        stats_colored = (
            f'{self._c(B97, str(errors))} errors  '
            f'{self._c(B97, str(warnings))} warnings  '
            f'{self._c(B97, str(dead_code))} dead code  '
            f'{self._c(B97, str(file_count))} files scanned'
        )
        label_pad = label + ' ' * (11 - len(label))
        stats_trail = ' ' * max(0, inner - 2 - len(label_pad) - len(stats_raw))
        stats_line = (
            '│  ' +
            self._c(color, label_pad) +
            stats_colored +
            stats_trail +
            '│'
        )

        print(self._c(GRAY, top))
        print(self._c(GRAY, blank))
        print(score_line)
        print(bar_line)
        print(stats_line)
        print(self._c(GRAY, blank))
        print(self._c(GRAY, bottom))
        print()

    def _print_priority_fixes(self, diagnostics):
        print('Top priority fixes:')
        errs = [d for d in diagnostics if d['type'] == 'ERR'][:3]
        for d in errs:
            arrow = self._c(RED, '→')
            rule = self._c(CYAN, d['rule'])
            print(f'{arrow} Fix {rule} — {d.get("description", "")}')
        print()

    def _print_footer(self):
        fix = self._c(CYAN, 'py_doctor . --fix')
        diff = self._c(CYAN, '--diff main')
        print(f'Run {fix} to auto-fix with AI · {diff} for PR mode')

    async def generate_markdown_report(
            self, project_path, diagnostics, detector,
            score, errors, warnings, dead_code, file_count):

        from datetime import date
        buf = []
        w = buf.append
        today = date.today().strftime('%Y-%m-%d')

        label = ('Great' if score >= 75
                 else 'Needs work' if score >= 50
                 else 'Critical')

        w('# py_doctor Report')
        w('')
        w(f'> Generated by `py_doctor` on {today}')
        w('')
        w('---')
        w('')
        w(f'## Health Score: {score} / 100 — {label}')
        w('')
        w('| Metric | Count |')
        w('|--------|-------|')
        w(f'| Errors | {errors} |')
        w(f'| Warnings | {warnings} |')
        w(f'| Dead code | {dead_code} |')
        w(f'| Files scanned | {file_count} |')
        w(f'| Python | {detector.python_version} |')
        if detector.fastapi_version:
            w(f'| FastAPI | {detector.fastapi_version} |')
        if detector.sqlalchemy_version:
            w(f'| SQLAlchemy | {detector.sqlalchemy_version} |')
        w('')

        errs = [d for d in diagnostics if d['type'] == 'ERR']
        warns = [d for d in diagnostics if d['type'] == 'WARN']
        deads = [d for d in diagnostics if d['type'] == 'DEAD']

        if errs:
            w('---')
            w('')
            w('## Errors — Fix these first')
            w('')
            w('> These cause crashes, data loss, or security issues.')
            w('')
            for d in errs:
                rule = d.get('rule', '')
                loc = d.get('location', '')
                desc = d.get('description', '')
                w(f'### `{rule}`')
                w(f'- **File:** `{loc}`')
                w(f'- **Problem:** {desc}')
                w(f'- **Why critical:** {_err_why(rule)}')
                w('- **How to fix:**')
                w('')
                w('  ```python')
                for line in _err_fix_code(rule, desc):
                    w(f'  {line}')
                w('  ```')
                w('')

        if warns:
            w('---')
            w('')
            w('## Warnings — Fix after errors')
            w('')
            w('> These degrade performance, maintainability, or security.')
            w('')
            seen_rules: dict = {}
            for d in sorted(warns, key=lambda x: x.get('rule', '')):
                rule = d.get('rule', '')
                loc = d.get('location', '')
                desc = d.get('description', '')
                seen_rules.setdefault(rule, []).append((loc, desc))

            for rule, occurrences in seen_rules.items():
                count = len(occurrences)
                plural = 's' if count > 1 else ''
                w(f'### `{rule}` ({count} occurrence{plural})')
                w(f'- **Why it matters:** {_warn_why(rule)}')
                w(f'- **How to fix:** {_warn_fix(rule)}')
                w('- **Affected locations:**')
                for loc, desc in occurrences[:10]:
                    w(f'  - `{loc}` — {desc}')
                if count > 10:
                    w(f'  - _...and {count - 10} more_')
                w('')

        if deads:
            w('---')
            w('')
            w('## Dead Code — Clean up')
            w('')
            w('> Unused files and imports increase bundle size and confusion.')
            w('')
            for d in deads:
                sub = d.get('subType', 'UNKNOWN')
                desc = d.get('description', '')
                w(f'- **{sub}:** `{desc}`')
                w(f'  - {_dead_fix(sub)}')
            w('')

        w('---')
        w('')
        w('## Improvements — After all fixes')
        w('')
        w('Once all errors and warnings are resolved:')
        w('')
        w('1. Run `ruff check . --fix` to auto-fix safe issues')
        w('2. Run `mypy .` to verify 0 type errors remain')
        w('3. Run `pytest` to confirm no regressions')
        w('4. Run `py_doctor . --verbose` to regenerate this report')
        w(f'5. Target score: **75 or above** (current: {score})')
        w('')

        if score < 50:
            w('> Warning: Critical score. Fix errors only first.')
        elif score < 75:
            w('> Note: Needs work. Group warnings by file to fix efficiently.')
        else:
            w('> Great score. Only minor cleanup remaining.')
        w('')
        w('---')
        w('_Run `py_doctor . --verbose` to refresh this report_')

        output_path = os.path.join(project_path, 'NEEDEDFIX.md')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(buf))


def _err_why(rule: str) -> str:
    m = {
        'ruff/F821': 'Undefined name causes NameError crash at runtime.',
        'ruff/F811': 'Redefined name causes unexpected behavior.',
        'ruff/F841': 'Assigned but unused variable is dead code.',
        'ruff/E999': 'Syntax error prevents the file from running at all.',
        'mypy/type-error': 'Type mismatch causes AttributeError or TypeError at runtime.',
        'fastapi/missing-await': 'Missing await returns a coroutine object instead of result.',
        'fastapi/sync-in-async-route': 'Blocking call freezes the entire event loop.',
        'fastapi/hardcoded-secret': 'Secret in source code visible to anyone with repo access.',
        'sqlalchemy/missing-session-close': 'Unclosed session leaks DB connections.',
        'bandit/B102': 'exec() runs arbitrary code — critical security risk.',
        'bandit/B301': 'pickle.loads() with untrusted data allows remote code execution.',
        'bandit/B303': 'MD5/SHA1 are cryptographically broken — use SHA256.',
    }
    return m.get(rule, 'This error causes crashes or undefined behavior at runtime.')


def _err_fix_code(rule: str, desc: str) -> list:
    m = {
        'ruff/F821': [
            '# Add missing import at top of file',
            'import ast  # or whatever module is undefined',
        ],
        'ruff/F841': [
            '# Remove the unused variable assignment',
            'try:',
            '    something()',
            'except Exception:  # remove "as e" if e is unused',
            '    pass',
        ],
        'fastapi/missing-await': [
            '# Before (wrong):',
            'result = db.execute(query)',
            '',
            '# After (correct):',
            'result = await db.execute(query)',
        ],
        'fastapi/sync-in-async-route': [
            '# Before (wrong):',
            'time.sleep(1)',
            '',
            '# After (correct):',
            'await asyncio.sleep(1)',
        ],
        'fastapi/hardcoded-secret': [
            '# Before (wrong):',
            'SECRET_KEY = "mysecret123"',
            '',
            '# After (correct):',
            'from pydantic_settings import BaseSettings',
            'class Settings(BaseSettings):',
            '    secret_key: str',
        ],
        'mypy/type-error': [
            '# Fix the type mismatch shown in the error message.',
            '# 1. Add type annotation: variable: Optional[str] = None',
            '# 2. Add null check: if value is not None:',
        ],
    }
    return m.get(rule, [f'# Fix: {desc}', '# See the error location.'])


def _warn_why(rule: str) -> str:
    m = {
        'ruff/F401': 'Unused imports slow down startup and confuse readers.',
        'ruff/E501': 'Long lines reduce readability in code review.',
        'ruff/W291': 'Trailing whitespace causes noisy diffs.',
        'structlog/print-instead-of-log': 'print() is lost in production. structlog adds context and log levels.',
        'fastapi/missing-response-model': 'Without response_model FastAPI leaks internal fields.',
        'fastapi/missing-status-code': 'Wrong HTTP status codes confuse API clients.',
        'bandit/B404': 'subprocess needs careful use to avoid command injection.',
        'bandit/B603': 'Verify subprocess input is not user-controlled.',
        'bandit/B607': 'Use full executable path for security.',
        'bandit/B110': 'Silent except/pass hides errors making debugging hard.',
        'bandit/B112': 'Bare except/continue can mask important errors.',
    }
    return m.get(rule, 'This warning degrades code quality or security.')


def _warn_fix(rule: str) -> str:
    m = {
        'ruff/F401': 'Remove the unused import line.',
        'ruff/E501': 'Break long lines using parentheses.',
        'ruff/W291': 'Run `ruff check . --fix` to auto-remove trailing whitespace.',
        'structlog/print-instead-of-log': 'Replace `print(msg)` with `logger.info(msg)`.',
        'fastapi/missing-response-model': 'Add `response_model=list[UserResponse]` to decorator.',
        'fastapi/missing-status-code': 'Add `status_code=201` to POST decorator.',
        'bandit/B404': 'Add `# nosec B404` if subprocess is intentional.',
        'bandit/B603': 'Add `# nosec B603` if input is trusted.',
        'bandit/B607': 'Use full path or add `# nosec B607`.',
        'bandit/B110': 'Log exception: `except Exception as e: logger.warning(str(e))`',
        'bandit/B112': 'Log before continuing: `except Exception as e: logger.debug(str(e))`',
    }
    return m.get(rule, 'Apply the fix at the file location.')


def _dead_fix(sub_type: str) -> str:
    m = {
        'UNUSED FILE': 'Verify nothing imports this file then delete it.',
        'UNUSED IMPORT': 'Delete the import line or run `ruff check . --fix`.',
        'DUPLICATE': 'Keep the better file, update all imports, delete the other.',
    }
    return m.get(sub_type.strip().upper(), 'Review and remove if safe.')