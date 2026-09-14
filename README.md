# someshwaran.dev

Personal site and resume manager, built with FastAPI and React. Maintains multiple resume
versions, exports to PDF/DOCX, and supports remote editing via an MCP server for LLM clients
like Claude.

See [CLAUDE.md](./CLAUDE.md) for the architecture, stack decisions, and phase plan. This repo
is currently at phase 1 (scaffolding) — no real features yet, just a green CI pipeline on a
minimal skeleton.

## Layout

- `backend/` — FastAPI app (Python, managed with [uv](https://docs.astral.sh/uv/))
- `frontend/` — React + Vite + shadcn/ui app

## Backend

```bash
cd backend
uv sync --dev        # install deps
uv run ruff check .  # lint
uv run mypy app      # typecheck
uv run pytest        # unit tests
uv run fastapi dev app/main.py  # run locally
```

## Frontend

```bash
cd frontend
npm install
npm run lint          # eslint
npm run format:check  # prettier
npm run typecheck     # tsc
npm run test          # vitest
npm run dev           # run locally
```

## Pre-commit

A single [pre-commit](https://pre-commit.com/) config at the repo root covers both languages
(ruff/mypy for Python, eslint/prettier for JS/TS):

```bash
pre-commit install
pre-commit run --all-files
```

## CI

Every pull request runs lint + typecheck + unit tests for both `backend/` and `frontend/`
(see `.github/workflows/ci.yml`). E2E (Playwright) and deploy workflows land in later phases.
