def _setup_recipient(client, **channels):
    cid = client.post("/api/v1/clients", json={"name": "app"}).json()["id"]
    r = client.post(
        "/api/v1/recipients",
        json={"client_id": cid, "external_id": "u1", **channels},
    ).json()
    return cid, r


def test_create_notification_auto_channels(client, session):
    cid, r = _setup_recipient(client, email="a@a.com", phone_sms="43996648750")

    resp = client.post(
        "/api/v1/notifications",
        json={
            "client_id": cid,
            "external_id": "u1",
            "content": "Olá **mundo**",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    channels_used = {j["channel"] for j in body["jobs"]}
    assert channels_used == {"sms", "email"}  # no whatsapp (not validated)
    assert all(j["status"] == "queued" for j in body["jobs"])
    assert len(client.enqueued) == 2


def test_create_notification_forced_channels(client):
    cid, _ = _setup_recipient(client, email="a@a.com", phone_sms="43996648750")

    resp = client.post(
        "/api/v1/notifications",
        json={
            "client_id": cid,
            "external_id": "u1",
            "content": "x",
            "channels": ["email"],
        },
    ).json()
    assert [j["channel"] for j in resp["jobs"]] == ["email"]
    assert resp["skipped"] == []


def test_forced_channel_not_available(client):
    cid, _ = _setup_recipient(client, email="a@a.com")

    resp = client.post(
        "/api/v1/notifications",
        json={"client_id": cid, "external_id": "u1", "content": "x", "channels": ["sms"]},
    )
    assert resp.status_code == 422


def test_no_eligible_channels(client):
    cid, _ = _setup_recipient(client)  # no email, no phone, no wa

    resp = client.post(
        "/api/v1/notifications",
        json={"client_id": cid, "external_id": "u1", "content": "x"},
    )
    assert resp.status_code == 422


def test_unknown_recipient(client):
    cid = client.post("/api/v1/clients", json={"name": "z"}).json()["id"]
    resp = client.post(
        "/api/v1/notifications",
        json={"client_id": cid, "external_id": "ghost", "content": "x"},
    )
    assert resp.status_code == 404


def test_list_logs_filter_by_channel(client):
    cid, _ = _setup_recipient(client, email="a@a.com", phone_sms="43996648750")
    client.post(
        "/api/v1/notifications",
        json={"client_id": cid, "external_id": "u1", "content": "x"},
    )
    r = client.get("/api/v1/notifications?channel=email").json()
    assert len(r) == 1
    assert r[0]["channel"] == "email"
