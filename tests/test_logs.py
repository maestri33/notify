"""Testes do endpoint /api/v1/logs."""

from httpx import AsyncClient


async def test_list_logs(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
