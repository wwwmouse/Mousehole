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

SKILL_DESIGN_SYSTEM = (
    "你是 mousehole 的技能设计师，负责把一次真实工作沉淀成可复用的 Skill。"
    "你只能输出用户要求的 Markdown 技能卡，不要输出解释或额外客套；"
    "不要编造当前对话中没有依据的步骤，信息不足时先提出一个具体问题。"
    "输出使用简体中文。"
)

SKILL_DESIGN_INSTRUCTION = """请把当前 Task 的工作提炼成一个可复用的 Skill。只输出下面这个 Markdown 结构（四个二级标题缺一不可，不要加代码围栏、前言或结尾）：

## 名称
不超过 20 字，动宾短语，例如“技术方案评审”。

## 描述
1–2 句话：用于【场景】，解决【问题】，产出【结果】。

## 指令
写给执行该 Skill 的模型的任务说明，必须具体、可照做，按以下结构组织：
- 输入：需要用户提供什么资料/信息；
- 步骤：3–8 条编号步骤，说明先做什么、如何分析、如何组织；
- 约束：不能做什么（不编造、不引入资料外事实、不输出无关内容）；
- 输出：最终产出的结构、格式与长度；
- 异常：资料不足/格式不支持时如何明确说明。

## System Prompt
一段系统提示：定义角色、专业范围、语气、输出语言与边界；强调忠实于资料、不编造。

补充要求：
- 必须泛化：不要写当前 Task 的专有事实或一次性内容，要写成以后可复用的流程；
- 如果当前对话不足以还原流程，只输出一行“需要补充：……”并向用户提问，不要编造；
- 不要调用工具，不要保存成果。"""

SKILL_DESIGN_TEMPLATE = """## 任务
{title}

{description}

## 资料
{context}

## 输出要求
{instruction}"""

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
    "skill_design": SkillDefinition(
        id="skill_design",
        name="流程沉淀",
        description="把一次任务或对话提炼成可复制到新建 Skill 界面的 Markdown 技能卡。",
        output_type="text/markdown",
        system_prompt=SKILL_DESIGN_SYSTEM,
        prompt_template=SKILL_DESIGN_TEMPLATE,
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
