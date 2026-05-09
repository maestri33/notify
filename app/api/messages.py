"""Endpoints de mensagens — envio multicanal (WhatsApp + Email)."""

from fastapi import APIRouter, Query, status

from app.exceptions import NotFound
from app.schemas.message import MessageRead, MessageSend
from app.services import message_service

router = APIRouter()


@router.post(
    "/send",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar mensagem multicanal",
)
async def send_message(payload: MessageSend) -> MessageRead:
    """Envia uma mensagem via WhatsApp + Email, com opcoes de IA, TTS e imagem.

    Fluxo completo:
    1. Resolve contacto por external_id (404 se nao existir)
    2. Se content e URL .md, faz download e extrai o texto
    3. Detecta midia (URL ou base64) se media_url informado
    4. Se flags.ai: DeepSeek Pro reescreve o texto
    5. Se flags.img: Gemini gera imagem (instruction = prompt da imagem;
       se nao informado, DeepSeek gera o prompt automaticamente)
    6. Cria registo Message
    7. Gera titulo do email via DeepSeek Flash
    8. Prepara HTML com template de email
    9. Envia WhatsApp (texto ou midia com caption)
    10. Envia Email (HTML com template, midia inline se houver)
    11. Se flags.tts (apenas texto): ElevenLabs gera audio MP3 e envia
        como nota de voz nativa (PTT) via WhatsApp
    12. Atualiza statuses e persiste

    Flags img e tts sao mutuamente exclusivas — img vence.
    """
    message = await message_service.send_message(payload)
    return MessageRead.model_validate(message, from_attributes=True)


@router.get(
    "",
    response_model=list[MessageRead],
    summary="Listar mensagens",
)
async def list_messages(
    contact_id: int | None = Query(
        default=None, description="Filtrar por ID do contacto"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Maximo de registros"),
    offset: int = Query(default=0, ge=0, description="Offset de paginacao"),
) -> list[MessageRead]:
    """Lista mensagens com paginacao. Opcionalmente filtra por contacto."""
    messages = await message_service.list_messages(
        contact_id=contact_id, limit=limit, offset=offset
    )
    return [MessageRead.model_validate(m, from_attributes=True) for m in messages]


@router.get(
    "/{message_id}",
    response_model=MessageRead,
    summary="Obter mensagem",
)
async def get_message(message_id: int) -> MessageRead:
    """Obtem uma mensagem pelo ID interno.

    Retorna 404 se nao encontrada.
    """
    msg = await message_service.get_message(message_id)
    if msg is None:
        raise NotFound(f"Mensagem {message_id} nao encontrada")
    return MessageRead.model_validate(msg, from_attributes=True)
