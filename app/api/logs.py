from fastapi import APIRouter, Query

from app.schemas.log import LogRead
from app.services import log_service

router = APIRouter()


@router.get("", response_model=list[LogRead])
async def list_logs(
    message_id: int | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
) -> list[LogRead]:
    """Lista logs. Opcionalmente filtra por message_id."""
    if message_id is not None:
        records = await log_service.list_logs_by_message(message_id)
    else:
        records = await log_service.list_logs(limit=limit, offset=offset)
    return [LogRead.model_validate(r, from_attributes=True) for r in records]
