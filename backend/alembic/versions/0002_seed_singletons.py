"""seed singletons: email_template + service_config

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22

"""
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

from app.models.email_template import DEFAULT_HTML, DEFAULT_SUBJECT

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.utcnow()
    op.bulk_insert(
        sa.table(
            "email_template",
            sa.column("id", sa.Integer),
            sa.column("subject", sa.Text),
            sa.column("html_body", sa.Text),
            sa.column("updated_at", sa.DateTime),
        ),
        [{"id": 1, "subject": DEFAULT_SUBJECT, "html_body": DEFAULT_HTML, "updated_at": now}],
    )
    op.bulk_insert(
        sa.table(
            "service_config",
            sa.column("id", sa.Integer),
            sa.column("updated_at", sa.DateTime),
        ),
        [{"id": 1, "updated_at": now}],
    )


def downgrade() -> None:
    op.execute("DELETE FROM service_config WHERE id = 1")
    op.execute("DELETE FROM email_template WHERE id = 1")
