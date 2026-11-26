# 模块职责：从模型回答中提取并校验 [文件名 p.N] 引用。
# 对外函数：
# - extract_citations(content, file_context)：只保留本轮上下文中真实存在的文件/页码引用。
from __future__ import annotations

import re

from app.modules.conversation.chat_context import ChatFileContext

_CITATION_RE = re.compile(r"\[([^\[\]\n]{1,300}?)\s+p\.(\d+)\]")


def extract_citations(
    content: str, file_context: ChatFileContext | None
) -> list[dict]:
    """只保留上下文真实存在的 [文件名 p.N] 引用。"""
    if file_context is None or not file_context.citations:
        return []
    by_name: dict[str, list[dict]] = {}
    for source in file_context.citations:
        filename = str(source.get("filename", ""))
        by_name.setdefault(filename.casefold(), []).append(source)
        basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        by_name.setdefault(basename.casefold(), []).append(source)

    result: list[dict] = []
    for match in _CITATION_RE.finditer(content):
        name = match.group(1).strip().casefold()
        page_no = int(match.group(2))
        for source in by_name.get(name, []):
            if int(source["page_no"]) != page_no:
                continue
            citation = {
                "file_id": source["file_id"],
                "filename": source["filename"],
                "page_no": page_no,
            }
            if citation not in result:
                result.append(citation)
            break
    return result
