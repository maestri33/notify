"""Schemas Pydantic para Contact."""

from datetime import datetime

from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    """Body para criacao de contacto.

    Pelo menos phone ou email deve ser informado.
    """

    external_id: str = Field(
        description="Identificador externo unico do contacto (source of truth)",
        examples=["victor-001"],
    )
    phone: str | None = Field(
        default=None,
        description="Numero de WhatsApp no formato DDI+DDD+numero, ex: 5543996648750",
        examples=["5543996648750"],
    )
    email: str | None = Field(
        default=None,
        description="Endereco de email valido",
        examples=["fulano@exemplo.com"],
    )


class ContactRead(BaseModel):
    """Representacao de um contacto persistido."""

    id: int = Field(description="ID interno no banco")
    external_id: str = Field(description="Identificador externo unico")
    phone: str | None = Field(default=None, description="Numero de WhatsApp")
    email: str | None = Field(default=None, description="Endereco de email")
    created_at: datetime = Field(description="Data de criacao (UTC)")
    updated_at: datetime = Field(description="Data da ultima atualizacao (UTC)")

    model_config = {"from_attributes": True}


class ContactCheckResponse(BaseModel):
    """Resposta do endpoint de verificacao de contacto.

    Nunca cria contacto — apenas consulta existencia local e valida
    telefone/email externamente.
    """

    found: bool = Field(description="Se o contacto ja existe na base local")
    external_id: str | None = Field(
        default=None, description="ID do contacto se encontrado"
    )
    phone: str | None = Field(default=None, description="Telefone do contacto se encontrado")
    email: str | None = Field(default=None, description="Email do contacto se encontrado")
    phone_valid: bool | None = Field(
        default=None,
        description="True se o WhatsApp confirmou que o numero existe, False se nao, None se nao verificado",
    )
    email_valid: bool | None = Field(
        default=None,
        description="True se o email tem formato valido, False se invalido, None se nao verificado",
    )
