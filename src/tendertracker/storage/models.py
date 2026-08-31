from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC timestamp — SQLite doesn't preserve tzinfo on round-trip,
    so a timezone-aware value read back would never equal a freshly-built
    one even when unchanged. Stay naive-UTC everywhere instead."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Tender(Base):
    """A single tender/bid opportunity, deduplicated by (source, external_id)."""

    __tablename__ = "tenders"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_tender_source_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    pipedrive_deal_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[int | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SyncLog(Base):
    """One row per pipeline run against a single source — what the ops CLI reads for health."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_fetched: Mapped[int] = mapped_column(default=0)
    records_new: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    records_filtered: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | success | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
