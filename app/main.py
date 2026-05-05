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
configure_logging(settings.log_level)
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
    version="0.1.0",
    lifespan=lifespan,
)

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


app.include_router(api_router)
app.mount("/files", StaticFiles(directory="data/public"), name="files")
