"""fix workspace context budget column

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-20 16:10:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: some databases applied the earlier revision before this
    # column was added to it.
    op.execute(
        'ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS context_budget_tokens INTEGER'
    )


def downgrade() -> None:
    # No-op on purpose: the column belongs to f6a7b8c9d0e1 (its upgrade added
    # it and its downgrade drops it). Dropping it here as well made
    # `alembic downgrade base` fail with 42703 (column does not exist).
    # Found by the Phase 5 H3 migration-chain test.
    pass
