"""skill library and artifact source

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-11-20 18:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i9d0e1f2a3b4'
down_revision: Union[str, None] = 'h8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skills',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.Column('output_type', sa.String(length=50), nullable=False),
        sa.Column('is_builtin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'task_skills',
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('skill_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('task_id', 'skill_id'),
        sa.UniqueConstraint('task_id', 'skill_id', name='uq_task_skills_task_skill'),
    )
    op.add_column(
        'artifacts',
        sa.Column('source_type', sa.String(length=20), nullable=False, server_default='execution'),
    )
    op.add_column(
        'artifacts',
        sa.Column('source_message_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_artifacts_source_message_id',
        'artifacts',
        'messages',
        ['source_message_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_artifacts_source_message_id', 'artifacts', ['source_message_id']
    )


def downgrade() -> None:
    op.drop_index('ix_artifacts_source_message_id', table_name='artifacts')
    op.drop_constraint('fk_artifacts_source_message_id', 'artifacts', type_='foreignkey')
    op.drop_column('artifacts', 'source_message_id')
    op.drop_column('artifacts', 'source_type')
    op.drop_table('task_skills')
    op.drop_table('skills')
