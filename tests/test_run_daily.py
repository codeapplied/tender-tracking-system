from tendertracker.config import PortalConfig
from tendertracker.pipeline.relevance import RelevanceRules
from tendertracker.pipeline.run_daily import run_all, run_source
from tendertracker.scrapers.base import RawTender, Scraper
from tendertracker.storage.db import get_engine, get_session_factory, init_db
from tendertracker.storage.models import SyncLog, Tender

SANDBOX_PORTAL = PortalConfig(
    name="sandbox",
    scraper_class="tendertracker.scrapers.sandbox_feed.SandboxFeedScraper",
)


def test_run_source_stores_matching_records(db_session):
    # sandbox fixture ships 5 records; only one matches an EV/charging filter
    portal = PortalConfig(
        name="sandbox",
        scraper_class="tendertracker.scrapers.sandbox_feed.SandboxFeedScraper",
        relevance=RelevanceRules(must_match=["EV", "electric vehicle", "charging"]),
    )
    result = run_source(db_session, portal)

    assert result.fetched == 5
    assert result.new == 1
    assert result.filtered == 4
    assert result.errors == 0
    assert db_session.query(Tender).count() == 1


def test_run_source_no_relevance_rules_stores_everything(db_session):
    result = run_source(db_session, SANDBOX_PORTAL)
    assert result.fetched == 5
    assert result.new == 5
    assert result.filtered == 0


def test_run_source_second_run_is_idempotent(db_session):
    run_source(db_session, SANDBOX_PORTAL)
    db_session.commit()

    result = run_source(db_session, SANDBOX_PORTAL)
    assert result.new == 0
    assert result.updated == 0  # nothing changed since the first run
    assert db_session.query(Tender).count() == 5


def test_run_source_respects_human_owned_fields(db_session):
    run_source(db_session, SANDBOX_PORTAL)
    db_session.commit()

    tender = db_session.query(Tender).first()
    tender.status = "reviewed-by-human"
    db_session.commit()

    run_source(db_session, SANDBOX_PORTAL)
    db_session.commit()

    tender = db_session.query(Tender).filter_by(id=tender.id).one()
    assert tender.status == "reviewed-by-human"  # scraper must not have reset it


def test_run_source_isolates_a_single_bad_record(db_session, monkeypatch):
    class BrokenScraper(Scraper):
        name = "broken-test"

        def fetch(self):
            yield RawTender(source=self.name, external_id="OK-1", title="Fine", raw={"category": "Goods"})
            yield RawTender(source=self.name, external_id="BAD-1", title="Bad", raw=None)  # .get() will raise
            yield RawTender(source=self.name, external_id="OK-2", title="Fine 2", raw={"category": "Services"})

    import tendertracker.pipeline.run_daily as run_daily_module

    monkeypatch.setattr(run_daily_module, "_load_scraper", lambda portal: BrokenScraper())

    portal = PortalConfig(name="broken-test", scraper_class="unused")
    result = run_source(db_session, portal)

    assert result.fetched == 3
    assert result.new == 2  # the two good records still made it through
    assert result.errors == 1
    assert "BAD-1" in result.error_messages[0]


# --- run_all(): only testable in isolation because it now takes `settings`
# explicitly instead of reading the global config.settings singleton — the
# fix for the run_daily/settings inconsistency this replaced. ---------------


def test_run_all_dry_run_writes_synclog_but_not_tenders(tmp_settings, monkeypatch):
    import tendertracker.pipeline.run_daily as run_daily_module

    init_db(get_engine(tmp_settings.db_path))
    monkeypatch.setattr(run_daily_module, "load_portals", lambda: [SANDBOX_PORTAL])

    results = run_all(tmp_settings, apply=False)
    assert len(results) == 1
    assert results[0].new == 5

    with get_session_factory(get_engine(tmp_settings.db_path))() as s:
        assert s.query(Tender).count() == 0
        assert s.query(SyncLog).one().status == "dry-run"


def test_run_all_apply_writes_tenders_and_synclog(tmp_settings, monkeypatch):
    import tendertracker.pipeline.run_daily as run_daily_module

    init_db(get_engine(tmp_settings.db_path))
    monkeypatch.setattr(run_daily_module, "load_portals", lambda: [SANDBOX_PORTAL])

    results = run_all(tmp_settings, apply=True)
    assert results[0].new == 5

    with get_session_factory(get_engine(tmp_settings.db_path))() as s:
        assert s.query(Tender).count() == 5
        assert s.query(SyncLog).one().status == "success"


def test_run_all_skips_disabled_portals(tmp_settings, monkeypatch):
    import tendertracker.pipeline.run_daily as run_daily_module

    init_db(get_engine(tmp_settings.db_path))
    disabled = PortalConfig(
        name="sandbox", scraper_class="tendertracker.scrapers.sandbox_feed.SandboxFeedScraper", enabled=False
    )
    monkeypatch.setattr(run_daily_module, "load_portals", lambda: [disabled])

    assert run_all(tmp_settings, apply=True) == []
