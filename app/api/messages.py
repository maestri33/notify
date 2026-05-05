from fastapi import APIRouter, status

from app.exceptions import NotFound
from app.models.message import Message
from app.schemas.message import MessageRead, MessageSend
from app.services import message_service

router = APIRouter()


@router.post("/send", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(payload: MessageSend) -> MessageRead:
    message = await message_service.send_message(payload)
    return MessageRead.model_validate(message, from_attributes=True)


@router.get("", response_model=list[MessageRead])
async def list_messages(
    contact_id: int | None = None, limit: int = 50, offset: int = 0
) -> list[MessageRead]:
    qs = Message.all()
    if contact_id is not None:
        qs = qs.filter(contact_id=contact_id)
    messages = await qs.offset(offset).limit(limit)
    return [MessageRead.model_validate(m, from_attributes=True) for m in messages]


@router.get("/{message_id}", response_model=MessageRead)
async def get_message(message_id: int) -> MessageRead:
    msg = await Message.get_or_none(id=message_id)
    if msg is None:
        raise NotFound(f"Mensagem {message_id} nao encontrada")
    return MessageRead.model_validate(msg, from_attributes=True)
