from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ..storage.models import SyncLog


@dataclass
class SourceHealth:
    source: str
    last_run_at: datetime | None
    last_status: str | None
    last_success_at: datetime | None
    error_count: int
    total_runs: int


def get_health_summary(session: Session) -> list[SourceHealth]:
    """Per-source rollup — the "at a glance" view an ops user actually
    wants, versus `status`'s flat recent-runs-across-all-sources list where
    a quiet source's last run can get buried by a noisy one."""
    sources = sorted(row[0] for row in session.query(SyncLog.source).distinct().all())

    summary = []
    for source in sources:
        last_run = session.query(SyncLog).filter_by(source=source).order_by(SyncLog.started_at.desc()).first()
        last_success = (
            session.query(SyncLog)
            .filter_by(source=source, status="success")
            .order_by(SyncLog.started_at.desc())
            .first()
        )
        error_count = session.query(SyncLog).filter(SyncLog.source == source, SyncLog.error_message.isnot(None)).count()
        total_runs = session.query(SyncLog).filter_by(source=source).count()
        summary.append(
            SourceHealth(
                source=source,
                last_run_at=last_run.started_at if last_run else None,
                last_status=last_run.status if last_run else None,
                last_success_at=last_success.started_at if last_success else None,
                error_count=error_count,
                total_runs=total_runs,
            )
        )
    return summary


def get_recent_errors(session: Session, limit: int = 20) -> list[SyncLog]:
    return (
        session.query(SyncLog)
        .filter(SyncLog.error_message.isnot(None))
        .order_by(SyncLog.started_at.desc())
        .limit(limit)
        .all()
    )
