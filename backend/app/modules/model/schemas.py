from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderRead(BaseModel):
    name: str
    kind: str
    base_url: str
    configured: bool
    masked_key: str
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None


class ProviderUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] | None = None
    default_model: str | None = None


class ProviderTestResult(BaseModel):
    ok: bool
    message: str


class ModelInfo(BaseModel):
    provider: str
    model: str
    label: str
