def test_create_recipient_full(client):
    r = client.post(
        "/api/v1/recipients",
        json={
            "external_id": "user-123",
            "email": "foo@bar.com",
            "phone": "+55 (43) 99664-8750",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "foo@bar.com"
    assert body["phone_sms"] == "43996648750"
    assert body["whatsapp_jid"] == "5543996648750@s.whatsapp.net"
    assert body["whatsapp_valid"] is True


def test_duplicate_external_id(client):
    base = {"external_id": "u1"}
    client.post("/api/v1/recipients", json={**base, "email": "a@a.com"})
    r = client.post("/api/v1/recipients", json={**base, "email": "b@b.com"})
    assert r.status_code == 409


def test_patch_only_updates_provided(client):
    r = client.post(
        "/api/v1/recipients",
        json={"external_id": "u2", "email": "a@a.com", "phone": "43996648750"},
    ).json()
    patched = client.patch(
        f"/api/v1/recipients/{r['id']}", json={"email": "c@c.com"}
    ).json()
    assert patched["email"] == "c@c.com"
    assert patched["phone_sms"] == "43996648750"


def test_patch_whatsapp_resets_validation(client):
    from app.main import app
    from app.services.baileys import get_baileys

    # Need a FakeBaileys that says "not exists" for the new number
    class Offline:
        def validate(self, phone):
            from app.services.baileys import BaileysError
            raise BaileysError("offline")

    r = client.post(
        "/api/v1/recipients",
        json={"external_id": "u3", "phone": "43996648750"},
    ).json()
    app.dependency_overrides[get_baileys] = lambda: Offline()
    try:
        patched = client.patch(
            f"/api/v1/recipients/{r['id']}", json={"phone": "43888888888"}
        ).json()
        assert patched["whatsapp_jid"] == "5543888888888@s.whatsapp.net"
        assert patched["whatsapp_valid"] is False
    finally:
        from tests.conftest import FakeBaileys
        app.dependency_overrides[get_baileys] = lambda: FakeBaileys()


def test_validation_marks_valid_when_sidecar_confirms(client):
    assert True  # now tested via test_create_recipient_full


def test_search_by_external_id(client):
    client.post("/api/v1/recipients", json={"external_id": "abc", "email": "a@a.com"})
    r = client.get("/api/v1/recipients?external_id=abc")
    assert r.status_code == 200
    assert len(r.json()) == 1
