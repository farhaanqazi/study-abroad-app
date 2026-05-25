"""add_appointment_idempotency_key

Adds an optional `idempotency_key` column to `appointments` plus a partial
unique index scoped per-vendor. Lets the booking handler safely retry on
double-tapped WhatsApp/Telegram buttons: insert with a deterministic key,
catch the unique violation, return the existing appointment.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Per-vendor scope: two vendors could legitimately receive colliding
# client-generated keys, so uniqueness is enforced per (vendor_id, key).
# Partial index (WHERE idempotency_key IS NOT NULL) so existing rows with
# NULL aren't constrained and flows that opt out of idempotency keep working.
INDEX_NAME = "uq_appointment_idempotency"


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        INDEX_NAME,
        "appointments",
        ["vendor_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="appointments")
    op.drop_column("appointments", "idempotency_key")
