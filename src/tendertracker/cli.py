import typer
from rich.console import Console
from rich.table import Table

from .config import load_portals, settings
from .storage.db import get_engine, get_session_factory, init_db
from .storage.models import SyncLog

app = typer.Typer(help="Tender Tracking System — ops CLI")
console = Console()


@app.command()
def init() -> None:
    """Initialize the database."""
    engine = get_engine(settings.db_path)
    init_db(engine)
    console.print(f"[green]Database initialized at {settings.db_path}[/green]")


@app.command()
def status() -> None:
    """Show pipeline health: recent sync runs per source."""
    engine = get_engine(settings.db_path)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        logs = session.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(20).all()

    if not logs:
        console.print("[yellow]No sync runs recorded yet. Run 'tendertracker run' first.[/yellow]")
        raise typer.Exit()

    table = Table(title="Recent Sync Runs")
    for column in ("Source", "Started", "Status", "Fetched", "New", "Updated", "Filtered"):
        table.add_column(column)
    for log in logs:
        table.add_row(
            log.source,
            str(log.started_at),
            log.status,
            str(log.records_fetched),
            str(log.records_new),
            str(log.records_updated),
            str(log.records_filtered),
        )
    console.print(table)


@app.command()
def sources() -> None:
    """List configured portal sources."""
    portals = load_portals()
    if not portals:
        console.print(
            "[yellow]No portals configured. Copy config/portals.example.yaml to config/portals.yaml.[/yellow]"
        )
        raise typer.Exit()
    for portal in portals:
        state = "enabled" if portal.enabled else "disabled"
        console.print(f"- {portal.name} ({state}) -> {portal.scraper_class}")


@app.command()
def run(
    apply: bool = typer.Option(
        False, "--apply", help="Actually write changes. Default is plan-only (dry-run) — no DB writes."
    ),
) -> None:
    """Run the daily fetch pipeline. Plan-only by default — pass --apply to write for real."""
    from .pipeline.run_daily import run_all

    results = run_all(apply=apply)
    if not results:
        console.print(
            "[yellow]No enabled sources to run. Copy config/portals.example.yaml to config/portals.yaml.[/yellow]"
        )
        raise typer.Exit()

    mode = "[bold green]APPLIED[/bold green]" if apply else "[bold yellow]PLAN ONLY (dry-run) — pass --apply to write for real[/bold yellow]"
    console.print(mode)

    table = Table(title="Run Results")
    for column in ("Source", "Fetched", "New", "Updated", "Filtered", "Errors"):
        table.add_column(column)
    for r in results:
        table.add_row(r.source, str(r.fetched), str(r.new), str(r.updated), str(r.filtered), str(r.errors))
    console.print(table)

    for r in results:
        for msg in r.error_messages[:5]:
            console.print(f"[red]  {r.source}: {msg}[/red]")


if __name__ == "__main__":
    app()
