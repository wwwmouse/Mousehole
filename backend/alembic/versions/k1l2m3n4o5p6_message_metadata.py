"""message metadata

Revision ID: k1l2m3n4o5p6
Revises: j0e1f2a3b4c5
Create Date: 2026-11-20 20:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('messages', 'metadata')
