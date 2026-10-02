from typing import Any
from uuid import uuid4

from voice_tutor.domain import Review, Setup, Turn


class FakeVoice:
    async def connect(self) -> dict[str, Any]:
        return {"conversation_id": "fake-" + str(uuid4()), "signed_url": None}

    async def details(self, conversation_id: str) -> dict[str, Any]:
        return {
            "conversation_id": conversation_id,
            "agent_id": "fake",
            "status": "done",
            "transcript": [
                {"role": "agent", "message": "What did you do yesterday?"},
                {"role": "user", "message": "Yesterday I go to the market."},
            ],
        }

    async def close(self) -> None:
        pass


class FakeReview:
    async def review(self, setup: Setup, turns: list[Turn]) -> Review:
        return Review(
            schema_version="1",
            summary="Simulation: you practiced a short conversation.",
            mistakes=[],
            new_vocabulary=[],
            suggested_next_topics=["Weekend plans", "Food", "Travel"],
        )

    async def close(self) -> None:
        pass
