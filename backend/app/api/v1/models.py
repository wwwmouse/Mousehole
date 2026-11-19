from __future__ import annotations

from fastapi import APIRouter

from app.modules.model import service as model_service
from app.modules.model.schemas import ModelInfo

router = APIRouter()


@router.get("", response_model=list[ModelInfo])
def list_models() -> list[ModelInfo]:
    return [ModelInfo(**item) for item in model_service.list_models()]
