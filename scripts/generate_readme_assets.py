"""Regenerate the CLI-output SVGs embedded in the README.

Runs the real CLI code paths (not a mockup) against a throwaway temp DB
populated by the sandbox scraper, capturing Rich's actual rendered output
(colors, tables, box-drawing) to SVG. Re-run this after any change to the
CLI's table layouts so the README images stay accurate.

Usage: python scripts/generate_readme_assets.py
"""

import os
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

REPO_ROOT = Path(__file__).parent.parent
ASSETS_DIR = REPO_ROOT / "docs" / "assets"


def main() -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="tendertracker-assets-"))
    original_cwd = Path.cwd()

    try:
        (tmp_dir / "config").mkdir()
        shutil.copy(REPO_ROOT / "config" / "portals.example.yaml", tmp_dir / "config" / "portals.yaml")

        os.chdir(tmp_dir)

        # Mutate the shared global `settings` singleton in place — every
        # module did `from ..config import settings` at import time, binding
        # to this one object, so reassigning cli_module.settings alone
        # wouldn't be seen by run_daily.py's own separately-bound reference.
        import tendertracker.cli as cli_module
        from tendertracker.config import settings as demo_settings

        demo_settings.db_path = str(tmp_dir / "demo.db")
        demo_settings.excel_export_path = str(tmp_dir / "demo.xlsx")
        demo_settings.pipedrive_api_token = None
        demo_settings.pipedrive_domain = None
        demo_settings.ms_graph_tenant_id = None
        demo_settings.ms_graph_client_id = None
        demo_settings.ms_graph_client_secret = None
        demo_settings.ms_graph_drive_id = None
        demo_settings.ms_graph_calendar_user_id = None

        from tendertracker.storage.db import get_engine, get_session_factory, init_db
        from tendertracker.storage.models import Tender

        engine = get_engine(demo_settings.db_path)
        init_db(engine)
        session_factory = get_session_factory(engine)

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        # --- tendertracker run --apply -----------------------------------
        console = Console(record=True, width=100)
        cli_module.console = console
        cli_module.run(apply=True)
        console.save_svg(str(ASSETS_DIR / "cli-run.svg"), title="tendertracker run --apply")

        # --- tendertracker health ----------------------------------------
        console = Console(record=True, width=100)
        cli_module.console = console
        cli_module.health()
        console.save_svg(str(ASSETS_DIR / "cli-health.svg"), title="tendertracker health")

        # --- tendertracker reconcile (with a real discrepancy) -----------
        with session_factory() as session:
            tender = session.query(Tender).first()
            tender.status = "bidding"  # DB says bidding; Excel (below) still says the old status
            session.commit()

        console = Console(record=True, width=100)
        cli_module.console = console
        cli_module.reconcile()
        console.save_svg(str(ASSETS_DIR / "cli-reconcile.svg"), title="tendertracker reconcile")

        print(f"Wrote SVGs to {ASSETS_DIR}")

    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
