"""Endpoints de health/readiness — usados por load balancer e Proxmox."""

from fastapi import APIRouter
from tortoise import Tortoise

from app.config import get_settings

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    """Verifica se o processo esta vivo.

    Usado pelo load balancer / Proxmox para saber se o container responde.
    Nao verifica dependencias externas — apenas confirma que o processo HTTP esta no ar.
    """
    return {"status": "ok", "service": get_settings().service_name}


@router.get("/ready", summary="Readiness probe")
async def ready() -> dict:
    """Verifica se o servico esta pronto para receber trafego.

    Diferente do /health, este endpoint testa a conectividade com o banco.
    Se o banco estiver indisponivel, o load balancer deve parar de enviar
    trafego para esta instancia.
    """
    try:
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")
        return {"status": "ready", "db": "ok"}
    except Exception:
        return {"status": "not_ready", "db": "unreachable"}
