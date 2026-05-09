"""Endpoints de contactos — CRUD e verificacao externa."""

from fastapi import APIRouter, Query, status

from app.schemas.contact import ContactCheckResponse, ContactCreate, ContactRead
from app.services import contact_service

router = APIRouter()


@router.get(
    "/check",
    response_model=ContactCheckResponse,
    summary="Verificar contacto",
)
async def check_contact(
    phone: str | None = Query(
        default=None,
        description="Numero WhatsApp DDI+DDD+numero, ex: 5543996648750",
    ),
    email: str | None = Query(
        default=None,
        description="Endereco de email, ex: fulano@exemplo.com",
    ),
) -> ContactCheckResponse:
    """Verifica se um contacto existe na base e valida phone/email externamente.

    - Se o contacto ja existe na base local, retorna found=true com os dados.
    - Se nao existe, valida o phone via WhatsApp (check_numbers) e o email
      via regex local, retornando found=false + phone_valid/email_valid.

    **Nunca cria contacto** — apenas consulta.
    """
    result = await contact_service.check_contact(phone=phone, email=email)
    return ContactCheckResponse(**result)


@router.post(
    "",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar contacto",
)
async def create_contact(payload: ContactCreate) -> ContactRead:
    """Cria um contacto simples.

    Requer external_id unico. Pelo menos phone ou email deve ser informado.
    Se o external_id ja existir, retorna 409 Conflict.
    """
    contact = await contact_service.create_contact(payload)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.get(
    "",
    response_model=list[ContactRead],
    summary="Listar contactos",
)
async def list_contacts(
    limit: int = Query(default=50, ge=1, le=200, description="Maximo de registros"),
    offset: int = Query(default=0, ge=0, description="Offset de paginacao"),
) -> list[ContactRead]:
    """Lista todos os contactos com paginacao."""
    contacts = await contact_service.list_contacts(limit=limit, offset=offset)
    return [ContactRead.model_validate(c, from_attributes=True) for c in contacts]


@router.get(
    "/{external_id}",
    response_model=ContactRead,
    summary="Obter contacto",
)
async def get_contact(external_id: str) -> ContactRead:
    """Obtem um contacto pelo external_id.

    Retorna 404 se nao encontrado.
    """
    contact = await contact_service.get_contact_by_external_id(external_id)
    return ContactRead.model_validate(contact, from_attributes=True)


@router.delete(
    "/{external_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar contacto",
)
async def delete_contact(external_id: str) -> None:
    """Destroi um contacto e todos os dados associados.

    Remove em cascata:
    - Todas as mensagens do contacto
    - Todos os logs vinculados a essas mensagens
    - O proprio contacto
    """
    await contact_service.delete_contact(external_id)
