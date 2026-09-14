# someshwaran.dev

Personal site + resume manager. Public-facing, will eventually be open-sourced.

## What this is
- Public site showing profile, projects, experience
- Resume management: multiple versions, one marked default, PDF/DOCX export
- Admin mode: create/clone/edit resumes, choose default
- Remote MCP server exposing the same actions to LLM clients

## Stack (decided, don't relitigate)
- Backend: FastAPI, SQLModel, SQLite (Alembic migrations from day one; may move to Postgres later, don't build around that assumption though)
- Frontend: React + Vite + shadcn/ui components
- E2E: Playwright, from day one, not bolted on later
- Pre-commit: unified `pre-commit` framework (ruff + mypy for Python, eslint + prettier for JS/TS) — one config, not two
- Hosting: FastAPI Cloud (`fastapi deploy`). Keep the app Docker-friendly regardless, as a fallback if FastAPI Cloud has gaps.

## Architecture principle
Resume content is modeled ONCE (personal_info, summary, skills, experience[], projects[], education[], certifications) and everything else — the public site page, PDF export, DOCX export, MCP tool responses — is a renderer over that single schema. Never duplicate resume content storage per output format.

## Testing bar (non-negotiable)
- Unit tests: backend services (DB mocked), frontend components in isolation
- Integration tests: FastAPI TestClient against a real temp SQLite DB
- E2E: Playwright against the running app
- Every PR: lint + typecheck + unit + integration must pass in CI before merge
- E2E runs on merge to main
- No feature is "done" without tests at the appropriate layer

## Auth
One auth mechanism (JWT or API key) shared by both the admin web routes and the MCP server. Don't build two separate auth systems.

## Phase plan (do not skip ahead or parallelize phases)
1. Scaffolding: repo structure, pre-commit, CI (lint+typecheck+unit) green on a near-empty app
2. Data model + Alembic migrations + CRUD service + unit/integration tests
3. Auth
4. Resume API: CRUD, clone, set-default, PDF/DOCX export
5. Frontend: public pages + admin pages (shadcn/ui components)
6. Playwright E2E flows
7. MCP server (reuses phase 3 auth)
8. Deploy to FastAPI Cloud (Dockerfile kept as fallback, deploy workflow gated on all checks)
9. Polish: docs, multiple templates, open-source prep

## Conventions
- Every feature: implementation + tests + docs in the same PR, not deferred
- Explain non-obvious decisions in code comments or commit messages, not just in chat
- Prefer small, reviewable commits over large batched ones
