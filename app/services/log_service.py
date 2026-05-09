"""
Servico de logs — listagem de registros do sistema.

Logs sao vinculados a Message (opcionalmente) e documentam
toda a logica de negocio: envios, enriquecimento, falhas.
"""

from app.models.log import Log
from app.utils.logging import get_logger

log = get_logger(__name__)


async def list_logs(limit: int = 50, offset: int = 0) -> list[Log]:
    return await Log.all().offset(offset).limit(limit)


async def list_logs_by_message(message_id: int) -> list[Log]:
    return await Log.filter(message_id=message_id).all()
