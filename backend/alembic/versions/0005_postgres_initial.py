"""PostgreSQL initial schema — legacy delivery tables in notify schema

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-01

Creates the 4 operational tables that don't yet exist on the PostgreSQL server.
The `notifications` and `push_subscriptions` tables already exist (created by DBA).
"""

from datetime import UTC, datetime
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "notify"


def upgrade() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)

    # -- service_config (singleton) ------------------------------------------------
    op.create_table(
        "service_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("elevenlabs_api_key", sa.String(), nullable=True),
        sa.Column("elevenlabs_voice_id", sa.String(), nullable=True),
        sa.Column("elevenlabs_model_id", sa.String(), nullable=False,
                  server_default="eleven_multilingual_v2"),
        sa.Column("sms_gateway_url", sa.String(), nullable=True),
        sa.Column("sms_gateway_user", sa.String(), nullable=True),
        sa.Column("sms_gateway_pass", sa.String(), nullable=True),
        sa.Column("sms_gateway_device_id", sa.String(), nullable=True),
        sa.Column("sms_sim_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("smtp_host", sa.String(), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_user", sa.String(), nullable=True),
        sa.Column("smtp_pass", sa.String(), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smtp_from_email", sa.String(), nullable=True),
        sa.Column("smtp_from_name", sa.String(), nullable=True),
        sa.Column("imap_host", sa.String(), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("imap_user", sa.String(), nullable=True),
        sa.Column("imap_pass", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        schema=SCHEMA,
    )
    op.execute(
        f"INSERT INTO {SCHEMA}.service_config (id, updated_at) VALUES (1, '{now}')"
    )

    # -- email_template (singleton) -----------------------------------------------
    op.create_table(
        "email_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject", sa.String(), nullable=False,
                  server_default="You have a new notification"),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        schema=SCHEMA,
    )
    op.execute(
        f"INSERT INTO {SCHEMA}.email_template (id, html_body, updated_at) "
        f"VALUES (1, '<html><body>{{body}}</body></html>', '{now}')"
    )

    # -- recipients ----------------------------------------------------------------
    op.create_table(
        "recipients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone_sms", sa.String(), nullable=True),
        sa.Column("whatsapp_jid", sa.String(), nullable=True),
        sa.Column("whatsapp_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("external_id", name="uq_recipient_external_id"),
        schema=SCHEMA,
    )
    op.create_index("ix_recipients_external_id", "recipients", ["external_id"],
                    schema=SCHEMA)

    # -- notification_logs ---------------------------------------------------------
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_tts", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("provider_msg_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], [f"{SCHEMA}.recipients.id"]),
        schema=SCHEMA,
    )
    op.create_index("ix_notification_logs_notification_id", "notification_logs",
                    ["notification_id"], schema=SCHEMA)
    op.create_index("ix_notification_logs_recipient_id", "notification_logs",
                    ["recipient_id"], schema=SCHEMA)
    op.create_index("ix_notification_logs_channel", "notification_logs",
                    ["channel"], schema=SCHEMA)
    op.create_index("ix_notification_logs_status", "notification_logs",
                    ["status"], schema=SCHEMA)
    op.create_index("ix_notification_logs_created_at", "notification_logs",
                    ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("notification_logs", schema=SCHEMA)
    op.drop_table("recipients", schema=SCHEMA)
    op.drop_table("email_template", schema=SCHEMA)
    op.drop_table("service_config", schema=SCHEMA)
