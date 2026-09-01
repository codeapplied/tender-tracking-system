import importlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ..config import PortalConfig, load_portals
from ..scrapers.base import Scraper
from ..storage.db import get_engine, get_session_factory
from ..storage.models import SyncLog, Tender, utcnow

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)

# Fields a re-scrape must never overwrite once a human may have touched them —
# see design notes: re-running the scraper should never silently clobber
# manually-tracked state (status, CRM linkage). Everything else is
# scraper-owned and refreshed on every run.
HUMAN_OWNED_FIELDS = {"status", "pipedrive_deal_id"}


@dataclass
class RunResult:
    source: str
    fetched: int = 0
    new: int = 0
    updated: int = 0
    filtered: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)


def _load_scraper(portal: PortalConfig) -> Scraper:
    module_path, class_name = portal.scraper_class.rsplit(".", 1)
    module = importlib.import_module(module_path)
    scraper_cls = getattr(module, class_name)
    return scraper_cls()


def _upsert(session: Session, raw, normalized: dict) -> str:
    """Insert or update a Tender, respecting HUMAN_OWNED_FIELDS. Returns
    'new', 'updated', or 'unchanged'."""
    existing = session.query(Tender).filter_by(source=raw.source, external_id=raw.external_id).one_or_none()

    if existing is None:
        session.add(Tender(source=raw.source, external_id=raw.external_id, **normalized))
        return "new"

    changed = False
    for name, value in normalized.items():
        if name in HUMAN_OWNED_FIELDS:
            continue
        if getattr(existing, name) != value:
            setattr(existing, name, value)
            changed = True
    return "updated" if changed else "unchanged"


def run_source(session: Session, portal: PortalConfig) -> RunResult:
    """Fetch + normalize + filter + upsert one source. Per-record error
    isolation: one bad record is logged and skipped, it doesn't abort the
    run."""
    from .normalize import normalize
    from .relevance import evaluate

    result = RunResult(source=portal.name)
    scraper = _load_scraper(portal)

    for raw in scraper.fetch():
        result.fetched += 1
        try:
            normalized = normalize(raw)

            text = f"{normalized.get('title') or ''} {normalized.get('description') or ''}"
            passes, score = evaluate(portal.relevance, text)
            if not passes:
                result.filtered += 1
                continue
            normalized["relevance_score"] = score

            outcome = _upsert(session, raw, normalized)
            if outcome == "new":
                result.new += 1
            elif outcome == "updated":
                result.updated += 1
        except Exception as exc:
            result.errors += 1
            result.error_messages.append(f"{raw.external_id}: {exc}")
            logger.warning("Error processing record from %s", portal.name, exc_info=True)

    return result


def run_all(settings: "Settings", apply: bool = False) -> list[RunResult]:
    """Run the pipeline across all enabled sources.

    Defaults to plan-only (apply=False): computes what would change, records
    a SyncLog entry either way, but rolls back the Tender writes instead of
    committing them. Pass apply=True to actually write.

    Takes `settings` explicitly, matching sync_pipedrive/sync_calendar/
    reconcile — this used to read the global config.settings singleton
    directly, the only pipeline module that did, which made it harder to
    test in isolation and inconsistent with the rest of the codebase.
    """
    portals = [p for p in load_portals() if p.enabled]
    if not portals:
        logger.warning("No enabled portals configured.")
        return []

    engine = get_engine(settings.db_path)
    session_factory = get_session_factory(engine)
    results: list[RunResult] = []

    with session_factory() as session:
        for portal in portals:
            log_entry = SyncLog(source=portal.name, started_at=utcnow(), status="running")
            session.add(log_entry)
            session.commit()  # persisted regardless of apply — dry-runs still show up in history

            try:
                result = run_source(session, portal)
                if apply:
                    session.commit()
                    log_entry.status = "success"
                else:
                    session.rollback()
                    log_entry.status = "dry-run"
            except Exception as exc:
                session.rollback()
                result = RunResult(source=portal.name, errors=1, error_messages=[str(exc)])
                log_entry.status = "failed"
                logger.error("Source %s failed entirely", portal.name, exc_info=True)

            log_entry.finished_at = utcnow()
            log_entry.records_fetched = result.fetched
            log_entry.records_new = result.new
            log_entry.records_updated = result.updated
            log_entry.records_filtered = result.filtered
            if result.error_messages:
                log_entry.error_message = "; ".join(result.error_messages[:20])
            session.commit()

            results.append(result)

    return results
