"""Testes do endpoint /health e /ready."""

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


async def test_ready(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}
