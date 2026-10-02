import asyncio

import pytest

from voice_tutor.clients.fake import FakeReview, FakeVoice
from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Setup
from voice_tutor.services.sessions import Sessions

SETUP = Setup(target_language="English", native_language="Spanish", level="B1", topic="Travel")


class CountingReview(FakeReview):
    def __init__(self, refusal=False):
        self.calls = 0
        self.refusal = refusal
        self.gate = asyncio.Event()

    async def review(self, setup, turns):
        self.calls += 1
        await self.gate.wait()
        if self.refusal:
            raise AppError("review_refused", "Declined.")
        if self.calls == 1:
            raise AppError("provider_unavailable", "Temporary failure.", retryable=True)
        return await super().review(setup, turns)


@pytest.mark.asyncio
async def test_retry_reuses_transcript_and_prevents_overlap():
    class CountingVoice(FakeVoice):
        calls = 0

        async def details(self, cid):
            self.calls += 1
            return await super().details(cid)

    voice, reviewer = CountingVoice(), CountingReview()
    service = Sessions(Settings(_env_file=None), voice, reviewer)
    created = await service.create(SETUP)
    item = service.end(created["id"])
    await asyncio.sleep(0)
    first = item.task
    assert service.end(item.id).task is first
    reviewer.gate.set()
    await first
    assert item.error.retryable
    second = service.end(item.id, retry=True).task
    assert service.end(item.id, retry=True).task is second
    await second
    assert item.state == "reviewed"
    assert reviewer.calls == 2
    assert voice.calls == 1
    assert service.end(item.id, retry=True).task is second
    await service.close()


@pytest.mark.asyncio
async def test_refusal_is_terminal():
    reviewer = CountingReview(refusal=True)
    reviewer.gate.set()
    service = Sessions(Settings(_env_file=None), FakeVoice(), reviewer)
    created = await service.create(SETUP)
    item = service.end(created["id"])
    await item.task
    with pytest.raises(AppError, match="state_conflict"):
        service.end(item.id, retry=True)
    assert reviewer.calls == 1
    await service.close()


@pytest.mark.asyncio
async def test_provider_processing_then_done():
    class ProcessingVoice(FakeVoice):
        calls = 0

        async def details(self, cid):
            self.calls += 1
            result = await super().details(cid)
            result["status"] = "processing" if self.calls == 1 else "done"
            return result

    voice = ProcessingVoice()
    service = Sessions(Settings(_env_file=None), voice, FakeReview())
    item = service.end((await service.create(SETUP))["id"], partial=True)
    assert item.state == "transcript_pending"
    await item.task
    assert item.state == "reviewed" and item.partial and voice.calls == 2
    await service.close()


@pytest.mark.asyncio
async def test_fallback_association_conflict():
    class FallbackVoice(FakeVoice):
        async def connect(self):
            return {"signed_url": None, "conversation_id": None}

    service = Sessions(
        Settings(_env_file=None, elevenlabs_agent_id="fake"), FallbackVoice(), FakeReview()
    )
    a, b = await service.create(SETUP), await service.create(SETUP)
    await service.started(a["id"], "conv_test")
    with pytest.raises(AppError, match="conversation_conflict"):
        await service.started(a["id"], "conv_other")
    with pytest.raises(AppError, match="conversation_conflict"):
        await service.started(b["id"], "conv_test")
    await service.close()
