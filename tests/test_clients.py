import json

import httpx
import httpx2
import pytest

from voice_tutor.clients.elevenlabs import ElevenLabs
from voice_tutor.clients.openai_review import OpenAIReview
from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Review, Setup
from voice_tutor.services.review import normalize

SETUP = Setup(target_language="English", native_language="Spanish", level="B1", topic="Travel")


@pytest.mark.asyncio
async def test_elevenlabs_signed_url_and_details():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["xi-api-key"] == "synthetic-key"
        if request.url.path.endswith("get-signed-url"):
            assert request.url.params["include_conversation_id"] == "true"
            return httpx.Response(
                200,
                json={
                    "signed_url": "wss://api.elevenlabs.io/test?signature=synthetic",
                    "conversation_id": "conv_test",
                },
            )
        return httpx.Response(
            200,
            json={
                "conversation_id": "conv_test",
                "agent_id": "agent_test",
                "status": "done",
                "transcript": [],
            },
        )

    client = ElevenLabs(
        Settings(
            _env_file=None, elevenlabs_api_key="synthetic-key", elevenlabs_agent_id="agent_test"
        ),
        httpx.MockTransport(handler),
    )
    assert (await client.connect())["conversation_id"] == "conv_test"
    assert (await client.details("conv_test"))["status"] == "done"
    assert len(calls) == 2
    await client.close()


@pytest.mark.asyncio
async def test_elevenlabs_auth_errors_are_safe():
    client = ElevenLabs(
        Settings(_env_file=None),
        httpx.MockTransport(
            lambda request: httpx.Response(401, json={"detail": "synthetic-private-payload"})
        ),
    )
    with pytest.raises(AppError) as exc:
        await client.connect()
    assert exc.value.code == "provider_auth_failed"
    assert not exc.value.retryable
    assert "synthetic-private-payload" not in str(exc.value)
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["success", "refusal", "incomplete", "auth"])
async def test_openai_structured_response_contract(kind):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["store"] is False
        assert body["model"] == "synthetic-model"
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["strict"] is True
        assert "INPUT DATA" in body["input"][1]["content"]
        if kind == "auth":
            return httpx2.Response(
                401,
                json={
                    "error": {"message": "private provider text", "type": "authentication_error"}
                },
            )
        review = Review(
            schema_version="1",
            summary="Bien hecho.",
            mistakes=[],
            new_vocabulary=[],
            suggested_next_topics=["Food", "Travel", "Family"],
        )
        content = (
            {"type": "refusal", "refusal": "No."}
            if kind == "refusal"
            else {"type": "output_text", "text": review.model_dump_json(), "annotations": []}
        )
        return httpx2.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "synthetic-model",
                "status": "incomplete" if kind == "incomplete" else "completed",
                "incomplete_details": {"reason": "max_output_tokens"}
                if kind == "incomplete"
                else None,
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [content],
                    }
                ],
            },
        )

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = OpenAIReview(
        Settings(
            _env_file=None, openai_api_key="synthetic-key", openai_review_model="synthetic-model"
        ),
        http,
    )
    # Metadata is irrelevant to this HTTP contract; avoid sandbox thread wakeup stalls.
    from openai._base_client import get_platform

    client.client._platform = get_platform()
    turns = normalize([{"role": "user", "message": "Hello."}])
    if kind == "success":
        assert (await client.review(SETUP, turns)).summary == "Bien hecho."
    else:
        with pytest.raises(AppError) as exc:
            await client.review(SETUP, turns)
        assert (
            exc.value.code
            == {
                "refusal": "review_refused",
                "incomplete": "review_incomplete",
                "auth": "provider_auth_failed",
            }[kind]
        )
    assert len(calls) == 1
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error,expected",
    [
        (429, {"code": "insufficient_quota"}, "review_quota_exceeded"),
        (429, {"type": "insufficient_quota", "code": None}, "review_quota_exceeded"),
        (429, {"code": "rate_limit_exceeded"}, "review_rate_limited"),
        (404, {"code": "model_not_found"}, "review_model_unavailable"),
        (400, {"code": "invalid_json_schema"}, "review_request_invalid"),
        (503, {"code": "server_error"}, "provider_unavailable"),
    ],
)
async def test_review_errors_are_actionable_and_safe(status, error, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(
            status,
            json={
                "error": {
                    **error,
                    "message": "synthetic-private-key-and-transcript",
                }
            },
        )

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = OpenAIReview(
        Settings(
            _env_file=None, openai_api_key="synthetic-key", openai_review_model="synthetic-model"
        ),
        http,
    )
    from openai._base_client import get_platform

    client.client._platform = get_platform()
    with pytest.raises(AppError) as exc:
        await client.review(SETUP, normalize([{"role": "user", "message": "Hello."}]))
    assert exc.value.code == expected
    assert exc.value.upstream_status == status
    assert exc.value.retryable == (status in (429, 503))
    assert "synthetic-private-key-and-transcript" not in exc.value.message
    assert len(calls) == 1
    await client.close()
