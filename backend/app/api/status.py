"""System status and WhatsApp endpoints."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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
