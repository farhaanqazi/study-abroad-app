from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ChannelType
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin


db_channel_type = ENUM("whatsapp", "telegram", name="channel_type", create_type=False)


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendors"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="Asia/Kolkata")
    default_language: Mapped[str] = mapped_column(String(40), nullable=False, default="english")
    flow_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    entry_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    channels: Mapped[list["VendorChannel"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="vendor")


class VendorChannel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendor_channels"
    __table_args__ = (UniqueConstraint("vendor_id", "channel", name="uq_vendor_channel"),)

    vendor_id = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[ChannelType] = mapped_column(db_channel_type, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    inbound_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    vendor: Mapped[Vendor] = relationship(back_populates="channels")


