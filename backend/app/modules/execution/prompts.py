from __future__ import annotations

from app.modules.task.models import Task

SUMMARY_SYSTEM = (
    "你是 mousehole 的文档摘要助手。请忠实提炼给定资料的关键信息，"
    "保留事实、数字、结论与来源文件名；不要编造资料中没有的内容。"
)

ANALYSIS_SYSTEM = (
    "你是 mousehole 的分析助手，运行在用户本地的个人 AI 工作空间中。"
    "请严格基于提供的资料完成任务，不要编造事实；不确定时明确说明。"
    "输出使用简体中文 Markdown。"
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


def summary_messages(filename: str, text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": (
                f"请为文件「{filename}」生成一份简洁摘要（不超过 500 字），"
                f"保留关键事实与结论：\n\n{text}"
            ),
        },
    ]


def analysis_messages(task: Task, context_text: str) -> list[dict[str, str]]:
    description = task.description.strip() if task.description else "（无额外说明）"
    content = ANALYSIS_TEMPLATE.format(
        title=task.title,
        description=description,
        context=context_text,
    )
    return [
        {"role": "system", "content": ANALYSIS_SYSTEM},
        {"role": "user", "content": content},
    ]
