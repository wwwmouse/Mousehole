from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class FileStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SnapshotSourceType(StrEnum):
    PROJECT_INHERITED = "project_inherited"
    TASK_ADDED = "task_added"


class SnapshotUsageMode(StrEnum):
    DIRECT = "direct"
    SUMMARIZED = "summarized"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FileOverrideAction(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


PROJECT_STATUSES = tuple(status.value for status in ProjectStatus)
TASK_STATUSES = tuple(status.value for status in TaskStatus)
FILE_STATUSES = tuple(status.value for status in FileStatus)
OVERRIDE_ACTIONS = tuple(action.value for action in FileOverrideAction)
MESSAGE_ROLES = tuple(role.value for role in MessageRole)
EXECUTION_STATUSES = tuple(status.value for status in ExecutionStatus)
EXECUTION_STEP_STATUSES = tuple(status.value for status in ExecutionStepStatus)
SNAPSHOT_SOURCE_TYPES = tuple(item.value for item in SnapshotSourceType)
SNAPSHOT_USAGE_MODES = tuple(item.value for item in SnapshotUsageMode)
