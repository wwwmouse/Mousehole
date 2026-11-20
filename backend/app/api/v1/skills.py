from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.api.deps import DbSession
from app.modules.skill import service as skill_service
from app.modules.file import service as file_service
from app.modules.skill.schemas import (
    SkillCreate,
    SkillFileAdd,
    SkillFileRead,
    SkillRead,
    SkillUpdate,
    TaskSkillAdd,
)
from app.modules.task import service as task_service

router = APIRouter()


@router.get("/skills", response_model=list[SkillRead])
def list_skills(db: DbSession) -> list[SkillRead]:
    return [
        SkillRead.model_validate(skill) for skill in skill_service.list_skills(db)
    ]


@router.post("/skills", response_model=SkillRead, status_code=201)
def create_skill(payload: SkillCreate, db: DbSession) -> SkillRead:
    skill = skill_service.create_skill(
        db,
        name=payload.name.strip(),
        description=payload.description,
        instruction=payload.instruction,
        system_prompt=payload.system_prompt,
    )
    db.commit()
    db.refresh(skill)
    return SkillRead.model_validate(skill)


@router.patch("/skills/{skill_id}", response_model=SkillRead)
def update_skill(
    skill_id: uuid.UUID, payload: SkillUpdate, db: DbSession
) -> SkillRead:
    skill = skill_service.get_skill(db, str(skill_id))
    updated = skill_service.update_skill(
        db,
        skill,
        name=payload.name.strip() if payload.name else None,
        description=payload.description,
        instruction=payload.instruction,
        system_prompt=payload.system_prompt,
    )
    db.commit()
    db.refresh(updated)
    return SkillRead.model_validate(updated)


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: uuid.UUID, db: DbSession) -> Response:
    skill = skill_service.get_skill(db, str(skill_id))
    skill_service.delete_skill(db, skill)
    db.commit()
    return Response(status_code=204)


# --- Skill assets (files / folders) --------------------------------------


@router.get("/skills/{skill_id}/files", response_model=list[SkillFileRead])
def list_skill_files(skill_id: uuid.UUID, db: DbSession) -> list[SkillFileRead]:
    skill = skill_service.get_skill(db, str(skill_id))
    return [
        SkillFileRead(
            file_id=file_row.id,
            filename=file_row.filename,
            file_type=file_row.file_type,
            size=file_row.size,
            path=link.path,
            created_at=link.created_at,
        )
        for link, file_row in skill_service.list_skill_files(db, skill.id)
    ]


@router.post(
    "/skills/{skill_id}/files", response_model=SkillFileRead, status_code=201
)
def add_skill_file(
    skill_id: uuid.UUID, payload: SkillFileAdd, db: DbSession
) -> SkillFileRead:
    skill = skill_service.get_skill(db, str(skill_id))
    file_row = file_service.get_file(db, payload.file_id)
    link = skill_service.add_skill_file(db, skill, file_row, payload.path)
    db.commit()
    return SkillFileRead(
        file_id=file_row.id,
        filename=file_row.filename,
        file_type=file_row.file_type,
        size=file_row.size,
        path=link.path,
        created_at=link.created_at,
    )


@router.delete("/skills/{skill_id}/files/{file_id}", status_code=204)
def remove_skill_file(
    skill_id: uuid.UUID, file_id: uuid.UUID, db: DbSession
) -> Response:
    skill = skill_service.get_skill(db, str(skill_id))
    skill_service.remove_skill_file(db, skill.id, file_id)
    db.commit()
    return Response(status_code=204)


# --- Task ↔ Skill references --------------------------------------------


@router.get("/tasks/{task_id}/skills", response_model=list[SkillRead])
def list_task_skills(task_id: uuid.UUID, db: DbSession) -> list[SkillRead]:
    task_service.get_task(db, task_id)
    return [
        SkillRead.model_validate(skill)
        for skill in skill_service.list_task_skills(db, task_id)
    ]


@router.post("/tasks/{task_id}/skills", response_model=SkillRead, status_code=201)
def add_task_skill(
    task_id: uuid.UUID, payload: TaskSkillAdd, db: DbSession
) -> SkillRead:
    task = task_service.get_task(db, task_id)
    skill = skill_service.get_skill(db, str(payload.skill_id))
    skill_service.add_task_skill(db, task, skill)
    db.commit()
    return SkillRead.model_validate(skill)


@router.delete("/tasks/{task_id}/skills/{skill_id}", status_code=204)
def remove_task_skill(
    task_id: uuid.UUID, skill_id: uuid.UUID, db: DbSession
) -> Response:
    task_service.get_task(db, task_id)
    skill_service.remove_task_skill(db, task_id, skill_id)
    db.commit()
    return Response(status_code=204)
