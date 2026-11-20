from __future__ import annotations

import asyncio
import json
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
from app.modules.conversation.models import Conversation, Message
from app.modules.conversation.schemas import ChatRequest, TaskMessagesRead
from app.modules.model import service as model_service
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace
from app.shared.usage import add_usage

router = APIRouter()

HISTORY_LIMIT = 20
MAX_TOOL_ROUNDS = 2

SYSTEM_PROMPT = (
    "你是 mousehole 的 AI 助手，运行在用户本地的个人 AI 工作空间中。"
    "请基于用户提供的任务目标和对话上下文，给出准确、简洁、可执行的回答。"
    "不要编造事实；不确定时明确说明。\n\n"
    "你可以使用受控工具：read_task_files（列出 Task 可用文件）、"
    "read_task_file（读取某个文件内容）、save_artifact（把内容保存为 Task 成果）、"
    "create_execution（启动正式执行）。"
    "当用户希望产出可保存的成果时，调用 save_artifact；"
    "当用户希望做多文档正式分析时，调用 create_execution。"
    "工具只能操作当前 Task，不能访问任意文件系统。"
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_messages(task: Task, history: list[Message]) -> list[dict[str, str]]:
    context: list[str] = []
    if task.title:
        context.append(f"当前 Task：{task.title}")
    if task.description:
        context.append(f"Task 说明：{task.description}")
    system = SYSTEM_PROMPT
    if context:
        system = system + "\n\n" + "\n".join(context)

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
    task = task_service.get_task(db, task_id)
    provider, model, _config = model_service.resolve_model(
        task.model_provider,
        task.model_name,
        payload.provider,
        payload.model,
    )
    conversation = conversation_service.get_or_create_conversation(db, task)
    conversation_service.append_message(
        db, conversation, role="user", content=payload.content
    )
    db.commit()

    history = conversation_repository.list_messages(
        db, conversation.id, limit=HISTORY_LIMIT
    )
    messages = _build_messages(task, history)
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

    async def event_stream() -> AsyncIterator[str]:
        chunks: list[str] = []
        usage: dict | None = None
        final_content: str | None = None
        created_artifacts: list[str] = []
        created_executions: list[str] = []
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
                        final_content = (result.get("content") or "").strip()
                        break
                    assistant_tool_calls = []
                    for call in tool_calls:
                        try:
                            arguments = json.loads(call.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            arguments = {}
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
                    messages_for_model.append(
                        {
                            "role": "assistant",
                            "content": result.get("content") or "",
                            "tool_calls": assistant_tool_calls,
                        }
                    )
            except Exception:  # noqa: BLE001 - tools unsupported -> plain streaming
                tools_ok = False
                final_content = None
                messages_for_model = list(messages)

            if final_content is None:
                async for event in model_service.stream_chat(
                    provider,
                    model,
                    messages_for_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if event["type"] == "delta":
                        chunks.append(event["text"])
                        yield _sse("delta", {"text": event["text"]})
                    elif event["type"] == "usage":
                        usage = add_usage(usage, event["usage"]) or usage
            else:
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
