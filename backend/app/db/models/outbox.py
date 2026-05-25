from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OutboxStatus
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

outbox_status_enum = SAEnum(
    OutboxStatus,
    name="outbox_status",
    values_callable=lambda enum: [member.value for member in enum],
)


class OutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Transactional-outbox event.

    Written in the *same* DB transaction as the business row (e.g. a lead), so
    a committed lead always has a committed job. The ARQ worker drains pending
    rows, performs the side effect (email/webhook), and records terminal state
    here — providing a durable audit trail and at-least-once delivery.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        # Fast claim query: pending rows that are due, oldest first.
        Index("ix_outbox_events_status_available", "status", "available_at"),
        # Optional caller-supplied dedup key for idempotent enqueue.
        UniqueConstraint("dedup_key", name="uq_outbox_events_dedup_key"),
    )

    vendor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # The source aggregate this event was emitted for (e.g. "inquiry", <uuid>).
    aggregate_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    aggregate_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[OutboxStatus] = mapped_column(
        outbox_status_enum,
        nullable=False,
        default=OutboxStatus.PENDING,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ProcessedEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Idempotency ledger for inbound side effects (webhooks, provider
    callbacks) and outbound deliveries. A unique (source, external_id) pair
    guarantees replay protection: a second arrival of the same external event
    is a no-op.
    """

    __tablename__ = "processed_events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_processed_events_source"),
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dedup_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
