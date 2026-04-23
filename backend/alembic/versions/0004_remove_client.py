"""remove client table and client_id columns, add unique constraint on recipient.external_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- notification_logs: drop client_id ---
    conn.execute(sa.text("""
        CREATE TABLE notification_logs_new (
            id TEXT NOT NULL,
            notification_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            channel VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            is_tts INTEGER NOT NULL DEFAULT 0,
            error_msg TEXT,
            provider_msg_id TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO notification_logs_new
            (id, notification_id, recipient_id, channel, status,
             attempts, is_tts, error_msg, provider_msg_id, created_at, updated_at)
        SELECT id, notification_id, recipient_id, channel, status,
               attempts, is_tts, error_msg, provider_msg_id, created_at, updated_at
        FROM notification_logs
    """))
    conn.execute(sa.text("DROP TABLE notification_logs"))
    conn.execute(sa.text("ALTER TABLE notification_logs_new RENAME TO notification_logs"))

    # --- recipients: drop client_id, add unique on external_id ---
    conn.execute(sa.text("""
        CREATE TABLE recipients_new (
            id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            email TEXT,
            phone_sms TEXT,
            whatsapp_jid TEXT,
            whatsapp_valid INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (external_id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO recipients_new
            (id, external_id, email, phone_sms, whatsapp_jid,
             whatsapp_valid, created_at, updated_at)
        SELECT id, external_id, email, phone_sms, whatsapp_jid,
               whatsapp_valid, created_at, updated_at
        FROM recipients
    """))
    conn.execute(sa.text("DROP TABLE recipients"))
    conn.execute(sa.text("ALTER TABLE recipients_new RENAME TO recipients"))

    # --- drop clients table ---
    conn.execute(sa.text("DROP TABLE IF EXISTS clients"))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE clients (
            id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE recipients_new (
            id TEXT NOT NULL,
            client_id TEXT,
            external_id TEXT NOT NULL,
            email TEXT,
            phone_sms TEXT,
            whatsapp_jid TEXT,
            whatsapp_valid INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (client_id, external_id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO recipients_new
            (id, external_id, email, phone_sms, whatsapp_jid,
             whatsapp_valid, created_at, updated_at)
        SELECT id, external_id, email, phone_sms, whatsapp_jid,
               whatsapp_valid, created_at, updated_at
        FROM recipients
    """))
    conn.execute(sa.text("DROP TABLE recipients"))
    conn.execute(sa.text("ALTER TABLE recipients_new RENAME TO recipients"))

    conn.execute(sa.text("""
        CREATE TABLE notification_logs_new (
            id TEXT NOT NULL,
            notification_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            client_id TEXT,
            channel VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            is_tts INTEGER NOT NULL DEFAULT 0,
            error_msg TEXT,
            provider_msg_id TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO notification_logs_new
            (id, notification_id, recipient_id, channel, status,
             attempts, is_tts, error_msg, provider_msg_id, created_at, updated_at)
        SELECT id, notification_id, recipient_id, channel, status,
               attempts, is_tts, error_msg, provider_msg_id, created_at, updated_at
        FROM notification_logs
    """))
    conn.execute(sa.text("DROP TABLE notification_logs"))
    conn.execute(sa.text("ALTER TABLE notification_logs_new RENAME TO notification_logs"))
