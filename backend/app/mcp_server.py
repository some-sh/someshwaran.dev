"""Remote MCP server exposing the same resume actions as the admin REST API
to LLM clients (CLAUDE.md phase 7).

Per CLAUDE.md's "one schema, one renderer" architecture principle, every
tool below is a thin wrapper over app.services.resume_service — the same
service the admin REST API (app/api/admin.py) calls. An MCP tool response
is just another renderer over that one underlying schema, not a parallel
implementation of resume actions.

Auth is reused from phase 3 too, just not via FastAPI's Depends: this
module only builds the MCP server and its ASGI transport. The whole
transport is wrapped in app.core.security.AdminBearerAuthMiddleware when
it's mounted in app/main.py, checked against the same admin API key as
every other admin route — see that middleware's docstring for why the
check has to happen at this layer instead.

build_mcp_server() is a factory, not a module-level singleton, and that's
deliberate: an MCPServer's streamable-HTTP session manager can only be
``.run()`` once per instance ("create a new instance if you need to run
again" — see mcp.server.streamable_http_manager). A real deployment only
ever starts the app once per process, so a singleton would never notice —
but this app's own test suite runs the real app's lifespan (and therefore
mcp.session_manager.run()) more than once in the same process, once per
test that does ``with TestClient(app):``. app/main.py calls this factory
fresh on every startup instead of importing one built at module-import
time, so every startup gets its own instance.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from sqlmodel import Session
from starlette.applications import Starlette

from app.db import get_engine
from app.schemas.resume import ResumeCreate, ResumeRead, ResumeSummary, ResumeUpdate
from app.services import resume_service


def _session() -> Session:
    """A plain (non-request-scoped) session, opened the same way
    app.db.get_session does for FastAPI routes — MCP tools aren't FastAPI
    path operations, so there's no request to hang a Depends(get_session)
    off of."""
    return Session(get_engine())


def build_mcp_server() -> MCPServer:
    """Builds a fresh MCPServer with every resume tool registered. See
    this module's docstring for why it's a factory rather than a
    module-level singleton."""
    server = MCPServer(
        "someshwaran.dev",
        instructions=(
            "Manage resume versions for someshwaran.dev: create, edit, "
            "clone, and delete versions, and choose which one is "
            "published on the public site."
        ),
    )

    @server.tool()
    def list_resumes() -> list[ResumeSummary]:
        """List every resume version (id, name, default flag, timestamps),
        without their full content — enough to pick one to open, clone,
        set default, or delete."""
        with _session() as session:
            return [ResumeSummary.model_validate(r) for r in resume_service.list_resumes(session)]

    @server.tool()
    def get_resume(resume_id: int) -> ResumeRead:
        """Get one resume's full content by id."""
        with _session() as session:
            resume = resume_service.get_resume(session, resume_id)
            if resume is None:
                raise ToolError(f"Resume {resume_id} not found")
            return ResumeRead.model_validate(resume)

    @server.tool()
    def get_default_resume() -> ResumeRead:
        """Get the resume version currently published on the public site."""
        with _session() as session:
            resume = resume_service.get_default_resume(session)
            if resume is None:
                raise ToolError("No default resume is set")
            return ResumeRead.model_validate(resume)

    @server.tool()
    def create_resume(data: ResumeCreate) -> ResumeRead:
        """Create a new resume version. Not published until
        set_default_resume is called on it."""
        with _session() as session:
            return ResumeRead.model_validate(resume_service.create_resume(session, data))

    @server.tool()
    def update_resume(resume_id: int, data: ResumeUpdate) -> ResumeRead:
        """Partially update a resume. Omitted fields are left unchanged;
        any nested section that IS provided (skills, experience, projects,
        education, certifications, personal_info) replaces that whole
        section, not a per-item merge."""
        with _session() as session:
            resume = resume_service.update_resume(session, resume_id, data)
            if resume is None:
                raise ToolError(f"Resume {resume_id} not found")
            return ResumeRead.model_validate(resume)

    @server.tool()
    def delete_resume(resume_id: int) -> dict[str, bool]:
        """Delete a resume version."""
        with _session() as session:
            if not resume_service.delete_resume(session, resume_id):
                raise ToolError(f"Resume {resume_id} not found")
            return {"deleted": True}

    @server.tool()
    def clone_resume(resume_id: int) -> ResumeRead:
        """Deep-copy a resume into a new, independent version named
        "<name> (copy)". The clone is never the default, even when cloning
        the current default — set_default_resume is a separate, explicit
        step."""
        with _session() as session:
            clone = resume_service.clone_resume(session, resume_id)
            if clone is None:
                raise ToolError(f"Resume {resume_id} not found")
            return ResumeRead.model_validate(clone)

    @server.tool()
    def set_default_resume(resume_id: int) -> ResumeRead:
        """Mark a resume as the one published on the public site,
        atomically unsetting any previous default."""
        with _session() as session:
            resume = resume_service.set_default_resume(session, resume_id)
            if resume is None:
                raise ToolError(f"Resume {resume_id} not found")
            return ResumeRead.model_validate(resume)

    return server


def build_mcp_asgi_app(server: MCPServer) -> Starlette:
    """Builds the ASGI app app/main.py mounts for a given server instance.
    Also the point at which server.session_manager becomes valid (it's
    created lazily by streamable_http_app() — see
    mcp.server.lowlevel.server), so main.py's lifespan can only enter
    server.session_manager.run() after calling this.
    """
    return server.streamable_http_app(
        streamable_http_path="/",
        # DNS-rebinding host checking exists to protect a *local* MCP
        # server that a browser tab might reach over localhost. This one
        # is a remote server reached directly by MCP clients (and, in
        # tests, by a test client using an arbitrary Host header) — the
        # actual security boundary is the bearer-key check in
        # AdminBearerAuthMiddleware, not the Host header, so this is
        # disabled rather than trying to keep an allowed_hosts list in
        # sync with every deploy/test hostname.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
