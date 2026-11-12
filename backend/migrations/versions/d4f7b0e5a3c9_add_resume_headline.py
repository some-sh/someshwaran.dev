"""add resumes.headline

The one-line professional headline shown under the name on a resume (for
example "Senior SDET | Test Automation & Infrastructure | Python, Playwright").
It had no home in the schema, so it was silently lost when a resume was
imported from a document that has one.

NOT NULL with an empty-string server default, so existing rows get "" and the
column can be added in one step on both SQLite and Postgres.

Revision ID: d4f7b0e5a3c9
Revises: c3e6a9d4f2b8
Create Date: 2026-11-12 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f7b0e5a3c9"
down_revision: str | Sequence[str] | None = "c3e6a9d4f2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column(
            "headline",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("resumes") as batch:
        batch.drop_column("headline")
