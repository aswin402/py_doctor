import html
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
        self, diagnostics, detector, score, errors, warnings, dead_code, file_count, threshold=75, project_path="."
    ):
        self._print_command(project_path)
        self._print_detection(detector)

        self.console.print("[bold green]✓[/bold green] Analysis complete\n")
        self.console.print("[dim]" + "─" * 76 + "[/dim]")

        self._print_lint_diagnostics(diagnostics)
        self._print_dead_code_diagnostics(diagnostics)
        self._print_health_score(score, errors, warnings, dead_code, file_count, threshold)
        self._print_priority_fixes(diagnostics)
        self._print_footer()

    def _print_command(self, project_path="."):
        cmd_str = f"py_doctor {project_path}{' --verbose' if self.verbose else ''}"
        self.console.print(f"[cyan]  ❯ {cmd_str}[/cyan]\n")

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
        if self.verbose and d.get("suggestion"):
            self.console.print(f"       [italic green]↳ Suggestion: {d['suggestion']}[/italic green]")
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
                loc = d.get("location", "")
                loc_str = f": [dim]{loc}[/dim]" if loc else ""
                self.console.print(f"  [red]→[/red] Fix [cyan]{d['rule']}[/cyan]{loc_str}")
                if d.get("suggestion"):
                    self.console.print(f"    [italic green]↳ Suggestion: {d['suggestion']}[/italic green]")
                elif d.get("description"):
                    self.console.print(f"    [dim]↳ Cause: {d['description']}[/dim]")
        else:
            self.console.print("  [bold green]✓ No errors found![/bold green]")
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
                sugg = d.get("suggestion", "")
                w(f"### `{rule}`")
                w(f"- **File:** `{loc}`")
                w(f"- **Problem:** {desc}")
                if sugg:
                    w(f"- **Suggestion:** {sugg}")
                w("- **How to fix:**")
                w("")
                w("  ```python")
                w(f"  # Fix: {sugg or desc}")
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

    async def generate_html_report(
        self,
        output_path: str,
        diagnostics: list[dict],
        detector,
        score: int,
        errors: int,
        warnings: int,
        dead_code: int,
        file_count: int,
        threshold: int = 75,
    ) -> str:
        today = date.today().strftime("%Y-%m-%d")
        mid_threshold = max(0, threshold - 25)
        color = "#10b981" if score >= threshold else "#f59e0b" if score >= mid_threshold else "#ef4444"
        label = "Great" if score >= threshold else "Needs work" if score >= mid_threshold else "Critical"

        rows = []
        for d in diagnostics:
            sev = d.get("type", "INFO")
            sev_class = "err" if sev == "ERR" else "warn" if sev == "WARN" else "dead" if sev == "DEAD" else "info"
            rule = html.escape(str(d.get("rule", "")))
            loc = html.escape(str(d.get("location", "")))
            desc = html.escape(str(d.get("description", "")))
            sugg = html.escape(str(d.get("suggestion", "")))

            sugg_html = f'<div class="suggestion"><strong>Suggestion:</strong> {sugg}</div>' if sugg else ""

            rows.append(f"""
            <div class="card issue-card {sev_class}">
                <div class="card-header">
                    <span class="badge {sev_class}">{sev}</span>
                    <span class="rule-name">{rule}</span>
                    <span class="location">{loc}</span>
                </div>
                <div class="card-body">
                    <p class="description">{desc}</p>
                    {sugg_html}
                </div>
            </div>
            """)

        cards_html = "\n".join(rows) if rows else '<div class="card"><p class="empty-state">No issues detected! Excellent code health.</p></div>'

        py_ver = html.escape(str(getattr(detector, "python_version", "unknown")))
        fa_ver = html.escape(str(getattr(detector, "fastapi_version", "not installed") or "not installed"))
        sa_ver = html.escape(str(getattr(detector, "sqlalchemy_version", "not installed") or "not installed"))

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>py_doctor Health Report</title>
<style>
  :root {{
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --text-muted: #8b949e;
    --err: #f85149;
    --warn: #d29922;
    --info: #58a6ff;
    --success: #3fb950;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    padding: 2rem;
    line-height: 1.5;
  }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
  }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #fff; }}
  .date {{ color: var(--text-muted); font-size: 0.9rem; }}
  .score-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 2rem;
  }}
  .score-circle {{
    font-size: 3rem;
    font-weight: 800;
    color: {color};
    min-width: 120px;
    text-align: center;
  }}
  .score-info {{ flex: 1; }}
  .score-label {{ font-size: 1.2rem; font-weight: 600; color: {color}; margin-bottom: 0.5rem; }}
  .bar-bg {{ background: #21262d; border-radius: 4px; height: 10px; overflow: hidden; margin-bottom: 0.8rem; }}
  .bar-fill {{ background: {color}; height: 100%; width: {score}%; transition: width 0.3s ease; }}
  .chips {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem; }}
  .chip {{
    background: #21262d;
    border: 1px solid var(--border);
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }}
  .filters {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; }}
  .btn {{
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
  }}
  .btn:hover {{ border-color: #8b949e; }}
  .btn.active {{ background: #21262d; border-color: #58a6ff; color: #58a6ff; }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.8rem;
  }}
  .card-header {{
    display: flex;
    align-items: center;
    gap: 0.8rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
  }}
  .badge {{
    font-size: 0.7rem;
    font-weight: 700;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    text-transform: uppercase;
  }}
  .badge.err {{ background: rgba(248, 81, 73, 0.2); color: var(--err); border: 1px solid var(--err); }}
  .badge.warn {{ background: rgba(210, 153, 34, 0.2); color: var(--warn); border: 1px solid var(--warn); }}
  .badge.dead {{ background: rgba(163, 113, 247, 0.2); color: #a371f7; border: 1px solid #a371f7; }}
  .badge.info {{ background: rgba(88, 166, 255, 0.2); color: var(--info); border: 1px solid var(--info); }}
  .rule-name {{ font-family: monospace; font-weight: 600; color: #fff; }}
  .location {{ color: var(--text-muted); font-size: 0.85rem; margin-left: auto; font-family: monospace; }}
  .description {{ font-size: 0.95rem; margin-bottom: 0.4rem; }}
  .suggestion {{
    background: #0d1117;
    border-left: 3px solid var(--success);
    padding: 0.5rem 0.8rem;
    border-radius: 0 4px 4px 0;
    font-size: 0.85rem;
    color: #e6edf3;
    margin-top: 0.5rem;
  }}
  .empty-state {{ text-align: center; color: var(--success); font-weight: 600; padding: 2rem; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>py_doctor Health Report</h1>
    <div class="date">Scanned {today}</div>
  </header>

  <div class="score-card">
    <div class="score-circle">{score}</div>
    <div class="score-info">
      <div class="score-label">{label} &bull; {score} / 100</div>
      <div class="bar-bg"><div class="bar-fill"></div></div>
      <div class="chips">
        <span class="chip">Python {py_ver}</span>
        <span class="chip">FastAPI {fa_ver}</span>
        <span class="chip">SQLAlchemy {sa_ver}</span>
        <span class="chip">{file_count} files</span>
        <span class="chip">{errors} errors</span>
        <span class="chip">{warnings} warnings</span>
        <span class="chip">{dead_code} dead code</span>
      </div>
    </div>
  </div>

  <div class="filters">
    <button class="btn active" onclick="filterType('all', this)">All ({len(diagnostics)})</button>
    <button class="btn" onclick="filterType('err', this)">Errors ({errors})</button>
    <button class="btn" onclick="filterType('warn', this)">Warnings ({warnings})</button>
    <button class="btn" onclick="filterType('dead', this)">Dead Code ({dead_code})</button>
  </div>

  <div id="issues-list">
    {cards_html}
  </div>
</div>

<script>
function filterType(type, btn) {{
  document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const cards = document.querySelectorAll('.issue-card');
  cards.forEach(c => {{
    if (type === 'all' || c.classList.contains(type)) {{
      c.style.display = 'block';
    }} else {{
      c.style.display = 'none';
    }}
  }});
}}
</script>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_content

