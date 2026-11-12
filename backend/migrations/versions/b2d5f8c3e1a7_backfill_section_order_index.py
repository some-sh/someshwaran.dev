"""backfill order_index for resume list sections

Resume sections (skills, experience, projects, education, certifications) are
rendered in ``order_index`` order, but the service never assigned it, so every
existing row has 0. Postgres makes no promise about the order of tied rows, so
the displayed order could change after an update or a vacuum.

This gives each row its position within its resume, ordered by the existing
(order_index, id) — i.e. exactly the order rows come back in today, now made
explicit. Data-only: no schema change, and it is a no-op for rows that already
have distinct positions.

Revision ID: b2d5f8c3e1a7
Revises: a1c4e7b2d9f0
Create Date: 2026-11-12 08:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d5f8c3e1a7"
down_revision: str | Sequence[str] | None = "a1c4e7b2d9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("skills", "experience", "projects", "education", "certifications")


def upgrade() -> None:
    # UPDATE ... FROM with a window function works on Postgres and on SQLite >= 3.33.
    for table in _TABLES:
        op.execute(
            f"""
            UPDATE {table}
            SET order_index = ranked.position
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY resume_id ORDER BY order_index, id
                       ) - 1 AS position
                FROM {table}
            ) AS ranked
            WHERE {table}.id = ranked.id
            """
        )


def downgrade() -> None:
    # The previous positions were all 0 and carried no information; keeping the
    # explicit ones is harmless, so there is nothing to undo.
    pass
