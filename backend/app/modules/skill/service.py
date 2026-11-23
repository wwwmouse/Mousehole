from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.file.models import File
from app.modules.skill import registry as builtin_registry
from app.modules.skill.models import Skill, SkillFile, TaskSkill
from app.modules.task.models import Task
from app.shared.exceptions import ConflictError, NotFoundError

BUILTIN_IDS: dict[str, uuid.UUID] = {
    "multi_doc_analysis": uuid.UUID("11111111-1111-4111-8111-111111111111"),
    "content_summary": uuid.UUID("22222222-2222-4222-8222-222222222222"),
}

PROMPT_BASE = """## 任务
{title}

{description}

## 资料
{context}"""


@dataclass(frozen=True)
class ResolvedSkill:
    id: str
    name: str
    system_prompt: str
    instruction: str
    output_type: str


def ensure_builtin_skills(session: Session) -> int:
    """Seed builtin skills when the Skill Library is empty. Idempotent."""
    existing = session.scalar(select(func.count()).select_from(Skill)) or 0
    if existing:
        return 0
    definitions = {
        "multi_doc_analysis": (
            "多文档分析",
            "基于 Task 可用文件做结构化分析，产出 Markdown 报告。",
            "请输出一份结构化的 Markdown 分析报告，包含：概述、关键要点、资料之间的关系或差异、结论与建议、引用的资料清单。只使用提供的资料，引用时标明文件名。",
        ),
        "content_summary": (
            "内容摘要",
            "对 Task 可用文件做简洁总结，产出 Markdown 摘要。",
            "请输出一份 Markdown 总结，包含：一句话结论、核心要点（不超过 8 条）、资料清单。只使用提供的资料，简洁、不编造。",
        ),
    }
    created = 0
    for code, (name, description, instruction) in definitions.items():
        skill = Skill(
            id=BUILTIN_IDS[code],
            code=code,
            name=name,
            description=description,
            system_prompt=builtin_registry.ANALYSIS_SYSTEM
            if code == "multi_doc_analysis"
            else builtin_registry.SUMMARY_SYSTEM,
            instruction=instruction,
            output_type="text/markdown",
            is_builtin=True,
        )
        session.add(skill)
        created += 1
    session.commit()
    return created


def _to_resolved(skill: Skill) -> ResolvedSkill:
    return ResolvedSkill(
        id=str(skill.id),
        name=skill.name,
        system_prompt=skill.system_prompt,
        instruction=skill.instruction,
        output_type=skill.output_type,
    )


def list_skills(session: Session) -> list[Skill]:
    return list(
        session.scalars(
            select(Skill).order_by(Skill.is_builtin.desc(), Skill.created_at)
        )
    )


def _find_by_id_or_code(session: Session, skill_id: str) -> Skill | None:
    try:
        parsed = uuid.UUID(skill_id)
    except (ValueError, AttributeError):
        parsed = None
    if parsed is not None:
        skill = session.get(Skill, parsed)
        if skill is not None:
            return skill
    return session.scalars(select(Skill).where(Skill.code == skill_id)).first()


def get_skill(session: Session, skill_id: str) -> Skill:
    skill = _find_by_id_or_code(session, skill_id)
    if skill is None:
        raise NotFoundError("Skill 不存在", details={"skill_id": skill_id})
    return skill


BUILTIN_INSTRUCTIONS: dict[str, str] = {
    "multi_doc_analysis": (
        "请输出一份结构化的 Markdown 分析报告，包含概述、关键要点、"
        "资料之间的关系或差异、结论与建议、引用的资料清单。只使用提供的资料，引用时标明文件名。"
    ),
    "content_summary": (
        "请输出一份 Markdown 总结，包含一句话结论、核心要点（不超过 8 条）、"
        "资料清单。只使用提供的资料，简洁、不编造。"
    ),
}


def _builtin_resolved(code: str) -> ResolvedSkill:
    definition = builtin_registry.SKILLS.get(code)
    if definition is None:
        raise NotFoundError("Skill 不存在", details={"skill_id": code})
    return ResolvedSkill(
        id=definition.id,
        name=definition.name,
        system_prompt=definition.system_prompt,
        instruction=BUILTIN_INSTRUCTIONS.get(code, "请输出结构化的 Markdown 内容。"),
        output_type=definition.output_type,
    )


def resolve_skill(session: Session, skill_id: str | None) -> ResolvedSkill:
    """Resolve a skill for execution; fall back to library default / builtin."""
    if skill_id:
        try:
            return _to_resolved(get_skill(session, skill_id))
        except NotFoundError:
            return _builtin_resolved(skill_id)
    skill = session.scalars(
        select(Skill).order_by(Skill.is_builtin.desc(), Skill.created_at)
    ).first()
    if skill is not None:
        return _to_resolved(skill)
    return _builtin_resolved(builtin_registry.DEFAULT_SKILL_ID)


def render_messages(
    skill: ResolvedSkill, task: Task, context_text: str
) -> list[dict[str, str]]:
    description = task.description.strip() if task.description else "（无额外说明）"
    user_content = PROMPT_BASE.format(
        title=task.title,
        description=description,
        context=context_text,
    )
    instruction = skill.instruction.strip()
    if instruction:
        user_content += "\n\n## 输出要求\n" + instruction
    return [
        {"role": "system", "content": skill.system_prompt},
        {"role": "user", "content": user_content},
    ]


def create_skill(
    session: Session,
    *,
    name: str,
    description: str | None,
    instruction: str,
    system_prompt: str | None = None,
) -> Skill:
    exists = session.scalars(select(Skill).where(Skill.name == name)).first()
    if exists is not None:
        raise ConflictError("同名 Skill 已存在", details={"name": name})
    skill = Skill(
        name=name,
        description=description,
        instruction=instruction,
        system_prompt=system_prompt or "",
        is_builtin=False,
    )
    session.add(skill)
    session.flush()
    return skill


def update_skill(
    session: Session,
    skill: Skill,
    *,
    name: str | None = None,
    description: str | None = None,
    instruction: str | None = None,
    system_prompt: str | None = None,
) -> Skill:
    if name is not None and name != skill.name:
        exists = session.scalars(select(Skill).where(Skill.name == name)).first()
        if exists is not None:
            raise ConflictError("同名 Skill 已存在", details={"name": name})
        skill.name = name
    if description is not None:
        skill.description = description
    if instruction is not None:
        skill.instruction = instruction
    if system_prompt is not None:
        skill.system_prompt = system_prompt
    session.flush()
    return skill


def delete_skill(session: Session, skill: Skill) -> None:
    # Keep execution snapshots; remove Task references first.
    for link in session.scalars(
        select(TaskSkill).where(TaskSkill.skill_id == skill.id)
    ):
        session.delete(link)
    session.delete(skill)
    session.flush()


# --- Skill assets (files / folders) --------------------------------------


def list_skill_files(
    session: Session, skill_id: uuid.UUID
) -> list[tuple[SkillFile, File]]:
    stmt = (
        select(SkillFile, File)
        .join(File, File.id == SkillFile.file_id)
        .where(SkillFile.skill_id == skill_id)
        .order_by(SkillFile.path, File.filename)
    )
    return [(link, file_row) for link, file_row in session.execute(stmt)]


def add_skill_file(
    session: Session, skill: Skill, file: File, path: str | None = None
) -> SkillFile:
    existing = session.get(SkillFile, (skill.id, file.id))
    if existing is not None:
        if path:
            existing.path = path
        session.flush()
        return existing
    link = SkillFile(skill_id=skill.id, file_id=file.id, path=path)
    session.add(link)
    session.flush()
    return link


def remove_skill_file(
    session: Session, skill_id: uuid.UUID, file_id: uuid.UUID
) -> None:
    link = session.get(SkillFile, (skill_id, file_id))
    if link is None:
        raise NotFoundError("Skill 未关联该文件")
    session.delete(link)
    session.flush()


def get_skill_file(session: Session, skill_id: uuid.UUID, file_id: uuid.UUID) -> File:
    link = session.get(SkillFile, (skill_id, file_id))
    if link is None:
        raise NotFoundError("Skill 未关联该文件")
    file_row = session.get(File, file_id)
    if file_row is None:
        raise NotFoundError("文件不存在")
    return file_row


# --- Task ↔ Skill references --------------------------------------------


def list_task_skills(session: Session, task_id: uuid.UUID) -> list[Skill]:
    stmt = (
        select(Skill)
        .join(TaskSkill, TaskSkill.skill_id == Skill.id)
        .where(TaskSkill.task_id == task_id)
        .order_by(TaskSkill.created_at)
    )
    return list(session.scalars(stmt))


def add_task_skill(session: Session, task: Task, skill: Skill) -> TaskSkill:
    existing = session.scalars(
        select(TaskSkill).where(
            TaskSkill.task_id == task.id, TaskSkill.skill_id == skill.id
        )
    ).first()
    if existing is not None:
        return existing
    link = TaskSkill(task_id=task.id, skill_id=skill.id)
    session.add(link)
    session.flush()
    return link


def remove_task_skill(
    session: Session, task_id: uuid.UUID, skill_id: uuid.UUID
) -> None:
    link = session.scalars(
        select(TaskSkill).where(
            TaskSkill.task_id == task_id, TaskSkill.skill_id == skill_id
        )
    ).first()
    if link is None:
        raise NotFoundError("该 Skill 未被 Task 引用")
    session.delete(link)
    session.flush()
