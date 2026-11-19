from __future__ import annotations

from typing import Any

USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def normalize_usage(raw: Any) -> dict[str, int] | None:
    """Return a clean usage dict or None when the provider gave nothing useful."""
    if not isinstance(raw, dict):
        return None
    cleaned: dict[str, int] = {}
    for key in USAGE_KEYS:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            cleaned[key] = int(value)
    if "total_tokens" not in cleaned and (
        "prompt_tokens" in cleaned or "completion_tokens" in cleaned
    ):
        cleaned["total_tokens"] = cleaned.get("prompt_tokens", 0) + cleaned.get(
            "completion_tokens", 0
        )
    return cleaned or None


def add_usage(current: Any, delta: Any) -> dict[str, int] | None:
    """Sum two usage payloads; both may be None."""
    left = normalize_usage(current) or {}
    right = normalize_usage(delta)
    if right is None:
        return left or None
    total = dict(left)
    for key in USAGE_KEYS:
        total[key] = int(left.get(key, 0)) + int(right.get(key, 0))
    return total or None
