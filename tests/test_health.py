from tendertracker.pipeline.health import get_health_summary, get_recent_errors
from tendertracker.storage.models import SyncLog, utcnow


def _log(source: str, status: str, error_message: str | None = None) -> SyncLog:
    return SyncLog(source=source, started_at=utcnow(), finished_at=utcnow(), status=status, error_message=error_message)


def test_empty_db_returns_empty_summary(db_session):
    assert get_health_summary(db_session) == []


def test_single_source_single_run(db_session):
    db_session.add(_log("sandbox", "success"))
    db_session.commit()

    summary = get_health_summary(db_session)
    assert len(summary) == 1
    s = summary[0]
    assert s.source == "sandbox"
    assert s.last_status == "success"
    assert s.last_success_at is not None
    assert s.error_count == 0
    assert s.total_runs == 1


def test_last_success_skips_a_more_recent_failure(db_session):
    """The whole point of tracking last_success separately from last_run —
    a source that's currently failing should still show when it last
    actually worked, not just 'never'."""
    import time

    db_session.add(_log("sandbox", "success"))
    db_session.commit()
    time.sleep(0.01)
    db_session.add(_log("sandbox", "failed", error_message="boom"))
    db_session.commit()

    summary = get_health_summary(db_session)
    s = summary[0]
    assert s.last_status == "failed"  # most recent run failed
    assert s.last_success_at is not None  # but a success exists earlier
    assert s.error_count == 1
    assert s.total_runs == 2


def test_never_succeeded_reports_none(db_session):
    db_session.add(_log("sandbox", "failed", error_message="boom"))
    db_session.commit()

    s = get_health_summary(db_session)[0]
    assert s.last_success_at is None


def test_multiple_sources_kept_separate_and_sorted(db_session):
    db_session.add(_log("zzz-source", "success"))
    db_session.add(_log("aaa-source", "success"))
    db_session.commit()

    summary = get_health_summary(db_session)
    assert [s.source for s in summary] == ["aaa-source", "zzz-source"]


def test_error_count_only_counts_rows_with_error_message(db_session):
    db_session.add(_log("sandbox", "success"))
    db_session.add(_log("sandbox", "dry-run"))
    db_session.add(_log("sandbox", "failed", error_message="boom"))
    db_session.commit()

    s = get_health_summary(db_session)[0]
    assert s.error_count == 1
    assert s.total_runs == 3


def test_get_recent_errors_only_returns_rows_with_error_message(db_session):
    db_session.add(_log("sandbox", "success"))
    db_session.add(_log("sandbox", "failed", error_message="boom"))
    db_session.commit()

    errors = get_recent_errors(db_session)
    assert len(errors) == 1
    assert errors[0].error_message == "boom"


def test_get_recent_errors_respects_limit(db_session):
    for i in range(5):
        db_session.add(_log("sandbox", "failed", error_message=f"error {i}"))
    db_session.commit()

    assert len(get_recent_errors(db_session, limit=2)) == 2
