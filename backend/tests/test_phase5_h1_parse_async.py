"""Phase 5 H1: parsing must not block the event loop; timeouts fail explicitly."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from app.modules.context import builder
from app.shared.exceptions import FileParseError


def _fake_file(name: str = "big.pdf") -> SimpleNamespace:
    return SimpleNamespace(
        storage_key=f"objects/test/{name}",
        file_type="pdf",
        filename=name,
        size=1024,
    )


def test_extract_text_async_offloads_to_worker_thread(monkeypatch) -> None:
    def slow_parse(file_row) -> str:  # noqa: ARG001 - fake storage row
        time.sleep(0.15)
        return "parsed text"

    monkeypatch.setattr(builder, "_read_and_parse_sync", slow_parse)

    async def scenario() -> tuple[str, int]:
        ticks = 0
        task = asyncio.create_task(
            builder._extract_text_async(_fake_file(), timeout_seconds=2.0)
        )
        for _ in range(5):
            await asyncio.sleep(0.02)
            ticks += 1
        return await task, ticks

    text, ticks = asyncio.run(scenario())
    assert text == "parsed text"
    # The event loop kept running while the parser slept in a worker thread.
    assert ticks == 5


def test_extract_text_async_timeout_is_explicit(monkeypatch) -> None:
    def never_ending(file_row) -> str:  # noqa: ARG001
        time.sleep(0.5)
        return "late"

    monkeypatch.setattr(builder, "_read_and_parse_sync", never_ending)

    with pytest.raises(FileParseError, match="解析超时"):
        asyncio.run(builder._extract_text_async(_fake_file(), timeout_seconds=0.05))


def test_parse_timeout_defaults_to_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        builder,
        "get_settings",
        lambda: SimpleNamespace(parse_timeout_seconds=7.0),
    )
    assert builder._parse_timeout(None) == 7.0
    assert builder._parse_timeout(1.5) == 1.5
