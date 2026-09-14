# someshwaran.dev

Personal site and resume manager, built with FastAPI and React. Maintains multiple resume
versions, exports to PDF/DOCX, and supports remote editing via an MCP server for LLM clients
like Claude.

See [CLAUDE.md](./CLAUDE.md) for the architecture, stack decisions, and phase plan. Phase 6
(Playwright E2E) is done — plus one piece of phase 8 pulled forward early (at the user's
request): the backend can serve the built frontend itself, one origin, one deploy
(`scripts/deploy.sh`). The MCP server (phase 7) and the rest of phase 8 (a CI-gated deploy
workflow) are still ahead.

## Layout

- `backend/` — FastAPI app (Python, managed with [uv](https://docs.astral.sh/uv/))
- `frontend/` — React + Vite + shadcn/ui (Radix primitives) + TanStack Router + TanStack Query
- `e2e/` — Playwright end-to-end tests against the real, built app

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

Config (DB URL, admin API key, etc.) comes from `app/core/config.py`, overridable via
`APP_`-prefixed env vars or a `backend/.env` file — the same settings both the app and
Alembic's `env.py` read, so migrations always target the database the app actually uses.

### Auth

One shared mechanism (`app/core/security.py`) guards both the admin web routes and, from
phase 7, the MCP server — not two separate systems. It's a single static API key, since this
is a personal, single-admin site rather than a multi-user one:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"  # paste into APP_ADMIN_API_KEY
```

Every route under `/api/admin/*` requires `Authorization: Bearer <key>`.

### Resume API

- `GET /api/resumes/default` — the current default resume, public, no auth (404 until one is set)
- `GET /api/resumes/default/export.pdf` / `.docx` — same, as a download
- `POST /api/admin/resumes` — create
- `GET /api/admin/resumes` — list (summaries)
- `GET|PATCH|DELETE /api/admin/resumes/{id}` — read / partial update / delete
- `POST /api/admin/resumes/{id}/clone` — deep copy, never defaulted
- `POST /api/admin/resumes/{id}/set-default` — mark as the one default, atomically unsetting any other
- `GET /api/admin/resumes/{id}/export.pdf` / `.docx` — export any resume, not just the default

All PDF/DOCX output — public and admin alike — renders through the single pipeline in
`app/services/export_service.py`, per CLAUDE.md's "one schema, one renderer" principle: there
is exactly one place resume content becomes a document per format.

### CORS

The frontend is served from its own origin, so the browser needs an explicit allowlist:
`cors_allowed_origins` (`APP_CORS_ALLOWED_ORIGINS`, comma-separated) defaults to the Vite dev
server, `http://localhost:5173`. Add the deployed frontend's origin once phase 8 picks one.

## Frontend

```bash
cd frontend
cp .env.example .env.local   # point VITE_API_BASE_URL at the backend, e.g. http://localhost:8000
npm install
npm run lint          # eslint
npm run format:check  # prettier
npm run typecheck     # tsc
npm run test          # vitest
npm run dev           # run locally
```

- `/` — public resume page: renders the current default resume (`GET /api/resumes/default`)
  with PDF/DOCX download links. Shows a plain message, not an error, when no default is set yet.
- `/admin/login` — paste the backend's `APP_ADMIN_API_KEY`; verified against `GET
  /api/admin/whoami` before it's saved to `localStorage`. Every admin page clears a key the
  moment a request 401s (revoked/wrong) and redirects back here.
- `/admin` — resume list: create, clone, set default, export, delete.
- `/admin/resumes/new` / `/admin/resumes/:id` — the resume editor — one form for every section
  (personal info, skills, experience, projects, education, certifications), each repeatable
  section with its own add/remove rows. Saving always replaces each nested collection wholesale
  (matching `resume_service.update_resume`'s semantics), not a per-row PATCH.

Nothing here builds its own auth system — `src/lib/api.ts` is the one place the admin API key is
read from `localStorage` and attached as `Authorization: Bearer <key>`, same mechanism as the
backend's `require_admin` (see CLAUDE.md's Auth section).

### Frontend architecture

- **Routing** — `src/router.tsx`, TanStack Router with a code-based route tree (not file-based:
  no codegen step or generated file needed for six routes). Auth is enforced at the route level,
  not per-page: the `/admin` layout route's `beforeLoad` redirects to `/admin/login` when no key
  is stored, and `/admin/login`'s own `beforeLoad` redirects the other way when one already is.
- **Server state** — `src/lib/queries.ts`, TanStack Query hooks over the plain fetch functions in
  `api.ts`. The `QueryClient` (`src/lib/queryClient.ts`) centralizes 401 handling in one
  `queryCache`/`mutationCache` `onError`, instead of every page repeating the same try/catch.
- **UI primitives** — shadcn/ui components built on Radix (not shadcn's newer Base UI option):
  Radix is what's already proven out here since phase 1, and Base UI is still pre-1.0.
- Shadcn's own CLI can't reach `ui.shadcn.com` from this network, so `src/components/ui/*.tsx`
  are hand-authored to match its canonical "new-york" output rather than generated.

### Deploying (backend + frontend, one origin)

```bash
./scripts/deploy.sh
```

Builds the frontend, copies it into `backend/frontend_dist/`, then runs `fastapi deploy` from
`backend/`. `app/main.py` serves it via FastAPI's own `app.frontend()` (checked only after every
real `/api/*` and `/health` route — it can never shadow them), falling back to `index.html` for
client-side routes so a hard refresh on `/admin/login` works. `backend/frontend_dist/` is
gitignored (it's a build output) but explicitly un-ignored in `.fastapicloudignore`, which takes
precedence for `fastapi deploy` — see that file. Local dev still runs the two apps separately
(`npm run dev` + `uv run fastapi dev`) on different ports, which is what the CORS config above is
for; nothing here needs it once same-origin in production.

## E2E

```bash
cd e2e
npm install
npm test               # builds the frontend, starts the real backend, runs the suite
npm run format:check   # prettier
```

`npm test` drives the actual app: `run-server.sh` builds `frontend/`, copies the build into
`backend/frontend_dist/` (same mechanism as `scripts/deploy.sh`), and starts `uvicorn` against a
disposable temp SQLite file — Playwright's `webServer` config spawns and health-checks it
automatically, so there's nothing to start by hand first. Tests run against one shared app
instance with `workers: 1`, since the suite exercises real global state (in particular, the
single "default resume" flag) rather than mocking the backend.

- `tests/admin-auth.spec.ts` — sign-in/redirect flows (no key, wrong key, correct key)
- `tests/resume-journey.spec.ts` — one continuous journey (`test.step` per stage, not independent
  tests, since each stage depends on the previous one's state): create a resume, confirm it isn't
  public yet, set it default, confirm the public page now renders it, clone it, delete the clone,
  delete the original, confirm the public page is empty again

e2e has no eslint/typecheck of its own — it's a test suite, not application code — but format
consistency is still enforced (prettier, matching frontend's style).

## Pre-commit

A single [pre-commit](https://pre-commit.com/) config at the repo root covers all three
directories (ruff/mypy for Python, eslint/prettier for `frontend/`, prettier for `e2e/`):

```bash
pre-commit install
pre-commit run --all-files
```

## CI

Every pull request runs lint + typecheck + unit tests for both `backend/` and `frontend/`. E2E
(Playwright) runs only on merge to `main`, per CLAUDE.md's testing bar — it drives the real app
rather than mocks, so it's slower and shares mutable state across the suite, which makes it a
poor fit for running on every PR push. See `.github/workflows/ci.yml`. The deploy workflow lands
in phase 8.
