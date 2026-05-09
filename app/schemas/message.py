"""Schemas Pydantic para Message."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import STATUS_PENDING


class MessageFlags(BaseModel):
    """Flags que controlam o pipeline de envio da mensagem.

    As flags atuam como modificadores do fluxo:
    - ai: DeepSeek reescreve o texto antes de enviar
    - tts: ElevenLabs gera audio e envia como nota de voz (so texto)
    - img: Gemini gera uma imagem e envia como midia

    img e tts sao mutuamente exclusivos — img vence.
    """

    tts: bool = Field(
        default=False,
        description="Gera audio via ElevenLabs e envia como nota de voz nativa (PTT). "
        "So funciona em mensagens de texto (ignorado se houver midia).",
    )
    ai: bool = Field(
        default=False,
        description="DeepSeek Pro reescreve o content da mensagem antes do envio",
    )
    img: bool = Field(
        default=False,
        description="Gemini gera uma imagem a partir de instruction (ou auto-prompt). "
        "Converte a mensagem para tipo 'media'.",
    )


class MessageSend(BaseModel):
    """Body para envio de mensagem multicanal (WhatsApp + Email)."""

    external_id: str = Field(
        description="ID do contacto destinatario (deve existir em /contacts)",
        examples=["victor-001"],
    )
    content: str = Field(
        description="Texto da mensagem, URL de .md (download + extracao), "
        "ou prompt para IA se flags.ai=True",
        examples=["Ola! Sua entrega chegou."],
    )
    media_url: str | None = Field(
        default=None,
        description="URL publica ou data URI base64 (data:image/png;base64,...) de midia anexa. "
        "Formatos: imagem, video, audio, documento.",
        examples=["data:image/png;base64,iVBORw0KGgo..."],
    )
    flags: MessageFlags = Field(
        default_factory=MessageFlags,
        description="Flags que controlam IA, TTS e geracao de imagem",
    )
    instruction: str | None = Field(
        default=None,
        description="Refinamento extra: com --ai define estilo/tom do texto; "
        "com --img define o prompt da imagem a ser gerada",
        examples=["Tom educado e formal, maximo 3 frases"],
    )


class MessageRead(BaseModel):
    """Representacao de uma mensagem persistida."""

    id: int = Field(description="ID interno da mensagem")
    contact_id: int = Field(description="ID do contacto destinatario")
    type: str = Field(description="Tipo: 'text' ou 'media'")
    content_text: str | None = Field(default=None, description="Conteudo textual da mensagem")
    whatsapp_status: str = Field(
        default=STATUS_PENDING,
        description="Status do envio WhatsApp: pending, sent, failed",
    )
    email_status: str = Field(
        default=STATUS_PENDING,
        description="Status do envio Email: pending, sent, failed, skipped",
    )
    email_subject: str | None = Field(
        default=None, description="Titulo do email (gerado por IA ou fallback)"
    )
    tts_audio_url: str | None = Field(
        default=None, description="URL publica do audio TTS gerado, se flags.tts=True"
    )
    created_at: datetime = Field(description="Data de criacao (UTC)")
    updated_at: datetime = Field(description="Data da ultima atualizacao (UTC)")

    model_config = {"from_attributes": True}
