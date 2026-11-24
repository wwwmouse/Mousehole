from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import DbFactory, DbSession
from app.core.config import get_settings
from app.modules.artifact import repository as artifact_repository
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation import service as conversation_service
from app.modules.conversation import tools as chat_tools
from app.modules.conversation.chat_context import (
    CHAT_FILE_BUDGET_TOKENS,
    build_file_context_async,
)
from app.modules.conversation.tools import tool_prompt
from app.modules.conversation.models import Conversation, Message
from app.modules.conversation.schemas import (
    ChatRequest,
    ConversationContextRead,
    ConversationContextUpdate,
    TaskMessagesRead,
)
from app.modules.model import service as model_service
from app.modules.skill import service as skill_service
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.defaults import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from app.shared.usage import add_usage

router = APIRouter()

logger = logging.getLogger("mousehole.chat")

MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = (
    "你是 mousehole 的 AI 助手，运行在用户本地的个人 AI 工作空间中。"
    "请基于用户提供的任务目标和对话上下文，给出准确、简洁、可执行的回答。"
    "不要编造事实；不确定时明确说明。"
    "严格只使用资料原文：不要添加资料中不存在的警告、免责声明、隐私提示、"
    "背景信息或数字；如果必须推断，明确标注「推断」。"
    "资料按最近更新时间排序，回答时优先参考最近更新的资料。"
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


def _looks_like_tool_markup(text: str) -> bool:
    tokens = ("<|DSML|", "<tool_call", "</tool_call>", "｜｜DSML｜｜")
    return any(token in text for token in tokens)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_with_heartbeat(stream) -> AsyncIterator[dict]:
    """逐个产出模型事件；模型静默超过 2 秒时发送思考心跳。"""
    iterator = stream.__aiter__()
    pending = asyncio.ensure_future(iterator.__anext__())
    try:
        while True:
            done_set, _ = await asyncio.wait({pending}, timeout=2.0)
            if not done_set:
                yield {"type": "thinking"}
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            yield event
            pending = asyncio.ensure_future(iterator.__anext__())
    finally:
        if not pending.done():
            pending.cancel()


def _build_messages(
    task: Task,
    history: list[Message],
    file_context: str | None = None,
    skill=None,
    *,
    include_tools: bool = False,
    mode: str = MODE_WORK,
    include_reasoning: bool = False,
) -> list[dict[str, str]]:
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

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history:
        if item.role not in ("user", "assistant") or not item.content:
            continue
        message: dict[str, str] = {"role": item.role, "content": item.content}
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


@router.get("/{task_id}/messages", response_model=TaskMessagesRead)
def list_messages(task_id: uuid.UUID, db: DbSession) -> TaskMessagesRead:
    return conversation_service.list_task_messages(db, task_id)


@router.patch("/{task_id}/messages/context", response_model=ConversationContextRead)
def update_context(
    task_id: uuid.UUID,
    payload: ConversationContextUpdate,
    db: DbSession,
) -> ConversationContextRead:
    """清空或恢复聊天上下文边界。

    消息永不删除；清空只是让旧消息不再发送给模型。
    """
    task = task_service.get_task(db, task_id)
    conversation = conversation_service.set_context_cleared(
        db, task, cleared=payload.cleared
    )
    return ConversationContextRead(
        task_id=task.id,
        conversation_id=conversation.id,
        context_cleared=conversation.context_start_sequence is not None,
        context_start_sequence=conversation.context_start_sequence,
    )


@router.post("/{task_id}/messages")
async def send_message(
    task_id: uuid.UUID,
    payload: ChatRequest,
    db: DbSession,
    factory: DbFactory,
) -> StreamingResponse:
    request_started = time.monotonic()
    task = task_service.get_task(db, task_id)
    provider, model, model_config = model_service.resolve_model(
        task.model_provider,
        task.model_name,
        payload.provider,
        payload.model,
    )
    supports_reasoning = provider == "deepseek" or "deepseek" in (
        (model_config or {}).get("base_url") or ""
    ).casefold()
    skill = (
        skill_service.resolve_skill(db, payload.skill_id)
        if payload.skill_id
        else None
    )
    conversation = conversation_service.get_or_create_conversation(db, task)
    workspace = db.get(Workspace, task.workspace_id)
    context_budget = (
        workspace.context_budget_tokens if workspace is not None else None
    ) or get_settings().default_context_budget_tokens
    file_budget = max(
        4_000, min(CHAT_FILE_BUDGET_TOKENS, context_budget - 6_000)
    )
    file_context = await build_file_context_async(
        db, task, skill, payload.file_ids, budget_tokens=file_budget
    )
    user_metadata = {
        "skill": (
            {"id": skill.id, "name": skill.name} if skill is not None else None
        ),
        # 只展示用户在本轮输入框中临时引入的文件；
        # 项目继承文件仍会进入模型上下文，但不作为本条消息的附件展示。
        "files": (
            [
                item
                for item in (file_context.files if file_context else [])
                if item.get("source") in ("task_added", "temporary")
            ]
        ),
        # H4：对话模式无工具，工作模式有工具；记录模式便于追溯。
        "mode": payload.mode,
    }
    conversation_service.append_message(
        db,
        conversation,
        role="user",
        content=payload.content,
        metadata=user_metadata,
    )
    db.commit()

    history = conversation_repository.list_messages(
        db,
        conversation.id,
        limit=get_settings().chat_history_limit,
        min_sequence=conversation.context_start_sequence,
    )
    work_mode = payload.mode == MODE_WORK
    # DeepSeek V4 思考模式：只要请求携带工具参数，所有历史助手消息都必须
    # 回传 reasoning_content 字段。旧消息可能没有保存该字段；此时对本次
    # 工具预判关闭思考模式，避免接口返回 400。
    history_missing_reasoning = any(
        item.role == "assistant"
        and not (item.message_metadata or {}).get("reasoning_content")
        for item in history
    )
    include_reasoning = (
        work_mode and supports_reasoning and not history_missing_reasoning
    )
    disable_thinking = (
        work_mode and supports_reasoning and history_missing_reasoning
    )
    messages_tools = _build_messages(
        task,
        history,
        file_context.text if file_context else None,
        skill,
        include_tools=True,
        mode=payload.mode,
        include_reasoning=include_reasoning,
    )
    messages_plain = _build_messages(
        task,
        history,
        file_context.text if file_context else None,
        skill,
        include_tools=False,
        mode=payload.mode,
    )
    conversation_id = conversation.id
    temperature = task.temperature
    max_tokens = task.max_tokens
    if temperature is None or max_tokens is None:
        if workspace is not None:
            if temperature is None:
                temperature = workspace.default_temperature
            if max_tokens is None:
                max_tokens = workspace.default_max_tokens
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    async def event_stream() -> AsyncIterator[str]:
        chunks: list[str] = []
        reasoning_chunks: list[str] = []
        usage: dict | None = None
        created_artifacts: list[str] = []
        created_executions: list[str] = []
        tool_trace: list[dict] = []
        messages_for_model: list[dict] = list(
            messages_tools if work_mode else messages_plain
        )

        try:
            yield _sse("start", {"provider": provider, "model": model, "mode": payload.mode})
            # --- 受控工具 pre-pass（非流式） ---
            # 工作模式始终提供工具，由模型决定是否调用；对话模式不会进入这里。
            tools_ok = work_mode
            try:
                for _round in range(MAX_TOOL_ROUNDS if tools_ok else 0):
                    # 非流式 pre-pass 可能较慢，用 thinking 心跳让界面知道仍在工作。
                    pending = asyncio.create_task(
                        model_service.complete_chat(
                            provider,
                            model,
                            messages_for_model,
                            tools=chat_tools.TOOL_SPECS,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            thinking=False if disable_thinking else None,
                        )
                    )
                    while True:
                        done_set, _ = await asyncio.wait({pending}, timeout=2.0)
                        if done_set:
                            result = pending.result()
                            break
                        yield _sse("thinking", {"phase": "model"})
                    usage = add_usage(usage, result.get("usage")) or usage
                    tool_calls = result.get("tool_calls") or []
                    if not tool_calls:
                    # 即使模型在这里返回了文本也忽略，最终回答统一走真正的 SSE
                    # 流式生成；工具预判只负责决定/执行工具。
                        break
                    assistant_tool_calls = []
                    parsed_calls: list[tuple[dict, dict]] = []
                    for call in tool_calls:
                        try:
                            arguments = json.loads(call.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            arguments = {}
                        parsed_calls.append((call, arguments))
                        assistant_tool_calls.append(
                            {
                                "id": call["id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": call.get("arguments") or "{}",
                                },
                            }
                        )
                    # 兼容 OpenAI 的顺序：assistant(tool_calls) 必须放在 tool 结果之前。
                    assistant_message: dict = {
                        "role": "assistant",
                        "content": result.get("content") or "",
                        "tool_calls": assistant_tool_calls,
                    }
                    reasoning = result.get("reasoning_content")
                    if reasoning:
                        # DeepSeek V4 思考模式要求下一轮回传。
                        assistant_message["reasoning_content"] = reasoning
                    messages_for_model.append(assistant_message)
                    for call, arguments in parsed_calls:
                        yield _sse(
                            "tool_call",
                            {"name": call["name"], "arguments": arguments},
                        )
                        with factory() as tool_session:
                            task_row = tool_session.get(Task, task_id)
                            outcome = await chat_tools.execute_tool(
                                tool_session,
                                task_row,
                                call["name"],
                                arguments,
                                conversation_id=conversation_id,
                            )
                        if outcome.get("artifact_id"):
                            created_artifacts.append(outcome["artifact_id"])
                        if outcome.get("execution_id"):
                            created_executions.append(outcome["execution_id"])
                        tool_trace.append(
                            {
                                "name": call["name"],
                                "ok": bool(outcome.get("ok")),
                                "summary": str(outcome.get("summary") or ""),
                            }
                        )
                        messages_for_model.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json.dumps(outcome, ensure_ascii=False),
                            }
                        )
                        yield _sse(
                            "tool_result",
                            {
                                "name": call["name"],
                                "ok": bool(outcome.get("ok")),
                                "summary": outcome.get("summary", ""),
                                "artifact_id": outcome.get("artifact_id"),
                                "execution_id": outcome.get("execution_id"),
                            },
                        )
            except Exception as exc:  # noqa: BLE001 - 工具不可用时降级为普通流式
                # 不要把整段对话判失败，但要留下可诊断的日志。
                logger.warning(
                    "tool pre-pass failed; falling back to plain chat (%s): %s",
                    exc.__class__.__name__,
                    getattr(exc, "details", None),
                )
                tools_ok = False
                messages_for_model = list(messages_plain)

            async def _clean_answer(target_messages: list[dict]) -> str | None:
                """去除工具标记的兜底回答；仅在流式结果泄漏工具文本时使用。"""
                nonlocal usage
                for _attempt in range(2):
                    outcome = await model_service.complete_chat(
                        provider,
                        model,
                        target_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    usage = add_usage(usage, outcome.get("usage")) or usage
                    candidate = (outcome.get("content") or "").strip()
                    if candidate and not _looks_like_tool_markup(candidate):
                        return candidate
                return None

            # 最终回答始终用真正的流式生成；上面的工具 pre-pass 只负责决定/执行工具，
            # 不会直接作为用户可见的回答。
            final_messages = list(messages_plain)
            if tool_trace:
                # 只保留 pre-pass 在原始对话之后追加的 assistant(tool_calls)/tool(result) 消息。
                final_messages.extend(messages_for_model[len(messages_tools):])
                final_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "请基于以上工具结果直接给出最终回答。不要再调用工具，"
                            "也不要输出任何工具调用标记（如 DSML / <tool_call>）。"
                        ),
                    }
                )

            buffer = ""
            emitted = False
            markup_detected = False
            stream = model_service.stream_chat(
                provider,
                model,
                final_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            async for event in _stream_with_heartbeat(stream):
                if event["type"] == "thinking":
                    yield _sse("thinking", {"phase": "stream"})
                    continue
                if event["type"] == "reasoning":
                    # DeepSeek 思考模式的思维链：留存给下一次带工具的请求，
                    # 绝不作为回答渲染。
                    reasoning_chunks.append(event["text"])
                    continue
                if event["type"] == "delta":
                    text = event["text"]
                    if not emitted:
                        buffer += text
                        if _looks_like_tool_markup(buffer):
                            markup_detected = True
                            break
                        if len(buffer) >= 80:
                            chunks.append(buffer)
                            yield _sse("delta", {"text": buffer})
                            emitted = True
                    else:
                        chunks.append(text)
                        yield _sse("delta", {"text": text})
                elif event["type"] == "usage":
                    usage = add_usage(usage, event["usage"]) or usage

            if markup_detected:
                chunks.clear()
                clean = await _clean_answer(final_messages)
                if clean is None:
                    yield _sse(
                        "error",
                        {
                            "code": "invalid_final_answer",
                            "message": "模型返回了无法解析的工具调用文本，请重试",
                        },
                    )
                    return
                for index in range(0, len(clean), 60):
                    piece = clean[index : index + 60]
                    chunks.append(piece)
                    yield _sse("delta", {"text": piece})
            elif not emitted and buffer:
                chunks.append(buffer)
                yield _sse("delta", {"text": buffer})
        except Exception as exc:  # noqa: BLE001 - 将 Provider 错误显式返回给客户端
            code = getattr(exc, "code", "provider_error")
            message = getattr(exc, "message", str(exc))
            yield _sse("error", {"code": code, "message": message})
            return

        content = "".join(chunks).strip()
        if not content:
            yield _sse(
                "error",
                {"code": "empty_response", "message": "模型没有返回任何内容"},
            )
            return

        try:
            with factory() as session:
                conversation_row = session.get(Conversation, conversation_id)
                task_row = session.get(Task, task_id)
                assistant = conversation_service.append_message(
                    session,
                    conversation_row,
                    role="assistant",
                    content=content,
                    usage=usage,
                    metadata={
                        "tools": tool_trace,
                        "mode": payload.mode,
                        "reasoning_content": "".join(reasoning_chunks) or None,
                        "duration_ms": int(
                            (time.monotonic() - request_started) * 1000
                        ),
                        "skill": user_metadata.get("skill"),
                        "artifacts": len(created_artifacts),
                        "executions": len(created_executions),
                    },
                )
                task_usage = conversation_service.bump_task_usage(
                    session, task_row, usage
                )
                message_id = assistant.id
                if created_artifacts:
                    artifact_repository.update_source_message(
                        session,
                        [uuid.UUID(item) for item in created_artifacts],
                        message_id,
                    )
                session.commit()
        except Exception as exc:  # noqa: BLE001 - 保存失败必须显式报错
            yield _sse(
                "error",
                {
                    "code": "persist_failed",
                    "message": f"回复已生成但保存失败：{exc.__class__.__name__}",
                },
            )
            return

        yield _sse(
            "done",
            {
                "message_id": str(message_id),
                "usage": usage,
                "task_usage": task_usage,
                "tools_enabled": tools_ok,
                "mode": payload.mode,
                "artifacts": created_artifacts,
                "executions": created_executions,
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
