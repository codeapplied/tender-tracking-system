import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..integrations.calendar_sync import CalendarClient
from ..storage.db import get_engine, get_session_factory
from ..storage.models import Tender

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)

CLOSED_STATUSES = {"closed", "lost"}


@dataclass
class CalendarSyncResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)


def is_configured(settings: "Settings") -> bool:
    return bool(
        settings.ms_graph_tenant_id
        and settings.ms_graph_client_id
        and settings.ms_graph_client_secret
        and settings.ms_graph_calendar_user_id
    )


def _event_body(tender: Tender) -> str:
    lines = [f"Source: {tender.source}", f"External ID: {tender.external_id}"]
    if tender.organization:
        lines.append(f"Organization: {tender.organization}")
    if tender.url:
        lines.append(f"URL: {tender.url}")
    return "\n".join(lines)


def sync_calendar(settings: "Settings", apply: bool = False) -> CalendarSyncResult:
    """Project each open tender's closing_date as a calendar event.

    Diffs against a locally-stored snapshot of what was last written
    (calendar_synced_title / calendar_synced_closing_date), not a live
    re-fetch from the Graph API — calendar APIs can normalize/rewrite values
    on the way back out, which makes live-diffing unreliable (see design
    notes). An unchanged tender since the last sync makes no API call at
    all. Plan-only by default, same convention as the rest of the pipeline.
    """
    result = CalendarSyncResult()
    if not is_configured(settings):
        logger.warning("Calendar sync not configured.")
        return result

    client = (
        CalendarClient(
            settings.ms_graph_tenant_id,
            settings.ms_graph_client_id,
            settings.ms_graph_client_secret,
            settings.ms_graph_calendar_user_id,
        )
        if apply
        else None
    )

    engine = get_engine(settings.db_path)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        active = (
            session.query(Tender)
            .filter(Tender.status.notin_(CLOSED_STATUSES), Tender.closing_date.isnot(None))
            .all()
        )

        for tender in active:
            try:
                if tender.calendar_event_id is None:
                    if apply:
                        event = client.create_event(
                            f"Tender closing: {tender.title}", tender.closing_date, _event_body(tender)
                        )
                        tender.calendar_event_id = event["id"]
                        tender.calendar_synced_title = tender.title
                        tender.calendar_synced_closing_date = tender.closing_date
                    result.created += 1
                elif tender.calendar_synced_title != tender.title or tender.calendar_synced_closing_date != tender.closing_date:
                    if apply:
                        client.update_event(
                            tender.calendar_event_id,
                            f"Tender closing: {tender.title}",
                            tender.closing_date,
                            _event_body(tender),
                        )
                        tender.calendar_synced_title = tender.title
                        tender.calendar_synced_closing_date = tender.closing_date
                    result.updated += 1
                else:
                    result.unchanged += 1
            except Exception as exc:
                result.errors += 1
                result.error_messages.append(f"{tender.external_id}: {exc}")
                logger.warning("Calendar sync error for %s", tender.external_id, exc_info=True)

        # Clean up events for tenders that have since closed — a stale
        # "closing today" reminder for something no longer open is worse
        # than no reminder at all.
        archived_with_events = (
            session.query(Tender).filter(Tender.status.in_(CLOSED_STATUSES), Tender.calendar_event_id.isnot(None)).all()
        )
        for tender in archived_with_events:
            try:
                if apply:
                    client.delete_event(tender.calendar_event_id)
                    tender.calendar_event_id = None
                    tender.calendar_synced_title = None
                    tender.calendar_synced_closing_date = None
                result.deleted += 1
            except Exception as exc:
                result.errors += 1
                result.error_messages.append(f"{tender.external_id}: {exc}")
                logger.warning("Calendar cleanup error for %s", tender.external_id, exc_info=True)

        if apply:
            session.commit()
        else:
            session.rollback()

    return result
