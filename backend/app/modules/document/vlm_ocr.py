# 模块职责：本地 VLM OCR 客户端，通过 OpenAI 兼容 /chat/completions 识别页图。
# 对外类型：
# - VlmOcrConfig：base_url/model/api_key/timeout 等配置。
# - VlmOcrClient：recognize_page(image_png, page_no) 识别单页；支持 close()/with。
"""本地 VLM OCR 客户端（OpenAI 兼容接口）。

默认适配 Ollama：
    base_url = http://127.0.0.1:11434/v1
    model    = qwen3-vl:4b

也兼容 vLLM / LM Studio 等 OpenAI 兼容服务。
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import httpx

from app.shared.exceptions import ProviderError

DEFAULT_PROMPT = (
    "你是文档 OCR 助手。请逐字转写图片中的全部文字，保持原有标题、段落、"
    "列表和表格顺序。不要总结、不要解释、不要添加资料中不存在的内容。"
    "无法辨认的字词用 [无法辨认] 标注。只输出转写正文，不要加代码围栏或前言。"
)


@dataclass(frozen=True)
class VlmOcrConfig:
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3-vl:4b"
    api_key: str = "ollama"
    timeout_seconds: float = 180.0
    max_tokens: int = 4096
    prompt: str = DEFAULT_PROMPT

    @classmethod
    def from_env(cls) -> "VlmOcrConfig":
        return cls(
            base_url=os.getenv(
                "OCR_VLM_BASE_URL", "http://127.0.0.1:11434/v1"
            ),
            model=os.getenv("OCR_VLM_MODEL", "qwen3-vl:4b"),
            api_key=os.getenv("OCR_VLM_API_KEY", "ollama"),
            timeout_seconds=float(
                os.getenv("OCR_VLM_TIMEOUT_SECONDS", "180")
            ),
            max_tokens=int(os.getenv("OCR_VLM_MAX_TOKENS", "4096")),
        )


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return ""


def _strip_fences(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) >= 2 and lines[-1].strip().startswith("```"):
        lines = lines[1:-1]
    else:
        lines = lines[1:]
    return "\n".join(lines).strip()


class VlmOcrClient:
    def __init__(
        self,
        config: VlmOcrConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or VlmOcrConfig.from_env()
        self._client = httpx.Client(
            timeout=self.config.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VlmOcrClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def recognize_page(self, image_png: bytes, page_no: int) -> str:
        """识别一页图片；失败显式抛 ProviderError，不返回空字符串。"""
        image_url = (
            "data:image/png;base64,"
            + base64.b64encode(image_png).decode("ascii")
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.config.prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"VLM OCR 超时（第 {page_no} 页）",
                transient=True,
                details={
                    "base_url": self.config.base_url,
                    "model": self.config.model,
                    "page": page_no,
                },
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                f"无法连接本地 VLM（第 {page_no} 页）：{exc.__class__.__name__}",
                transient=True,
                details={
                    "base_url": self.config.base_url,
                    "model": self.config.model,
                    "page": page_no,
                },
            ) from exc

        if response.status_code >= 400:
            snippet = response.text[:300].replace("\n", " ")
            raise ProviderError(
                f"VLM 返回 HTTP {response.status_code}（第 {page_no} 页）：{snippet}",
                details={
                    "base_url": self.config.base_url,
                    "model": self.config.model,
                    "page": page_no,
                },
            )

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"VLM 返回格式异常（第 {page_no} 页）",
                details={"model": self.config.model, "page": page_no},
            ) from exc

        text = _strip_fences(_content_text(content))
        if not text:
            raise ProviderError(
                f"VLM 未返回文字（第 {page_no} 页）",
                details={"model": self.config.model, "page": page_no},
            )
        return text
