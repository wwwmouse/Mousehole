"""Explicit model defaults shared by chat and execution.

Keep these in sync with the frontend composer defaults so "unset" never means
"provider-defined and invisible".
"""
from __future__ import annotations

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
