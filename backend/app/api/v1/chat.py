from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import DbFactory, DbSession
from app.modules.conversation import service as conversation_service
from app.modules.conversation.chat_turn import (
    ChatTurnEvent,
    prepare_chat_turn,
    run_chat_turn,
)
from app.modules.conversation.schemas import (
    ChatRequest,
    ConversationContextRead,
    ConversationContextUpdate,
    TaskMessagesRead,
)
from app.modules.task import service as task_service

router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _sse_events(
    events: AsyncIterator[ChatTurnEvent],
) -> AsyncIterator[str]:
    """把 Chat 领域事件转换为 SSE 帧。"""
    async for event in events:
        yield _sse(event.event, event.data)


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
    # 准备阶段在返回 StreamingResponse 之前完成，任务不存在、模型未配置等
    # 错误仍然走普通 HTTP 错误，而不是变成 SSE error。
    plan = await prepare_chat_turn(db, task_id, payload)
    return StreamingResponse(
        _sse_events(run_chat_turn(plan, factory)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
