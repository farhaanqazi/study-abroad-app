from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SupportTicketStatus
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin

support_ticket_status_enum = SAEnum(
    SupportTicketStatus,
    name="support_ticket_status",
    values_callable=lambda enum: [member.value for member in enum],
)


class SupportTicket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A support/help ticket. Optionally scoped to a vendor. Worked in the
    back-office; threaded via :class:`SupportTicketMessage`."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_status_created", "status", "created_at"),
    )

    vendor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opened_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assignee_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SupportTicketStatus] = mapped_column(
        support_ticket_status_enum,
        nullable=False,
        default=SupportTicketStatus.OPEN,
        server_default=SupportTicketStatus.OPEN.value,
        index=True,
    )

    messages: Mapped[list["SupportTicketMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportTicketMessage.created_at",
    )


class SupportTicketMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One message in a support ticket thread. ``is_internal`` marks operator-
    only notes not shown to the vendor."""

    __tablename__ = "support_ticket_messages"

    ticket_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")
