"""
Servico de contactos — CRUD, verificacao e enriquecimento via IA.

Fluxo principal:
  GET /contacts/check  → check_contact()     (lookup + validacao externa)
  POST /contacts       → enrich_contact()    (criacao com pipeline IA)
"""

import json
import re
from typing import Any

import httpx

from app.config import get_settings
from app.exceptions import Conflict, DomainError, NotFound
from app.models.contact import Contact
from app.schemas.contact import ContactCreate
from app.services.clients.deepseek import DeepSeekClient
from app.services.clients.gemini import GeminiClient
from app.services.clients.whatsapp import WhatsAppClient
from app.utils.logging import get_logger

log = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_email(email: str) -> bool:
    """Valida formato de email (RFC 5322 simplificado)."""
    return bool(_EMAIL_RE.match(email))


# ------------------------------------------------------------------
# CRUD basico (mantido para compatibilidade)
# ------------------------------------------------------------------


async def create_contact(payload: ContactCreate) -> Contact:
    """Cria um contacto simples (sem enriquecimento).

    Prefira enrich_contact() para o fluxo completo com IA.
    """
    existing = await Contact.get_or_none(external_id=payload.external_id)
    if existing:
        raise Conflict(f"Contacto {payload.external_id} ja existe")
    return await Contact.create(**payload.model_dump())


async def get_contact_by_external_id(external_id: str) -> Contact:
    contact = await Contact.get_or_none(external_id=external_id)
    if contact is None:
        raise NotFound(f"Contacto {external_id} nao encontrado")
    return contact


async def list_contacts(limit: int = 50, offset: int = 0) -> list[Contact]:
    return await Contact.all().offset(offset).limit(limit)


# ------------------------------------------------------------------
# Verificacao e enriquecimento
# ------------------------------------------------------------------


async def check_contact(
    phone: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Verifica se um contacto existe e valida phone/email externamente.

    Nunca cria contacto — apenas consulta.

    Args:
        phone: Numero DDI+DDD+numero (ex: "5543996648750").
        email: Endereco de email.

    Returns:
        Se encontrado: {found: true, external_id, phone, email}
        Se nao encontrado: {found: false, phone_valid, email_valid}
    """
    if not phone and not email:
        raise DomainError("Pelo menos telefone ou email deve ser informado")

    # 1. Busca no banco
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

    # 2. Nao encontrado — validacao externa
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


async def enrich_contact(payload: ContactCreate) -> Contact:
    """Cria um contacto com pipeline de enriquecimento via IA e WhatsApp.

    Fluxo:
      1. Deduplicacao — check_contact interno
      2. Se email → DeepSeek Pro analisa (nome, genero, nascimento)
      3. Se phone validado → WhatsApp perfil + perfil comercial + Gemini foto
      4. DeepSeek Pro consolida todos os dados → extracao estruturada
      5. Persiste Contact com campos enriquecidos
    """
    # 1. Deduplicacao
    if payload.phone or payload.email:
        check = await check_contact(phone=payload.phone, email=payload.email)
        if check["found"]:
            raise Conflict(
                f"Contacto ja existe com external_id={check['external_id']}"
            )

    collected: dict[str, Any] = {}
    settings = get_settings()

    async with httpx.AsyncClient() as http:
        deepseek = DeepSeekClient(http)

        # 2. Enriquecimento de email
        if payload.email and _validate_email(payload.email):
            try:
                email_analysis = await deepseek._chat(
                    system_prompt=(
                        "Voce analisa enderecos de email e extrai informacoes sobre a pessoa. "
                        "Retorne um JSON com as chaves: name, gender, birth_date. "
                        "Seja conservador: NAO invente dados. Se nao ha informacao suficiente "
                        "para inferir um campo, use null. "
                        "Ex: 'joao.silva1985@gmail.com' sugere name='Joao Silva', "
                        "birth_date='1985'. "
                        "Ex: 'contato@empresa.com.br' — name=null, gender=null, birth_date=null. "
                        "Ex: 'maria.oliveira@outlook.com' sugere name='Maria Oliveira'. "
                        "Apenas o que for razoavelmente inferido do endereco de email."
                    ),
                    user_message=f"Analise este email: {payload.email}",
                    model="deepseek-v4-pro",
                    temperature=0.1,
                )
                collected["email_analysis"] = email_analysis
                log.info(
                    "contact.email_analyzed",
                    email=payload.email,
                    has_name=bool(email_analysis.get("name")),
                )
            except Exception as exc:
                log.error("contact.email_analysis_failed", error=str(exc))
                collected["email_analysis"] = None

        # 3. Enriquecimento de telefone
        if payload.phone:
            whatsapp = WhatsAppClient(http)
            gemini = GeminiClient(http)

            # 3a. Validar numero
            try:
                result = await whatsapp.check_numbers([payload.phone])
                phone_valid = (
                    len(result) > 0
                    and isinstance(result[0], dict)
                    and result[0].get("exists", False)
                )
                collected["phone_valid"] = phone_valid
                collected["whatsapp_check"] = result[0] if result else {}
            except Exception as exc:
                log.error("contact.phone_check_failed", phone=payload.phone, error=str(exc))
                phone_valid = False
                collected["phone_valid"] = False

            if phone_valid:
                # 3b. Perfil WhatsApp
                profile = None
                try:
                    profile = await whatsapp.fetch_profile(payload.phone)
                    collected["whatsapp_profile"] = profile
                    log.info(
                        "contact.profile_fetched",
                        phone=payload.phone,
                        has_picture=bool(profile.get("picture")),
                        is_business=profile.get("isBusiness", False),
                    )
                except Exception as exc:
                    log.error("contact.profile_fetch_failed", error=str(exc))
                    collected["whatsapp_profile"] = None

                # 3c. Perfil comercial
                if profile and profile.get("isBusiness"):
                    try:
                        biz = await whatsapp.fetch_business_profile(payload.phone)
                        collected["business_profile"] = biz
                        log.info(
                            "contact.business_profile_fetched",
                            phone=payload.phone,
                            has_category=bool(biz.get("category")),
                        )
                    except Exception as exc:
                        log.error(
                            "contact.business_profile_fetch_failed", error=str(exc)
                        )
                        collected["business_profile"] = None

                # 3d. Gemini: descrever foto de perfil
                if profile and profile.get("picture"):
                    try:
                        description = await gemini.describe_image(
                            image_url=profile["picture"],
                            prompt=(
                                "Descreva esta foto de perfil em detalhes. "
                                "Identifique: se e uma pessoa ou nao, genero aparente, "
                                "faixa etaria aproximada, caracteristicas fisicas relevantes, "
                                "contexto ou ambiente da foto."
                            ),
                            language="pt-BR",
                        )
                        collected["photo_description"] = description
                        log.info(
                            "contact.photo_described",
                            phone=payload.phone,
                            desc_len=len(description),
                        )
                    except Exception as exc:
                        log.error(
                            "contact.photo_description_failed", error=str(exc)
                        )
                        collected["photo_description"] = None

        # 4. Extracao estruturada via DeepSeek (so se houver dados)
        if collected:
            try:
                extracted = await deepseek._chat(
                    system_prompt=(
                        "Voce e um analista de dados de contacto. "
                        "Recebe dados brutos de varias fontes (analise de email, perfil WhatsApp, "
                        "descricao de foto, perfil comercial) e extrai informacao estruturada. "
                        "Retorne um JSON com as chaves:\n"
                        "  - name: string ou null (nome completo da pessoa)\n"
                        "  - gender: string ou null ('masculino', 'feminino', 'outro')\n"
                        "  - birth_date: string ou null (YYYY-MM-DD ou YYYY se so tiver ano)\n"
                        "  - avatar_url: string ou null (URL da foto — so preencha se for "
                        "foto de uma PESSOA; se for logo, paisagem, animal, use null)\n"
                        "  - profile_data: objeto com TODOS os dados uteis agregados\n"
                        "  - initial_analysis: texto narrativo detalhado em portugues brasileiro "
                        "descrevendo TUDO que foi possivel obter sobre este contacto. "
                        "Inclua inferencias razoaveis e indique o grau de confianca. "
                        "Seja honesto: marque quando um dado e incerto ou especulativo.\n"
                        "  - is_business: boolean\n"
                        "REGRAS:\n"
                        "1. NAO invente dados. Se nao ha evidencia suficiente, use null.\n"
                        "2. Confie mais em dados do WhatsApp (perfil verificado) "
                        "do que em analise de email.\n"
                        "3. avatar_url so preencha se a foto for claramente de uma pessoa.\n"
                        "4. initial_analysis deve ser um texto rico, detalhado, em portugues "
                        "brasileiro, com paragrafos bem estruturados.\n"
                        "5. profile_data deve conter TODOS os dados brutos organizados "
                        "de forma util."
                    ),
                    user_message=json.dumps(collected, ensure_ascii=False, default=str),
                    model="deepseek-v4-pro",
                    temperature=0.3,
                )
                log.info(
                    "contact.extraction_done",
                    has_name=bool(extracted.get("name")),
                    has_gender=bool(extracted.get("gender")),
                    has_birth=bool(extracted.get("birth_date")),
                    has_avatar=bool(extracted.get("avatar_url")),
                    analysis_len=len(extracted.get("initial_analysis", "")),
                )
            except Exception as exc:
                log.error(
                    "contact.extraction_failed",
                    error=str(exc),
                    exc_type=type(exc).__name__,
                )
                extracted = {
                    "name": None,
                    "gender": None,
                    "birth_date": None,
                    "avatar_url": None,
                    "profile_data": collected,
                    "initial_analysis": f"Erro na extracao dos dados: {exc}",
                    "is_business": False,
                }
        else:
            extracted = {
                "name": None,
                "gender": None,
                "birth_date": None,
                "avatar_url": None,
                "profile_data": None,
                "initial_analysis": None,
                "is_business": False,
            }

    # 5. Persiste Contact
    contact = await Contact.create(
        external_id=payload.external_id,
        phone=payload.phone,
        email=payload.email,
        name=extracted.get("name"),
        gender=extracted.get("gender"),
        birth_date=extracted.get("birth_date"),
        avatar_url=extracted.get("avatar_url"),
        profile_data=extracted.get("profile_data"),
        initial_analysis=extracted.get("initial_analysis"),
        is_business=extracted.get("is_business", False),
    )
    log.info(
        "contact.created_enriched",
        external_id=payload.external_id,
        has_name=bool(contact.name),
        has_avatar=bool(contact.avatar_url),
        is_business=contact.is_business,
    )
    return contact
