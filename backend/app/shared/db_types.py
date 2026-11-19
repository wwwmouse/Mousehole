from __future__ import annotations

from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB

# UUID v4 primary keys; SQLAlchemy renders native UUID on PostgreSQL and CHAR(32) elsewhere.
UUIDType = Uuid(as_uuid=True)

# Token usage payloads: JSONB on PostgreSQL, generic JSON on SQLite (tests).
UsageJSON = JSON().with_variant(JSONB(), "postgresql")
