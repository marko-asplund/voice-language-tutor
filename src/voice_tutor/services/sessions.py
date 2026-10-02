import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Review, Setup, Turn
from voice_tutor.services.review import normalize, validate_evidence

log = logging.getLogger(__name__)


class VoiceClient(Protocol):
    async def connect(self) -> dict[str, Any]: ...
    async def details(self, conversation_id: str) -> dict[str, Any]: ...
    async def close(self) -> None: ...


class ReviewClient(Protocol):
    async def review(self, setup: Setup, turns: list[Turn]) -> Review: ...
    async def close(self) -> None: ...


@dataclass
class Session:
    setup: Setup
    id: str = field(default_factory=lambda: str(uuid4()))
    created: float = field(default_factory=time.monotonic)
    conversation_id: str | None = None
    state: str = "connecting"
    transcript: list[Turn] = field(default_factory=list)
    review: Review | None = None
    error: AppError | None = None
    partial: bool = False
    task: asyncio.Task[None] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "setup": self.setup.model_dump(),
            "transcript": [t.model_dump() for t in self.transcript],
            "review": self.review.model_dump() if self.review else None,
            "partial": self.partial,
            "error": {
                "code": self.error.code,
                "message": self.error.message,
                "retryable": self.error.retryable,
            }
            if self.error
            else None,
        }


class Sessions:
    def __init__(self, settings: Settings, voice: VoiceClient, reviewer: ReviewClient):
        self.settings, self.voice, self.reviewer = settings, voice, reviewer
        self.items: dict[str, Session] = {}
        self.association_lock = asyncio.Lock()

    def get(self, sid: str) -> Session:
        if sid not in self.items:
            raise AppError("session_not_found", "Session expired or the server restarted.", 404)
        return self.items[sid]

    async def create(self, setup: Setup) -> dict[str, Any]:
        now = time.monotonic()
        for sid, item in list(self.items.items()):
            if now - item.created > 7200 and (not item.task or item.task.done()):
                del self.items[sid]
        if len(self.items) >= 100:
            raise AppError("sessions_full", "Restart the local server to clear old sessions.", 409)
        descriptor = await self.voice.connect()
        session = Session(setup=setup, conversation_id=descriptor.get("conversation_id"))
        self.items[session.id] = session
        return {
            **session.public(),
            **descriptor,
            "mode": self.settings.app_mode,
            "dynamic_variables": setup.model_dump(),
        }

    async def started(self, sid: str, cid: str) -> Session:
        session = self.get(sid)
        if session.conversation_id and session.conversation_id != cid:
            raise AppError("conversation_conflict", "Conversation association conflicts.", 409)
        if session.state not in ("connecting", "active"):
            raise AppError("state_conflict", "Session has already ended.", 409)
        async with self.association_lock:
            if session.conversation_id and session.conversation_id != cid:
                raise AppError("conversation_conflict", "Conversation association conflicts.", 409)
            if session.state not in ("connecting", "active"):
                raise AppError("state_conflict", "Session has already ended.", 409)
            if not session.conversation_id:
                details = await self.voice.details(cid)
                if details.get("agent_id") != self.settings.elevenlabs_agent_id:
                    raise AppError(
                        "conversation_conflict", "Conversation belongs to another agent.", 409
                    )
                if any(s.conversation_id == cid for s in self.items.values() if s.id != sid):
                    raise AppError("conversation_conflict", "Conversation already associated.", 409)
                session.conversation_id = cid
        session.state = "active"
        return session

    def end(self, sid: str, partial: bool = False, retry: bool = False) -> Session:
        session = self.get(sid)
        if session.review or (session.task and not session.task.done()):
            return session
        if session.error and not retry:
            return session
        if retry and (not session.error or not session.error.retryable):
            raise AppError("state_conflict", "This session cannot be retried.", 409)
        if not session.conversation_id:
            raise AppError("connection_lost", "No conversation was established. Start again.", 409)
        session.partial = session.partial or partial
        session.error = None
        session.state = "transcript_pending"
        session.task = asyncio.create_task(self.finish(session))
        return session

    async def finish(self, session: Session) -> None:
        began = time.monotonic()
        try:
            if not session.transcript:
                async with asyncio.timeout(self.settings.transcript_wait_seconds):
                    delay = 1
                    while True:
                        details = await self.voice.details(session.conversation_id or "")
                        expected = (
                            "fake"
                            if self.settings.app_mode == "fake"
                            else self.settings.elevenlabs_agent_id
                        )
                        if details.get("agent_id") != expected:
                            raise AppError(
                                "conversation_conflict", "Agent association failed.", 409
                            )
                        if details.get("status") == "failed":
                            raise AppError("provider_unavailable", "Voice conversation failed.")
                        if details.get("status") == "done":
                            session.transcript = normalize(details.get("transcript", []))
                            break
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 8)
            session.state = "reviewing"
            async with asyncio.timeout(self.settings.review_timeout_seconds):
                result = await self.reviewer.review(session.setup, session.transcript)
            session.review = validate_evidence(result, session.transcript)
            session.state = "reviewed"
        except TimeoutError:
            code = (
                "transcript_timeout" if session.state == "transcript_pending" else "review_timeout"
            )
            session.error = AppError(
                code, "Timed out. Explicit retry may repeat a provider request.", retryable=True
            )
            session.state = "failed"
        except AppError as exc:
            session.error, session.state = exc, "failed"
        except Exception:  # noqa: BLE001 — background boundary; never log provider payloads
            session.error = AppError(
                "provider_unavailable", "Provider response could not be used.", retryable=True
            )
            session.state = "failed"
        finally:
            log.info(
                "session=%s stage=%s elapsed=%.1f code=%s",
                session.id,
                session.state,
                time.monotonic() - began,
                session.error.code if session.error else "ok",
            )

    async def close(self) -> None:
        tasks = [s.task for s in self.items.values() if s.task and not s.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.voice.close()
        await self.reviewer.close()
