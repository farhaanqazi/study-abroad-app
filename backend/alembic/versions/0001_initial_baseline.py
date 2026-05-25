"""initial baseline

Marks the schema state produced by sql/schema.sql + migration_v2..v5.sql
as the starting point for Alembic. Both upgrade() and downgrade() are
intentional no-ops: existing environments should be marked as having
reached this revision via `alembic stamp head`, and fresh local databases
should apply schema.sql manually before stamping.

Future schema deltas start at revision 0002 and use real op.* calls
(or op.execute(...) for RLS policies, triggers, and functions).

Revision ID: 0001
Revises:
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
