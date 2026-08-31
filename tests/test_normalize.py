from datetime import datetime, timezone

from tendertracker.pipeline.normalize import normalize, parse_date
from tendertracker.scrapers.base import RawTender


def test_parse_date_handles_date_only():
    assert parse_date("2026-09-15") == datetime(2026, 9, 15)


def test_parse_date_handles_datetime():
    assert parse_date("2026-09-15T14:00:00") == datetime(2026, 9, 15, 14, 0, 0)


def test_parse_date_strips_timezone_if_present():
    aware = datetime(2026, 9, 15, tzinfo=timezone.utc)
    result = parse_date(aware)
    assert result.tzinfo is None
    assert result == datetime(2026, 9, 15)


def test_parse_date_none_or_empty_returns_none():
    assert parse_date(None) is None
    assert parse_date("") is None


def test_parse_date_unparseable_returns_none():
    assert parse_date("not a date") is None


def test_normalize_sandbox_maps_all_fields():
    raw = RawTender(
        source="sandbox",
        external_id="SAMPLE-1",
        title="Test Tender",
        raw={
            "description": "A description",
            "category": "Construction",
            "organization": "Test Org",
            "published_date": "2026-08-01",
            "closing_date": "2026-09-01",
            "estimated_value": 1000,
            "currency": "CAD",
            "url": "https://example.org/1",
        },
    )
    result = normalize(raw)
    assert result["title"] == "Test Tender"
    assert result["description"] == "A description"
    assert result["category"] == "Construction"
    assert result["organization"] == "Test Org"
    assert result["published_date"] == datetime(2026, 8, 1)
    assert result["closing_date"] == datetime(2026, 9, 1)
    assert result["estimated_value"] == 1000
    assert result["currency"] == "CAD"
    assert result["url"] == "https://example.org/1"


def test_normalize_canadabuys_maps_bilingual_field_names():
    raw = RawTender(
        source="canadabuys-open-data",
        external_id="cb-123",
        title="Canoe Request",
        raw={
            "tenderDescription-descriptionAppelOffres-eng": "Fifty canoes",
            "procurementCategory-categorieApprovisionnement": "*GD",
            "contractingEntityName-nomEntitContractante-eng": "Department of National Defence",
            "publicationDate-datePublication": "2026-08-31",
            "tenderClosingDate-appelOffresDateCloture": "2026-09-15T14:00:00",
            "noticeURL-URLavis-eng": "https://canadabuys.canada.ca/x",
        },
    )
    result = normalize(raw)
    assert result["description"] == "Fifty canoes"
    assert result["category"] == "GD"  # leading "*" stripped
    assert result["organization"] == "Department of National Defence"
    assert result["published_date"] == datetime(2026, 8, 31)
    assert result["closing_date"] == datetime(2026, 9, 15, 14, 0, 0)
    assert result["url"] == "https://canadabuys.canada.ca/x"
    # CanadaBuys feed doesn't carry a structured value/currency field
    assert result["estimated_value"] is None
    assert result["currency"] is None


def test_normalize_unregistered_source_falls_back_to_generic():
    raw = RawTender(
        source="some-new-source-not-registered",
        external_id="X-1",
        title="Some Title",
        raw={"description": "d", "category": "c", "url": "https://x"},
    )
    result = normalize(raw)
    # generic fallback assumes the sandbox's flat field-name shape
    assert result["title"] == "Some Title"
    assert result["description"] == "d"
    assert result["category"] == "c"
    assert result["url"] == "https://x"
