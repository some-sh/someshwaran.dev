"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.admin import router as admin_router

app = FastAPI(title="someshwaran.dev API")
app.include_router(admin_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe used by CI, deploy checks, and local smoke tests."""
    return {"status": "ok"}
