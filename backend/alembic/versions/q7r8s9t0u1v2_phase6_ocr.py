"""phase 6 OCR pages and jobs

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-11-26 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'q7r8s9t0u1v2'
down_revision: Union[str, None] = 'p6q7r8s9t0u1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'file_pages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('file_id', sa.Uuid(), nullable=False),
        sa.Column('page_no', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('text_source', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "text_source IN ('native', 'ocr')",
            name='file_page_text_source_valid',
        ),
        sa.ForeignKeyConstraint(
            ['file_id'], ['files.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_id', 'page_no', name='file_page_unique'),
    )
    op.create_index(
        'ix_file_pages_file_id', 'file_pages', ['file_id']
    )

    op.create_table(
        'ocr_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('file_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('route', sa.String(length=20), nullable=False),
        sa.Column('total_pages', sa.Integer(), nullable=False),
        sa.Column('processed_pages', sa.Integer(), nullable=False),
        sa.Column('image_coverage', sa.Float(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name='ocr_job_status_valid',
        ),
        sa.CheckConstraint(
            "route IN ('text', 'ocr', 'mixed')",
            name='ocr_job_route_valid',
        ),
        sa.ForeignKeyConstraint(
            ['file_id'], ['files.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ocr_jobs_file_id', 'ocr_jobs', ['file_id'])


def downgrade() -> None:
    op.drop_index('ix_ocr_jobs_file_id', table_name='ocr_jobs')
    op.drop_table('ocr_jobs')
    op.drop_index('ix_file_pages_file_id', table_name='file_pages')
    op.drop_table('file_pages')
