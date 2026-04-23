"""sms device_id and sim_number columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("service_config") as batch_op:
        batch_op.add_column(
            sa.Column("sms_gateway_device_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("sms_sim_number", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    with op.batch_alter_table("service_config") as batch_op:
        batch_op.drop_column("sms_sim_number")
        batch_op.drop_column("sms_gateway_device_id")
