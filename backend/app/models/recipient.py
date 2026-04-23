import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models._common import utcnow


class Recipient(SQLModel, table=True):
    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_recipient_external_id"),
    )

    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    external_id: str = Field(index=True)

    email: str | None = None
    phone_sms: str | None = None  # "43996648750" (no country code)
    whatsapp_jid: str | None = None  # "554396648750@s.whatsapp.net"
    whatsapp_valid: bool = False

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
