"""One deliberate paid review request, using synthetic speech only; never print provider output."""

import asyncio

from voice_tutor.clients.openai_review import OpenAIReview
from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Setup
from voice_tutor.services.review import normalize, validate_evidence


async def main() -> None:
    settings = Settings()
    if not settings.openai_api_key.get_secret_value() or not settings.openai_review_model:
        print("Set OPENAI_API_KEY and OPENAI_REVIEW_MODEL in local .env first.")
        raise SystemExit(1)
    client = OpenAIReview(settings)
    try:
        setup = Setup(
            target_language="English", native_language="Spanish", level="B1", topic="Shopping"
        )
        turns = normalize(
            [
                {"role": "agent", "message": "What did you do yesterday?"},
                {"role": "user", "message": "Yesterday I go to the market."},
            ]
        )
        result = validate_evidence(await client.review(setup, turns), turns)
        print(
            f"Structured review and evidence validation passed ({len(result.mistakes)} corrections)."
        )
    except AppError as exc:
        print(f"{exc.code}: {exc.message}")
        raise SystemExit(1) from None
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
