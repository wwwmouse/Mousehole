from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.shared.exceptions import ProviderError, ProviderNotConfiguredError
from app.shared.usage import normalize_usage

DEFAULT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def _snippet(raw: bytes, limit: int = 300) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    return text[:limit]


async def stream_openai(
    config: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    api_key = config.get("api_key") or ""
    if not api_key:
        raise ProviderNotConfiguredError(
            f"Provider {config['name']} 尚未配置 API Key",
            details={"provider": config["name"]},
        )
    url = config["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    usage: dict[str, int] | None = None
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            async with client.stream(
                "POST", url, headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderError(
                        f"模型服务返回错误（HTTP {response.status_code}）",
                        transient=response.status_code >= 500,
                        details={"provider": config["name"], "body": _snippet(body)},
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield {"type": "delta", "text": text}
                    if event.get("usage"):
                        usage = normalize_usage(event["usage"])
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"无法连接模型服务：{exc.__class__.__name__}",
            transient=True,
            details={"provider": config["name"], "base_url": config["base_url"]},
        ) from exc
    if usage:
        yield {"type": "usage", "usage": usage}


async def stream_ollama(
    config: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    url = config["base_url"].rstrip("/") + "/api/chat"
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderError(
                        f"Ollama 返回错误（HTTP {response.status_code}）",
                        transient=response.status_code >= 500,
                        details={"provider": "ollama", "body": _snippet(body)},
                    )
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = event.get("message") or {}
                    text = message.get("content")
                    if text:
                        yield {"type": "delta", "text": text}
                    if event.get("done"):
                        usage = normalize_usage(
                            {
                                "prompt_tokens": event.get("prompt_eval_count"),
                                "completion_tokens": event.get("eval_count"),
                            }
                        )
                        if usage:
                            yield {"type": "usage", "usage": usage}
                        break
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"无法连接 Ollama：{exc.__class__.__name__}",
            transient=True,
            details={"provider": "ollama", "base_url": config["base_url"]},
        ) from exc


async def stream(
    config: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    kind = config.get("kind")
    if kind == "openai":
        async for event in stream_openai(
            config, model, messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield event
    elif kind == "ollama":
        async for event in stream_ollama(
            config, model, messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield event
    else:
        raise ProviderError(
            f"不支持的 Provider 类型：{kind}", details={"provider": config.get("name")}
        )
