"""
main.py
--------
Unified CLI entrypoint for AegisQA (typer-based).

Subcommands:
    crawl <url>     Run core.crawler standalone — prints/saves CrawlGraph.
    run   <url>     Full headless run: crawl → synthesise → execute → scan → report.
    dashboard       Launch `streamlit run dashboard/app.py`.
    demo            Start tests/sample_app/app.py AND the dashboard together
                    — the single command judges need.
"""

import json
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# ── Bootstrap project root ───────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import settings
import storage.db as db

app = typer.Typer(
    name="aegisqa",
    help="AegisQA -- Autonomous Quality Engineering for the AI Development Era",
    add_completion=False,
)

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for arrows/emoji)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_crawl_graph(graph: dict) -> None:
    """Pretty-print a CrawlGraph summary to the console."""
    console.print(Panel(
        f"[bold cyan]Base URL:[/] {graph['base_url']}\n"
        f"[bold cyan]Pages discovered:[/] {len(graph['pages'])}",
        title="CrawlGraph",
    ))
    for page in graph["pages"]:
        table = Table(title=f"{page.get('url')} - {page.get('title', '')}", show_header=True)
        table.add_column("Role", style="green")
        table.add_column("Accessible Name", style="yellow")
        table.add_column("Selector Hint")
        for el in page.get("interactive_elements", []):
            table.add_row(
                el.get("role", ""),
                el.get("accessible_name", ""),
                el.get("selector_hint") or "-",
            )
        console.print(table)


def _print_run_result(result: dict) -> None:
    """Pretty-print a RunResult to the console."""
    status = result.get("status", "?")
    heals = result.get("heal_count", 0)
    dur = result.get("duration_ms", 0)
    color = "green" if status == "passed" else "yellow" if heals > 0 else "red"

    console.print(Panel(
        f"[bold {color}]Status:[/]  {status.upper()}\n"
        f"[bold cyan]Heals:[/]   {heals}\n"
        f"[bold cyan]Duration:[/]{dur:.0f} ms\n"
        f"[bold cyan]Run ID:[/]  {result.get('run_id', '?')}",
        title="Run Result",
        border_style=color,
    ))

    # Steps table
    table = Table(title="Steps", show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Intent")
    table.add_column("Status")
    table.add_column("Duration (ms)")
    for s in result.get("steps", []):
        st_color = "green" if s["status"] == "passed" else "yellow" if s["status"] == "healed" else "red"
        table.add_row(
            str(s["step_index"] + 1),
            s["intent"],
            f"[{st_color}]{s['status']}[/]",
            f"{s.get('duration_ms', 0):.0f}",
        )
    console.print(table)

    # Findings
    findings = result.get("findings", [])
    reflected = [f for f in findings if f.get("reflected")]
    if reflected:
        ft = Table(title="[!] Security Findings", show_header=True, border_style="red")
        ft.add_column("Field")
        ft.add_column("Severity")
        ft.add_column("Payload (excerpt)")
        for f in reflected:
            ft.add_row(f["field"], f["severity"], f["payload"][:60])
        console.print(ft)
    else:
        console.print("[green]No XSS reflections detected[/]")


# ---------------------------------------------------------------------------
# Subcommand: crawl
# ---------------------------------------------------------------------------

@app.command()
def crawl(
    url: str = typer.Argument(help="Target URL to crawl"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save CrawlGraph JSON"),
    max_depth: int = typer.Option(settings.CRAWLER_MAX_DEPTH, "--depth"),
    max_pages: int = typer.Option(settings.CRAWLER_MAX_PAGES, "--pages"),
) -> None:
    """Crawl a web application and print its accessibility-tree graph."""
    from core.crawler import Crawler

    console.print(f"[bold]AegisQA Crawler[/] -> {url}")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Crawling...", total=None)
        crawler = Crawler()
        graph = crawler.crawl(url, max_depth=max_depth, max_pages=max_pages)
        progress.update(task, completed=True)

    _print_crawl_graph(graph)

    if save:
        out = Path("storage") / "crawl_graph.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        console.print(f"[dim]Saved -> {out}[/]")


# ---------------------------------------------------------------------------
# Subcommand: run
# ---------------------------------------------------------------------------

@app.command()
def run(
    url: str = typer.Argument(help="Target URL to run against"),
    workflow_file: str | None = typer.Option(None, "--workflow", "-w",
                                              help="Path to a pre-generated workflow JSON"),
    no_security: bool = typer.Option(False, "--no-security", help="Skip security scan"),
    headless: bool = typer.Option(True, "--headless/--headed"),
) -> None:
    """Full autonomous test run: crawl -> synthesise -> execute -> report."""
    from core.crawler import Crawler
    from core.healer import Healer
    from core.intent_engine import IntentEngine
    from runners.ui_runner import UIRunner

    run_id = str(uuid.uuid4())
    console.print(f"[bold]AegisQA Run[/]  id={run_id[:8]}...  target={url}")

    # -- Phase 1: Crawl
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        task = prog.add_task("Crawling...", total=None)
        crawler = Crawler()
        graph = crawler.crawl(url)
        prog.update(task, description=f"Crawl done - {len(graph['pages'])} page(s)")
        prog.update(task, completed=True)

    # -- Phase 2: Synthesise
    if workflow_file:
        workflow = json.loads(Path(workflow_file).read_text())
        console.print(f"[dim]Using workflow from {workflow_file}[/]")
    else:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            task = prog.add_task("Synthesising workflows...", total=None)
            engine = IntentEngine()
            workflows = engine.synthesize_workflows(graph)
            workflow = workflows[0] if workflows else engine._fallback_workflow()
            engine.generate_playwright_spec(workflow)
            prog.update(task, description=f"Workflow: {workflow.get('name')}", completed=True)

    # -- Phase 3: Execute
    def on_event(ev: dict) -> None:
        etype = ev.get("type", "")
        if etype == "step_started":
            console.print(f"  >> [{ev['step_index']+1}] {ev['intent']}")
        elif etype == "step_passed":
            console.print(f"  [green]PASS[/] [{ev['step_index']+1}] ({ev.get('duration_ms', 0):.0f} ms)")
        elif etype == "step_healed":
            console.print(
                f"  [yellow]HEALED[/] [{ev['step_index']+1}]  "
                f"{ev.get('original_locator', '')} -> {ev.get('healed_locator', '')}  "
                f"({ev.get('heal_latency_ms', 0):.0f} ms)"
            )
        elif etype == "step_failed":
            console.print(f"  [red]FAIL[/] [{ev['step_index']+1}] FAILED: {ev.get('error', '')}")
        elif etype == "security_scan_started":
            console.print("[dim]Security scan...[/]")
        elif etype == "security_scan_finished":
            console.print(f"[dim]Security scan done - {ev.get('reflected_count', 0)} finding(s)[/]")

    healer = Healer(run_id)
    runner = UIRunner(url, run_id)
    result = runner.run(
        workflow,
        healer=healer,
        event_callback=on_event,
        scan_security=not no_security,
    )
    healer.shutdown()

    _print_run_result(result)


# ---------------------------------------------------------------------------
# Subcommand: dashboard
# ---------------------------------------------------------------------------

@app.command()
def dashboard() -> None:
    """Launch the Streamlit dashboard."""
    dash_path = Path(__file__).parent / "dashboard" / "app.py"
    console.print(f"[bold]Launching dashboard...[/]  http://localhost:{settings.DASHBOARD_PORT}")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(dash_path),
         "--server.port", str(settings.DASHBOARD_PORT),
         "--server.headless", "true"],
        check=False,
    )


# ---------------------------------------------------------------------------
# Subcommand: demo
# ---------------------------------------------------------------------------

@app.command()
def demo(
    version: str = typer.Option("v1", "--version", "-v", help="APP_VERSION: v1 or v2"),
    port: int = typer.Option(settings.SAMPLE_APP_PORT, "--port"),
) -> None:
    """
    Demo mode -- starts the sample app AND the dashboard together.

    This is the single command judges need to run from nothing.
    """
    sample_path = Path(__file__).parent / "tests" / "sample_app" / "app.py"
    dash_path = Path(__file__).parent / "dashboard" / "app.py"

    # Ensure DB is ready
    db.init_db()

    app_url = f"http://localhost:{port}"
    dash_url = f"http://localhost:{settings.DASHBOARD_PORT}"

    console.print(Panel(
        f"[bold cyan]Sample App:[/] {app_url}  (APP_VERSION={version})\n"
        f"[bold cyan]Dashboard:[/]  {dash_url}\n\n"
        f"[dim]Press Ctrl+C to stop both processes.[/]",
        title="AegisQA Demo",
        border_style="cyan",
    ))

    env = {**__import__("os").environ, "APP_VERSION": version, "SAMPLE_APP_PORT": str(port)}

    # Start sample app
    sample_proc = subprocess.Popen(
        [sys.executable, str(sample_path)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    console.print(f"[green]OK[/] Sample app started (PID {sample_proc.pid}) -> {app_url}")

    # Give Flask a moment to bind
    time.sleep(1.5)

    # Start dashboard
    dash_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(dash_path),
            "--server.port", str(settings.DASHBOARD_PORT),
            "--server.headless", "true",
        ],
    )
    console.print(f"[green]OK[/] Dashboard started (PID {dash_proc.pid}) -> {dash_url}")
    console.print("[bold]Open the dashboard URL above in your browser.[/]")

    def _cleanup(sig, frame):
        console.print("\n[yellow]Stopping...[/]")
        sample_proc.terminate()
        dash_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    # Wait until one of the processes exits
    try:
        while True:
            if sample_proc.poll() is not None or dash_proc.poll() is not None:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        sample_proc.terminate()
        dash_proc.terminate()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
