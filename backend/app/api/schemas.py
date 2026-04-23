from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models import Channel, NotificationStatus


class RecipientCreate(BaseModel):
    external_id: str
    email: EmailStr | None = None
    phone: str | None = None  # single field — normalized to SMS and WhatsApp


class RecipientUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None  # single field — normalized to SMS and WhatsApp


class RecipientOut(BaseModel):
    id: UUID
    external_id: str
    email: str | None
    phone_sms: str | None
    whatsapp_jid: str | None
    whatsapp_valid: bool
    created_at: datetime
    updated_at: datetime


class ServiceStatus(BaseModel):
    api: str  # "ok"
    whatsapp_state: str  # connected | qr_pending | connecting | disconnected | unreachable
    whatsapp_jid: str | None
    whatsapp_device: str | None
    redis: str  # "ok" | "error"
    sms_configured: bool
    smtp_configured: bool
    elevenlabs_configured: bool


class WhatsAppStatus(BaseModel):
    state: str
    jid: str | None
    device_name: str | None
    last_seen: str | None


class CheckResult(BaseModel):
    found: bool
    external_id: str | None = None
    recipient: RecipientOut | None = None
    whatsapp_valid: bool | None = None
    whatsapp_jid: str | None = None


class NotificationCreate(BaseModel):
    external_id: str
    content: str
    is_tts: bool = False
    media_urls: list[str] = []
    channels: list[Channel] | None = None  # None = auto (all eligible)


class NotificationJob(BaseModel):
    channel: Channel
    log_id: UUID
    status: NotificationStatus


class NotificationCreateResponse(BaseModel):
    notification_id: UUID
    recipient_id: UUID
    jobs: list[NotificationJob]
    skipped: list[Channel]  # eligible channels that weren't triggered (e.g. forced filter)


class ConfigUpdate(BaseModel):
    # SMTP
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_use_tls: bool | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None
    # SMS Gateway
    sms_gateway_url: str | None = None
    sms_gateway_user: str | None = None
    sms_gateway_pass: str | None = None
    sms_gateway_device_id: str | None = None
    sms_sim_number: int | None = None
    # ElevenLabs
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str | None = None


class ConfigOut(BaseModel):
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_from_email: str | None
    smtp_from_name: str | None
    smtp_use_tls: bool
    sms_gateway_url: str | None
    sms_gateway_user: str | None
    sms_gateway_device_id: str | None
    sms_sim_number: int
    elevenlabs_voice_id: str | None
    elevenlabs_model_id: str
    updated_at: datetime


class NotificationLogOut(BaseModel):
    id: UUID
    notification_id: UUID
    recipient_id: UUID
    channel: Channel
    status: NotificationStatus
    attempts: int
    is_tts: bool
    error_msg: str | None
    provider_msg_id: str | None
    created_at: datetime
    updated_at: datetime
