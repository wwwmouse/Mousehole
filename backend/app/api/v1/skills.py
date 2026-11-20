from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.skill import registry as skill_registry

router = APIRouter()


class SkillInfo(BaseModel):
    id: str
    name: str
    description: str
    output_type: str


@router.get("", response_model=list[SkillInfo])
def list_skills() -> list[SkillInfo]:
    return [
        SkillInfo(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            output_type=skill.output_type,
        )
        for skill in skill_registry.list_skills()
    ]
