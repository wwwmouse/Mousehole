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


class FileOverrideAction(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


PROJECT_STATUSES = tuple(status.value for status in ProjectStatus)
TASK_STATUSES = tuple(status.value for status in TaskStatus)
FILE_STATUSES = tuple(status.value for status in FileStatus)
OVERRIDE_ACTIONS = tuple(action.value for action in FileOverrideAction)
