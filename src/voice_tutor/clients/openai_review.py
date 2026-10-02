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
            if exc.status_code in (401, 403):
                raise AppError(
                    "provider_auth_failed", "Check OpenAI key permissions and model access."
                ) from None
            raise AppError(
                "provider_unavailable",
                "OpenAI rejected the review; check model access or credits.",
                retryable=exc.status_code == 429 or exc.status_code >= 500,
            ) from None
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
