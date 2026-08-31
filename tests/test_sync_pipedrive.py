from unittest.mock import patch

import pytest

from tendertracker.config import PortalConfig
from tendertracker.pipeline.run_daily import run_source
from tendertracker.pipeline.sync_pipedrive import is_configured, sync_pipedrive
from tendertracker.storage.db import get_engine, get_session_factory
from tendertracker.storage.models import Tender

SANDBOX_PORTAL = PortalConfig(name="sandbox", scraper_class="tendertracker.scrapers.sandbox_feed.SandboxFeedScraper")


@pytest.fixture
def settings_with_one_tender(tmp_settings, db_session):
    run_source(db_session, SANDBOX_PORTAL)
    db_session.commit()
    tmp_settings.pipedrive_api_token = "FAKE_TOKEN"
    tmp_settings.pipedrive_domain = "fakecompany"
    return tmp_settings


def test_is_configured(tmp_settings):
    assert is_configured(tmp_settings) is False
    tmp_settings.pipedrive_api_token = "t"
    tmp_settings.pipedrive_domain = "d"
    assert is_configured(tmp_settings) is True


def test_unconfigured_returns_empty_result_no_crash(tmp_settings):
    result = sync_pipedrive(tmp_settings, apply=True)
    assert result.created == 0 and result.updated == 0 and result.errors == 0


def test_dry_run_computes_plan_with_zero_api_calls_and_zero_writes(settings_with_one_tender):
    with patch("tendertracker.pipeline.sync_pipedrive.PipedriveClient") as MockClient:
        instance = MockClient.return_value
        result = sync_pipedrive(settings_with_one_tender, apply=False)

    assert result.created == 5  # sandbox_feed ships 5 records, no relevance filter here
    instance.create_deal.assert_not_called()

    engine = get_engine(settings_with_one_tender.db_path)
    with get_session_factory(engine)() as s:
        assert all(t.pipedrive_deal_id is None for t in s.query(Tender).all())


def test_apply_creates_org_deal_note_and_persists_deal_id(settings_with_one_tender):
    with patch("tendertracker.pipeline.sync_pipedrive.PipedriveClient") as MockClient:
        instance = MockClient.return_value
        instance.find_or_create_organization.return_value = 555
        instance.create_deal.return_value = {"id": 888}

        result = sync_pipedrive(settings_with_one_tender, apply=True)

    assert result.created == 5
    assert instance.create_deal.call_count == 5
    assert instance.add_note.call_count == 5

    engine = get_engine(settings_with_one_tender.db_path)
    with get_session_factory(engine)() as s:
        assert all(t.pipedrive_deal_id == "888" for t in s.query(Tender).all())


def test_second_apply_updates_instead_of_recreating(settings_with_one_tender):
    with patch("tendertracker.pipeline.sync_pipedrive.PipedriveClient") as MockClient:
        instance = MockClient.return_value
        instance.find_or_create_organization.return_value = 555
        instance.create_deal.return_value = {"id": 888}
        sync_pipedrive(settings_with_one_tender, apply=True)

        instance.reset_mock()
        result = sync_pipedrive(settings_with_one_tender, apply=True)

    assert result.updated == 5
    assert result.created == 0
    instance.create_deal.assert_not_called()
    assert instance.update_deal.call_count == 5
