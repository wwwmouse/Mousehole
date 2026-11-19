from __future__ import annotations

from sqlalchemy import Uuid

# UUID v4 primary keys; SQLAlchemy renders native UUID on PostgreSQL and CHAR(32) elsewhere.
UUIDType = Uuid(as_uuid=True)
