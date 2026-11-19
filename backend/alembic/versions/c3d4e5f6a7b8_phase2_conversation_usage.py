"""phase2 conversation and usage

Revision ID: c3d4e5f6a7b8
Revises: 282f77031316
Create Date: 2026-11-19 23:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '282f77031316'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tasks',
        sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        'conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
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
            ['task_id'],
            ['tasks.id'],
            name=op.f('fk_conversations_task_id_tasks'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations')),
        sa.UniqueConstraint('task_id', name='conversation_task_unique'),
    )
    op.create_index(
        op.f('ix_conversations_task_id'), 'conversations', ['task_id'], unique=False
    )
    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')",
            name=op.f('ck_messages_message_role_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['conversation_id'],
            ['conversations.id'],
            name=op.f('fk_messages_conversation_id_conversations'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
        sa.UniqueConstraint(
            'conversation_id', 'sequence', name='message_sequence_unique'
        ),
    )
    op.create_index(
        op.f('ix_messages_conversation_id'),
        'messages',
        ['conversation_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_conversations_task_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_column('tasks', 'usage')
