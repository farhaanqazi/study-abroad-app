from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import WorkspaceRequestStatus
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

workspace_request_status_enum = SAEnum(
    WorkspaceRequestStatus,
    name="workspace_request_status",
    values_callable=lambda enum: [member.value for member in enum],
)


class WorkspaceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's request to have a workspace (vendor) provisioned.

    Submitted by any authenticated user that has no workspace; lands in a
    pending queue an admin approves/rejects in the back-office. Approval
    creates the Vendor + owner membership and links ``created_vendor_id``.
    """

    __tablename__ = "workspace_requests"
    __table_args__ = (
        Index("ix_workspace_requests_status_created", "status", "created_at"),
    )

    requested_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    desired_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[WorkspaceRequestStatus] = mapped_column(
        workspace_request_status_enum,
        nullable=False,
        default=WorkspaceRequestStatus.PENDING,
        server_default=WorkspaceRequestStatus.PENDING.value,
        index=True,
    )
    reviewed_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_vendor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Immutable record of a platform-operator action.

    Written for every mutating admin endpoint (and read-sensitive ones like
    impersonation). Append-only: no updated_at, never mutated after insert.
    NOTE: the JSONB column is ``details`` — ``metadata`` is reserved by
    SQLAlchemy's declarative API and cannot be used as a column attribute.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_vendor_created", "vendor_id", "created_at"),
    )

    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Snapshot of the actor's platform role at action time (audit integrity:
    # survives later role changes).
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    vendor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
