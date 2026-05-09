"""
Orquestrador central de envio de mensagens.

Fluxo:
  1. Resolve contacto por external_id
  2. Extrai texto (de .md ou direto)
  3. Detecta tipo de midia se houver (base64 ou URL)
  4. Gera titulo via DeepSeek Flash
  5. Insere texto no template HTML (adapta midia p/ email)
  6. Envia WhatsApp (texto + midia se houver)
  7. Envia Email (HTML com midia adaptada)
  8. Se --tts (so p/ texto), gera audio e envia WhatsApp audio nativo (PTT)
  9. Atualiza statuses
"""

import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.integrations.deepseek import DeepSeekClient
from app.integrations.elevenlabs import ElevenLabsClient
from app.integrations.gemini import GeminiClient
from app.integrations.smtp import SMTPClient
from app.integrations.whatsapp import WhatsAppClient
from app.models.message import (
    STATUS_FAILED,
    STATUS_SENT,
    STATUS_SKIPPED,
    Message,
)
from app.schemas.message import MessageSend
from app.services.contact_service import get_contact_by_external_id
from app.services.template_service import get_template
from app.utils.logging import get_logger

log = get_logger(__name__)

# MIME type -> WhatsApp media_type
_MIME_MAP = {
    "image/jpeg": "image", "image/jpg": "image", "image/png": "image",
    "image/webp": "image", "image/gif": "image",
    "video/mp4": "video", "video/quicktime": "video",
    "audio/mpeg": "audio", "audio/mp3": "audio", "audio/ogg": "audio",
    "audio/opus": "audio", "audio/wav": "audio",
}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}
_AUDIO_EXT = {".mp3", ".ogg", ".wav", ".opus", ".m4a"}


def _detect_media(source: str) -> tuple[str, str | None]:
    """Detecta o tipo de midia e o MIME type."""
    if source.startswith("data:"):
        m = re.match(r"data:([^;]+);", source)
        mime = m.group(1) if m else "application/octet-stream"
        return _MIME_MAP.get(mime, "document"), mime

    path = urlparse(source).path.lower()
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in _IMAGE_EXT:
        return "image", mimetypes.types_map.get(ext)
    if ext in _VIDEO_EXT:
        return "video", mimetypes.types_map.get(ext)
    if ext in _AUDIO_EXT:
        return "audio", mimetypes.types_map.get(ext)
    return "document", mimetypes.types_map.get(ext)


def _public_url(relative_path: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/media/{relative_path}"


def _dmz_url(relative_path: str) -> str:
    """URL interna da DMZ para WhatsApp/Evolution (acesso local)."""
    base = get_settings().dmz_base_url.rstrip("/")
    return f"{base}/media/{relative_path}"


def _handle_base64_media(data_uri: str) -> tuple[str, str, str]:
    """Decodifica data URI base64, salva em disco, retorna (url_publica, url_dmz, media_type)."""
    import base64 as b64
    import uuid

    m = re.match(r"data:([^;]+);base64,(.+)", data_uri, re.DOTALL)
    if not m:
        raise ValueError("Data URI invalida")
    mime = m.group(1)
    raw = b64.b64decode(m.group(2))

    media_type = _MIME_MAP.get(mime, "document")
    ext_map = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
        "video/mp4": ".mp4", "video/quicktime": ".mov",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/ogg": ".ogg",
        "audio/opus": ".opus", "audio/wav": ".wav",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime, mimetypes.guess_extension(mime) or ".bin")
    filename = f"{uuid.uuid4().hex}{ext}"
    out = Path("media/imagem")
    out.mkdir(parents=True, exist_ok=True)
    (out / filename).write_bytes(raw)
    relative = f"imagem/{filename}"
    public_url = _public_url(relative)
    dmz_url = _dmz_url(relative)
    log.info("media.base64_decoded", mime=mime, relative=relative)
    return public_url, dmz_url, media_type


def _email_media_html(media_url: str, media_type: str, caption: str) -> str:
    """Adapta a midia para HTML de email."""
    if media_type == "image":
        return (
            f'<div style="margin:16px 0"><img src="{media_url}" '
            f'style="max-width:100%;height:auto;border-radius:4px" alt="{caption}">'
            f'<p style="color:#333;font-size:14px;margin:8px 0 0">{caption}</p></div>'
        )
    if media_type == "video":
        return (
            f'<div style="margin:16px 0;background:#f0f0f0;padding:16px;border-radius:4px;text-align:center">'
            f'<p style="margin:0 0 8px;font-size:24px">🎬</p>'
            f'<p style="margin:0"><a href="{media_url}" style="color:#1a73e8">Clique para ver o video</a></p>'
            f'<p style="color:#666;font-size:14px;margin:8px 0 0">{caption}</p></div>'
        )
    if media_type == "audio":
        return (
            f'<div style="margin:16px 0;background:#f0f0f0;padding:16px;border-radius:4px;text-align:center">'
            f'<p style="margin:0 0 8px;font-size:24px">🎵</p>'
            f'<p style="margin:0"><a href="{media_url}" style="color:#1a73e8">Clique para ouvir o audio</a></p>'
            f'<p style="color:#666;font-size:14px;margin:8px 0 0">{caption}</p></div>'
        )
    name = media_url.rsplit("/", 1)[-1] if "/" in media_url else "arquivo"
    return (
        f'<div style="margin:16px 0;background:#f0f0f0;padding:16px;border-radius:4px;text-align:center">'
        f'<p style="margin:0 0 8px;font-size:24px">📎</p>'
        f'<p style="margin:0"><a href="{media_url}" style="color:#1a73e8">Baixar {name}</a></p>'
        f'<p style="color:#666;font-size:14px;margin:8px 0 0">{caption}</p></div>'
    )


def _render_html(template: str, title: str, content: str) -> str:
    settings = get_settings()

    # Escapa {{ e }} para nao quebrarem o template Jinja2
    safe_title = title.replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")
    safe_content = content.replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")

    return (
        template.replace("{{title}}", safe_title)
        .replace("{{content}}", safe_content.replace("\n", "<br>"))
        .replace("{{service_name}}", settings.service_name)
    )


async def list_messages(
    contact_id: int | None = None, limit: int = 50, offset: int = 0
) -> list[Message]:
    qs = Message.all()
    if contact_id is not None:
        qs = qs.filter(contact_id=contact_id)
    return await qs.offset(offset).limit(limit)


async def get_message(message_id: int) -> Message | None:
    return await Message.get_or_none(id=message_id)


async def send_message(payload: MessageSend) -> Message:
    """Envia mensagem via WhatsApp + Email, com TTS opcional (apenas texto)."""
    settings = get_settings()

    # Resolve contacto
    contact = await get_contact_by_external_id(payload.external_id)

    # Cliente HTTP unico para toda a orquestracao
    async with httpx.AsyncClient() as http:
        # Extrai texto (URL .md ou direto)
        text = payload.content
        if text.startswith(("http://", "https://")) and text.endswith(".md"):
            resp = await http.get(text, timeout=15.0)
            resp.raise_for_status()
            text = resp.text

        # Detecta midia
        media_type = None
        media_url = payload.media_url
        whatsapp_media_url: str | None = None
        if payload.media_url:
            if payload.media_url.startswith("data:"):
                media_url, whatsapp_media_url, media_type = _handle_base64_media(payload.media_url)
            else:
                media_type, _ = _detect_media(payload.media_url)

        msg_type = "media" if media_type else "text"
        tts_enabled = payload.flags.tts and msg_type == "text"

        # IA — gera texto (DeepSeek)
        ai_used = False
        if payload.flags.ai and msg_type == "text":
            ai_used = True
            try:
                text = await DeepSeekClient(http).generate_message(
                    prompt=text,
                    extra_instruction=payload.instruction,
                    for_tts=tts_enabled,
                )
                log.info("ai.text_generated", length=len(text))
                if "{{" in text:
                    log.warning("ai.unresolved_placeholder_cleaned", text_preview=text[:200])
                    text = re.sub(r"\{\{.*?\}\}", "", text).strip()
            except Exception as exc:
                log.error("ai.generation_failed", error=str(exc))

        # Imagem — gera via Gemini (com prompt opcional do DeepSeek)
        img_used = False
        if payload.flags.img:
            img_used = True
            if payload.instruction:
                image_prompt = payload.instruction
            else:
                try:
                    image_prompt = await DeepSeekClient(http).generate_image_prompt(text)
                    log.info("img.prompt_generated", prompt_preview=image_prompt[:80])
                except Exception as exc:
                    log.error("img.prompt_failed", error=str(exc))
                    image_prompt = text

            try:
                ref_url = media_url if media_type == "image" else None
                relative = await GeminiClient(http).generate_image(
                    prompt=image_prompt,
                    reference_image_url=ref_url,
                )
                media_url = _public_url(relative)
                whatsapp_media_url = _dmz_url(relative)
                media_type = "image"
                msg_type = "media"
                tts_enabled = False
                log.info("img.generated", relative=relative)
            except Exception as exc:
                log.error("img.generation_failed", error=str(exc))

        # Cria registo de mensagem
        message = await Message.create(
            contact=contact, type=msg_type, content_text=text
        )

        # Gera titulo via AI
        try:
            title = await DeepSeekClient(http).generate_title(text)
        except Exception:
            title = "Nova mensagem"

        # Prepara HTML do email
        template = await get_template()
        email_body = _email_media_html(media_url, media_type, text) if media_type and media_url else text
        html = _render_html(template, title, email_body)

        # Envia WhatsApp (texto ou midia; TTS substitui o texto)
        whatsapp = WhatsAppClient(http)
        _wa_url = whatsapp_media_url or media_url
        if not tts_enabled:
            try:
                if media_type and media_url:
                    await whatsapp.send_media(contact.phone, _wa_url, media_type, caption=text)
                else:
                    await whatsapp.send_text(contact.phone, text)
                message.whatsapp_status = STATUS_SENT
            except Exception as exc:
                log.error("whatsapp.send_failed", error=str(exc))
                message.whatsapp_status = STATUS_FAILED

        # Envia Email
        if contact.email:
            try:
                smtp = SMTPClient(http)
                await smtp.configure_smtp(
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_user=settings.smtp_user,
                    smtp_pass=settings.smtp_pass,
                )
                await smtp.send_single_email(
                    to_email=contact.email,
                    subject=title,
                    sender_name=settings.service_name,
                    html_content=html,
                )
                message.email_status = STATUS_SENT
            except Exception as exc:
                log.error("email.send_failed", error=str(exc))
                message.email_status = STATUS_FAILED
        else:
            message.email_status = STATUS_SKIPPED

        # TTS — envia nota de voz nativa (substitui texto no WhatsApp)
        if tts_enabled:
            try:
                tts = ElevenLabsClient()
                relative_path = tts.generate_and_save(text)
                message.tts_audio_url = _public_url(relative_path)
                await whatsapp.send_whatsapp_audio(contact.phone, _dmz_url(relative_path))
                message.whatsapp_status = STATUS_SENT
                log.info("tts.sent", contact=payload.external_id, url=message.tts_audio_url)
            except Exception as exc:
                log.error("tts.failed", error=str(exc))
                message.whatsapp_status = STATUS_FAILED

    # Atualiza e persiste
    message.email_subject = title
    await message.save()
    log.info(
        "message.sent",
        id=message.id,
        type=msg_type,
        media=media_type,
        whatsapp=message.whatsapp_status,
        email=message.email_status,
        tts=tts_enabled,
        ai=ai_used,
        img=img_used,
    )
    return message
