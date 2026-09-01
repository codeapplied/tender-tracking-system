import logging

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.table import Table

from .config import load_portals, settings
from .storage.db import get_engine, get_session_factory, init_db
from .storage.models import SyncLog

app = typer.Typer(help="Tender Tracking System — ops CLI")
console = Console()


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug-level logging.")) -> None:
    """Tender Tracking System — ops CLI."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False)],
    )


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
            escape(log.source),
            str(log.started_at),
            log.status,
            str(log.records_fetched),
            str(log.records_new),
            str(log.records_updated),
            str(log.records_filtered),
        )
    console.print(table)


@app.command()
def health() -> None:
    """Per-source pipeline health: last run, last success, error counts.
    The "at a glance" view — 'status' shows recent runs flat across all
    sources, which can bury a quiet source's last run under a noisy one."""
    from .pipeline.health import get_health_summary

    engine = get_engine(settings.db_path)
    with get_session_factory(engine)() as session:
        summary = get_health_summary(session)

    if not summary:
        console.print("[yellow]No sync history yet. Run 'tendertracker run' first.[/yellow]")
        raise typer.Exit()

    table = Table(title="Source Health")
    for column in ("Source", "Last Run", "Last Status", "Last Success", "Errors", "Total Runs"):
        table.add_column(column)
    for s in summary:
        last_status = f"[red]{s.last_status}[/red]" if s.last_status == "failed" else s.last_status
        last_success = str(s.last_success_at) if s.last_success_at else "[red]never[/red]"
        table.add_row(
            escape(s.source),
            str(s.last_run_at) if s.last_run_at else "-",
            last_status or "-",
            last_success,
            str(s.error_count),
            str(s.total_runs),
        )
    console.print(table)


@app.command()
def errors(limit: int = typer.Option(20, help="Max number of recent error entries to show.")) -> None:
    """List recent pipeline errors, most recent first."""
    from .pipeline.health import get_recent_errors

    engine = get_engine(settings.db_path)
    with get_session_factory(engine)() as session:
        logs = get_recent_errors(session, limit=limit)

    if not logs:
        console.print("[green]No errors recorded.[/green]")
        raise typer.Exit()

    for log in logs:
        # Parentheses, not brackets, around the source — a literal "[x]" in
        # the composed string gets parsed as Rich markup regardless of what
        # escape() does to the *contents*, so avoid typing brackets ourselves.
        console.print(f"[red]{log.started_at}[/red] ({escape(log.source)}) {escape(log.error_message)}")


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
        console.print(f"- {escape(portal.name)} ({state}) -> {escape(portal.scraper_class)}")


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
            console.print(f"[red]  {escape(r.source)}: {escape(msg)}[/red]")

    if apply:
        _export_excel_and_cloud_sync()
        _sync_pipedrive_if_configured()
        _sync_calendar_if_configured()


def _export_excel_and_cloud_sync() -> None:
    from .integrations.onedrive_sync import sync_excel_if_configured
    from .storage.excel_export import export_to_excel

    with get_session_factory(get_engine(settings.db_path))() as session:
        active, archived = export_to_excel(session, settings.excel_export_path)
    console.print(f"[green]Excel synced to {settings.excel_export_path}[/green] ({active} active, {archived} archived)")

    try:
        result = sync_excel_if_configured(settings)
        if result is not None:
            console.print(f"[green]Cloud sync:[/green] {escape(result.get('webUrl', settings.ms_graph_upload_path))}")
    except Exception as exc:
        console.print(f"[red]Cloud sync failed: {escape(str(exc))}[/red]")


def _sync_pipedrive_if_configured() -> None:
    from .pipeline.sync_pipedrive import is_configured, sync_pipedrive

    if not is_configured(settings):
        return
    result = sync_pipedrive(settings, apply=True)
    console.print(
        f"[green]Pipedrive synced:[/green] {result.created} created, {result.updated} updated, {result.errors} errors"
    )
    for msg in result.error_messages[:5]:
        console.print(f"[red]  {escape(msg)}[/red]")


def _sync_calendar_if_configured() -> None:
    from .pipeline.sync_calendar import is_configured, sync_calendar

    if not is_configured(settings):
        return
    result = sync_calendar(settings, apply=True)
    console.print(
        f"[green]Calendar synced:[/green] {result.created} created, {result.updated} updated, "
        f"{result.unchanged} unchanged, {result.deleted} deleted, {result.errors} errors"
    )
    for msg in result.error_messages[:5]:
        console.print(f"[red]  {escape(msg)}[/red]")


@app.command()
def export() -> None:
    """Regenerate the Excel tracker from current DB state (no pipeline run).
    Also syncs to OneDrive/SharePoint if configured."""
    _export_excel_and_cloud_sync()


@app.command(name="sync-cloud")
def sync_cloud() -> None:
    """Upload the current Excel tracker to OneDrive/SharePoint (Microsoft Graph)."""
    from .integrations.onedrive_sync import is_configured, sync_excel_if_configured

    if not is_configured(settings):
        console.print(
            "[yellow]Cloud sync not configured — set MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, "
            "MS_GRAPH_CLIENT_SECRET, MS_GRAPH_DRIVE_ID in .env. See docs/CLOUD_SYNC_SETUP.md.[/yellow]"
        )
        raise typer.Exit(code=1)

    result = sync_excel_if_configured(settings)
    console.print(f"[green]Cloud sync:[/green] {escape(result.get('webUrl', settings.ms_graph_upload_path))}")


@app.command(name="sync-pipedrive")
def sync_pipedrive_cmd(
    apply: bool = typer.Option(
        False, "--apply", help="Actually write changes. Default is plan-only (dry-run) — no Pipedrive writes."
    ),
) -> None:
    """Create/update Pipedrive deals for tracked tenders. Plan-only by default."""
    from .pipeline.sync_pipedrive import is_configured, sync_pipedrive

    if not is_configured(settings):
        console.print(
            "[yellow]Pipedrive not configured — set PIPEDRIVE_API_TOKEN and PIPEDRIVE_DOMAIN in .env.[/yellow]"
        )
        raise typer.Exit(code=1)

    result = sync_pipedrive(settings, apply=apply)
    mode = "[bold green]APPLIED[/bold green]" if apply else "[bold yellow]PLAN ONLY (dry-run) — pass --apply to write for real[/bold yellow]"
    console.print(mode)
    console.print(f"Created: {result.created}  Updated: {result.updated}  Errors: {result.errors}")
    for msg in result.error_messages[:5]:
        console.print(f"[red]  {escape(msg)}[/red]")


@app.command(name="sync-calendar")
def sync_calendar_cmd(
    apply: bool = typer.Option(
        False, "--apply", help="Actually write changes. Default is plan-only (dry-run) — no calendar writes."
    ),
) -> None:
    """Project open tenders' closing dates as Outlook calendar events. Plan-only by default."""
    from .pipeline.sync_calendar import is_configured, sync_calendar

    if not is_configured(settings):
        console.print(
            "[yellow]Calendar sync not configured — set MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, "
            "MS_GRAPH_CLIENT_SECRET, MS_GRAPH_CALENDAR_USER_ID in .env. See docs/CLOUD_SYNC_SETUP.md.[/yellow]"
        )
        raise typer.Exit(code=1)

    result = sync_calendar(settings, apply=apply)
    mode = "[bold green]APPLIED[/bold green]" if apply else "[bold yellow]PLAN ONLY (dry-run) — pass --apply to write for real[/bold yellow]"
    console.print(mode)
    console.print(
        f"Created: {result.created}  Updated: {result.updated}  Unchanged: {result.unchanged}  "
        f"Deleted: {result.deleted}  Errors: {result.errors}"
    )
    for msg in result.error_messages[:5]:
        console.print(f"[red]  {escape(msg)}[/red]")


@app.command()
def reconcile() -> None:
    """Read-only diff: DB vs. Excel (status) and DB vs. Pipedrive (title,
    value). Reports discrepancies for a human to resolve — never writes a
    fix itself."""
    from .pipeline.reconcile import reconcile as run_reconcile

    result = run_reconcile(settings)
    console.print(f"Checked {result.checked} tenders.")
    console.print(
        f"Excel comparison: {'available' if result.excel_available else '[yellow]skipped — no exported .xlsx found, run tendertracker export first[/yellow]'}"
    )
    console.print(
        f"Pipedrive comparison: {'available' if result.pipedrive_configured else '[yellow]skipped — not configured[/yellow]'}"
    )

    if not result.excel_available and not result.pipedrive_configured:
        console.print(
            "[yellow]Nothing was actually compared — 'no discrepancies' below doesn't mean verified in sync.[/yellow]"
        )

    if result.discrepancies:
        table = Table(title="Discrepancies")
        for column in ("External ID", "Field", "DB value", "Other value", "Other system"):
            table.add_column(column)
        for d in result.discrepancies:
            # DB/other values are human-editable content from Excel or
            # Pipedrive — escape before it reaches Rich's markup parser.
            table.add_row(
                escape(d.external_id), d.field, escape(d.db_value), escape(d.other_value), d.other_system
            )
        console.print(table)
    else:
        console.print("[green]No discrepancies found.[/green]")

    for err in result.errors:
        console.print(f"[red]{escape(err)}[/red]")


if __name__ == "__main__":
    app()
