import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints
from starlette.middleware.trustedhost import TrustedHostMiddleware

from voice_tutor.clients.fake import FakeReview, FakeVoice
from voice_tutor.config import ROOT, Settings
from voice_tutor.domain import AppError, Setup
from voice_tutor.services.sessions import ReviewClient, Sessions, VoiceClient


class Started(BaseModel):
    conversation_id: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,150}$")]


class End(BaseModel):
    partial: bool = False


def create_app(
    settings: Settings | None = None,
    voice: VoiceClient | None = None,
    reviewer: ReviewClient | None = None,
) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    for logger in ("httpx", "httpx2", "httpcore", "httpcore2", "openai"):
        logging.getLogger(logger).setLevel(logging.WARNING)
    if settings.app_mode == "fake":
        voice, reviewer = voice or FakeVoice(), reviewer or FakeReview()
    else:
        from voice_tutor.clients.elevenlabs import ElevenLabs
        from voice_tutor.clients.openai_review import OpenAIReview

        voice, reviewer = voice or ElevenLabs(settings), reviewer or OpenAIReview(settings)
    sessions = Sessions(settings, voice, reviewer)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await sessions.close()

    app = FastAPI(lifespan=lifespan)
    app.state.sessions = sessions
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def local_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        origin = request.headers.get("origin")
        allowed_origins = {settings.app_origin, "http://localhost:8000", "http://127.0.0.1:8000"}
        if (origin and origin not in allowed_origins) or (
            request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"code": "invalid_origin", "message": "Use the local app."}, 403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            status_code=exc.status,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.app_mode}

    @app.post("/api/sessions")
    async def create(setup: Setup) -> dict[str, object]:
        return await sessions.create(setup)

    @app.post("/api/sessions/{sid}/started")
    async def started(sid: str, body: Started) -> dict[str, object]:
        return (await sessions.started(sid, body.conversation_id)).public()

    @app.post("/api/sessions/{sid}/end", status_code=202)
    async def end(sid: str, body: End) -> dict[str, object]:
        return sessions.end(sid, partial=body.partial).public()

    @app.get("/api/sessions/{sid}")
    async def get(sid: str) -> dict[str, object]:
        return sessions.get(sid).public()

    @app.post("/api/sessions/{sid}/review/retry", status_code=202)
    async def retry(sid: str) -> dict[str, object]:
        return sessions.end(sid, retry=True).public()

    static = ROOT / "src/voice_tutor/web/static"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app
