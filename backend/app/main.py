"""FastAPI application entrypoint.

Phase 1 scaffolding only — no data model, auth, or resume routes yet.
Those land in later phases per CLAUDE.md's phase plan.
"""

from fastapi import FastAPI

app = FastAPI(title="someshwaran.dev API")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe used by CI, deploy checks, and local smoke tests."""
    return {"status": "ok"}
