# 模块职责：编排 Chat 的一轮对话：准备上下文、工具 pre-pass、流式回答与消息落库。
# 对外函数：
# - prepare_chat_turn(session, task_id, payload)：请求开始前完成同步准备并写入 user message。
# - run_chat_turn(plan, factory)：产出 start/thinking/delta/tool_call/tool_result/done/error 结构化事件。
# 对外类型：
# - ChatTurnEvent：API 层将其转换为 SSE 帧。
# - ChatTurnPlan：一轮对话已准备好的不可变输入。
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.artifact import service as artifact_service
from app.modules.conversation import service as conversation_service
from app.modules.conversation import tools as chat_tools
from app.modules.conversation.chat_context import (
    CHAT_FILE_BUDGET_TOKENS,
    ChatFileContext,
    build_file_context_async,
)
from app.modules.conversation.chat_prompts import MODE_WORK, build_messages
from app.modules.conversation.citations import extract_citations
from app.modules.conversation.schemas import ChatRequest
from app.modules.model import service as model_service
from app.modules.skill import service as skill_service
from app.modules.task import service as task_service
from app.modules.workspace import service as workspace_service
from app.shared.defaults import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from app.shared.usage import add_usage

logger = logging.getLogger("mousehole.chat")

MAX_TOOL_ROUNDS = 4


@dataclass(frozen=True, slots=True)
class ChatTurnEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChatTurnPlan:
    task_id: uuid.UUID
    conversation_id: uuid.UUID
    provider: str
    model: str
    mode: str
    work_mode: bool
    file_context: ChatFileContext | None
    messages_tools: list[dict[str, Any]]
    messages_plain: list[dict[str, Any]]
    temperature: float
    max_tokens: int
    disable_thinking: bool
    skill_meta: dict | None
    request_started: float


def _looks_like_tool_markup(text: str) -> bool:
    tokens = ("<|DSML|", "<tool_call", "</tool_call>", "｜｜DSML｜｜")
    return any(token in text for token in tokens)


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


async def prepare_chat_turn(
    session: Session, task_id: uuid.UUID, payload: ChatRequest
) -> ChatTurnPlan:
    """请求开始前完成准备；失败在这里抛出，由 API 返回正常的 HTTP 错误。"""
    request_started = time.monotonic()
    task = task_service.get_task(session, task_id)
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
        skill_service.resolve_skill(session, payload.skill_id)
        if payload.skill_id
        else None
    )
    conversation = conversation_service.get_or_create_conversation(session, task)
    workspace = workspace_service.get_workspace(session, task.workspace_id)
    context_budget = (
        workspace.context_budget_tokens
        or get_settings().default_context_budget_tokens
    )
    file_budget = max(
        4_000, min(CHAT_FILE_BUDGET_TOKENS, context_budget - 6_000)
    )
    file_context = await build_file_context_async(
        session, task, skill, payload.file_ids, budget_tokens=file_budget
    )
    skill_meta = (
        {"id": skill.id, "name": skill.name} if skill is not None else None
    )
    # 只展示用户在本轮输入框中临时引入的文件；项目继承文件仍会进入模型上下文，
    # 但不作为本条消息的附件展示。
    user_metadata = {
        "skill": skill_meta,
        "files": [
            item
            for item in (file_context.files if file_context else [])
            if item.get("source") in ("task_added", "temporary")
        ],
        "mode": payload.mode,
    }
    conversation_service.append_message(
        session,
        conversation,
        role="user",
        content=payload.content,
        metadata=user_metadata,
    )
    session.commit()

    history = conversation_service.list_recent_messages(
        session,
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
    messages_tools = build_messages(
        task,
        history,
        file_context.text if file_context else None,
        skill,
        include_tools=True,
        mode=payload.mode,
        include_reasoning=include_reasoning,
    )
    messages_plain = build_messages(
        task,
        history,
        file_context.text if file_context else None,
        skill,
        include_tools=False,
        mode=payload.mode,
    )
    temperature = task.temperature
    max_tokens = task.max_tokens
    if temperature is None:
        temperature = workspace.default_temperature
    if max_tokens is None:
        max_tokens = workspace.default_max_tokens
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    return ChatTurnPlan(
        task_id=task_id,
        conversation_id=conversation.id,
        provider=provider,
        model=model,
        mode=payload.mode,
        work_mode=work_mode,
        file_context=file_context,
        messages_tools=messages_tools,
        messages_plain=messages_plain,
        temperature=temperature,
        max_tokens=max_tokens,
        disable_thinking=disable_thinking,
        skill_meta=skill_meta,
        request_started=request_started,
    )


async def run_chat_turn(
    plan: ChatTurnPlan, factory: sessionmaker[Session]
) -> AsyncIterator[ChatTurnEvent]:
    chunks: list[str] = []
    reasoning_chunks: list[str] = []
    usage: dict | None = None
    created_artifacts: list[str] = []
    created_executions: list[str] = []
    tool_trace: list[dict] = []
    tools_ok = plan.work_mode
    messages_for_model: list[dict[str, Any]] = list(
        plan.messages_tools if plan.work_mode else plan.messages_plain
    )

    try:
        yield ChatTurnEvent(
            "start",
            {
                "provider": plan.provider,
                "model": plan.model,
                "mode": plan.mode,
            },
        )
        # --- 受控工具 pre-pass（非流式） ---
        # 工作模式始终提供工具，由模型决定是否调用；对话模式不会进入这里。
        try:
            for _round in range(MAX_TOOL_ROUNDS if tools_ok else 0):
                pending = asyncio.create_task(
                    model_service.complete_chat(
                        plan.provider,
                        plan.model,
                        messages_for_model,
                        tools=chat_tools.TOOL_SPECS,
                        temperature=plan.temperature,
                        max_tokens=plan.max_tokens,
                        thinking=False if plan.disable_thinking else None,
                    )
                )
                while True:
                    done_set, _ = await asyncio.wait({pending}, timeout=2.0)
                    if done_set:
                        result = pending.result()
                        break
                    yield ChatTurnEvent("thinking", {"phase": "model"})
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
                    yield ChatTurnEvent(
                        "tool_call",
                        {"name": call["name"], "arguments": arguments},
                    )
                    with factory() as tool_session:
                        task_row = task_service.get_task(
                            tool_session, plan.task_id
                        )
                        outcome = await chat_tools.execute_tool(
                            tool_session,
                            task_row,
                            call["name"],
                            arguments,
                            conversation_id=plan.conversation_id,
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
                            "content": json.dumps(
                                outcome, ensure_ascii=False
                            ),
                        }
                    )
                    yield ChatTurnEvent(
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
            messages_for_model = list(plan.messages_plain)

        async def _clean_answer(target_messages: list[dict]) -> str | None:
            """去除工具标记的兜底回答；仅在流式结果泄漏工具文本时使用。"""
            nonlocal usage
            for _attempt in range(2):
                outcome = await model_service.complete_chat(
                    plan.provider,
                    plan.model,
                    target_messages,
                    temperature=plan.temperature,
                    max_tokens=plan.max_tokens,
                )
                usage = add_usage(usage, outcome.get("usage")) or usage
                candidate = (outcome.get("content") or "").strip()
                if candidate and not _looks_like_tool_markup(candidate):
                    return candidate
            return None

        # 最终回答始终用真正的流式生成；上面的工具 pre-pass 只负责决定/执行工具，
        # 不会直接作为用户可见的回答。
        final_messages = list(plan.messages_plain)
        if tool_trace:
            # 只保留 pre-pass 在原始对话之后追加的 assistant(tool_calls)/tool(result) 消息。
            final_messages.extend(
                messages_for_model[len(plan.messages_tools) :]
            )
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
            plan.provider,
            plan.model,
            final_messages,
            temperature=plan.temperature,
            max_tokens=plan.max_tokens,
        )
        async for event in _stream_with_heartbeat(stream):
            if event["type"] == "thinking":
                yield ChatTurnEvent("thinking", {"phase": "stream"})
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
                        yield ChatTurnEvent("delta", {"text": buffer})
                        emitted = True
                else:
                    chunks.append(text)
                    yield ChatTurnEvent("delta", {"text": text})
            elif event["type"] == "usage":
                usage = add_usage(usage, event["usage"]) or usage

        if markup_detected:
            chunks.clear()
            clean = await _clean_answer(final_messages)
            if clean is None:
                yield ChatTurnEvent(
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
                yield ChatTurnEvent("delta", {"text": piece})
        elif not emitted and buffer:
            chunks.append(buffer)
            yield ChatTurnEvent("delta", {"text": buffer})
    except Exception as exc:  # noqa: BLE001 - 将 Provider 错误显式返回给客户端
        code = getattr(exc, "code", "provider_error")
        message = getattr(exc, "message", str(exc))
        yield ChatTurnEvent("error", {"code": code, "message": message})
        return

    content = "".join(chunks).strip()
    if not content:
        yield ChatTurnEvent(
            "error",
            {"code": "empty_response", "message": "模型没有返回任何内容"},
        )
        return

    citations = extract_citations(content, plan.file_context)

    try:
        with factory() as persist_session:
            conversation_row = conversation_service.get_conversation(
                persist_session, plan.conversation_id
            )
            task_row = task_service.get_task(persist_session, plan.task_id)
            assistant = conversation_service.append_message(
                persist_session,
                conversation_row,
                role="assistant",
                content=content,
                usage=usage,
                metadata={
                    "tools": tool_trace,
                    "mode": plan.mode,
                    "reasoning_content": "".join(reasoning_chunks) or None,
                    "duration_ms": int(
                        (time.monotonic() - plan.request_started) * 1000
                    ),
                    "skill": plan.skill_meta,
                    "artifacts": len(created_artifacts),
                    "executions": len(created_executions),
                    "citations": citations,
                },
            )
            task_usage = conversation_service.bump_task_usage(
                persist_session, task_row, usage
            )
            message_id = assistant.id
            if created_artifacts:
                artifact_service.attach_source_message(
                    persist_session,
                    [uuid.UUID(item) for item in created_artifacts],
                    message_id,
                )
            persist_session.commit()
    except Exception as exc:  # noqa: BLE001 - 保存失败必须显式报错
        yield ChatTurnEvent(
            "error",
            {
                "code": "persist_failed",
                "message": f"回复已生成但保存失败：{exc.__class__.__name__}",
            },
        )
        return

    yield ChatTurnEvent(
        "done",
        {
            "message_id": str(message_id),
            "usage": usage,
            "task_usage": task_usage,
            "tools_enabled": tools_ok,
            "mode": plan.mode,
            "artifacts": created_artifacts,
            "executions": created_executions,
            "citations": citations,
        },
    )
