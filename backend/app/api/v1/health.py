from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter()


@router.get("/health")
def health(db: DbSession) -> dict:
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - depends on runtime environment
        database = "unavailable"
    return {"status": "ok", "app": "mousehole", "version": "0.1.0", "database": database}
