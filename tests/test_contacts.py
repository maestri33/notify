"""
Testes do modulo de contactos — check, create, get, list.
"""

from httpx import AsyncClient


async def test_check_contact_email_valid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check?email=teste@exemplo.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["email_valid"] is True
    assert body["phone_valid"] is None


async def test_check_contact_email_invalid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check?email=invalido")
    assert resp.status_code == 200
    assert resp.json()["email_valid"] is False
    assert resp.json()["found"] is False


async def test_check_contact_no_params(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/check")
    assert resp.status_code == 400


async def test_create_contact_basic(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/contacts", json={
        "external_id": "basic-001",
        "phone": "5511999999999",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_id"] == "basic-001"
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_contact_duplicate_conflict(client: AsyncClient) -> None:
    await client.post("/api/v1/contacts", json={
        "external_id": "dup-001",
        "phone": "5511999999991",
    })
    resp = await client.post("/api/v1/contacts", json={
        "external_id": "dup-001",
        "phone": "5511999999992",
    })
    assert resp.status_code == 409


async def test_get_contact_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/contacts/inexistente")
    assert resp.status_code == 404


async def test_get_contact_found(client: AsyncClient) -> None:
    await client.post("/api/v1/contacts", json={
        "external_id": "get-me",
        "phone": "5511999999993",
    })
    resp = await client.get("/api/v1/contacts/get-me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == "get-me"
    assert body["phone"] == "5511999999993"
    assert "created_at" in body


async def test_create_contact_no_phone_or_email(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/contacts", json={
        "external_id": "no-data",
    })
    assert resp.status_code == 400


async def test_list_contacts(client: AsyncClient) -> None:
    await client.post("/api/v1/contacts", json={
        "external_id": "list-001", "phone": "5511999999994",
    })
    await client.post("/api/v1/contacts", json={
        "external_id": "list-002", "phone": "5511999999995",
    })
    resp = await client.get("/api/v1/contacts?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 2
