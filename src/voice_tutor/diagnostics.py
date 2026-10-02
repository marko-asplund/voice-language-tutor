"""Explicit provider checks sharing the app's clients, schemas, and evidence validation."""

import argparse
import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from voice_tutor.clients.elevenlabs import ElevenLabs
from voice_tutor.clients.openai_review import OpenAIReview
from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Setup
from voice_tutor.services.review import normalize, validate_evidence
from voice_tutor.services.sessions import ReviewClient, VoiceClient

Provider = Literal["openai", "elevenlabs", "all"]


@dataclass
class Result:
    name: str
    endpoint: str
    ok: bool
    code: str
    message: str
    elapsed_ms: int = 0
    upstream_status: int | None = None

    def line(self) -> str:
        status = f" HTTP {self.upstream_status}" if self.upstream_status is not None else ""
        return (
            f"{'PASS' if self.ok else 'FAIL'} {self.name}{status} "
            f"[{self.code}] ({self.elapsed_ms} ms) {self.endpoint}: {self.message}"
        )


async def measure(
    name: str, endpoint: str, call: Callable[[], Awaitable[str]], timeout: float
) -> Result:
    began = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            detail = await call()
        return Result(
            name, endpoint, True, "ok", detail, int((time.monotonic() - began) * 1000), 200
        )
    except AppError as exc:
        return Result(
            name,
            endpoint,
            False,
            exc.code,
            exc.message,
            int((time.monotonic() - began) * 1000),
            exc.upstream_status,
        )
    except TimeoutError:
        return Result(
            name,
            endpoint,
            False,
            "diagnostic_timeout",
            "Check timed out; an explicit retry may repeat the upstream request.",
            int((time.monotonic() - began) * 1000),
        )
    except Exception:  # noqa: BLE001 — no raw SDK payloads or tracebacks in diagnostic output
        return Result(
            name,
            endpoint,
            False,
            "diagnostic_failed",
            "Check failed without a usable provider response.",
            int((time.monotonic() - began) * 1000),
        )


async def diagnose(
    settings: Settings,
    provider: Provider = "all",
    live: bool = False,
    conversation_id: str | None = None,
    voice: VoiceClient | None = None,
    reviewer: ReviewClient | None = None,
) -> list[Result]:
    results: list[Result] = []
    for selected in ("openai", "elevenlabs"):
        if provider not in (selected, "all"):
            continue
        required = (
            (
                ("OPENAI_API_KEY", settings.openai_api_key.get_secret_value()),
                ("OPENAI_REVIEW_MODEL", settings.openai_review_model),
            )
            if selected == "openai"
            else (
                ("ELEVENLABS_API_KEY", settings.elevenlabs_api_key.get_secret_value()),
                ("ELEVENLABS_AGENT_ID", settings.elevenlabs_agent_id),
            )
        )
        missing = [name for name, value in required if not value]
        results.append(
            Result(
                selected + " configuration",
                "local configuration",
                not missing,
                "missing_configuration" if missing else "configured",
                "Missing: " + ", ".join(missing)
                if missing
                else "Required settings present (values hidden; access not yet tested).",
            )
        )
        if missing or not live:
            continue
        if selected == "openai":
            client = reviewer or OpenAIReview(settings)

            async def check_review(client: ReviewClient = client) -> str:
                setup = Setup(
                    target_language="English",
                    native_language="English",
                    level="C1",
                    topic="Shopping",
                )
                turns = normalize(
                    [
                        {"role": "agent", "message": "What did you do yesterday?"},
                        {"role": "user", "message": "Yesterday I go to the market."},
                    ]
                )
                result = validate_evidence(await client.review(setup, turns), turns)
                return (
                    f"Structured review and evidence passed ({len(result.mistakes)} corrections)."
                )

            try:
                results.append(
                    await measure(
                        "OpenAI review",
                        "POST /v1/responses",
                        check_review,
                        settings.review_timeout_seconds,
                    )
                )
            finally:
                await client.close()
        else:
            voice_client = voice or ElevenLabs(settings)

            async def check_connection(voice_client: VoiceClient = voice_client) -> str:
                await voice_client.connect()
                return "Signed URL received; no microphone or voice connection started."

            async def check_transcript(voice_client: VoiceClient = voice_client) -> str:
                details = await voice_client.details(conversation_id or "")
                if details.get("agent_id") != settings.elevenlabs_agent_id:
                    raise AppError(
                        "conversation_conflict", "Conversation belongs to another agent."
                    )
                if details.get("status") != "done":
                    raise AppError("transcript_not_ready", "Conversation is not finalized.")
                turns = normalize(details.get("transcript", []))
                return f"Final transcript normalized ({len(turns)} turns; contents hidden)."

            try:
                results.append(
                    await measure(
                        "ElevenLabs connection",
                        "GET /v1/convai/conversation/get-signed-url",
                        check_connection,
                        35,
                    )
                )
                if conversation_id:
                    results.append(
                        await measure(
                            "ElevenLabs transcript",
                            "GET /v1/convai/conversations/{conversation_id}",
                            check_transcript,
                            35,
                        )
                    )
            finally:
                await voice_client.close()
    return results


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe provider diagnostics. Default: config only.")
    parser.add_argument("--provider", choices=["openai", "elevenlabs", "all"], default="all")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call real providers; OpenAI makes one potentially paid synthetic review.",
    )
    parser.add_argument(
        "--conversation-id", help="Also fetch an existing finalized ElevenLabs transcript."
    )
    args = parser.parse_args(argv)
    if args.conversation_id and (not args.live or args.provider == "openai"):
        parser.error("--conversation-id requires --live with elevenlabs or all")
    if args.conversation_id and not re.fullmatch(r"[a-zA-Z0-9_-]{1,150}", args.conversation_id):
        parser.error("Invalid conversation ID format")
    for name in ("httpx", "httpx2", "httpcore", "httpcore2", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        # Check selected providers independently, even when live app configuration is incomplete.
        # --live still uses real clients; this override never substitutes fake calls.
        settings = Settings(app_mode="fake")
    except ValidationError:
        print(
            "FAIL configuration [invalid_configuration]: Check .env field formats and local origin."
        )
        return 1
    print(
        "Live checks enabled; OpenAI may incur an API charge."
        if args.live
        else "Configuration only; no provider calls. Use --live to test access.",
        flush=True,
    )
    try:
        results = asyncio.run(diagnose(settings, args.provider, args.live, args.conversation_id))
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001 — CLI boundary; never print raw SDK exceptions
        print(
            "FAIL diagnostic [diagnostic_failed]: Could not complete checks; no provider payload displayed."
        )
        return 1
    for result in results:
        print(result.line())
    return 0 if all(result.ok for result in results) else 1
