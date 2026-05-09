"""Schemas Pydantic para Log."""

from datetime import datetime

from pydantic import BaseModel, Field


class LogRead(BaseModel):
    """Registro de log do sistema — acao documentada com detalhes."""

    id: int = Field(description="ID interno do log")
    message_id: int | None = Field(
        default=None,
        description="ID da mensagem associada (None para logs de contacto/sistema)",
    )
    action: str = Field(
        description="Acao registrada, ex: 'contact.created', 'message.sent', 'whatsapp.text_sent'",
        examples=["message.sent", "contact.created"],
    )
    details: dict | None = Field(
        default=None,
        description="Dados adicionais da acao em formato livre (JSON)",
    )
    created_at: datetime = Field(description="Data do registro (UTC)")

    model_config = {"from_attributes": True}
