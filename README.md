# someshwaran.dev

Personal site and resume manager, built with FastAPI and React. Maintains multiple resume
versions, exports to PDF/DOCX, and supports remote editing via an MCP server for LLM clients
like Claude.

See [CLAUDE.md](./CLAUDE.md) for the architecture, stack decisions, and phase plan. Phase 8
(deploy to FastAPI Cloud, gated on CI, with a Dockerfile kept as a fallback) is done. Phase 9
(polish, multiple templates, open-source prep) is still ahead.

## Layout

- `backend/` — FastAPI app (Python, managed with [uv](https://docs.astral.sh/uv/))
- `frontend/` — React + Vite + shadcn/ui (Radix primitives) + TanStack Router + TanStack Query
- `e2e/` — Playwright end-to-end tests against the real, built app
- `Dockerfile` — Docker fallback for FastAPI Cloud (see Deploying, below)

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

### MCP server

A remote MCP server (`app/mcp_server.py`, built on the official
[`mcp`](https://github.com/modelcontextprotocol/python-sdk) SDK's streamable HTTP transport)
exposes the same resume actions as the admin API above to LLM clients like Claude — every tool
is a thin wrapper over `app/services/resume_service.py`, the same service the REST routes call,
per CLAUDE.md's "one schema, one renderer" principle again: an MCP tool response is just another
renderer over the one underlying schema.

- Mounted at `/api/mcp/` (trailing slash — the bare path 307-redirects there), on the same origin
  and same admin API key as everything else. Point an MCP client's URL at
  `http://<host>/api/mcp/` with `Authorization: Bearer <key>`.
- Tools: `list_resumes`, `get_resume`, `get_default_resume`, `create_resume`, `update_resume`,
  `delete_resume`, `clone_resume`, `set_default_resume` — deliberately not PDF/DOCX export; a
  binary download is a poor fit for a tool result in a chat client, so that's left to the REST
  API and public site for now.
- Auth is still the one mechanism from `app/core/security.py`, just enforced a layer lower: the
  MCP server is a mounted Starlette app, not a set of FastAPI path operations, so there's no
  request to hang a `Depends(require_admin)` off of. `AdminBearerAuthMiddleware` wraps the mount
  instead, checking the same `is_valid_admin_key` function `require_admin` calls.
- `app/mcp_server.py`'s `build_mcp_server()` is a factory, not a module-level singleton: an
  `MCPServer`'s streamable-HTTP session manager can only be started once per instance, so
  `app/main.py`'s lifespan builds a fresh one on every app startup — see that function's
  docstring for why a singleton would break this app's own test suite (though never a real
  deployment, which only starts once per process).

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

#### CI-gated deploy

`.github/workflows/ci.yml`'s `deploy` job runs this same script on every push to `main`, gated
(via `needs:`) on the `backend`, `frontend`, and `e2e` jobs all succeeding first — a red or
skipped check never reaches FastAPI Cloud. It authenticates with two repo secrets instead of an
interactive `fastapi login` session:

```bash
cd backend
uv run fastapi login                    # opens a browser once, locally
uv run fastapi cloud apps list          # note the app's ID (FASTAPI_CLOUD_APP_ID)
uv run fastapi cloud tokens create --app-id <id>   # prints a deploy token (FASTAPI_CLOUD_TOKEN)
```

Set both as repository secrets under **Settings → Secrets and variables → Actions** — this is
the one manual, one-time step here that only the repo owner can do (an agent has no FastAPI
Cloud login to provision a token from). `uv run fastapi cloud ci print-workflow` prints FastAPI
Cloud's own canonical version of this job, for reference or if it ever needs regenerating.

#### Docker fallback

CLAUDE.md calls for staying Docker-friendly regardless of FastAPI Cloud, so the root `Dockerfile`
builds and serves the same app `scripts/deploy.sh` ships — frontend baked into
`backend/frontend_dist`, one image, one origin:

```bash
docker build -t someshwaran-dev .
docker run -p 8000:8000 -e APP_ADMIN_API_KEY=... -v app-data:/app/data someshwaran-dev
```

SQLite is a single file, so mount a volume (`/app/data`, matching the default
`APP_DATABASE_URL`) for anything but throwaway/local use. Alembic migrations still run at
process startup (`app/main.py`'s `lifespan`) — no separate migration step needed here either.

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
(Playwright) and the deploy to FastAPI Cloud both run only on merge to `main` — E2E per CLAUDE.md's
testing bar (it drives the real app rather than mocks, so it's slower and shares mutable state
across the suite, a poor fit for every PR push); deploy because `needs: [backend, frontend, e2e]`
means it only fires once every other job has actually succeeded on that same push — see the
"CI-gated deploy" section above. All four jobs live in the one `.github/workflows/ci.yml`.
