from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.modules.model import config as provider_config
from app.modules.model.schemas import (
    ProviderRead,
    ProviderTestResult,
    ProviderUpdate,
)

router = APIRouter()


@router.get("", response_model=list[ProviderRead])
def list_providers() -> list[ProviderRead]:
    return [ProviderRead(**item) for item in provider_config.list_providers()]


@router.put("/{name}", response_model=ProviderRead)
def update_provider(name: str, payload: ProviderUpdate) -> ProviderRead:
    updated = provider_config.update_provider(
        name, payload.model_dump(exclude_unset=True)
    )
    return ProviderRead(**updated)


@router.post("/{name}/test", response_model=ProviderTestResult)
async def test_provider(name: str) -> ProviderTestResult:
    config = provider_config.get_provider(name)
    if config["kind"] == "openai" and not config.get("api_key"):
        return ProviderTestResult(ok=False, message="尚未配置 API Key")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            if config["kind"] == "openai":
                headers = {"Authorization": f"Bearer {config['api_key']}"}
                response = await client.get(
                    config["base_url"].rstrip("/") + "/models", headers=headers
                )
            else:
                response = await client.get(
                    config["base_url"].rstrip("/") + "/api/tags"
                )
    except httpx.HTTPError as exc:
        return ProviderTestResult(
            ok=False, message=f"连接失败：{exc.__class__.__name__}"
        )
    if response.status_code >= 400:
        return ProviderTestResult(
            ok=False, message=f"服务返回 HTTP {response.status_code}"
        )

    models: list[str] = []
    try:
        payload = response.json()
        if config["kind"] == "openai":
            models = [
                str(item["id"])
                for item in payload.get("data", [])
                if isinstance(item, dict) and item.get("id")
            ]
        else:
            models = [
                str(item["name"])
                for item in payload.get("models", [])
                if isinstance(item, dict) and item.get("name")
            ]
    except (ValueError, AttributeError):
        models = []

    if models:
        update: dict = {"models": models}
        if not config.get("default_model") or config["default_model"] not in models:
            update["default_model"] = models[0]
        provider_config.update_provider(name, update)

    suffix = f"，发现 {len(models)} 个模型" if models else ""
    return ProviderTestResult(ok=True, message=f"连接成功{suffix}")
