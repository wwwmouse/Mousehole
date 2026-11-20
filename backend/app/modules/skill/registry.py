from __future__ import annotations

from dataclasses import dataclass

from app.modules.task.models import Task
from app.shared.exceptions import NotFoundError

DEFAULT_SKILL_ID = "multi_doc_analysis"


@dataclass(frozen=True)
class SkillDefinition:
    """Code-level skill definition.

    MVP keeps skills in code (no user-defined skill management yet); the
    Execution records skill_id/skill_name so the capability is traceable and
    can later be backed by a database entity without changing the pipeline.
    """

    id: str
    name: str
    description: str
    output_type: str
    system_prompt: str
    prompt_template: str


ANALYSIS_SYSTEM = (
    "你是 mousehole 的分析助手，运行在用户本地的个人 AI 工作空间中。"
    "请严格基于提供的资料完成任务，不要编造事实；不确定时明确说明。"
    "输出使用简体中文 Markdown。"
)

SUMMARY_SYSTEM = (
    "你是 mousehole 的文档总结助手。请基于给定资料输出简洁、忠实的总结，"
    "保留关键事实与结论，不要编造资料中没有的内容。输出使用简体中文 Markdown。"
)

ANALYSIS_TEMPLATE = """## 任务
{title}

{description}

## 资料
{context}

## 输出要求
请输出一份结构化的 Markdown 分析报告，包含：
1. 概述
2. 关键要点（分条）
3. 资料之间的关系或差异
4. 结论与建议
5. 引用的资料清单（文件名）

要求：只使用上述资料中的信息；引用资料时标明文件名。"""

SUMMARY_TEMPLATE = """## 任务
{title}

{description}

## 资料
{context}

## 输出要求
请输出一份 Markdown 总结，包含：
1. 一句话结论
2. 核心要点（不超过 8 条）
3. 资料清单（文件名）

要求：只使用上述资料中的信息，简洁、不编造。"""


SKILLS: dict[str, SkillDefinition] = {
    "multi_doc_analysis": SkillDefinition(
        id="multi_doc_analysis",
        name="多文档分析",
        description="基于 Task 可用文件做结构化分析，产出 Markdown 报告。",
        output_type="text/markdown",
        system_prompt=ANALYSIS_SYSTEM,
        prompt_template=ANALYSIS_TEMPLATE,
    ),
    "content_summary": SkillDefinition(
        id="content_summary",
        name="内容摘要",
        description="对 Task 可用文件做简洁总结，产出 Markdown 摘要。",
        output_type="text/markdown",
        system_prompt=SUMMARY_SYSTEM,
        prompt_template=SUMMARY_TEMPLATE,
    ),
}


def list_skills() -> list[SkillDefinition]:
    return list(SKILLS.values())


def get_skill(skill_id: str | None = None) -> SkillDefinition:
    if not skill_id:
        return SKILLS[DEFAULT_SKILL_ID]
    skill = SKILLS.get(skill_id)
    if skill is None:
        raise NotFoundError("未知的 Skill", details={"skill_id": skill_id})
    return skill


def render_messages(
    skill: SkillDefinition, task: Task, context_text: str
) -> list[dict[str, str]]:
    description = task.description.strip() if task.description else "（无额外说明）"
    user_content = skill.prompt_template.format(
        title=task.title,
        description=description,
        context=context_text,
    )
    return [
        {"role": "system", "content": skill.system_prompt},
        {"role": "user", "content": user_content},
    ]
