def _setup_recipient(client, **channels):
    body = {"external_id": "u1"}
    if "email" in channels:
        body["email"] = channels["email"]
    if "phone" in channels:
        body["phone"] = channels["phone"]
    return client.post("/api/v1/recipients", json=body).json()


def test_create_notification_auto_channels(client, session):
    r = _setup_recipient(client, email="a@a.com", phone="43996648750")

    resp = client.post(
        "/api/v1/notifications",
        json={
            "external_id": "u1",
            "content": "Olá **mundo**",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    channels_used = {j["channel"] for j in body["jobs"]}
    assert channels_used == {"sms", "email", "whatsapp"}
    assert all(j["status"] == "queued" for j in body["jobs"])
    assert len(client.enqueued) == 3


def test_create_notification_forced_channels(client):
    _setup_recipient(client, email="a@a.com", phone="43996648750")

    resp = client.post(
        "/api/v1/notifications",
        json={
            "external_id": "u1",
            "content": "x",
            "channels": ["email"],
        },
    ).json()
    assert [j["channel"] for j in resp["jobs"]] == ["email"]
    assert resp["skipped"] == []


def test_forced_channel_not_available(client):
    _setup_recipient(client, email="a@a.com")

    resp = client.post(
        "/api/v1/notifications",
        json={"external_id": "u1", "content": "x", "channels": ["sms"]},
    )
    assert resp.status_code == 422


def test_no_eligible_channels(client, session):
    # Direct DB insert — API requires at least email or phone
    from app.models import Recipient
    r = Recipient(external_id="empty")
    session.add(r)
    session.commit()

    resp = client.post(
        "/api/v1/notifications",
        json={"external_id": "empty", "content": "x"},
    )
    assert resp.status_code == 422


def test_unknown_recipient(client):
    resp = client.post(
        "/api/v1/notifications",
        json={"external_id": "ghost", "content": "x"},
    )
    assert resp.status_code == 404


def test_list_logs_filter_by_channel(client):
    _setup_recipient(client, email="a@a.com", phone="43996648750")
    client.post(
        "/api/v1/notifications",
        json={"external_id": "u1", "content": "x"},
    )
    r = client.get("/api/v1/notifications?channel=email").json()
    assert len(r) == 1
    assert r[0]["channel"] == "email"
