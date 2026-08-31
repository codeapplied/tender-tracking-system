from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..scrapers.base import RawTender

DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")


def parse_date(value: Any) -> datetime | None:
    """Returns a naive datetime (assumed UTC) — see storage.models.utcnow
    for why this project stays naive-UTC throughout rather than using
    timezone-aware values SQLite can't round-trip."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _normalize_sandbox(raw: RawTender) -> dict:
    data = raw.raw
    return {
        "title": raw.title,
        "description": data.get("description"),
        "category": data.get("category"),
        "published_date": parse_date(data.get("published_date")),
        "closing_date": parse_date(data.get("closing_date")),
        "estimated_value": data.get("estimated_value"),
        "currency": data.get("currency"),
        "url": data.get("url"),
    }


def _normalize_canadabuys(raw: RawTender) -> dict:
    data = raw.raw
    return {
        "title": raw.title,
        "description": data.get("tenderDescription-descriptionAppelOffres-eng"),
        "category": (data.get("procurementCategory-categorieApprovisionnement") or "").lstrip("*") or None,
        "published_date": parse_date(data.get("publicationDate-datePublication")),
        "closing_date": parse_date(data.get("tenderClosingDate-appelOffresDateCloture")),
        "estimated_value": None,
        "currency": None,
        "url": data.get("noticeURL-URLavis-eng"),
    }


def _normalize_generic(raw: RawTender) -> dict:
    """Fallback for any scraper not registered below — assumes flat,
    English-named fields matching the sandbox shape. New scrapers should
    add a dedicated normalizer here if their raw shape differs."""
    return _normalize_sandbox(raw)


NORMALIZERS: dict[str, Callable[[RawTender], dict]] = {
    "sandbox": _normalize_sandbox,
    "canadabuys-open-data": _normalize_canadabuys,
}


def normalize(raw: RawTender) -> dict:
    """Map a RawTender's source-specific `raw` payload into the common
    Tender field set. Each source has its own raw shape (the sandbox fixture
    uses flat English field names; CanadaBuys uses its bilingual CSV column
    names) — this is where that gets reconciled into one schema."""
    normalizer = NORMALIZERS.get(raw.source, _normalize_generic)
    return normalizer(raw)
