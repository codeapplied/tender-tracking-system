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
    a quiet source's last run can get buried by a noisy one.

    One query fetches every SyncLog row (newest first), then aggregates per
    source in Python — previously 4 separate queries per source (4N+1
    total), fine at this project's real scale (a handful of sources) but a
    real inefficiency if it ever needs to track many.
    """
    logs = session.query(SyncLog).order_by(SyncLog.started_at.desc()).all()

    by_source: dict[str, list[SyncLog]] = {}
    for log in logs:
        by_source.setdefault(log.source, []).append(log)

    summary = []
    for source in sorted(by_source):
        source_logs = by_source[source]  # already newest-first
        last_run = source_logs[0]
        last_success = next((log for log in source_logs if log.status == "success"), None)
        error_count = sum(1 for log in source_logs if log.error_message is not None)
        summary.append(
            SourceHealth(
                source=source,
                last_run_at=last_run.started_at,
                last_status=last_run.status,
                last_success_at=last_success.started_at if last_success else None,
                error_count=error_count,
                total_runs=len(source_logs),
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
