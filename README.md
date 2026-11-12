# someshwaran.dev

Personal site and resume manager, built with FastAPI and React. Maintains multiple resume
versions, exports to PDF/DOCX, and supports remote editing via an MCP server for LLM clients
like Claude.

See [CLAUDE.md](./CLAUDE.md) for the architecture, stack decisions, and phase plan. Phase 8
(deploy to FastAPI Cloud, gated on CI, with a Dockerfile kept as a fallback) is done. Phase 9
(polish, multiple templates, open-source prep) is still ahead.

## Versions

Developed, tested and deployed on **Python 3.15** and **Node 26** (the current LTS), and the
Docker image uses the same (`python:3.15-slim`, `node:26-slim`). The oldest Python the backend
supports is **3.11** (`requires-python`), and CI runs the whole backend suite on it as its own job,
so something that only works on a newer Python can't slip in. `ruff` and `mypy` are pinned to 3.11
syntax for the same reason. `backend/.python-version` is what `uv` (and the FastAPI Cloud build)
installs.

PyYAML (pulled in by uvicorn) has no Python 3.15 wheel yet, so `uv sync` builds it from source on
3.15. That works without a C compiler too — it falls back to the pure-Python implementation, which
is all uvicorn's log config needs — and goes away once PyYAML publishes 3.15 wheels.

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

**Database.** Local dev and most tests use SQLite (`sqlite:///./data/app.db`, nothing to set up).
**Production uses Postgres**: a SQLite file lives on the container's filesystem, which every
deploy replaces, so anything written there is lost on the next deploy. The app reads
`APP_DATABASE_URL`, or the plain `DATABASE_URL` that FastAPI Cloud's Neon integration injects
(`APP_DATABASE_URL` wins if both are set); `postgres://` / `postgresql://` URLs are accepted as
given and routed to psycopg 3. Neon scales to zero when idle, so the first request after a quiet
spell can be slower. Migrations run at startup under a Postgres advisory lock, so several
instances starting at once after a deploy don't race on first-time table creation.

**Resume exports.** PDF and DOCX are drawn from one display model
(`app/services/resume_document.py`: formatted dates, safe links, bullets gathered under their
sub-headings) by a *template* (`app/services/templates/`). The default and currently only
template is `ats` — an ATS-plain layout: A4, one column, standard fonts, conventional section
names, real selectable text, dates right-aligned, clickable email/LinkedIn/GitHub/website links
(only `http`, `https` and `mailto` are ever linked), no tables, images or icons. Pick a template
with `?template=ats` on any `export.pdf` / `export.docx` route; an unknown name is a 422. To add
a template, add its two modules, its name to `Template` in `export_service.py`, and register it.
Note: layout-aware PDF text extractors return each role and its dates as one line, while
reading-order ones return the dates as the very next text; if dates must never be separated from
the role, put them inline instead of right-aligned.

A resume has a `headline` (the line under the name, e.g. "Senior SDET | Test Automation |
Python") and each experience's `highlights` are `{text, group}` items: consecutive bullets with
the same `group` render under that sub-heading. Plain-string highlights (the original format) are
still accepted everywhere and read as ungrouped. In the admin editor, type bullets one per line;
a line starting with `##` names a group for the bullets after it, and a bare `##` ends the group.

**Data guarantees.** List sections (skills, experience, ...) are rendered in a stored
`order_index`, assigned from input order on create, update and clone, with `id` as a tiebreak —
never left to whatever order the database returns. "At most one default resume" is enforced by a
partial unique index (`uq_resumes_single_default`), and `set_default_resume` serializes concurrent
callers with a Postgres advisory lock. PDF export escapes all resume text before it reaches
reportlab's markup parser, so resume content is always printed literally.

To run the Postgres-only tests locally (they are skipped otherwise; CI runs them against a
service container), point `APP_TEST_POSTGRES_URL` at a throwaway database whose name contains
`test` — the tests wipe its `public` schema and refuse any other name:

```bash
APP_TEST_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/app_test uv run pytest
```

### Auth

One shared mechanism (`app/core/security.py`) guards both the admin web routes and, from
phase 7, the MCP server — not two separate systems. It's a single static API key, since this
is a personal, single-admin site rather than a multi-user one:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"  # paste into APP_ADMIN_API_KEY
```

Every route under `/api/admin/*` requires `Authorization: Bearer <key>`.

**Use a long random key** (the command above gives 43 characters / 256 bits). Startup logs a
warning if `APP_ADMIN_API_KEY` is unset or under 32 characters; it does not refuse to start, so a
short key can't lock you out of your own deployment. To rotate it, set a new value on the
deployment (`fastapi cloud env set APP_ADMIN_API_KEY ...`); the old key stops working on redeploy.

**Wrong-key throttling.** After `APP_ADMIN_AUTH_MAX_FAILURES` (default 10) wrong keys from one
address within `APP_ADMIN_AUTH_WINDOW_SECONDS` (default 300), that address gets `429` with
`Retry-After` — on both the REST routes and MCP, from one shared decision. A locked address is
refused even with the *correct* key, otherwise "429 for wrong, 200 for right" would tell a guesser
when they found it. What it does not do: the counters are per process (several instances multiply
the limit), and the address comes from `CF-Connecting-IP` / `X-Forwarded-For`, which a caller who
reaches the app directly can forge, so treat this as a speed bump and rely on a long random key.

### Performance, caching and health

- **The public page, PDF and DOCX are cached by resume *version*** (`app/services/response_cache.py`,
  `app/api/exports.py`). A version is the resume's id plus its `updated_at`; it costs one narrow
  query to read. Responses carry a strong `ETag` and `Cache-Control: public, no-cache` — cached, but
  revalidated every time — so a repeat request is 1 query and a `304`, a miss skips loading the six
  nested sections and the rendering (an in-process LRU of the bytes), and **an edit is visible on the
  very next request**, never after a timeout. The ETag also hashes the rendering code, so a deploy
  that changes a template invalidates everything. Admin exports stay `no-store`. Measured through
  the routes: cold 7+ queries, warm 1, revalidation 1. (Eager loading was measured and rejected:
  `selectinload` is still 7 queries, `joinedload` returns the cross product of every section.)
- **Static files:** hashed `/assets/*` are `immutable` for a year; `index.html` is `no-cache` so a
  deploy takes effect immediately.
- **`GET /health`** is liveness (the process is up, and whether the frontend mounted).
  **`GET /health/ready`** is readiness: it queries the database and returns `503` if it can't,
  without saying why (the reason goes to the log).

### Backup and restore

A resume lives in one database, so keep a copy somewhere else. **Admin → Resumes → Backup** has
"Download backup" and "Restore from file…", or from a terminal:

```bash
APP_URL=https://someshwarandev.fastapicloud.dev APP_ADMIN_API_KEY=... ./scripts/backup.sh ~/backups
```

The file is plain, versioned JSON in the same shape the create API accepts (readable and diffable;
no database ids). **Restore** (`POST /api/admin/import`) is all-or-nothing in one transaction;
names that already exist are skipped, so running it twice is harmless; the current default is never
taken away (a backup's default applies only if there is none); `?replace=true` (the "Replace all
existing resumes" box, which asks for confirmation) deletes everything first, in the same
transaction, so a rejected file changes nothing. Imports are validated like any other write.
**Keep backups private**: they contain every draft, not just the published resume, so don't commit
them or attach them to a public CI run.

### Security hardening

- **Headers** (`app/core/security_headers.py`, on every response): a strict
  Content-Security-Policy (own-origin scripts/styles only, no inline or eval, no framing, no
  plugins), `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP, HSTS over
  https (no `includeSubDomains`/`preload`: the app doesn't own the parent domain), and
  `Cache-Control: no-store` on `/api/admin` and `/api/mcp`. A CSP can break the whole site, so
  `e2e/tests/security.spec.ts` loads the real built app in a browser and fails on any violation.
- **API docs are off** (`/docs`, `/redoc`, `/openapi.json` return 404) because they list every
  admin route. `APP_ENABLE_DOCS=true` turns them on for local development.
- **Input limits** (`app/schemas/resume.py`): writes via REST and MCP have length and list-size
  limits, a validated email, and links restricted to http(s)/bare hosts (never `javascript:`,
  `data:`, `file:`). Reads are unconstrained, so existing data always loads.
- **Logging:** migrations run from the app no longer reconfigure logging (Alembic's default
  silently disabled uvicorn's and the app's loggers).
- **Known gaps:** there is no automatic backup (use the script, ideally on a schedule you control);
  the admin key is kept in `localStorage` (the CSP limits what injected script
  could do with it); MCP uses the same full-access key as the admin UI; there is no audit log.

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

In production the frontend is served by the API itself (same origin), so CORS is not involved.
It only matters for local development, where Vite runs on another port:
`cors_allowed_origins` (`APP_CORS_ALLOWED_ORIGINS`, comma-separated) defaults to the Vite dev
server, `http://localhost:5173`. Set it only if the frontend is ever hosted on a separate origin.

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
- `/admin` — resume list: create, clone, preview, set default, export, delete. Shown as stacked cards
  (not a table) so the action buttons wrap on a phone instead of scrolling off-screen.
- `/admin/resumes/new` / `/admin/resumes/:id` — the resume editor — one form for every section
  (personal info, skills, experience, projects, education, certifications), each repeatable
  section with its own add/remove rows. Saving always replaces each nested collection wholesale
  (matching `resume_service.update_resume`'s semantics), not a per-row PATCH.
- `/admin/resumes/:id/preview` — renders any resume (default or not) exactly as the public page
  does, through the same `ResumeView` component, with a banner saying whether it is published.
  It reads the admin endpoint (the public one only serves the default), so a draft can be reviewed
  without publishing it. It shows the *saved* version; unsaved editor changes are not included.

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
the **repo root** (the FastAPI Cloud app is connected to this repo with its app directory set to
`backend`, so the CLI uploads the whole repo and the remote builds from `backend/`; deploying from
`backend/` itself fails the remote build). `app/main.py` serves it via FastAPI's own `app.frontend()` (checked only after every
real `/api/*` and `/health` route — it can never shadow them), falling back to `index.html` for
client-side routes so a hard refresh on `/admin/login` works. `GET /health` reports `frontend_mounted` (and the directory it looked in), so a deploy that
shipped without `frontend_dist/` is visible with a plain `curl` — no platform logs needed. `backend/frontend_dist/` is
gitignored (it's a build output) but explicitly un-ignored in `backend/.fastapicloudignore` — see that file. Local dev still runs the two apps separately
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

Without `DATABASE_URL`/`APP_DATABASE_URL` this uses SQLite, a single file: mount a volume
(`/app/data`) for anything but throwaway/local use, or point it at Postgres. Alembic migrations still run at
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

The workflow runs with read-only token permissions, every action is pinned to a commit SHA (the
version is in a comment; Dependabot, configured in `.github/dependabot.yml`, keeps them and the
backend/frontend/e2e/Docker dependencies current in weekly grouped PRs), jobs have timeouts, a
newer push to a PR cancels its older run (pushes to `main` are never cancelled), and only one
production deploy runs at a time.
