import pytest

from tendertracker.config import Settings
from tendertracker.storage.db import get_engine, get_session_factory, init_db


@pytest.fixture
def tmp_settings(tmp_path) -> Settings:
    """A Settings instance pointing at a throwaway temp DB/Excel path —
    isolates every test from the real data/ directory and from each other."""
    return Settings(
        db_path=str(tmp_path / "test.db"),
        excel_export_path=str(tmp_path / "test.xlsx"),
        pipedrive_api_token=None,
        pipedrive_domain=None,
        ms_graph_tenant_id=None,
        ms_graph_client_id=None,
        ms_graph_client_secret=None,
        ms_graph_drive_id=None,
        ms_graph_upload_path="TenderTracker/tenders.xlsx",
        ms_graph_calendar_user_id=None,
    )


@pytest.fixture
def db_session(tmp_settings):
    """An initialized DB session against the temp DB, for tests that read/
    write Tender or SyncLog rows directly."""
    engine = get_engine(tmp_settings.db_path)
    init_db(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        yield session
