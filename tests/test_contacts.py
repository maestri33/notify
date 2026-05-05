"""
Testes do modulo de contactos — check, create, get, list.
"""

from httpx import AsyncClient


async def test_check_contact_email_valid(client: AsyncClient) -> None:
    resp = await client.get("/contacts/check?email=teste@exemplo.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["email_valid"] is True
    assert body["phone_valid"] is None


async def test_check_contact_email_invalid(client: AsyncClient) -> None:
    resp = await client.get("/contacts/check?email=invalido")
    assert resp.status_code == 200
    assert resp.json()["email_valid"] is False
    assert resp.json()["found"] is False


async def test_check_contact_no_params(client: AsyncClient) -> None:
    resp = await client.get("/contacts/check")
    assert resp.status_code == 400


async def test_create_contact_basic(client: AsyncClient) -> None:
    """Cria contacto basico (sem phone/email) — nao dispara enriquecimento."""
    resp = await client.post("/contacts", json={"external_id": "basic-001"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_id"] == "basic-001"
    assert body["name"] is None
    assert body["initial_analysis"] is None
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_contact_duplicate_conflict(client: AsyncClient) -> None:
    await client.post("/contacts", json={
        "external_id": "dup-001",
        "email": "dup@exemplo.com",
    })
    resp = await client.post("/contacts", json={
        "external_id": "dup-002",
        "email": "dup@exemplo.com",
    })
    assert resp.status_code == 409


async def test_get_contact_not_found(client: AsyncClient) -> None:
    resp = await client.get("/contacts/inexistente")
    assert resp.status_code == 404


async def test_get_contact_with_new_fields(client: AsyncClient) -> None:
    """Contacto criado sem enriquecimento retorna campos novos como null."""
    await client.post("/contacts", json={"external_id": "sem-enrich"})
    resp = await client.get("/contacts/sem-enrich")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == "sem-enrich"
    assert "name" in body
    assert "gender" in body
    assert "birth_date" in body
    assert "avatar_url" in body
    assert "profile_data" in body
    assert "initial_analysis" in body
    assert "is_business" in body


async def test_list_contacts(client: AsyncClient) -> None:
    await client.post("/contacts", json={"external_id": "list-001"})
    await client.post("/contacts", json={"external_id": "list-002"})
    resp = await client.get("/contacts?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 2


async def test_list_logs(client: AsyncClient) -> None:
    resp = await client.get("/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
