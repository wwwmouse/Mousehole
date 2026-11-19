from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.conversation import repository
from app.modules.conversation.models import Conversation, Message
from app.modules.conversation.schemas import (
    MessageRead,
    TaskMessagesRead,
)
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.shared.usage import add_usage


def get_or_create_conversation(session: Session, task: Task) -> Conversation:
    conversation = repository.get_by_task(session, task.id)
    if conversation is None:
        conversation = repository.create(session, task.id)
        session.commit()
        session.refresh(conversation)
    return conversation


def list_task_messages(session: Session, task_id: uuid.UUID) -> TaskMessagesRead:
    task = task_service.get_task(session, task_id)
    conversation = repository.get_by_task(session, task_id)
    if conversation is None:
        return TaskMessagesRead(
            task_id=task.id,
            conversation_id=None,
            messages=[],
            task_usage=task.usage,
        )
    messages = repository.list_messages(session, conversation.id)
    return TaskMessagesRead(
        task_id=task.id,
        conversation_id=conversation.id,
        messages=[MessageRead.model_validate(item) for item in messages],
        task_usage=task.usage,
    )


def append_message(
    session: Session,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    usage: dict | None = None,
) -> Message:
    message = repository.add_message(
        session,
        conversation_id=conversation.id,
        role=role,
        content=content,
        sequence=repository.next_sequence(session, conversation.id),
        usage=usage,
    )
    session.flush()
    return message


def bump_task_usage(session: Session, task: Task, usage: dict | None) -> dict | None:
    if usage:
        task.usage = add_usage(task.usage, usage)
    return task.usage
