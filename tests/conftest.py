"""
Fixtures globais.

- `app` e `client` sobem o FastAPI com Tortoise apontando pra SQLite in-memory,
  para testes isolados e rapidos.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db() -> AsyncIterator[None]:
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
    )
    await Tortoise.generate_schemas()
    try:
        yield
    finally:
        await Tortoise.close_connections()


@pytest.fixture
async def client(db: None) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
