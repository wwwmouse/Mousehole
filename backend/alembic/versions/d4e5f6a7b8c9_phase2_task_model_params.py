"""phase2 task model parameters

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-20 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('temperature', sa.Float(), nullable=True))
    op.add_column('tasks', sa.Column('max_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'max_tokens')
    op.drop_column('tasks', 'temperature')
