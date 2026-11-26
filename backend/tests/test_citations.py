"""Citation extraction tests for chat metadata."""

from __future__ import annotations

from app.modules.conversation.citations import extract_citations
from app.modules.conversation.chat_context import ChatFileContext


def _context() -> ChatFileContext:
    return ChatFileContext(
        text="context",
        citations=[
            {
                "file_id": "11111111-1111-4111-8111-111111111111",
                "filename": "学生手册.pdf",
                "page_no": 37,
            },
            {
                "file_id": "11111111-1111-4111-8111-111111111111",
                "filename": "学生手册.pdf",
                "page_no": 38,
            },
        ],
    )


def test_extract_citations_keeps_only_known_pages() -> None:
    content = (
        "第一条结论 [学生手册.pdf p.37]；"
        "第二条结论 [学生手册.pdf p.38]；"
        "伪造来源 [手册.pdf p.99]。"
    )
    citations = extract_citations(content, _context())
    assert citations == [
        {
            "file_id": "11111111-1111-4111-8111-111111111111",
            "filename": "学生手册.pdf",
            "page_no": 37,
        },
        {
            "file_id": "11111111-1111-4111-8111-111111111111",
            "filename": "学生手册.pdf",
            "page_no": 38,
        },
    ]


def test_extract_citations_without_context_is_empty() -> None:
    assert extract_citations("[学生手册.pdf p.37]", None) == []
