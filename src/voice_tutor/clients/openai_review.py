import json

import httpx2 as httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from voice_tutor.config import ROOT, Settings
from voice_tutor.domain import AppError, Review, Setup, Turn


class OpenAIReview:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self.model = settings.openai_review_model
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.review_timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )
        self.prompt = (ROOT / "prompts/review_system_prompt.md").read_text()

    async def review(self, setup: Setup, turns: list[Turn]) -> Review:
        try:
            response = await self.client.responses.parse(
                model=self.model,
                store=False,
                max_output_tokens=4000,
                text_format=Review,
                input=[
                    {"role": "system", "content": self.prompt},
                    {
                        "role": "user",
                        "content": "INPUT DATA\n"
                        + json.dumps(
                            {
                                "setup": setup.model_dump(),
                                "transcript": [t.model_dump() for t in turns],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
        except APITimeoutError:
            raise AppError(
                "review_timeout",
                "Review timed out. Explicit retry may repeat the request.",
                retryable=True,
            ) from None
        except APIConnectionError:
            raise AppError(
                "provider_unavailable",
                "OpenAI could not be reached. Retry may repeat a request.",
                retryable=True,
            ) from None
        except APIStatusError as exc:
            error = self.status_error(exc)
            error.upstream_status = exc.status_code
            raise error from None
        except (ValidationError, ValueError):
            raise AppError(
                "review_incomplete", "Review output could not be validated.", retryable=True
            ) from None
        for output in response.output:
            if output.type == "message" and any(
                content.type == "refusal" for content in output.content
            ):
                raise AppError(
                    "review_refused", "OpenAI declined this review. Try a new conversation."
                )
        if response.status != "completed" or response.output_parsed is None:
            raise AppError(
                "review_incomplete", "OpenAI returned an incomplete review.", retryable=True
            )
        return response.output_parsed

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def status_error(exc: APIStatusError) -> AppError:
        if exc.status_code in (401, 403):
            return AppError(
                "provider_auth_failed", "Check OpenAI key permissions and model access."
            )
        # Inspect only machine-readable categories; never expose the provider message/body.
        body = exc.body if isinstance(exc.body, dict) else {}
        error = body.get("error", body)
        error = error if isinstance(error, dict) else {}
        if error.get("code") == "insufficient_quota" or error.get("type") == "insufficient_quota":
            return AppError(
                "review_quota_exceeded",
                "OpenAI API quota is unavailable. Check API billing, credits, and the usage "
                "limit for the project associated with this key. ChatGPT subscription access "
                "does not supply API credits. Once resolved, retry this review.",
                retryable=True,
            )
        if exc.status_code == 429:
            return AppError(
                "review_rate_limited",
                "OpenAI temporarily rate-limited the review. Wait briefly, then retry.",
                retryable=True,
            )
        if exc.status_code == 404:
            return AppError(
                "review_model_unavailable",
                "The configured OpenAI review model was not found or is unavailable to this "
                "API project. Check OPENAI_REVIEW_MODEL and project model access.",
            )
        if exc.status_code in (400, 422):
            return AppError(
                "review_request_invalid",
                "OpenAI rejected the review request format. Check that the configured model "
                "supports Responses structured output and the review schema is compatible.",
            )
        return AppError(
            "provider_unavailable",
            "OpenAI is unavailable. Retry later if the problem is temporary.",
            retryable=exc.status_code >= 500,
        )
