export PATH := $(CURDIR)/.tools/node/bin:$(PATH)
export UV_CACHE_DIR ?= /tmp/voice-tutor-uv
export UV_LINK_MODE := copy
export npm_config_cache := /tmp/voice-tutor-npm
.PHONY: setup build-web run serve lint types test check
setup:
	uv sync --locked
	npm --prefix frontend ci
	$(MAKE) build-web
	@test -f .env || install -m 600 .env.example .env
build-web:
	npm --prefix frontend run build
run:
	uv run uvicorn voice_tutor.main:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log
serve:
	uv run uvicorn voice_tutor.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
types:
	uv run mypy src scripts
	npm --prefix frontend run typecheck
test:
	uv run pytest -q
check: lint types test build-web
.PHONY: install-node probe-review
install-node:
	bash scripts/install-node.sh
probe-review:
	uv run python scripts/probe_review.py
