from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VendorCostSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-vendor cost figures that drive the study-abroad cost calculator.

    One row per (vendor, country, study_level). The calculator reads these
    rates to compute an estimate; vendors edit them in the management UI.
    `study_level` defaults to 'any' so a vendor can provide a single
    country-wide rate without breaking the uniqueness scope.
    """

    __tablename__ = "vendor_cost_settings"
    __table_args__ = (
        UniqueConstraint(
            "vendor_id", "country", "study_level", name="uq_vendor_cost_country_level"
        ),
    )

    vendor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    study_level: Mapped[str] = mapped_column(String(60), nullable=False, default="any")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    tuition_per_year: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rent_per_month: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    food_per_month: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
