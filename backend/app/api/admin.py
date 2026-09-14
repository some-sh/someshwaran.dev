"""Admin routes.

Phase 3 only wires up the auth mechanism itself, so this router is
deliberately thin: one route that proves ``require_admin`` is enforced
end-to-end. Real admin actions (resume CRUD, clone, set-default, export)
land in phase 4 as further routes on this same router, behind the same
dependency.
"""

from fastapi import APIRouter, Depends

from app.core.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/whoami")
def whoami() -> dict[str, bool]:
    """Trivial authenticated route: reaching this handler means the caller
    presented a valid admin API key."""
    return {"authenticated": True}
