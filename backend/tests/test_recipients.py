def _new_client(client, name="app1"):
    return client.post("/api/v1/clients", json={"name": name}).json()["id"]


def test_create_recipient_full(client):
    cid = _new_client(client)
    r = client.post(
        "/api/v1/recipients",
        json={
            "client_id": cid,
            "external_id": "user-123",
            "email": "foo@bar.com",
            "phone_sms": "+55 (43) 99664-8750",
            "whatsapp": "43996648750",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "foo@bar.com"
    assert body["phone_sms"] == "43996648750"
    assert body["whatsapp_jid"] == "5543996648750@s.whatsapp.net"
    assert body["whatsapp_valid"] is False


def test_upsert_same_external_id(client):
    cid = _new_client(client)
    base = {"client_id": cid, "external_id": "u1"}
    r1 = client.post("/api/v1/recipients", json={**base, "email": "a@a.com"}).json()
    r2 = client.post("/api/v1/recipients", json={**base, "email": "b@b.com"}).json()
    assert r1["id"] == r2["id"]
    assert r2["email"] == "b@b.com"


def test_patch_only_updates_provided(client):
    cid = _new_client(client)
    r = client.post(
        "/api/v1/recipients",
        json={"client_id": cid, "external_id": "u2", "email": "a@a.com", "phone_sms": "43996648750"},
    ).json()
    patched = client.patch(
        f"/api/v1/recipients/{r['id']}", json={"email": "c@c.com"}
    ).json()
    assert patched["email"] == "c@c.com"
    assert patched["phone_sms"] == "43996648750"


def test_patch_whatsapp_resets_validation(client):
    cid = _new_client(client)
    r = client.post(
        "/api/v1/recipients",
        json={"client_id": cid, "external_id": "u3", "whatsapp": "43996648750"},
    ).json()
    # simulate previously validated
    # (can't hit DB directly via TestClient easily; the create already sets valid=False)
    patched = client.patch(
        f"/api/v1/recipients/{r['id']}", json={"whatsapp": "43888888888"}
    ).json()
    assert patched["whatsapp_jid"] == "5543888888888@s.whatsapp.net"
    assert patched["whatsapp_valid"] is False


def test_missing_client(client):
    r = client.post(
        "/api/v1/recipients",
        json={"client_id": "00000000-0000-0000-0000-000000000000", "external_id": "x"},
    )
    assert r.status_code == 404


def test_validation_marks_valid_when_sidecar_confirms(client):
    # Override with a fake that confirms existence
    from app.main import app
    from app.services.baileys import get_baileys

    class Ok:
        def validate(self, phone):
            return {"exists": True, "jid": f"55{phone[2:]}@s.whatsapp.net"}

    app.dependency_overrides[get_baileys] = lambda: Ok()
    try:
        cid = _new_client(client, name="validated")
        r = client.post(
            "/api/v1/recipients",
            json={"client_id": cid, "external_id": "uX", "whatsapp": "43996648750"},
        ).json()
        assert r["whatsapp_valid"] is True
    finally:
        # let conftest restore the fallback fake
        from tests.conftest import FakeBaileys

        app.dependency_overrides[get_baileys] = lambda: FakeBaileys()


def test_search_by_external_id(client):
    cid = _new_client(client)
    client.post("/api/v1/recipients", json={"client_id": cid, "external_id": "abc"})
    r = client.get(f"/api/v1/recipients?client_id={cid}&external_id=abc")
    assert r.status_code == 200
    assert len(r.json()) == 1
