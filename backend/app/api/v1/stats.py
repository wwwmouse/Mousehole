from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.modules.stats import service as stats_service
from app.modules.stats.schemas import StatsOverview

router = APIRouter()


@router.get("/stats/overview", response_model=StatsOverview)
def get_overview(
    db: DbSession,
    days: int = Query(default=7, ge=1, le=90),
) -> StatsOverview:
    return stats_service.overview(db, days=days)
