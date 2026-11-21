"""cleanup legacy temporary file overrides

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-11-21 18:00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Temporary files used to be included in the Task context. They are now
    # per-message attachments; drop any persisted include/exclude overrides.
    op.execute(
        "DELETE FROM task_file_overrides "
        "WHERE file_id IN (SELECT id FROM files WHERE is_temporary = true)"
    )


def downgrade() -> None:
    pass
