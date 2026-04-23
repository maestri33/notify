"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clients_name", "clients", ["name"])

    op.create_table(
        "recipients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("phone_sms", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("whatsapp_jid", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("whatsapp_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.UniqueConstraint("client_id", "external_id", name="uq_recipient_client_external"),
    )
    op.create_index("ix_recipients_client_id", "recipients", ["client_id"])
    op.create_index("ix_recipients_external_id", "recipients", ["external_id"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_tts", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("provider_msg_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["recipients.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )
    op.create_index("ix_notif_notification_id", "notification_logs", ["notification_id"])
    op.create_index("ix_notif_recipient_id", "notification_logs", ["recipient_id"])
    op.create_index("ix_notif_client_id", "notification_logs", ["client_id"])
    op.create_index("ix_notif_channel", "notification_logs", ["channel"])
    op.create_index("ix_notif_status", "notification_logs", ["status"])
    op.create_index("ix_notif_created_at", "notification_logs", ["created_at"])

    op.create_table(
        "email_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "service_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("elevenlabs_api_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("elevenlabs_voice_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "elevenlabs_model_id",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="eleven_multilingual_v2",
        ),
        sa.Column("sms_gateway_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sms_gateway_user", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sms_gateway_pass", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("smtp_host", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_user", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("smtp_pass", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("smtp_from_email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("smtp_from_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("imap_host", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("imap_user", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("imap_pass", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_config")
    op.drop_table("email_template")
    op.drop_table("notification_logs")
    op.drop_table("recipients")
    op.drop_table("clients")
