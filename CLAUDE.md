# Decibel Python SDK — Claude Code Instructions

## Pre-commit Checklist

Before EVERY commit, run the full CI pipeline and verify all steps pass:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -k "not testnet"
```

Or equivalently: `make all`

If `ruff format --check` fails, run `uv run ruff format src tests` to fix.

Do NOT commit if any of these fail.

## Project Structure

- `src/decibel/` — SDK source code
- `src/decibel/read/` — Read-only API readers (REST + WebSocket subscriptions)
- `src/decibel/write/` — On-chain transaction writers (async + sync)
- `tests/api_resources/` — Spec compliance and integration tests
- `docs/SPEC*.md` — API specification documents

## Testing

- Unit/spec tests (no network): `uv run pytest -k "not testnet"`
- Integration tests (needs API key): `DECIBEL_API_KEY=<key> uv run pytest tests/api_resources/test_testnet_integration.py -v`
- Integration tests auto-skip without `DECIBEL_API_KEY`

## Code Style

- Line length: 100 (enforced by ruff)
- Format: `uv run ruff format src tests`
- Lint: `uv run ruff check src tests` (auto-fix with `--fix`)
- Type checking: `uv run pyright` (strict mode on `src/`)
- Python 3.11+, async-first with sync wrappers
- Pydantic v2 for all data models
