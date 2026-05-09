"""
Servico de contactos — CRUD e verificacao.

Fluxo principal:
  GET /contacts/check  → check_contact()    (lookup + validacao externa)
  POST /contacts       → create_contact()   (insere contacto simples)
"""

import re
from typing import Any

import httpx

from app.exceptions import Conflict, DomainError, NotFound
from app.integrations.whatsapp import WhatsAppClient
from app.models.contact import Contact
from app.models.log import Log
from app.models.message import Message
from app.schemas.contact import ContactCreate
from app.utils.logging import get_logger

log = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_email(email: str) -> bool:
    """Valida formato de email (RFC 5322 simplificado)."""
    return bool(_EMAIL_RE.match(email))


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------


async def create_contact(payload: ContactCreate) -> Contact:
    """Cria um contacto simples."""
    if not payload.phone and not payload.email:
        raise DomainError("Pelo menos telefone ou email deve ser informado")
    existing = await Contact.get_or_none(external_id=payload.external_id)
    if existing:
        raise Conflict(f"Contacto {payload.external_id} ja existe")
    return await Contact.create(
        external_id=payload.external_id,
        phone=payload.phone,
        email=payload.email,
    )


async def get_contact_by_external_id(external_id: str) -> Contact:
    contact = await Contact.get_or_none(external_id=external_id)
    if contact is None:
        raise NotFound(f"Contacto {external_id} nao encontrado")
    return contact


async def delete_contact(external_id: str) -> None:
    """Destroi um contacto e todas as suas mensagens e logs."""
    contact = await get_contact_by_external_id(external_id)
    messages = await Message.filter(contact_id=contact.id).all()
    message_ids = [m.id for m in messages]
    if message_ids:
        await Log.filter(message_id__in=message_ids).delete()
    await Message.filter(contact_id=contact.id).delete()
    await contact.delete()
    log.info("contact.deleted", external_id=external_id, messages=len(message_ids))


async def list_contacts(limit: int = 50, offset: int = 0) -> list[Contact]:
    return await Contact.all().offset(offset).limit(limit)


# ------------------------------------------------------------------
# Verificacao
# ------------------------------------------------------------------


async def check_contact(
    phone: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Verifica se um contacto existe e valida phone/email externamente.

    Nunca cria contacto — apenas consulta.
    """
    if not phone and not email:
        raise DomainError("Pelo menos telefone ou email deve ser informado")

    contact = None
    if phone:
        contact = await Contact.get_or_none(phone=phone)
    if not contact and email:
        contact = await Contact.get_or_none(email=email)

    if contact:
        log.info("contact.check_found", external_id=contact.external_id)
        return {
            "found": True,
            "external_id": contact.external_id,
            "phone": contact.phone,
            "email": contact.email,
        }

    phone_valid: bool | None = None
    email_valid: bool | None = None

    if email:
        email_valid = _validate_email(email)

    if phone:
        async with httpx.AsyncClient() as http:
            whatsapp = WhatsAppClient(http)
            try:
                result = await whatsapp.check_numbers([phone])
                phone_valid = (
                    len(result) > 0
                    and isinstance(result[0], dict)
                    and result[0].get("exists", False)
                )
                log.info("contact.phone_checked", phone=phone, exists=phone_valid)
            except Exception as exc:
                log.error("contact.phone_check_failed", phone=phone, error=str(exc))
                phone_valid = False

    log.info("contact.check_not_found", phone_valid=phone_valid, email_valid=email_valid)
    return {
        "found": False,
        "phone_valid": phone_valid,
        "email_valid": email_valid,
    }


