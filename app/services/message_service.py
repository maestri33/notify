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
from app.models.message import Message
from app.schemas.message import MessageSend
from app.services.clients.deepseek import DeepSeekClient
from app.services.clients.elevenlabs import ElevenLabsClient
from app.services.clients.gemini import GeminiClient
from app.services.clients.whatsapp import WhatsAppClient
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
    """Detecta o tipo de midia e o MIME type.

    Args:
        source: URL ou data URI (base64). Ex: "data:image/png;base64,iVBOR..."

    Returns:
        (media_type, mime_type) onde media_type e image/video/audio/document
        e mime_type e o MIME detectado (ou None).
    """
    # data URI: data:image/png;base64,...
    if source.startswith("data:"):
        m = re.match(r"data:([^;]+);", source)
        mime = m.group(1) if m else "application/octet-stream"
        media_type = _MIME_MAP.get(mime, "document")
        return media_type, mime

    # URL — detecta por extensao
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
    """Converte path relativo (ex: 'audio/abc.mp3') em URL publica (email, etc)."""
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/files/{relative_path}"


def _dmz_url(relative_path: str) -> str:
    """URL interna da DMZ para WhatsApp/Evolution (acesso local)."""
    return f"http://10.10.10.144:80/files/{relative_path}"


def _handle_base64_media(data_uri: str) -> tuple[str, str]:
    """Decodifica data URI base64, salva em disco, retorna (url, media_type)."""
    import base64 as b64
    import uuid

    m = re.match(r"data:([^;]+);base64,(.+)", data_uri, re.DOTALL)
    if not m:
        raise ValueError("Data URI invalida")
    mime = m.group(1)
    raw = b64.b64decode(m.group(2))

    media_type = _MIME_MAP.get(mime, "document")
    # Determina extensao
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
    out = Path("data/public/media")
    out.mkdir(parents=True, exist_ok=True)
    (out / filename).write_bytes(raw)
    relative = f"media/{filename}"
    url = _public_url(relative)
    log.info("media.base64_decoded", mime=mime, relative=relative)
    return url, media_type


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
    # document / fallback
    name = media_url.rsplit("/", 1)[-1] if "/" in media_url else "arquivo"
    return (
        f'<div style="margin:16px 0;background:#f0f0f0;padding:16px;border-radius:4px;text-align:center">'
        f'<p style="margin:0 0 8px;font-size:24px">📎</p>'
        f'<p style="margin:0"><a href="{media_url}" style="color:#1a73e8">Baixar {name}</a></p>'
        f'<p style="color:#666;font-size:14px;margin:8px 0 0">{caption}</p></div>'
    )


async def _extract_text(content: str) -> str:
    """Se content e URL de .md, baixa e extrai. Senao retorna o texto direto."""
    if content.startswith(("http://", "https://")) and content.endswith(".md"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(content, timeout=15.0)
            resp.raise_for_status()
            return resp.text
    return content


def _render_html(template: str, title: str, content: str) -> str:
    """Insere titulo e conteudo no template HTML."""
    settings = get_settings()
    return (
        template.replace("{{title}}", title)
        .replace("{{content}}", content.replace("\n", "<br>"))
        .replace("{{service_name}}", settings.service_name)
    )


async def send_message(payload: MessageSend) -> Message:
    """Envia mensagem via WhatsApp + Email, com TTS opcional (apenas texto)."""
    settings = get_settings()

    # 1. Resolve contacto
    contact = await get_contact_by_external_id(payload.external_id)

    # 2. Extrai texto
    text = await _extract_text(payload.content)

    # 3. Detecta midia
    media_type = None
    media_url = payload.media_url  # pode ser substituido se for base64
    if payload.media_url:
        if payload.media_url.startswith("data:"):
            # Base64 — decodifica, salva, gera URL publica
            media_url, media_type = _handle_base64_media(payload.media_url)
        else:
            media_type, _ = _detect_media(payload.media_url)

    msg_type = "media" if media_type else "text"

    # TTS so faz sentido sem midia
    tts_enabled = payload.flags.tts and msg_type == "text"

    # 3.5. Se --ai, gera texto via IA (substitui content original)
    ai_used = False
    if payload.flags.ai and msg_type == "text":
        ai_used = True
        # Precisamos do cliente DeepSeek aqui — cria um temporario
        async with httpx.AsyncClient() as _ai_http:
            _ai = DeepSeekClient(_ai_http)
            try:
                text = await _ai.generate_message(
                    prompt=text,
                    extra_instruction=payload.instruction,
                    for_tts=tts_enabled,
                )
                log.info("ai.text_generated", length=len(text))
                # Detecta placeholders nao resolvidos {{...}} no output da IA
                if "{{" in text:
                    log.error(
                        "ai.unresolved_placeholder",
                        text_preview=text[:200],
                        hint="placeholder {{...}} detectado — "
                             "resolucao de variaveis sera implementada em fase posterior",
                    )
            except Exception as exc:
                log.error("ai.generation_failed", error=str(exc))

    # 3.6. Se --img, gera imagem via Gemini
    # content = texto/caption, instruction = prompt da imagem
    # Se nao tem instruction, DeepSeek gera o prompt a partir do texto
    img_used = False
    if payload.flags.img:
        img_used = True
        async with httpx.AsyncClient() as _img_http:
            # Resolve o prompt da imagem
            if payload.instruction:
                image_prompt = payload.instruction
            else:
                # Gera prompt de imagem via DeepSeek baseado no texto
                _ds = DeepSeekClient(_img_http)
                try:
                    image_prompt = await _ds.generate_image_prompt(text)
                    log.info("img.prompt_generated", prompt_preview=image_prompt[:80])
                except Exception as exc:
                    log.error("img.prompt_failed", error=str(exc))
                    image_prompt = text  # fallback: usa o proprio texto

            _gemini = GeminiClient(_img_http)
            try:
                # Se tem media_url, usa como referencia p/ edicao/inspiracao
                ref_url = media_url if media_type == "image" else None
                relative = await _gemini.generate_image(
                    prompt=image_prompt,
                    reference_image_url=ref_url,
                )
                media_url = _public_url(relative)
                whatsapp_media_url = _dmz_url(relative)
                media_type = "image"
                msg_type = "media"
                tts_enabled = False  # --img invalida --tts
                log.info("img.generated", relative=relative)
            except Exception as exc:
                log.error("img.generation_failed", error=str(exc))

    # 4. Cria registo de mensagem
    message = await Message.create(
        contact=contact, type=msg_type, content_text=text
    )

    # 5. Cliente HTTP compartilhado
    async with httpx.AsyncClient() as http:
        whatsapp = WhatsAppClient(http)
        deepseek = DeepSeekClient(http)

        # 6. Gera titulo via AI
        try:
            title = await deepseek.generate_title(text)
        except Exception:
            title = "Nova mensagem"

        # 7. Prepara HTML do email (com midia se houver)
        template = await get_template()
        email_body = text
        if media_type and media_url:
            media_block = _email_media_html(media_url, media_type, text)
            email_body = media_block
        html = _render_html(template, title, email_body)

        # 8. Envia WhatsApp — texto + midia (com caption=texto)
        # Para midia local (Gemini/TTS), usa URL interna da DMZ;
        # para midia externa (user-provided URL), usa a URL original.
        _wa_url = locals().get("whatsapp_media_url", media_url)
        try:
            if media_type and media_url:
                await whatsapp.send_media(
                    contact.phone,
                    _wa_url,
                    media_type,
                    caption=text,
                )
            else:
                await whatsapp.send_text(contact.phone, text)
            message.whatsapp_status = "sent"
        except Exception as exc:
            log.error("whatsapp.send_failed", error=str(exc))
            message.whatsapp_status = "failed"

        # 9. Envia Email
        if contact.email:
            try:
                from app.services.clients.smtp import SMTPClient

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
                message.email_status = "sent"
            except Exception as exc:
                log.error("email.send_failed", error=str(exc))
                message.email_status = "failed"
        else:
            message.email_status = "skipped"

        # 10. TTS — apenas para texto (sem midia)
        if tts_enabled:
            try:
                tts = ElevenLabsClient()
                relative_path = tts.generate_and_save(text)
                audio_url = _public_url(relative_path)
                message.tts_audio_url = audio_url
                # WhatsApp usa URL interna da DMZ (Evolution esta na mesma rede)
                await whatsapp.send_whatsapp_audio(
                    contact.phone, _dmz_url(relative_path)
                )
                log.info("tts.sent", contact=payload.external_id, url=audio_url)
            except Exception as exc:
                log.error("tts.failed", error=str(exc))

    # 11. Atualiza mensagem e persiste
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
