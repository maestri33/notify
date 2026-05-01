from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models import Channel, NotificationStatus


# ── Recipients ──────────────────────────────────────────────────────────

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


# ── Status ──────────────────────────────────────────────────────────────

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


# ── Notifications ───────────────────────────────────────────────────────

class CheckOut(BaseModel):
    """Response for /check — look up a phone/email in recipients or validate externally."""
    found: bool
    external_id: str | None = None
    phone: str | None = None
    email: str | bool | None = None
    whatsapp: bool | None = None


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


# ── Config ──────────────────────────────────────────────────────────────

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


# ── Groups ──────────────────────────────────────────────────────────────

class GroupSummary(BaseModel):
    jid: str
    subject: str
    subject_owner: str | None = None
    subject_time: int | None = None
    size: int
    creation: int | None = None
    owner: str | None = None
    desc: str | None = None
    announce: bool = False
    restrict: bool = False
    ephemeral: int | None = None
    is_group: bool = True


class GroupList(BaseModel):
    groups: list[GroupSummary]


class GroupParticipant(BaseModel):
    id: str
    admin: str | None = None  # "admin" | "superadmin" | None


class GroupDetail(BaseModel):
    id: str
    subject: str
    subject_owner: str | None = None
    subject_time: int | None = None
    creation: int | None = None
    owner: str | None = None
    desc: str | None = None
    announce: bool = False
    restrict: bool = False
    ephemeral: int | None = None
    size: int
    participants: list[GroupParticipant]


class GroupMembers(BaseModel):
    jid: str
    subject: str
    participants: list[GroupParticipant]


class GroupInvite(BaseModel):
    jid: str
    invite_code: str
    invite_link: str


# ── User Profile ────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    jid: str
    profile_picture_url_high: str | None = None
    profile_picture_url_low: str | None = None
    status: list | dict | None = None  # raw status from Baileys (array or object)
    contact: dict | None = None  # DB contact row

# ── Enriched Members (with contact info) ──────────────────────────────────

class MemberWithContact(BaseModel):
    id: str
    admin: str | None = None
    name: str | None = None        # from contacts.notify or contacts.name
    contact_jid: str | None = None  # @s.whatsapp.net (phone) if available


class GroupMembersEnriched(BaseModel):
    jid: str
    subject: str
    participants: list[MemberWithContact]
