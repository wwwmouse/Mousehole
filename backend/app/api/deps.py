from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.session import (
    get_db,
    get_session_factory as _get_session_factory,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_db_factory() -> sessionmaker[Session]:
    """Factory for sessions used outside the request scope (SSE generators)."""
    return _get_session_factory()


DbFactory = Annotated[sessionmaker[Session], Depends(get_db_factory)]
