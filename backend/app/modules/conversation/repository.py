from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.conversation.models import Conversation, Message


def get_by_task(session: Session, task_id: uuid.UUID) -> Conversation | None:
    return session.scalars(
        select(Conversation).where(Conversation.task_id == task_id)
    ).first()


def create(session: Session, task_id: uuid.UUID) -> Conversation:
    conversation = Conversation(task_id=task_id)
    session.add(conversation)
    session.flush()
    return conversation


def list_messages(
    session: Session, conversation_id: uuid.UUID, *, limit: int = 200
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence)
        .limit(limit)
    )
    return list(session.scalars(stmt))


def next_sequence(session: Session, conversation_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(Message.sequence)).where(
            Message.conversation_id == conversation_id
        )
    )
    return int(current or 0) + 1


def add_message(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    sequence: int,
    usage: dict | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence=sequence,
        usage=usage,
    )
    session.add(message)
    session.flush()
    return message
