import pytest

from voice_tutor.clients.fake import FakeReview, FakeVoice
from voice_tutor.config import Settings
from voice_tutor.diagnostics import diagnose, measure
from voice_tutor.domain import AppError


class Voice(FakeVoice):
    calls = 0
    closed = False

    async def connect(self):
        self.calls += 1
        return await super().connect()

    async def details(self, cid):
        self.calls += 1
        return await super().details(cid)

    async def close(self):
        self.closed = True


class Reviewer(FakeReview):
    calls = 0
    closed = False

    async def review(self, setup, turns):
        self.calls += 1
        return await super().review(setup, turns)

    async def close(self):
        self.closed = True


def settings(**kwargs):
    return Settings(
        _env_file=None,
        openai_api_key="synthetic-secret",
        openai_review_model="synthetic-model",
        elevenlabs_api_key="synthetic-secret",
        elevenlabs_agent_id="fake",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_configuration_only_never_calls_providers():
    voice, reviewer = Voice(), Reviewer()
    results = await diagnose(settings(), voice=voice, reviewer=reviewer)
    assert all(result.ok for result in results)
    assert voice.calls == reviewer.calls == 0
    assert "synthetic-secret" not in "\n".join(result.line() for result in results)


@pytest.mark.asyncio
async def test_live_checks_share_clients_and_hide_payloads():
    voice, reviewer = Voice(), Reviewer()
    results = await diagnose(
        settings(), live=True, conversation_id="conv_test", voice=voice, reviewer=reviewer
    )
    assert all(result.ok for result in results)
    assert voice.calls == 2 and reviewer.calls == 1
    assert voice.closed and reviewer.closed
    output = "\n".join(result.line() for result in results)
    assert "HTTP 200" in output and "POST /v1/responses" in output
    assert "conv_test" not in output and "Yesterday" not in output and "wss:" not in output


@pytest.mark.asyncio
async def test_only_selected_provider_configuration_is_required():
    reviewer = Reviewer()
    config = Settings(
        _env_file=None, openai_api_key="synthetic-secret", openai_review_model="synthetic-model"
    )
    results = await diagnose(config, provider="openai", live=True, reviewer=reviewer)
    assert all(result.ok for result in results) and reviewer.calls == 1
    results = await diagnose(Settings(_env_file=None), provider="openai", live=True)
    assert len(results) == 1 and results[0].code == "missing_configuration"


@pytest.mark.asyncio
async def test_upstream_status_and_safe_failure_reporting():
    class QuotaReview(Reviewer):
        async def review(self, setup, turns):
            raise AppError("review_quota_exceeded", "Check API credits.", upstream_status=429)

    client = QuotaReview()
    results = await diagnose(settings(), provider="openai", live=True, reviewer=client)
    assert not results[-1].ok and results[-1].upstream_status == 429
    assert results[-1].code == "review_quota_exceeded" and client.closed


@pytest.mark.asyncio
async def test_unexpected_errors_never_expose_payloads():
    async def unsafe():
        raise RuntimeError("synthetic-secret and private transcript")

    result = await measure("test", "synthetic endpoint", unsafe, 1)
    assert not result.ok and result.code == "diagnostic_failed"
    assert "synthetic-secret" not in result.line()


@pytest.mark.asyncio
async def test_transcript_agent_is_verified():
    class WrongAgent(Voice):
        async def details(self, cid):
            result = await super().details(cid)
            result["agent_id"] = "another-agent"
            return result

    results = await diagnose(
        settings(),
        provider="elevenlabs",
        live=True,
        conversation_id="conv_test",
        voice=WrongAgent(),
    )
    assert results[-1].code == "conversation_conflict"
