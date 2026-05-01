"""System status and WhatsApp endpoints."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session

from app.api.schemas import ServiceStatus, WhatsAppStatus
from app.db import get_session
from app.models.service_config import ServiceConfig
from app.services.baileys import BaileysClient, BaileysError, get_baileys

router = APIRouter(tags=["status"])


# ---------- GET /status ----------

@router.get("/status", response_model=ServiceStatus)
def system_status(
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> ServiceStatus:
    # WhatsApp / Baileys
    wa_state = "unreachable"
    wa_jid = None
    wa_device = None
    try:
        s = baileys.status()
        wa_state = s.get("state", "unknown")
        wa_jid = s.get("jid")
        wa_device = s.get("device_name")
    except BaileysError:
        pass

    # Redis — try importing rq and pinging
    redis_status = "ok"
    try:
        import redis as redis_lib
        from app.config import settings
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
    except Exception:
        redis_status = "error"

    # ServiceConfig
    cfg = session.get(ServiceConfig, 1)
    sms_ok = bool(cfg and cfg.sms_gateway_url)
    smtp_ok = bool(cfg and cfg.smtp_host and cfg.smtp_from_email)
    el_ok = bool(cfg and cfg.elevenlabs_api_key and cfg.elevenlabs_voice_id)

    return ServiceStatus(
        api="ok",
        whatsapp_state=wa_state,
        whatsapp_jid=wa_jid,
        whatsapp_device=wa_device,
        redis=redis_status,
        sms_configured=sms_ok,
        smtp_configured=smtp_ok,
        elevenlabs_configured=el_ok,
    )


# ---------- GET /whatsapp/status ----------

@router.get("/whatsapp/status", response_model=WhatsAppStatus)
def whatsapp_status(baileys: BaileysClient = Depends(get_baileys)) -> WhatsAppStatus:
    try:
        s = baileys.status()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return WhatsAppStatus(
        state=s.get("state", "unknown"),
        jid=s.get("jid"),
        device_name=s.get("device_name"),
        last_seen=s.get("last_seen"),
    )


# ---------- GET /whatsapp/qr ----------

@router.get("/whatsapp/qr")
def whatsapp_qr(
    fmt: str = "png",
    baileys: BaileysClient = Depends(get_baileys),
) -> Response:
    """
    Returns the WhatsApp pairing QR code.

    - `fmt=png`  → image/png binary (default)
    - `fmt=base64` → JSON `{"qr": "<base64 string>"}` — handy for mobile apps
    - Returns 404 if already connected or QR not yet generated.
    - Returns 503 if Baileys sidecar is unreachable.
    """
    try:
        png = baileys.qr_png()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

    if png is None:
        raise HTTPException(404, "QR not available — already connected or not yet generated")

    if fmt == "base64":
        import json
        return Response(
            content=json.dumps({"qr": base64.b64encode(png).decode()}),
            media_type="application/json",
        )

    return Response(content=png, media_type="image/png")


# ---------- POST /whatsapp/validate ----------

class ValidateRequest(BaseModel):
    phone: str


class ValidateResponse(BaseModel):
    exists: bool
    jid: str | None = None


@router.post("/whatsapp/validate", response_model=ValidateResponse)
def whatsapp_validate(
    body: ValidateRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    """Check if a phone number is registered on WhatsApp."""
    try:
        result = baileys.validate(body.phone)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return ValidateResponse(exists=result.get("exists", False), jid=result.get("jid"))


# ---------- POST /whatsapp/logout ----------

@router.post("/whatsapp/logout")
def whatsapp_logout(baileys: BaileysClient = Depends(get_baileys)) -> dict:
    try:
        baileys.logout()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return {"ok": True}


# ---------- POST /whatsapp/restart ----------

@router.post("/whatsapp/restart")
def whatsapp_restart(baileys: BaileysClient = Depends(get_baileys)) -> dict:
    try:
        baileys.restart()
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    return {"ok": True}


# ---------- POST /whatsapp/send/text ----------

class SendTextRequest(BaseModel):
    phone: str
    text: str


class SendPhoneResponse(BaseModel):
    message_id: str
    jid: str


@router.post("/whatsapp/send/text", response_model=SendPhoneResponse)
def whatsapp_send_text(
    body: SendTextRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    """Send a text message to a phone number (auto-resolves WhatsApp JID)."""
    try:
        result = baileys.send_text_phone(body.phone, body.text)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    if "error" in result:
        raise HTTPException(404, result["error"])
    return SendPhoneResponse(message_id=result["message_id"], jid=result["jid"])


# ---------- POST /whatsapp/send/ptt ----------

class SendPttRequest(BaseModel):
    phone: str
    audio_base64: str | None = None
    text: str | None = None  # if provided + no audio_base64, TTS is used


from app.services.tts import synthesize, TTSError
from app.services.config_store import load_service_config
from app.services.markdown import md_to_plain


@router.post("/whatsapp/send/ptt", response_model=SendPhoneResponse)
def whatsapp_send_ptt(
    body: SendPttRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    """Send a voice note (PTT) to a phone number.

    Provide `audio_base64` (pre-synthesized OGG/Opus) OR `text` (for server-side TTS).
    """
    audio_b64 = body.audio_base64
    if not audio_b64 and body.text:
        plain = md_to_plain(body.text)
        if not plain:
            raise HTTPException(422, "text is empty after stripping markdown")
        cfg = load_service_config()
        try:
            audio_bytes = synthesize(plain, cfg)
        except TTSError as e:
            raise HTTPException(503, f"TTS failed: {e}")
        audio_b64 = base64.b64encode(audio_bytes).decode()
    if not audio_b64:
        raise HTTPException(422, "audio_base64 or text required")

    try:
        result = baileys.send_ptt_phone(body.phone, audio_b64)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")
    if "error" in result:
        raise HTTPException(404, result["error"])
    return SendPhoneResponse(message_id=result["message_id"], jid=result["jid"])


# ---------- POST /whatsapp/broadcast ----------

class BroadcastRequest(BaseModel):
    phones: list[str]
    content: str
    is_tts: bool = False
    media_urls: list[str] = []


class BroadcastResultItem(BaseModel):
    phone: str
    jid: str | None = None
    status: str  # "sent" | "not_found" | "error"
    message_id: str | None = None
    error: str | None = None


class BroadcastResponse(BaseModel):
    results: list[BroadcastResultItem]


@router.post("/whatsapp/broadcast", response_model=BroadcastResponse)
def whatsapp_broadcast(
    body: BroadcastRequest,
    baileys: BaileysClient = Depends(get_baileys),
):
    """Send the same message to multiple phone numbers.

    If `is_tts=True`, audio is synthesized once and reused for all recipients.
    Media URLs are sent to each recipient independently.
    """
    from app.services.markdown import md_to_whatsapp, md_to_plain
    from app.services.tts import synthesize, TTSError
    from app.services.config_store import load_service_config

    results: list[BroadcastResultItem] = []

    # Pre-synthesize TTS audio if needed (once for all recipients)
    audio_b64 = None
    if body.is_tts:
        plain = md_to_plain(body.content)
        if not plain:
            raise HTTPException(422, "content is empty after stripping markdown")
        cfg = load_service_config()
        try:
            audio_bytes = synthesize(plain, cfg)
        except TTSError as e:
            raise HTTPException(503, f"TTS failed: {e}")
        audio_b64 = base64.b64encode(audio_bytes).decode()

    try:
        if body.is_tts and audio_b64:
            # PTT broadcast (one audio, all phones)
            result = baileys.broadcast_ptt(body.phones, audio_b64)
        else:
            # Text broadcast
            wa_text = md_to_whatsapp(body.content)
            result = baileys.broadcast_text(body.phones, wa_text)
    except BaileysError as e:
        raise HTTPException(503, f"Baileys unreachable: {e}")

    for r in result.get("results", []):
        results.append(BroadcastResultItem(**r))

    # Send media to each successfully sent recipient (if any)
    if body.media_urls:
        for r in results:
            if r.status == "sent" and r.jid:
                for url in body.media_urls:
                    try:
                        from app.services.senders import _head_mimetype
                        mime = _head_mimetype(url)
                        baileys.send_media(r.jid, url=url, mimetype=mime)
                    except BaileysError:
                        pass  # media is best-effort

    return BroadcastResponse(results=results)
