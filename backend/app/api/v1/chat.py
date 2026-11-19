from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import DbFactory, DbSession
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation import service as conversation_service
from app.modules.conversation.models import Conversation, Message
from app.modules.conversation.schemas import ChatRequest, TaskMessagesRead
from app.modules.model import service as model_service
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.modules.workspace.models import Workspace

router = APIRouter()

HISTORY_LIMIT = 20

SYSTEM_PROMPT = (
    "你是 mousehole 的 AI 助手，运行在用户本地的个人 AI 工作空间中。"
    "请基于用户提供的任务目标和对话上下文，给出准确、简洁、可执行的回答。"
    "不要编造事实；不确定时明确说明。"
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
        try:
            yield _sse("start", {"provider": provider, "model": model})
            async for event in model_service.stream_chat(
                provider,
                model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                if event["type"] == "delta":
                    chunks.append(event["text"])
                    yield _sse("delta", {"text": event["text"]})
                elif event["type"] == "usage":
                    usage = event["usage"]
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
            task_usage = conversation_service.bump_task_usage(session, task_row, usage)
            session.commit()
            message_id = str(assistant.id)

        yield _sse(
            "done",
            {"message_id": message_id, "usage": usage, "task_usage": task_usage},
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
