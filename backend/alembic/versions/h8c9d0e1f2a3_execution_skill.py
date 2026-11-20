"""execution skill snapshot

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-11-20 17:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h8c9d0e1f2a3'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('executions', sa.Column('skill_id', sa.String(length=50), nullable=True))
    op.add_column('executions', sa.Column('skill_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('executions', 'skill_name')
    op.drop_column('executions', 'skill_id')
