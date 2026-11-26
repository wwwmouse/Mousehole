# 模块职责：集中管理 Chat 的系统提示、模式提示和消息组装。
# 对外函数：
# - build_messages(task, history, file_context=None, skill=None, *, include_tools=False, mode=MODE_WORK, include_reasoning=False)：组装发给模型的 system + 历史消息。
from __future__ import annotations

from typing import Any

from app.modules.conversation.tools import tool_prompt

SYSTEM_PROMPT = (
    "你是 mousehole 的 AI 助手，运行在用户本地的个人 AI 工作空间中。"
    "请基于用户提供的任务目标和对话上下文，给出准确、简洁、可执行的回答。"
    "不要编造事实；不确定时明确说明。"
    "严格只使用资料原文：不要添加资料中不存在的警告、免责声明、隐私提示、"
    "背景信息或数字；如果必须推断，明确标注「推断」。"
    "资料按最近更新时间排序，回答时优先参考最近更新的资料。"
)

CITATION_PROMPT = (
    "资料中可能出现「--- 第 N 页 ---」页码标记。"
    "当回答使用该资料的事实/结论时，在对应句子末尾用 [文件名 p.N] 标注来源，"
    "例如 [学生手册.pdf p.37]；只能引用本轮资料中真实出现的文件名和页码，"
    "没有页码依据的事实不要编造引用。"
)

# 阶段 5 H4：用显式的「对话 / 工作」两种模式替代工具开关和关键词猜测。
# 工作模式下由模型自行决定是否调用工具。
MODE_CHAT = "chat"
MODE_WORK = "work"

MODE_CHAT_PROMPT = (
    "当前为【对话模式】：本轮不提供任何工具调用能力，不能读取文件、保存成果或启动执行。"
    "即使历史对话中使用过工具，本轮也不能调用。已注入的资料内容仍可直接阅读和引用；"
    "如果用户要求读取文件、保存成果或启动执行，请说明需要切换到【工作模式】后再操作。"
)
MODE_WORK_PROMPT = (
    "当前为【工作模式】：本轮已提供受控工具（read_task_files / read_task_file / "
    "save_artifact / create_execution），请根据用户意图决定是否调用。"
    "当用户要求保存/生成成果、读取任务资料或启动多文档分析时，必须调用对应工具，"
    "不要只在聊天里输出内容就结束；普通问答直接回答，不要调用不必要的工具。"
    "历史对话中任何“没有工具能力/只能读取/不能保存”的说法均已过时，"
    "一律以本轮系统提示为准。"
)

# 这段提醒追加在历史消息之后：长对话里旧回答常声称“不能写文件”，
# 会压过系统提示中的工具说明。
MODE_WORK_REMINDER = (
    "【工作模式工具提醒】本轮工具已就绪：save_artifact 会把 Markdown 内容真正"
    "保存为当前 Task 的成果（后端落库并生成版本），你不需要也不能直接写本地文件。"
    "历史中关于“没有工具/只能读取/不能保存”的说法不适用于本轮；"
    "用户要求生成或保存 md 文档时必须立即调用 save_artifact。"
)


def build_messages(
    task: Any,
    history: list[Any],
    file_context: str | None = None,
    skill: Any = None,
    *,
    include_tools: bool = False,
    mode: str = MODE_WORK,
    include_reasoning: bool = False,
) -> list[dict[str, Any]]:
    context: list[str] = []
    if task.title:
        context.append(f"当前 Task：{task.title}")
    if task.description:
        context.append(f"Task 说明：{task.description}")
    if skill is not None:
        context.append(
            f"本次对话使用 Skill「{skill.name}」，请遵循其要求：\n{skill.instruction}"
        )
    system = SYSTEM_PROMPT
    if mode == MODE_CHAT:
        system = system + "\n\n" + MODE_CHAT_PROMPT
    elif include_tools:
        # 只有工具 pre-pass 才携带工具说明；最终流式回答没有 tools 参数，
        # 因此不能让模型看到工具说明。
        system = system + "\n\n" + MODE_WORK_PROMPT + "\n\n" + tool_prompt()
    if skill is not None and skill.system_prompt:
        system = skill.system_prompt + "\n\n" + system
    if context:
        system = system + "\n\n" + "\n".join(context)
    if file_context:
        system = system + "\n\n" + file_context
        if "--- 第 " in file_context:
            system = system + "\n\n" + CITATION_PROMPT

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for item in history:
        if item.role not in ("user", "assistant") or not item.content:
            continue
        message: dict[str, Any] = {"role": item.role, "content": item.content}
        if item.role == "assistant" and include_reasoning:
            # DeepSeek V4 思考模式要求：带工具参数的请求必须回传历史
            # reasoning_content 字段。
            reasoning = (item.message_metadata or {}).get("reasoning_content")
            if reasoning:
                message["reasoning_content"] = reasoning
        messages.append(message)
    if include_tools and mode == MODE_WORK:
        messages.append({"role": "system", "content": MODE_WORK_REMINDER})
    return messages
