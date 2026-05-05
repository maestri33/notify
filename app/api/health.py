"""Endpoints de health/readiness — usados por load balancer e Proxmox."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness — o processo esta vivo."""
    return {"status": "ok", "service": get_settings().service_name}


@router.get("/ready")
async def ready() -> dict:
    """Readiness — pronto pra receber trafego.

    Em servicos com dependencia externa critica, faz ping no banco/redis aqui.
    """
    return {"status": "ready"}
