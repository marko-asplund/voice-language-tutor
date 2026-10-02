import asyncio

import httpx
import pytest

from voice_tutor.config import Settings
from voice_tutor.domain import Setup
from voice_tutor.main import create_app

SETUP = {
    "target_language": "English",
    "native_language": "Spanish",
    "level": "B1",
    "topic": "Travel",
}


@pytest.mark.asyncio
async def test_fake_flow_and_duplicate_end():
    app = create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        response = await client.post("/api/sessions", json=SETUP)
        assert response.headers["cache-control"] == "no-store"
        session = response.json()
        sid = session["id"]
        assert (
            await client.post(
                f"/api/sessions/{sid}/started", json={"conversation_id": session["conversation_id"]}
            )
        ).status_code == 200
        await client.post(f"/api/sessions/{sid}/end", json={})
        task = app.state.sessions.get(sid).task
        await client.post(f"/api/sessions/{sid}/end", json={})
        assert app.state.sessions.get(sid).task is task
        await task
        result = (await client.get(f"/api/sessions/{sid}")).json()
        assert result["state"] == "reviewed"
        assert result["transcript"][1]["speaker"] == "learner"
        await client.post(f"/api/sessions/{sid}/review/retry")
        assert app.state.sessions.get(sid).task is task
        assert (
            await client.post("/api/sessions", json={**SETUP, "level": "Z1"})
        ).status_code == 422
        assert (await client.get("/api/sessions/missing")).status_code == 404
        assert (
            await client.post(
                "/api/sessions", json=SETUP, headers={"Origin": "https://example.com"}
            )
        ).status_code == 403
    await app.state.sessions.close()


@pytest.mark.asyncio
async def test_timeout():
    from voice_tutor.clients.fake import FakeVoice

    class SlowVoice(FakeVoice):
        async def details(self, conversation_id):
            await asyncio.sleep(1)

    app = create_app(Settings(_env_file=None, transcript_wait_seconds=0.01), voice=SlowVoice())
    session = await app.state.sessions.create(Setup(**SETUP))
    item = app.state.sessions.end(session["id"])
    await item.task
    assert item.error.code == "transcript_timeout"
    await app.state.sessions.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin,expected",
    [
        ("http://localhost:8000", 200),
        ("http://127.0.0.1:8000", 200),
        ("http://localhost:9000", 403),
        ("https://example.com", 403),
    ],
)
async def test_local_origin_aliases(origin, expected):
    app = create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        response = await client.get("/health", headers={"Origin": origin})
        assert response.status_code == expected
    await app.state.sessions.close()
