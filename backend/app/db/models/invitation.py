from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import InvitationStatus, UserRole
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin

invitation_status_enum = SAEnum(
    InvitationStatus,
    name="invitation_status",
    values_callable=lambda enum: [member.value for member in enum],
)
# Reuse the existing user_role enum type (do not redefine the DB type).
_invite_role_enum = SAEnum(
    UserRole,
    name="user_role",
    values_callable=lambda enum: [member.value for member in enum],
    create_type=False,
)


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An invitation for an email to join a vendor with a role.

    Claimed when that email next authenticates (matched in the auth/provisioning
    path). Lets admins/owners add members who haven't logged in yet, without
    manual DB writes.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        # At most one OPEN invite per (vendor, email) — enforced in the service
        # layer; this index also accelerates the claim lookup by email.
        Index("ix_invitations_vendor_email", "vendor_id", "email"),
        Index("ix_invitations_email_status", "email", "status"),
        UniqueConstraint("token", name="uq_invitations_token"),
    )

    vendor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[UserRole] = mapped_column(_invite_role_enum, nullable=False)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        invitation_status_enum,
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default=InvitationStatus.PENDING.value,
        index=True,
    )
    invited_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
