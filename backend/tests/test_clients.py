def test_create_and_list_client(client):
    r = client.post("/api/v1/clients", json={"name": "app-alpha"})
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.get("/api/v1/clients")
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json())


def test_get_not_found(client):
    r = client.get("/api/v1/clients/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_delete(client):
    cid = client.post("/api/v1/clients", json={"name": "x"}).json()["id"]
    assert client.delete(f"/api/v1/clients/{cid}").status_code == 204
    assert client.get(f"/api/v1/clients/{cid}").status_code == 404
