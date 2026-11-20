from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import DbFactory, DbSession
from app.modules.artifact import repository as artifact_repository
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation import service as conversation_service
from app.modules.conversation import tools as chat_tools
from app.modules.conversation.chat_context import build_file_context
from app.modules.conversation.tools import tool_prompt
from app.modules.conversation.models import Conversation, Message
from app.modules.conversation.schemas import ChatRequest, TaskMessagesRead
from app.modules.model import service as model_service
from app.modules.skill import service as skill_service
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.defaults import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from app.shared.usage import add_usage

router = APIRouter()

HISTORY_LIMIT = 20
MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = (
    "你是 mousehole 的 AI 助手，运行在用户本地的个人 AI 工作空间中。"
    "请基于用户提供的任务目标和对话上下文，给出准确、简洁、可执行的回答。"
    "不要编造事实；不确定时明确说明。"
    "严格只使用资料原文：不要添加资料中不存在的警告、免责声明、隐私提示、"
    "背景信息或数字；如果必须推断，明确标注「推断」。"
    "资料按最近更新时间排序，回答时优先参考最近更新的资料。\n\n"
    + tool_prompt()
)


# Safety net only: when the user explicitly asks to save/export, we persist the
# final answer even if the model forgot to call save_artifact. Normal artifact
# creation is still the model's decision via tool calling.
ARTIFACT_INTENT_TOKENS = (
    "保存",
    "存为",
    "存成",
    "导出",
    "artifact",
)


def _wants_artifact(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ARTIFACT_INTENT_TOKENS)


def _looks_like_tool_markup(text: str) -> bool:
    tokens = ("<|DSML|", "<tool_call", "</tool_call>", "｜｜DSML｜｜")
    return any(token in text for token in tokens)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_with_heartbeat(stream) -> AsyncIterator[dict]:
    """Yield model events, emitting a thinking heartbeat every 2s of silence."""
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
    if skill is not None and skill.system_prompt:
        system = skill.system_prompt + "\n\n" + system
    if context:
        system = system + "\n\n" + "\n".join(context)
    if file_context:
        system = system + "\n\n" + file_context

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history[-HISTORY_LIMIT:]:
        if item.role in ("user", "assistant") and item.content:
            messages.append({"role": item.role, "content": item.content})
    return messages


@router.get("/{task_id}/messages", response_model=TaskMessagesRead)
def list_messages(task_id: uuid.UUID, db: DbSession) -> TaskMessagesRead:
    return conversation_service.list_task_messages(db, task_id)


@router.post("/{task_id}/messages")
async def send_message(
    task_id: uuid.UUID,
    payload: ChatRequest,
    db: DbSession,
    factory: DbFactory,
) -> StreamingResponse:
    request_started = time.monotonic()
    task = task_service.get_task(db, task_id)
    provider, model, _config = model_service.resolve_model(
        task.model_provider,
        task.model_name,
        payload.provider,
        payload.model,
    )
    skill = (
        skill_service.resolve_skill(db, payload.skill_id)
        if payload.skill_id
        else None
    )
    conversation = conversation_service.get_or_create_conversation(db, task)
    file_context = build_file_context(db, task, skill)
    user_metadata = {
        "skill": (
            {"id": skill.id, "name": skill.name} if skill is not None else None
        ),
        # Only surface files the user temporarily introduced in the composer;
        # project-inherited files stay in the model context but are not shown
        # as per-message attachments.
        "files": (
            [
                item
                for item in (file_context.files if file_context else [])
                if item.get("source") == "task_added"
            ]
        ),
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
        db, conversation.id, limit=HISTORY_LIMIT
    )
    messages = _build_messages(
        task,
        history,
        file_context.text if file_context else None,
        skill,
    )
    conversation_id = conversation.id
    temperature = task.temperature
    max_tokens = task.max_tokens
    if temperature is None or max_tokens is None:
        workspace = db.get(Workspace, task.workspace_id)
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
        usage: dict | None = None
        final_content: str | None = None
        created_artifacts: list[str] = []
        created_executions: list[str] = []
        tool_trace: list[dict] = []
        messages_for_model: list[dict] = list(messages)

        try:
            yield _sse("start", {"provider": provider, "model": model})
            # --- controlled tool-calling pre-pass (non-streaming) ---
            tools_ok = True
            try:
                for _round in range(MAX_TOOL_ROUNDS):
                    # Heartbeats keep the UI informed while the non-streaming
                    # tool pre-pass is in flight (can take a while on local models).
                    pending = asyncio.create_task(
                        model_service.complete_chat(
                            provider,
                            model,
                            messages_for_model,
                            tools=chat_tools.TOOL_SPECS,
                            temperature=temperature,
                            max_tokens=max_tokens,
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
                        candidate = (result.get("content") or "").strip()
                        if _looks_like_tool_markup(candidate):
                            # The model emitted tool-call markup as text; force a
                            # clean final answer via the plain streaming path.
                            final_content = None
                        else:
                            final_content = candidate
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
                    # OpenAI-compatible order: assistant(tool_calls) BEFORE tool results.
                    messages_for_model.append(
                        {
                            "role": "assistant",
                            "content": result.get("content") or "",
                            "tool_calls": assistant_tool_calls,
                        }
                    )
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
            except Exception:  # noqa: BLE001 - tools unsupported -> plain streaming
                tools_ok = False
                final_content = None
                messages_for_model = list(messages)

            async def _clean_answer() -> str | None:
                """Final answer without tools; retry once if markup leaks."""
                nonlocal usage
                final_messages = list(messages_for_model) + [
                    {
                        "role": "user",
                        "content": (
                            "请基于以上信息直接给出最终回答。不要再调用工具，"
                            "也不要输出任何工具调用标记（如 DSML / <tool_call>）。"
                        ),
                    }
                ]
                for _attempt in range(2):
                    outcome = await model_service.complete_chat(
                        provider,
                        model,
                        final_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    usage = add_usage(usage, outcome.get("usage")) or usage
                    candidate = (outcome.get("content") or "").strip()
                    if candidate and not _looks_like_tool_markup(candidate):
                        return candidate
                return None

            if final_content is None:
                if tools_ok:
                    # Tool rounds exhausted: ask for a clean, tool-free answer.
                    final_content = await _clean_answer()
                    if final_content is None:
                        yield _sse(
                            "error",
                            {
                                "code": "invalid_final_answer",
                                "message": "模型返回了无法解析的工具调用文本，请重试",
                            },
                        )
                        return
                else:
                    # Tools unsupported: stream normally, but buffer the opening
                    # characters so leaked tool markup can be detected early.
                    buffer = ""
                    emitted = False
                    markup_detected = False
                    stream = model_service.stream_chat(
                        provider,
                        model,
                        messages_for_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    async for event in _stream_with_heartbeat(stream):
                        if event["type"] == "thinking":
                            yield _sse("thinking", {"phase": "stream"})
                            continue
                        if event["type"] == "delta":
                            text = event["text"]
                            if not emitted:
                                buffer += text
                                if _looks_like_tool_markup(buffer):
                                    markup_detected = True
                                    break
                                if len(buffer) >= 160:
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
                        final_content = await _clean_answer()
                        if final_content is None:
                            yield _sse(
                                "error",
                                {
                                    "code": "invalid_final_answer",
                                    "message": "模型返回了无法解析的工具调用文本，请重试",
                                },
                            )
                            return
                    elif not emitted and buffer:
                        chunks.append(buffer)
                        yield _sse("delta", {"text": buffer})

            if final_content is not None:
                for index in range(0, len(final_content), 60):
                    piece = final_content[index : index + 60]
                    chunks.append(piece)
                    yield _sse("delta", {"text": piece})
        except Exception as exc:  # noqa: BLE001 - surface provider errors to the client
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

        # Deterministic fallback: if the user explicitly asked for a document/
        # artifact but the model answered without calling save_artifact, save the
        # final answer anyway so there is always a persisted Artifact.
        already_saved = any(
            item["name"] == "save_artifact" for item in tool_trace
        )
        if _wants_artifact(payload.content) and not already_saved:
            yield _sse(
                "tool_call",
                {
                    "name": "save_artifact",
                    "arguments": {"title": f"{task.title} · 成果"},
                },
            )
            with factory() as tool_session:
                task_row = tool_session.get(Task, task_id)
                outcome = await chat_tools.execute_tool(
                    tool_session,
                    task_row,
                    "save_artifact",
                    {
                        "title": f"{task.title} · 成果",
                        "content": content,
                        "series_title": f"{task.title} · 对话成果",
                    },
                    conversation_id=conversation_id,
                )
            if outcome.get("artifact_id"):
                created_artifacts.append(outcome["artifact_id"])
            tool_trace.append(
                {
                    "name": "save_artifact",
                    "ok": bool(outcome.get("ok")),
                    "summary": str(outcome.get("summary") or ""),
                }
            )
            yield _sse(
                "tool_result",
                {
                    "name": "save_artifact",
                    "ok": bool(outcome.get("ok")),
                    "summary": outcome.get("summary", ""),
                    "artifact_id": outcome.get("artifact_id"),
                    "execution_id": outcome.get("execution_id"),
                },
            )

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
        except Exception as exc:  # noqa: BLE001
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
