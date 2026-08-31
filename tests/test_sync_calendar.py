from unittest.mock import patch

import pytest

from tendertracker.config import PortalConfig
from tendertracker.pipeline.relevance import RelevanceRules
from tendertracker.pipeline.run_daily import run_source
from tendertracker.pipeline.sync_calendar import is_configured, sync_calendar
from tendertracker.storage.db import get_engine, get_session_factory
from tendertracker.storage.models import Tender

# Filter down to the one sandbox record that has a closing_date and passes,
# to keep assertions simple (one tender, not five).
FILTERED_PORTAL = PortalConfig(
    name="sandbox",
    scraper_class="tendertracker.scrapers.sandbox_feed.SandboxFeedScraper",
    relevance=RelevanceRules(must_match=["EV", "electric vehicle", "charging"]),
)


@pytest.fixture
def settings_with_one_tender(tmp_settings, db_session):
    run_source(db_session, FILTERED_PORTAL)
    db_session.commit()
    tmp_settings.ms_graph_tenant_id = "T"
    tmp_settings.ms_graph_client_id = "C"
    tmp_settings.ms_graph_client_secret = "S"
    tmp_settings.ms_graph_calendar_user_id = "someone@example.com"
    return tmp_settings


def test_is_configured(tmp_settings):
    assert is_configured(tmp_settings) is False


def test_dry_run_makes_zero_api_calls_and_zero_writes(settings_with_one_tender):
    with patch("tendertracker.pipeline.sync_calendar.CalendarClient") as MockClient:
        instance = MockClient.return_value
        result = sync_calendar(settings_with_one_tender, apply=False)

    assert result.created == 1
    instance.create_event.assert_not_called()

    engine = get_engine(settings_with_one_tender.db_path)
    with get_session_factory(engine)() as s:
        assert s.query(Tender).first().calendar_event_id is None


def test_apply_creates_and_persists_snapshot(settings_with_one_tender):
    with patch("tendertracker.pipeline.sync_calendar.CalendarClient") as MockClient:
        instance = MockClient.return_value
        instance.create_event.return_value = {"id": "EVT-NEW"}
        result = sync_calendar(settings_with_one_tender, apply=True)

    assert result.created == 1
    instance.create_event.assert_called_once()

    engine = get_engine(settings_with_one_tender.db_path)
    with get_session_factory(engine)() as s:
        t = s.query(Tender).first()
        assert t.calendar_event_id == "EVT-NEW"
        assert t.calendar_synced_title == t.title
        assert t.calendar_synced_closing_date == t.closing_date


def test_second_sync_unchanged_makes_zero_api_calls(settings_with_one_tender):
    """The whole point of the local-snapshot-diff design: an unrelated
    second run shouldn't hit the Calendar API at all if nothing changed."""
    with patch("tendertracker.pipeline.sync_calendar.CalendarClient") as MockClient:
        instance = MockClient.return_value
        instance.create_event.return_value = {"id": "EVT-NEW"}
        sync_calendar(settings_with_one_tender, apply=True)

        instance.reset_mock()
        result = sync_calendar(settings_with_one_tender, apply=True)

    assert result.unchanged == 1
    assert result.created == 0
    assert result.updated == 0
    instance.create_event.assert_not_called()
    instance.update_event.assert_not_called()


def test_title_change_triggers_update(settings_with_one_tender):
    engine = get_engine(settings_with_one_tender.db_path)

    with patch("tendertracker.pipeline.sync_calendar.CalendarClient") as MockClient:
        instance = MockClient.return_value
        instance.create_event.return_value = {"id": "EVT-NEW"}
        sync_calendar(settings_with_one_tender, apply=True)

        with get_session_factory(engine)() as s:
            t = s.query(Tender).first()
            t.title = "A retitled tender"
            s.commit()

        instance.reset_mock()
        result = sync_calendar(settings_with_one_tender, apply=True)

    assert result.updated == 1
    instance.update_event.assert_called_once()


def test_closing_deletes_the_calendar_event(settings_with_one_tender):
    engine = get_engine(settings_with_one_tender.db_path)

    with patch("tendertracker.pipeline.sync_calendar.CalendarClient") as MockClient:
        instance = MockClient.return_value
        instance.create_event.return_value = {"id": "EVT-NEW"}
        sync_calendar(settings_with_one_tender, apply=True)

        with get_session_factory(engine)() as s:
            t = s.query(Tender).first()
            t.status = "closed"
            s.commit()

        instance.reset_mock()
        result = sync_calendar(settings_with_one_tender, apply=True)

    assert result.deleted == 1
    instance.delete_event.assert_called_once()

    with get_session_factory(engine)() as s:
        assert s.query(Tender).first().calendar_event_id is None
