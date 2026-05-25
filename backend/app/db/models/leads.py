from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.common import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _vendor_fk(*, nullable: bool = False):
    """Vendor tenant FK shared by every lead table. Leads are tenant-scoped."""
    return mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=nullable,
        index=True,
    )


class Inquiry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Generic contact / inquiry form submission (Horizon `inquiries`)."""

    __tablename__ = "inquiries"

    vendor_id: Mapped[UUID] = _vendor_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class Callback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Request-a-callback submission (Horizon `callbacks`)."""

    __tablename__ = "callbacks"

    vendor_id: Mapped[UUID] = _vendor_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Full study-abroad application submission (Horizon `applications`)."""

    __tablename__ = "applications"

    vendor_id: Mapped[UUID] = _vendor_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    education: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intake: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class QrLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Fire-and-forget QR-scan log (Horizon `qr_logs`).

    `vendor_id` is nullable: a scan can be logged before the vendor context
    is fully resolved, and we never want logging to block on it.
    """

    __tablename__ = "qr_logs"

    vendor_id: Mapped[UUID | None] = _vendor_fk(nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CostEstimate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A gated cost-calculator submission — the lead magnet's lead row.

    Stores the student's inputs, their contact details (capture is gated:
    the estimate is only returned after these are provided), and the
    server-computed breakdown at submission time.
    """

    __tablename__ = "cost_estimates"

    vendor_id: Mapped[UUID] = _vendor_fk()
    # contact (gated capture)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    # inputs
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    study_level: Mapped[str | None] = mapped_column(String(60), nullable=True)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    intake: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    # computed breakdown (snapshot at submission time)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    est_tuition: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    est_stay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    est_food: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    est_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
