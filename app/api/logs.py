"""Endpoints de logs do sistema."""

from fastapi import APIRouter, Query

from app.schemas.log import LogRead
from app.services import log_service

router = APIRouter()


@router.get(
    "",
    response_model=list[LogRead],
    summary="Listar logs",
)
async def list_logs(
    message_id: int | None = Query(
        default=None, description="Filtrar por ID da mensagem"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximo de registros"),
    offset: int = Query(default=0, ge=0, description="Offset de paginacao"),
) -> list[LogRead]:
    """Lista logs de acoes do sistema com paginacao.

    Logs documentam toda a atividade: criacao de contactos, envio de
    mensagens, falhas de integracao e enriquecimento.
    Opcionalmente filtra por message_id para ver o historico de uma
    mensagem especifica.
    """
    if message_id is not None:
        records = await log_service.list_logs_by_message(message_id)
    else:
        records = await log_service.list_logs(limit=limit, offset=offset)
    return [LogRead.model_validate(r, from_attributes=True) for r in records]
