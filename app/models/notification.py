from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Index, Integer, String, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# pylint: disable=W0223
class UTCDateTime(TypeDecorator): 
    """UTC datetime with timezone-aware bind parameters and result values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    SUCCEEDED = "SUCCEEDED"
    DEAD_LETTER = "DEAD_LETTER"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notifications_idem_key"),
        Index("ix_notifications_due", "status", "next_retry_at"),
        Index("ix_notifications_provider_status", "provider", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=NotificationStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_response_summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=_utcnow
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
