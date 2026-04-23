from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models._common import utcnow


class ServiceConfig(SQLModel, table=True):
    __tablename__ = "service_config"

    id: int = Field(default=1, primary_key=True)

    # ElevenLabs (TTS)
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # SMS Gateway for Android
    sms_gateway_url: str | None = None
    sms_gateway_user: str | None = None
    sms_gateway_pass: str | None = None
    sms_gateway_device_id: str | None = None
    sms_sim_number: int = 1

    # SMTP (outbound email)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None

    # IMAP (reserved for future: reading replies)
    imap_host: str | None = None
    imap_port: int = 993
    imap_user: str | None = None
    imap_pass: str | None = None

    updated_at: datetime = Field(default_factory=utcnow)
