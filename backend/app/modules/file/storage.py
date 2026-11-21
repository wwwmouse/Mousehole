from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.shared.exceptions import StorageError


class LocalFileStorage:
    """Content-addressed local storage. Business code never builds paths by hand."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, extension: str) -> tuple[str, str, int]:
        digest = hashlib.sha256(data).hexdigest()
        clean_ext = extension if extension.startswith(".") else f".{extension}"
        storage_key = f"objects/{digest[:2]}/{digest[2:4]}/{digest}{clean_ext.lower()}"
        target = self._resolve(storage_key)
        if target.exists() and target.stat().st_size == len(data):
            return storage_key, digest, len(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, temp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".part")
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
        except OSError as exc:
            raise StorageError(f"文件保存失败：{exc}") from exc
        return storage_key, digest, len(data)

    def read(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"存储文件不存在：{storage_key}") from exc

    def delete(self, storage_key: str) -> None:
        """Soft-delete keeps physical data; explicit purge is not exposed in MVP."""
        raise StorageError("MVP 不提供物理文件删除能力")

    def purge(self, storage_key: str) -> None:
        """Remove physical bytes for an internal temporary file.

        Only used when a Task-scoped temporary File row is being discarded and
        no other File row can reference the same content-addressed key.
        """
        path = self._resolve(storage_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"临时文件清理失败：{exc}") from exc

    def _resolve(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise StorageError("非法的 storage key")
        return candidate


_storage: LocalFileStorage | None = None


def get_storage() -> LocalFileStorage:
    global _storage
    if _storage is None:
        _storage = LocalFileStorage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
