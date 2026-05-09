"""
Entrypoint FastAPI.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 80
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.db import close_db, init_db
from app.exceptions import DomainError
from app.utils.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level, json_mode=settings.env != "dev")
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("service.startup", service=settings.service_name, env=settings.env)
    await init_db()
    try:
        yield
    finally:
        await close_db()
        log.info("service.shutdown")


app = FastAPI(
    title=settings.service_name,
    version="0.4.0",
    lifespan=lifespan,
)


@app.get(
    "/",
    summary="Status completo do servico",
    description="Dashboard de staff — retorna metadata e conectividade de "
    "todas as integracoes (banco, Redis, RabbitMQ, SMTP, WhatsApp, "
    "DeepSeek, ElevenLabs, Gemini).",
)
async def root() -> dict:
    from tortoise import Tortoise

    info: dict = {
        "service": settings.service_name,
        "version": app.version,
        "env": settings.env,
    }

    # Banco
    try:
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")
        info["db"] = "ok"
    except Exception:
        info["db"] = "unreachable"

    # Redis
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
            info["redis"] = "ok"
        except Exception:
            info["redis"] = "unreachable"
    else:
        info["redis"] = "not_configured"

    # RabbitMQ
    if settings.amqp_url:
        try:
            import aio_pika
            conn = await aio_pika.connect_robust(settings.amqp_url)
            await conn.close()
            info["amqp"] = "ok"
        except Exception:
            info["amqp"] = "unreachable"
    else:
        info["amqp"] = "not_configured"

    # Integracoes HTTP (health check leve — apenas conectividade)
    import httpx

    async with httpx.AsyncClient(timeout=5.0) as http:
        # SMTP (Mail Merge API)
        try:
            resp = await http.get(f"{settings.smtp_api_base_url}/vercel")
            info["smtp_api"] = "ok" if resp.status_code < 500 else "error"
        except Exception:
            info["smtp_api"] = "unreachable"

        # WhatsApp (Evolution GO)
        try:
            resp = await http.get(
                f"{settings.whatsapp_api_base_url}/instance/status",
                headers={"apikey": settings.whatsapp_global_api_key},
            )
            info["whatsapp_api"] = "ok" if resp.status_code < 500 else "error"
        except Exception:
            info["whatsapp_api"] = "unreachable"

        # DeepSeek — so verifica se a chave esta configurada
        info["deepseek"] = "configured" if settings.deepseek_api_key else "not_configured"

        # ElevenLabs — so verifica se a chave esta configurada
        info["elevenlabs"] = "configured" if settings.elevenlabs_api_key else "not_configured"

        # Gemini — so verifica se a chave esta configurada
        info["gemini"] = "configured" if settings.gemini_api_key else "not_configured"

    return info

# DMZ: CORS aberto por enquanto. Apertar quando o usuario pedir "trava isso".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Converte excecoes de dominio em respostas HTTP padronizadas."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


app.include_router(api_router, prefix="/api/v1")
app.mount("/media", StaticFiles(directory="media"), name="media")
