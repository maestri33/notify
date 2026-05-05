from datetime import datetime

from pydantic import BaseModel


class MessageFlags(BaseModel):
    tts: bool = False
    ai: bool = False
    img: bool = False


class MessageSend(BaseModel):
    external_id: str
    content: str  # texto direto, URL de .md, ou prompt p/ IA (se flags.ai)
    media_url: str | None = None
    flags: MessageFlags = MessageFlags()
    instruction: str | None = None  # refinamento extra para geracao IA


class MessageRead(BaseModel):
    id: int
    contact_id: int
    type: str
    content_text: str | None = None
    whatsapp_status: str = "pending"
    email_status: str = "pending"
    email_subject: str | None = None
    tts_audio_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
