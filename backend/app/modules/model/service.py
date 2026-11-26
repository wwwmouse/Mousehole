# 模块职责：模型选择、Provider 配置解析，以及流式/非流式调用入口。
# 对外函数：
# - resolve_model(task_provider, task_model, request_provider=None, request_model=None)：解析本轮使用的 provider/model。
# - stream_chat(provider, model, messages, *, temperature=None, max_tokens=None)：流式聊天。
# - complete_chat(provider, model, messages, *, tools=None, temperature=None, max_tokens=None, thinking=None)：非流式调用（工具 pre-pass）。
# - list_models()：列出已配置 provider 的可用模型。
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.modules.model import adapters
from app.modules.model import config as provider_config
from app.shared.exceptions import (
    ModelRequiredError,
    ProviderNotConfiguredError,
)


def resolve_model(
    task_provider: str | None,
    task_model: str | None,
    request_provider: str | None = None,
    request_model: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Resolve the provider/model to use, with a fallback to the first configured one."""
    provider = request_provider or task_provider
    model = request_model or task_model
    if not provider or not model:
        fallback = provider_config.default_selection()
        if fallback is None:
            raise ModelRequiredError(
                "尚未配置可用的模型 Provider，请先在 Settings 中配置 DeepSeek 或 Ollama"
            )
        provider = provider or fallback[0]
        model = model or fallback[1]
    config = provider_config.get_provider(provider)
    if not provider_config.is_configured(provider):
        raise ProviderNotConfiguredError(
            f"Provider {provider} 尚未配置，请先在 Settings 中完成配置",
            details={"provider": provider},
        )
    return provider, model, config


async def stream_chat(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    config = provider_config.get_provider(provider)
    async for event in adapters.stream(
        config,
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        yield event


async def complete_chat(
    provider: str,
    model: str,
    messages: list[dict],
    *,
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    thinking: bool | None = None,
) -> dict:
    config = provider_config.get_provider(provider)
    return await adapters.complete(
        config,
        model,
        messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        thinking=thinking,
    )


def list_models() -> list[dict[str, str]]:
    return provider_config.available_models()
