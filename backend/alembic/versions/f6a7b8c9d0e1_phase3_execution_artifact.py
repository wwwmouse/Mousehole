"""phase3 execution and artifact

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-20 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workspaces',
        sa.Column('context_budget_tokens', sa.Integer(), nullable=True),
    )
    op.create_table(
        'executions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('model_provider', sa.String(length=50), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('input_summary', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name=op.f('ck_executions_execution_status_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['task_id'], ['tasks.id'],
            name=op.f('fk_executions_task_id_tasks'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_executions')),
        sa.UniqueConstraint('task_id', 'sequence', name='execution_sequence_unique'),
    )
    op.create_index(op.f('ix_executions_task_id'), 'executions', ['task_id'], unique=False)

    op.create_table(
        'execution_steps',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('execution_id', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('step_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('input_summary', sa.Text(), nullable=True),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name=op.f('ck_execution_steps_execution_step_status_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['execution_id'], ['executions.id'],
            name=op.f('fk_execution_steps_execution_id_executions'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_execution_steps')),
        sa.UniqueConstraint('execution_id', 'sequence', name='execution_step_sequence_unique'),
    )
    op.create_index(
        op.f('ix_execution_steps_execution_id'), 'execution_steps', ['execution_id'], unique=False
    )

    op.create_table(
        'execution_file_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('execution_id', sa.Uuid(), nullable=False),
        sa.Column('file_id', sa.Uuid(), nullable=False),
        sa.Column('filename_snapshot', sa.String(length=512), nullable=False),
        sa.Column('content_hash_snapshot', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=30), nullable=False),
        sa.Column('usage_mode', sa.String(length=20), nullable=False),
        sa.Column(
            'used_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('project_inherited', 'task_added')",
            name=op.f('ck_execution_file_snapshots_snapshot_source_type_valid'),
        ),
        sa.CheckConstraint(
            "usage_mode IN ('direct', 'summarized')",
            name=op.f('ck_execution_file_snapshots_snapshot_usage_mode_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['execution_id'], ['executions.id'],
            name=op.f('fk_execution_file_snapshots_execution_id_executions'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['file_id'], ['files.id'],
            name=op.f('fk_execution_file_snapshots_file_id_files'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_execution_file_snapshots')),
        sa.UniqueConstraint('execution_id', 'file_id', name='execution_file_unique'),
    )
    op.create_index(
        op.f('ix_execution_file_snapshots_execution_id'),
        'execution_file_snapshots', ['execution_id'], unique=False,
    )
    op.create_index(
        op.f('ix_execution_file_snapshots_file_id'),
        'execution_file_snapshots', ['file_id'], unique=False,
    )

    op.create_table(
        'artifact_series',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('current_artifact_id', sa.Uuid(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['task_id'], ['tasks.id'],
            name=op.f('fk_artifact_series_task_id_tasks'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_artifact_series')),
        sa.UniqueConstraint('task_id', 'title', name='artifact_series_title_unique'),
    )
    op.create_index(
        op.f('ix_artifact_series_task_id'), 'artifact_series', ['task_id'], unique=False
    )

    op.create_table(
        'artifacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('series_id', sa.Uuid(), nullable=False),
        sa.Column('source_execution_id', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('storage_key', sa.String(length=512), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            'version > 0', name=op.f('ck_artifacts_artifact_version_positive')
        ),
        sa.ForeignKeyConstraint(
            ['series_id'], ['artifact_series.id'],
            name=op.f('fk_artifacts_series_id_artifact_series'), ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_execution_id'], ['executions.id'],
            name=op.f('fk_artifacts_source_execution_id_executions'), ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_artifacts')),
        sa.UniqueConstraint('series_id', 'version', name='artifact_version_unique'),
    )
    op.create_index(
        op.f('ix_artifacts_series_id'), 'artifacts', ['series_id'], unique=False
    )
    op.create_index(
        op.f('ix_artifacts_source_execution_id'),
        'artifacts', ['source_execution_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_column('workspaces', 'context_budget_tokens')
    op.drop_index(op.f('ix_artifacts_source_execution_id'), table_name='artifacts')
    op.drop_index(op.f('ix_artifacts_series_id'), table_name='artifacts')
    op.drop_table('artifacts')
    op.drop_index(op.f('ix_artifact_series_task_id'), table_name='artifact_series')
    op.drop_table('artifact_series')
    op.drop_index(
        op.f('ix_execution_file_snapshots_file_id'), table_name='execution_file_snapshots'
    )
    op.drop_index(
        op.f('ix_execution_file_snapshots_execution_id'),
        table_name='execution_file_snapshots',
    )
    op.drop_table('execution_file_snapshots')
    op.drop_index(
        op.f('ix_execution_steps_execution_id'), table_name='execution_steps'
    )
    op.drop_table('execution_steps')
    op.drop_index(op.f('ix_executions_task_id'), table_name='executions')
    op.drop_table('executions')
