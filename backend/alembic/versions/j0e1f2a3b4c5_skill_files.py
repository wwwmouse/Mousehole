"""skill files and snapshot source

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-11-20 20:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'j0e1f2a3b4c5'
down_revision: Union[str, None] = 'i9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skill_files',
        sa.Column('skill_id', sa.Uuid(), nullable=False),
        sa.Column('file_id', sa.Uuid(), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('skill_id', 'file_id'),
    )
    op.drop_constraint(
        'snapshot_source_type_valid', 'execution_file_snapshots', type_='check'
    )
    op.create_check_constraint(
        'snapshot_source_type_valid',
        'execution_file_snapshots',
        "source_type IN ('project_inherited', 'task_added', 'skill_asset')",
    )


def downgrade() -> None:
    op.drop_constraint(
        'snapshot_source_type_valid', 'execution_file_snapshots', type_='check'
    )
    op.create_check_constraint(
        'snapshot_source_type_valid',
        'execution_file_snapshots',
        "source_type IN ('project_inherited', 'task_added')",
    )
    op.drop_table('skill_files')
