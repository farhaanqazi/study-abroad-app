"""add_vendor_lead_tables

Adds the study-abroad lead-capture tables (all tenant-scoped via vendor_id):
inquiries, callbacks, applications, qr_logs, plus the cost-calculator lead
magnet's tables: vendor_cost_settings (per-vendor rates) and cost_estimates
(gated submissions). Mirrors the DDL added to sql/schema.sql so both the
fresh-DB bootstrap and forward-rolling Alembic paths converge.

RLS is intentionally not enabled (auth deferred; API filters by vendor_id).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LEAD_TABLES = (
    "inquiries",
    "callbacks",
    "applications",
    "qr_logs",
    "vendor_cost_settings",
    "cost_estimates",
)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _vendor_fk(*, nullable: bool = False) -> sa.Column:
    return sa.Column(
        "vendor_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=nullable,
        index=True,
    )


def upgrade() -> None:
    op.create_table(
        "inquiries",
        _uuid_pk(),
        _vendor_fk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "callbacks",
        _uuid_pk(),
        _vendor_fk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("preferred_time", sa.String(120), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "applications",
        _uuid_pk(),
        _vendor_fk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("education", sa.String(255), nullable=True),
        sa.Column("course", sa.String(255), nullable=True),
        sa.Column("country", sa.String(120), nullable=True),
        sa.Column("intake", sa.String(120), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "qr_logs",
        _uuid_pk(),
        _vendor_fk(nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "vendor_cost_settings",
        _uuid_pk(),
        _vendor_fk(),
        sa.Column("country", sa.String(120), nullable=False),
        sa.Column("study_level", sa.String(60), nullable=False, server_default="any"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("tuition_per_year", sa.Numeric(12, 2), nullable=False),
        sa.Column("rent_per_month", sa.Numeric(12, 2), nullable=False),
        sa.Column("food_per_month", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("vendor_id", "country", "study_level", name="uq_vendor_cost_country_level"),
    )
    op.create_table(
        "cost_estimates",
        _uuid_pk(),
        _vendor_fk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("country", sa.String(120), nullable=False),
        sa.Column("study_level", sa.String(60), nullable=True),
        sa.Column("course", sa.String(255), nullable=True),
        sa.Column("intake", sa.String(120), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("est_tuition", sa.Numeric(12, 2), nullable=True),
        sa.Column("est_stay", sa.Numeric(12, 2), nullable=True),
        sa.Column("est_food", sa.Numeric(12, 2), nullable=True),
        sa.Column("est_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_index("idx_inquiries_vendor_created", "inquiries", ["vendor_id", "created_at"])
    op.create_index("idx_callbacks_vendor_created", "callbacks", ["vendor_id", "created_at"])
    op.create_index("idx_applications_vendor_created", "applications", ["vendor_id", "created_at"])
    op.create_index("idx_qr_logs_vendor_created", "qr_logs", ["vendor_id", "created_at"])
    op.create_index("idx_cost_estimates_vendor_created", "cost_estimates", ["vendor_id", "created_at"])

    # updated_at triggers (function update_updated_at() already exists from baseline)
    for table in _LEAD_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS set_updated_at_on_{table} ON {table};"
            f"CREATE TRIGGER set_updated_at_on_{table} BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION update_updated_at();"
        )


def downgrade() -> None:
    for table in _LEAD_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS set_updated_at_on_{table} ON {table};")
    op.drop_table("cost_estimates")
    op.drop_table("vendor_cost_settings")
    op.drop_table("qr_logs")
    op.drop_table("applications")
    op.drop_table("callbacks")
    op.drop_table("inquiries")
