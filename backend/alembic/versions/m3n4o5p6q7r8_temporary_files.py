"""temporary task files

Revision ID: m3n4o5p6q7r8
Revises: k1l2m3n4o5p6
Create Date: 2026-11-21 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'files',
        sa.Column('is_temporary', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('files', sa.Column('owner_task_id', sa.Uuid(), nullable=True))
    op.create_index('ix_files_owner_task_id', 'files', ['owner_task_id'])


def downgrade() -> None:
    op.drop_index('ix_files_owner_task_id', table_name='files')
    op.drop_column('files', 'owner_task_id')
    op.drop_column('files', 'is_temporary')
