"""Global Library file API.

Contract:
  POST   /api/v1/files                    multipart upload (field: file)
  GET    /api/v1/files                    list + search
  GET    /api/v1/files/{file_id}          metadata + references
  GET    /api/v1/files/{file_id}/content  extracted text (PDF/MD/TXT)
  DELETE /api/v1/files/{file_id}          409 with references when still in use
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Query, Response, UploadFile, status

from app.api.deps import DbSession
from app.modules.file import service
from app.modules.file.schemas import FileContentRead, FileDetail, FileRead

router = APIRouter()


@router.post("", response_model=FileRead, status_code=status.HTTP_201_CREATED)
def upload_file(db: DbSession, file: UploadFile) -> FileRead:
    """Upload a PDF / Markdown / TXT file into the Global Library."""
    return service.upload_file(db, file)


@router.get("", response_model=list[FileRead])
def list_files(
    db: DbSession,
    search: str | None = None,
    file_type: str | None = None,
    status_filter: str | None = Query(default="active", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[FileRead]:
    return service.list_files(
        db,
        search=search,
        file_type=file_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/{file_id}", response_model=FileDetail)
def get_file(file_id: uuid.UUID, db: DbSession) -> FileDetail:
    return service.get_file_detail(db, file_id)


@router.get("/{file_id}/content", response_model=FileContentRead)
def get_file_content(
    file_id: uuid.UUID,
    db: DbSession,
    max_chars: int = Query(default=20000, ge=1),
) -> FileContentRead:
    return service.get_file_content(db, file_id, max_chars=max_chars)


@router.get("/{file_id}/raw")
def get_file_raw(file_id: uuid.UUID, db: DbSession) -> Response:
    """返回原始文件字节，供浏览器 PDF 预览等只读场景使用。"""
    file, data = service.get_file_raw(db, file_id)
    return Response(
        content=data,
        media_type=file.mime_type,
        headers={
            "Content-Disposition": (
                f"inline; filename*=UTF-8''{quote(file.filename)}"
            ),
            "Cache-Control": "private, max-age=60",
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: uuid.UUID, db: DbSession) -> Response:
    service.delete_file(db, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
