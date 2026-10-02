# Voice Language Tutor

Local personal language practice: ElevenLabs handles live voice; OpenAI prepares grounded text
reviews. SolidJS + TypeScript + Vite runs in the Windows browser, served by FastAPI directly in WSL.

## Isolated setup

Use Linux uv and make in WSL. Python 3.12 is managed by uv; application packages live in `.venv`.
Node is pinned in `.node-version` and installed **only** under ignored `.tools/node`; frontend
packages live in `frontend/node_modules`. Nothing installs system-wide, and no sudo is needed.
The existing uv-managed Python 3.12 interpreter is reused. Caches use `/tmp`.

```bash
cd /home/marko/code/voice-language-tutor
make install-node  # downloads/checks official pinned Node archive, repo-local
make setup         # locked Python/npm dependencies, web build, mode-600 .env if absent
make check
make serve
```

Open **http://localhost:8000** in your Windows browser. Default `APP_MODE=fake` is clearly labeled
simulation: no mic or provider calls. Click Start then End to exercise the sample transcript/review.
Stop the WSL process with Ctrl+C. `make run` enables development reload; `make serve` runs one
process on 127.0.0.1. The built frontend is served by FastAPI, so no separate frontend server is needed.

## Live voice and reviews

Follow [private-agent setup](docs/elevenlabs-setup.md), copy the tutor prompt into the ElevenLabs
dashboard, and choose an available OpenAI conversation model there. Put credentials **only** in the
ignored local `.env`, retaining mode 600. Never paste keys into chat, frontend source, Git, or logs.
Set `APP_MODE=live`, both provider keys, `ELEVENLABS_AGENT_ID`, and an `OPENAI_REVIEW_MODEL` that
supports Responses structured output. Restart the server. Missing live settings fail startup with
field names; simulation never silently switches to paid calls.

`make probe-review` deliberately makes one paid OpenAI text call on synthetic speech, validates
its structure/evidence, and prints only a safe result. Browser Start makes an ElevenLabs voice call;
End stops the SDK audio/mic, waits for finalized transcript, then requests an OpenAI review.

The initial implementation is verified offline; actual account access, a five-minute conversation,
patience tuning, mic release, and useful real reviews still require the [manual checks](docs/manual-checks.md).
See [PROGRESS.md](PROGRESS.md) for current verification status.

Audio goes directly to ElevenLabs. Review text goes to OpenAI with `store=false`; vendor retention
is governed by their settings/policies. The app does not record audio or save personal history.
Sessions remain in memory for up to two hours and are cleared on process restart. Browser reload
loses the current view. Transcripts over 24,000 characters or turns over 1,000 characters are rejected
in this version. Transcript polling and review requests have bounded deadlines. Explicit retry can
repeat an upstream request that timed out. Refusals and credential errors are not automatically retried.

## Checks and development

- `make check`: Ruff lint/format, Python mypy, TypeScript checker, offline pytest, frontend build.
- `make test`: fake clients and mocked provider HTTP contracts; no live calls.
- `make build-web`: rebuild generated/ignored assets.
- `make lint`, `make types`: individual checks.

Setup/voice/review signals live in `frontend/src/App.tsx`; the official voice SDK is wrapped in
`voice.ts`. Session tasks and evidence validation live under `src/voice_tutor/services`; external
calls are small fixed-stack clients. Only `config.py` reads application environment values.

Read the [refined plan](voice-language-tutor-plan-refined.md) for scope and design. The external
Downloads source and [original snapshot](docs/source/voice-language-tutor-plan-original.md) remain
unchanged; [provenance](docs/source/provenance.json) records their hash. No containers, cloud hosting,
accounts, alternative voice providers, budget systems, or production infrastructure are included.
