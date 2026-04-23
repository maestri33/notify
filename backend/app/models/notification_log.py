import uuid
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.models._common import utcnow


class Channel(str, Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    email = "email"


class NotificationStatus(str, Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class NotificationLog(SQLModel, table=True):
    __tablename__ = "notification_logs"

    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    notification_id: UUID = Field(index=True)  # groups the N logs of one POST /notifications
    recipient_id: UUID = Field(foreign_key="recipients.id", index=True)

    channel: Channel = Field(index=True)
    status: NotificationStatus = Field(default=NotificationStatus.queued, index=True)
    attempts: int = 0
    is_tts: bool = False

    error_msg: str | None = None
    provider_msg_id: str | None = None

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
