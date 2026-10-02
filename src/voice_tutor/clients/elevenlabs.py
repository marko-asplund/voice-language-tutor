import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from voice_tutor.config import Settings
from voice_tutor.domain import AppError


class ElevenLabs:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.agent_id = settings.elevenlabs_agent_id
        self.http = httpx.AsyncClient(
            base_url="https://api.elevenlabs.io",
            headers={"xi-api-key": settings.elevenlabs_api_key.get_secret_value()},
            timeout=15,
            transport=transport,
        )

    async def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        for attempt in range(2):
            try:
                response = await self.http.get(path, params=params)
            except httpx.TimeoutException:
                raise AppError(
                    "provider_unavailable", "ElevenLabs request timed out.", retryable=True
                ) from None
            except httpx.RequestError:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise AppError(
                    "provider_unavailable", "ElevenLabs could not be reached.", retryable=True
                ) from None
            if response.status_code in (401, 403):
                raise AppError(
                    "provider_auth_failed",
                    "Check ElevenLabs key permissions and agent access.",
                    upstream_status=response.status_code,
                )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                raise AppError(
                    "provider_unavailable",
                    "ElevenLabs is unavailable; check access or credits.",
                    retryable=True,
                    upstream_status=response.status_code,
                )
            if not response.is_success:
                raise AppError(
                    "provider_unavailable",
                    "ElevenLabs rejected the request.",
                    upstream_status=response.status_code,
                )
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise TypeError
                return data
            except (ValueError, TypeError):
                raise AppError(
                    "provider_unavailable", "Invalid ElevenLabs response.", retryable=True
                ) from None
        raise AssertionError("unreachable")

    async def connect(self) -> dict[str, Any]:
        data = await self.get(
            "/v1/convai/conversation/get-signed-url",
            {"agent_id": self.agent_id, "include_conversation_id": "true"},
        )
        signed = data.get("signed_url")
        if (
            not isinstance(signed, str)
            or urlparse(signed).scheme != "wss"
            or (
                urlparse(signed).hostname
                not in (
                    "api.elevenlabs.io",
                    "api.us.elevenlabs.io",
                    "api.eu.residency.elevenlabs.io",
                )
            )
        ):
            raise AppError("provider_unavailable", "Invalid ElevenLabs connection descriptor.")
        cid = data.get("conversation_id")
        return {"signed_url": signed, "conversation_id": cid if isinstance(cid, str) else None}

    async def details(self, conversation_id: str) -> dict[str, Any]:
        data = await self.get(f"/v1/convai/conversations/{conversation_id}")
        if data.get("conversation_id") != conversation_id:
            raise AppError("conversation_conflict", "Conversation ID did not match.", 409)
        return data

    async def close(self) -> None:
        await self.http.aclose()
