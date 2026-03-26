import os
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class Reporter:
    def __init__(self, verbose: bool = False, max_errors: int = 1000):
        self.verbose = verbose
        self.max_errors = max_errors
        self.console = Console()

    async def generate_report(
        self, diagnostics, detector, score, errors, warnings, dead_code, file_count, threshold=75
    ):
        self._print_command()
        self._print_detection(detector)
        
        self.console.print("[bold green]✓[/bold green] Analysis complete\n")
        self.console.print("[dim]" + "─" * 76 + "[/dim]")
        
        self._print_lint_diagnostics(diagnostics)
        self._print_dead_code_diagnostics(diagnostics)
        self._print_health_score(score, errors, warnings, dead_code, file_count, threshold)
        self._print_priority_fixes(diagnostics)
        self._print_footer()

    def _print_command(self):
        self.console.print("[cyan]  ❯ py_doctor . --verbose[/cyan]\n")

    def _print_detection(self, detector):
        self.console.print("Detecting project...")
        parts = [f"Python {detector.python_version}"]
        if detector.fastapi_version:
            parts.append(f"FastAPI {detector.fastapi_version}")
        if detector.sqlalchemy_version:
            parts.append(f"SQLAlchemy {detector.sqlalchemy_version}")
            
        sep = "[dim] · [/dim]"
        self.console.print(f"  [bold green]✓[/bold green] {sep.join(parts)}")

        extras = []
        if detector.has_alembic:
            extras.append("Alembic detected")
        if detector.has_structlog:
            extras.append("structlog detected")
        if detector.has_asyncpg:
            extras.append("asyncpg detected")
        extras.append(f"{detector.source_file_count} source files")
        
        self.console.print(f"  [bold green]✓[/bold green] {sep.join(extras)}\n")

    def _print_lint_diagnostics(self, diagnostics):
        lints = [d for d in diagnostics if d["type"] in ("ERR", "WARN", "INFO")]
        if not lints:
            return

        errs = [d for d in lints if d["type"] == "ERR"]
        warns = [d for d in lints if d["type"] == "WARN"]
        infos = [d for d in lints if d["type"] == "INFO"]

        if errs:
            self.console.print(f"\n[bold dim]ERRORS ({len(errs)})[/bold dim]\n")
            for d in errs[:20]:
                self._print_issue("ERR", "red", d)

        if warns:
            self.console.print(f"\n[bold dim]WARNINGS ({len(warns)})[/bold dim]\n")
            for d in warns[:20]:
                self._print_issue("WARN", "yellow", d)

        if infos and self.verbose:
            self.console.print(f"\n[bold dim]INFO ({len(infos)})[/bold dim]\n")
            for d in infos[:10]:
                self._print_issue("INFO", "blue", d)

        if len(lints) > 50:
            self.console.print(f"[dim]  ... and {len(lints) - 50} more diagnostics[/dim]")

        self.console.print("[dim]" + "─" * 76 + "[/dim]\n")

    def _print_issue(self, label: str, color: str, d: dict):
        tag = f"[bold white on {color}] {label} [/]"
        rule = f"[cyan]{d['rule']}[/cyan]"
        loc = f"[dim]{d.get('location', '')}[/dim]"
        
        # Calculate padding to right-align the location
        rule_len = len(d['rule'])
        loc_len = len(d.get('location', ''))
        pad = max(2, 76 - 6 - rule_len - loc_len)
        
        self.console.print(f"{tag}  {rule}{' ' * pad}{loc}")
        if self.verbose and d.get("description"):
            self.console.print(f"       [dim]{d['description']}[/dim]")
        self.console.print()

    def _print_dead_code_diagnostics(self, diagnostics):
        deads = [d for d in diagnostics if d["type"] == "DEAD"]
        if not deads:
            return

        self.console.print("[bold dim]DEAD CODE[/bold dim]\n")
        for d in deads:
            sub = d.get("subType", "UNKNOWN").ljust(16).upper()
            desc = d.get("description", "")
            tag = "[bold white on blue] DEAD [/]"
            self.console.print(f"{tag}  [dim]{sub}[/dim][magenta]{desc}[/magenta]\n")
            
        self.console.print("[dim]" + "─" * 76 + "[/dim]\n")

    def _print_health_score(self, score, errors, warnings, dead_code, file_count, threshold):
        mid_threshold = max(0, threshold - 25)
        color = "green" if score >= threshold else "yellow" if score >= mid_threshold else "red"
        label = "Great" if score >= threshold else "Needs work" if score >= mid_threshold else "Critical"

        filled = round(score / 100 * 48)
        empty = 48 - filled
        bar = f"[{color}]{'━' * filled}[/][dim]{'─' * empty}[/dim]"

        table = Table.grid(padding=1)
        table.add_column(justify="left")
        table.add_column(justify="right")

        score_text = Text(f"{score}", style=f"bold {color}")
        stats_text = Text.from_markup(
            f"[bold white]{errors}[/] errors  [bold white]{warnings}[/] warnings  "
            f"[bold white]{dead_code}[/] dead code  [bold white]{file_count}[/] files scanned"
        )
        
        table.add_row(score_text, "[dim]HEALTH SCORE[/dim]")
        table.add_row(bar, "")
        table.add_row(f"[{color}]{label}[/]", stats_text)

        panel = Panel(table, border_style="dim", width=79)
        self.console.print(panel)
        self.console.print()

    def _print_priority_fixes(self, diagnostics):
        self.console.print("Top priority fixes:")
        errs = [d for d in diagnostics if d["type"] == "ERR"][:5]
        if errs:
            for d in errs:
                desc = d.get("description", "")[:60]
                self.console.print(f"[red]→[/red] Fix [cyan]{d['rule']}[/cyan] — {desc}")
        else:
            self.console.print("[bold green]✓ No errors found![/bold green]")
        self.console.print()

    def _print_footer(self):
        self.console.print("Run [cyan]py_doctor . --fix[/cyan] to auto-fix with AI · [cyan]--diff main[/cyan] for PR mode")

    async def generate_markdown_report(
        self, project_path, diagnostics, detector, score, errors, warnings, dead_code, file_count, threshold=75
    ):
        buf = []
        w = buf.append
        today = date.today().strftime("%Y-%m-%d")

        mid_threshold = max(0, threshold - 25)
        label = "Great" if score >= threshold else "Needs work" if score >= mid_threshold else "Critical"

        w("# py_doctor Report")
        w("")
        w(f"> Generated by `py_doctor` on {today}")
        w("")
        w("---")
        w("")
        w(f"## Health Score: {score} / 100 — {label}")
        w("")
        w("| Metric | Count |")
        w("|--------|-------|")
        w(f"| Errors | {errors} |")
        w(f"| Warnings | {warnings} |")
        w(f"| Dead code | {dead_code} |")
        w(f"| Files scanned | {file_count} |")
        w(f"| Python | {detector.python_version} |")
        if detector.fastapi_version:
            w(f"| FastAPI | {detector.fastapi_version} |")
        if detector.sqlalchemy_version:
            w(f"| SQLAlchemy | {detector.sqlalchemy_version} |")
        w("")

        errs = [d for d in diagnostics if d["type"] == "ERR"]
        warns = [d for d in diagnostics if d["type"] == "WARN"]
        deads = [d for d in diagnostics if d["type"] == "DEAD"]

        if errs:
            w("---")
            w("")
            w("## Errors — Fix these first")
            w("")
            w("> These cause crashes, data loss, or security issues.")
            w("")
            for d in errs[:20]:
                rule = d.get("rule", "")
                loc = d.get("location", "")
                desc = d.get("description", "")
                w(f"### `{rule}`")
                w(f"- **File:** `{loc}`")
                w(f"- **Problem:** {desc}")
                w("- **How to fix:**")
                w("")
                w("  ```python")
                w(f"  # Fix: {desc}")
                w("  ```")
                w("")

        if warns:
            w("---")
            w("")
            w("## Warnings — Fix after errors")
            w("")
            w("> These degrade performance, maintainability, or security.")
            w("")
            seen_rules: dict = {}
            for d in sorted(warns, key=lambda x: x.get("rule", "")):
                rule = d.get("rule", "")
                loc = d.get("location", "")
                desc = d.get("description", "")
                seen_rules.setdefault(rule, []).append((loc, desc))

            for rule, occurrences in seen_rules.items():
                count = len(occurrences)
                plural = "s" if count > 1 else ""
                w(f"### `{rule}` ({count} occurrence{plural})")
                w("- **Affected locations:**")
                for loc, desc in occurrences[:10]:
                    w(f"  - `{loc}` — {desc}")
                if count > 10:
                    w(f"  - _...and {count - 10} more_")
                w("")

        if deads:
            w("---")
            w("")
            w("## Dead Code — Clean up")
            w("")
            w("> Unused files and imports increase bundle size and confusion.")
            w("")
            for d in deads:
                sub = d.get("subType", "UNKNOWN")
                desc = d.get("description", "")
                w(f"- **{sub}:** `{desc}`")
            w("")

        w("---")
        w("")
        w("## Improvements — After all fixes")
        w("")
        w("Once all errors and warnings are resolved:")
        w("")
        w("1. Run `ruff check . --fix` to auto-fix safe issues")
        w("2. Run `mypy .` to verify 0 type errors remain")
        w("3. Run `pytest` to confirm no regressions")
        w("4. Run `py_doctor . --verbose` to regenerate this report")
        w(f"5. Target score: **{threshold} or above** (current: {score})")
        w("")

        output_path = os.path.join(project_path, "NEEDEDFIX.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(buf))