"""System health status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.schemas import ServiceStatus
from app.db import get_session
from app.models.service_config import ServiceConfig
from app.services.baileys import BaileysClient, BaileysError, get_baileys

router = APIRouter(tags=["system"])


@router.get("/status", response_model=ServiceStatus)
def system_status(
    session: Session = Depends(get_session),
    baileys: BaileysClient = Depends(get_baileys),
) -> ServiceStatus:
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

    redis_status = "ok"
    try:
        import redis as redis_lib
        from app.config import settings
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
    except Exception:
        redis_status = "error"

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
