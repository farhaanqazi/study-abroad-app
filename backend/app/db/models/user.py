from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserRole
from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


db_user_role = None  # Will be set at runtime from ENUM


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Dashboard user model for authentication and authorization.

    Links to Supabase Auth users by ID. The id field should match
    the auth.uid() from Supabase Auth.
    """
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role = 'admin' OR vendor_id IS NOT NULL",
            name="users_role_vendor_check",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        PG_ENUM(
            UserRole,
            name="user_role",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],  # Use enum values, not member names
        ),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    vendor = relationship("Vendor", back_populates="users")
    created_users = relationship("User", remote_side="User.id", backref="creator")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_vendor_owner(self) -> bool:
        return self.role == UserRole.VENDOR_OWNER

    @property
    def is_reception(self) -> bool:
        return self.role == UserRole.RECEPTION
