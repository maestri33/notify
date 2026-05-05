from fastapi import APIRouter, Query, status

from app.schemas.contact import ContactCheckResponse, ContactCreate, ContactRead
from app.services import contact_service

router = APIRouter()


@router.get("/check", response_model=ContactCheckResponse)
async def check_contact(
    phone: str | None = Query(default=None),
    email: str | None = Query(default=None),
) -> ContactCheckResponse:
    """Verifica se um contacto existe e valida phone/email externamente.

    Nunca cria um contacto — apenas consulta.
    """
    result = await contact_service.check_contact(phone=phone, email=email)
    return ContactCheckResponse(**result)


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(payload: ContactCreate) -> ContactRead:
    """Cria um contacto com enriquecimento via IA e WhatsApp.

    Se telefone for informado: valida no WhatsApp, busca perfil e foto.
    Se email for informado: analisa via DeepSeek para extrair nome/genero/idade.
    Todos os dados sao consolidados por IA em dados estruturados.
    """
    contact = await contact_service.enrich_contact(payload)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.get("/{external_id}", response_model=ContactRead)
async def get_contact(external_id: str) -> ContactRead:
    contact = await contact_service.get_contact_by_external_id(external_id)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.get("", response_model=list[ContactRead])
async def list_contacts(
    limit: int = 50,
    offset: int = 0,
) -> list[ContactRead]:
    contacts = await contact_service.list_contacts(limit=limit, offset=offset)
    return [ContactRead.model_validate(c, from_attributes=True) for c in contacts]
