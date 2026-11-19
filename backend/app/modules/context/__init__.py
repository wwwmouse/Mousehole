"""Context module: resolve the file context available to a Task."""

from app.modules.context.service import compute_task_files, get_task_files

__all__ = ["compute_task_files", "get_task_files"]
