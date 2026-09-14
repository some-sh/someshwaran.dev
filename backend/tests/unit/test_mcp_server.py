"""Unit tests for the MCP tools (app/mcp_server.py), against a real
temp-file SQLite DB — same bar as the resume service's own tests, since
every tool here is a thin wrapper over that service.

Uses the MCP SDK's in-memory `Client(server)` (no HTTP, no ASGI
transport): that's the SDK-recommended way to test tool behavior
directly, and it's also the only practical option here, since the actual
ASGI/auth-gate integration is exercised separately in
tests/integration/test_mcp_auth.py. Each test builds its own server via
build_mcp_server() rather than sharing one — see that function's
docstring for why it's a factory, not a singleton, in the first place.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp.client import Client
from sqlmodel import SQLModel, create_engine

import app.models  # noqa: F401  ensures tables are registered on metadata
from app import mcp_server
from app.db import ensure_sqlite_directory_exists
from app.mcp_server import build_mcp_server


@pytest.fixture(autouse=True)
def _temp_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Points app/mcp_server.py's _session() at a fresh temp-file SQLite DB
    for each test, the same way tests/conftest.py's `client` fixture does
    for the REST API — MCP tools open their own Session directly rather
    than through a FastAPI Depends, so there's no dependency_overrides
    seam to use instead."""
    db_path = tmp_path / "test.db"
    ensure_sqlite_directory_exists(f"sqlite:///{db_path}")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "get_engine", lambda: engine)


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with Client(build_mcp_server()) as connected:
        yield connected


def _create_args(name: str = "Backend-focused") -> dict:
    return {
        "data": {
            "name": name,
            "summary": "Backend engineer.",
            "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
            "skills": [{"name": "Python"}],
        }
    }


@pytest.mark.anyio
async def test_lists_tools(client: Client) -> None:
    tools = await client.list_tools()

    assert {
        "list_resumes",
        "get_resume",
        "get_default_resume",
        "create_resume",
        "update_resume",
        "delete_resume",
        "clone_resume",
        "set_default_resume",
    } <= {t.name for t in tools.tools}


@pytest.mark.anyio
async def test_create_list_get_update_delete_flow(client: Client) -> None:
    created = await client.call_tool("create_resume", _create_args())
    assert created.structured_content["personal_info"]["full_name"] == "Ada Lovelace"
    resume_id = created.structured_content["id"]

    listed = await client.call_tool("list_resumes", {})
    assert [r["name"] for r in listed.structured_content["result"]] == ["Backend-focused"]

    fetched = await client.call_tool("get_resume", {"resume_id": resume_id})
    assert fetched.structured_content["name"] == "Backend-focused"

    updated = await client.call_tool(
        "update_resume", {"resume_id": resume_id, "data": {"summary": "Updated."}}
    )
    assert updated.structured_content["summary"] == "Updated."

    deleted = await client.call_tool("delete_resume", {"resume_id": resume_id})
    assert deleted.structured_content == {"deleted": True}

    missing = await client.call_tool("get_resume", {"resume_id": resume_id})
    assert missing.is_error


@pytest.mark.anyio
async def test_get_update_delete_missing_resume_is_a_tool_error(client: Client) -> None:
    for tool_name, args in [
        ("get_resume", {"resume_id": 999}),
        ("update_resume", {"resume_id": 999, "data": {"summary": "x"}}),
        ("delete_resume", {"resume_id": 999}),
        ("clone_resume", {"resume_id": 999}),
        ("set_default_resume", {"resume_id": 999}),
    ]:
        result = await client.call_tool(tool_name, args)
        assert result.is_error, f"{tool_name} should have failed"


@pytest.mark.anyio
async def test_clone_creates_an_independent_non_default_copy(client: Client) -> None:
    created = await client.call_tool("create_resume", _create_args())
    resume_id = created.structured_content["id"]

    cloned = await client.call_tool("clone_resume", {"resume_id": resume_id})

    assert cloned.structured_content["id"] != resume_id
    assert cloned.structured_content["name"] == "Backend-focused (copy)"
    assert cloned.structured_content["is_default"] is False


@pytest.mark.anyio
async def test_set_default_and_get_default_resume(client: Client) -> None:
    no_default = await client.call_tool("get_default_resume", {})
    assert no_default.is_error

    created = await client.call_tool("create_resume", _create_args())
    resume_id = created.structured_content["id"]

    await client.call_tool("set_default_resume", {"resume_id": resume_id})

    default = await client.call_tool("get_default_resume", {})
    assert default.structured_content["id"] == resume_id


@pytest.mark.anyio
async def test_a_tool_error_message_names_the_missing_resume(client: Client) -> None:
    """Checks the actual error text, not just is_error, for one
    representative case — the other not-found cases share the same
    ToolError(f"Resume {id} not found") shape (see build_mcp_server)."""
    result = await client.call_tool("get_resume", {"resume_id": 999})

    assert result.is_error
    assert "999" in result.content[0].text
    assert "not found" in result.content[0].text


@pytest.mark.anyio
async def test_build_mcp_server_returns_a_fresh_instance_each_call() -> None:
    """Guards the factory contract every caller relies on: app/main.py's
    lifespan needs a genuinely new MCPServer (and therefore a new,
    not-yet-run session manager) on every startup — see build_mcp_server's
    docstring."""
    assert build_mcp_server() is not build_mcp_server()
