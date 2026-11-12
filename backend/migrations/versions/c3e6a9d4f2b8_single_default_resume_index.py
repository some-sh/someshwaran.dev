"""enforce at most one default resume in the database

``resume_service.set_default_resume`` keeps "at most one is_default" by
unsetting the old default and setting the new one, but that is only a
convention: two concurrent requests (the app can run as several instances, and
the MCP server is a second writer) can each unset and then each set, leaving
two defaults. A partial unique index makes the database refuse that.

(Both SQLite and Postgres support partial unique indexes; the earlier comment
in the service claiming SQLite had no equivalent was wrong.)

Existing duplicates, if any, are resolved first by keeping the lowest id —
the index could not be created otherwise.

Revision ID: c3e6a9d4f2b8
Revises: b2d5f8c3e1a7
Create Date: 2026-11-12 08:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e6a9d4f2b8"
down_revision: str | Sequence[str] | None = "b2d5f8c3e1a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_resumes_single_default"


def upgrade() -> None:
    resumes = sa.table("resumes", sa.column("id", sa.Integer), sa.column("is_default", sa.Boolean))
    keep = (
        sa.select(sa.func.min(resumes.c.id)).where(resumes.c.is_default.is_(True)).scalar_subquery()
    )
    op.execute(
        resumes.update()
        .where(resumes.c.is_default.is_(True), resumes.c.id != keep)
        .values(is_default=False)
    )
    op.create_index(
        INDEX_NAME,
        "resumes",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="resumes")
