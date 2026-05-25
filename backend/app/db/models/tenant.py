from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserRole
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin

# DB-native role enum. The type is owned by Alembic (created in the baseline
# migration); we store enum *values* (owner/agent/viewer), not member names.
user_role_enum = SAEnum(
    UserRole,
    name="user_role",
    values_callable=lambda enum: [member.value for member in enum],
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A human identity, synchronized from the external IdP (Clerk).

    A user is *not* bound to a single tenant — tenant access is expressed
    entirely through :class:`VendorMembership`. Provisioned lazily on first
    authenticated request (see auth dependency layer).
    """

    __tablename__ = "users"

    clerk_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["VendorMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User id={self.id} email={self.email}>"


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tenant: a study-abroad agency with its own public site and members."""

    __tablename__ = "vendors"

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["VendorMembership"]] = relationship(
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    site_config: Mapped[Optional["VendorSiteConfig"]] = relationship(
        back_populates="vendor",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Vendor id={self.id} slug={self.slug}>"


class VendorMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Many-to-many membership binding a :class:`User` to a :class:`Vendor`
    with a role. This is the authorization root: no user touches a tenant
    without a membership row.
    """

    __tablename__ = "vendor_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "vendor_id", name="uq_vendor_memberships_user_id"),
        Index("ix_vendor_memberships_vendor_user", "vendor_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    vendor: Mapped[Vendor] = relationship(back_populates="memberships")


class VendorSiteConfig(TimestampMixin, Base):
    """Published + draft site configuration for a tenant, stored as JSONB.

    `vendor_id` is the primary key (one config per vendor). `config` is the
    live published document; `draft_config` holds unpublished edits.
    """

    __tablename__ = "vendor_site_configs"

    vendor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    draft_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    vendor: Mapped[Vendor] = relationship(back_populates="site_config")
