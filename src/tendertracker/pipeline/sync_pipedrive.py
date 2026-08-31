import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..integrations.pipedrive import PipedriveClient
from ..storage.db import get_engine, get_session_factory
from ..storage.models import Tender

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)

CLOSED_STATUSES = {"closed", "lost"}


@dataclass
class PipedriveSyncResult:
    created: int = 0
    updated: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)


def is_configured(settings: "Settings") -> bool:
    return bool(settings.pipedrive_api_token and settings.pipedrive_domain)


def _build_note(tender: Tender) -> str:
    lines = [
        f"Source: {tender.source}",
        f"External ID: {tender.external_id}",
        f"Category: {tender.category or 'n/a'}",
        f"Relevance score: {tender.relevance_score if tender.relevance_score is not None else 'n/a'}",
    ]
    if tender.url:
        lines.append(f"URL: {tender.url}")
    return "\n".join(lines)


def sync_pipedrive(settings: "Settings", apply: bool = False) -> PipedriveSyncResult:
    """Create/update Pipedrive deals for tracked, non-archived tenders.

    Plan-only by default (apply=False): computes what would be created or
    updated (no Pipedrive API writes, no DB writes) — same default-safe
    convention as the rest of the pipeline. Not configured (missing token/
    domain) returns an empty result rather than raising, matching how cloud
    sync degrades when unconfigured.
    """
    result = PipedriveSyncResult()
    if not is_configured(settings):
        logger.warning("Pipedrive not configured — set PIPEDRIVE_API_TOKEN and PIPEDRIVE_DOMAIN.")
        return result

    client = PipedriveClient(settings.pipedrive_api_token, settings.pipedrive_domain) if apply else None

    engine = get_engine(settings.db_path)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        tenders = session.query(Tender).filter(Tender.status.notin_(CLOSED_STATUSES)).all()

        for tender in tenders:
            try:
                if tender.pipedrive_deal_id:
                    if apply:
                        client.update_deal(int(tender.pipedrive_deal_id), tender.title, tender.estimated_value, tender.currency)
                    result.updated += 1
                else:
                    if apply:
                        org_id = client.find_or_create_organization(tender.organization) if tender.organization else None
                        deal = client.create_deal(tender.title, org_id, tender.estimated_value, tender.currency)
                        tender.pipedrive_deal_id = str(deal["id"])
                        client.add_note(deal["id"], _build_note(tender))
                    result.created += 1
            except Exception as exc:
                result.errors += 1
                result.error_messages.append(f"{tender.external_id}: {exc}")
                logger.warning("Pipedrive sync error for %s", tender.external_id, exc_info=True)

        if apply:
            session.commit()
        else:
            session.rollback()

    return result
