# someshwaran.dev

Personal site and resume manager, built with FastAPI and React. Maintains multiple resume
versions, exports to PDF/DOCX, and supports remote editing via an MCP server for LLM clients
like Claude.

See [CLAUDE.md](./CLAUDE.md) for the architecture, stack decisions, and phase plan. This repo
is currently at phase 2 (data model + migrations + CRUD service) — no API/auth/frontend
wiring to the data yet.

## Layout

- `backend/` — FastAPI app (Python, managed with [uv](https://docs.astral.sh/uv/))
- `frontend/` — React + Vite + shadcn/ui app

## Backend

```bash
cd backend
uv sync --dev                   # install deps
uv run ruff check .             # lint
uv run ruff format --check .    # format check
uv run mypy app                 # typecheck
uv run pytest                   # unit + integration tests
uv run alembic upgrade head     # apply migrations (creates ./data/app.db)
uv run alembic revision --autogenerate -m "..."  # after changing a model
uv run fastapi dev app/main.py  # run locally
```

Config (DB URL, etc.) comes from `app/core/config.py`, overridable via `APP_`-prefixed env
vars or a `backend/.env` file — the same settings both the app and Alembic's `env.py` read,
so migrations always target the database the app actually uses.

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
