"""project-private files

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-11-24 21:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'p6q7r8s9t0u1'
down_revision: Union[str, None] = 'o5p6q7r8s9t0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'files',
        sa.Column('owner_project_id', sa.Uuid(), nullable=True),
    )
    op.create_index(
        'ix_files_owner_project_id', 'files', ['owner_project_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_files_owner_project_id', table_name='files')
    op.drop_column('files', 'owner_project_id')
