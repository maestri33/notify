"""
Cliente HTTP para falar com outros microservices.

- Async (httpx).
- Retry simples com backoff exponencial pra erros transitorios.
- Timeout default sensato.
- Para CADA servico externo, crie um wrapper em
  `app/integrations/<servico>_client.py` que usa este client e expoe
  funcoes de alto nivel — NAO espalhe httpx.get(...) pelo codigo.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.exceptions import IntegrationError
from app.utils.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRYABLE_STATUS = {429, 502, 503, 504}


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yielda um AsyncClient — use como Depends() no FastAPI."""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        yield client


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    backoff_base: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """Faz a request com retry exponencial em erros transitorios."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < max_attempts:
                log.warning(
                    "http.retry",
                    method=method,
                    url=url,
                    status=resp.status_code,
                    attempt=attempt,
                )
                await asyncio.sleep(backoff_base * 2 ** (attempt - 1))
                continue
            return resp
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            log.warning("http.transport_error", url=url, attempt=attempt, error=str(exc))
            if attempt == max_attempts:
                raise IntegrationError(f"Falha ao chamar {url}: {exc}") from exc
            await asyncio.sleep(backoff_base * 2 ** (attempt - 1))
    # nao deve cair aqui, mas pro mypy:
    raise IntegrationError(f"Falha ao chamar {url}: {last_exc}")
