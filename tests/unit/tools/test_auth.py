import base64

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(platform):
    from app.api.app import app
    return TestClient(app)


def test_api_locked_until_login(client):
    assert client.get("/api/meta").status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200          # the page itself (login screen) is public
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin@123"})
    assert r.status_code == 200 and "ait_session" in r.cookies
    assert client.get("/api/auth/me").json() == {"user": "admin"}
    assert client.get("/api/dashboard").status_code == 200
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/dashboard").status_code == 401


def test_basic_auth_for_scripts_and_tampered_cookie(client):
    good = "Basic " + base64.b64encode(b"admin:admin@123").decode()
    assert client.get("/api/dashboard", headers={"Authorization": good}).status_code == 200
    client.cookies.set("ait_session", "YWRtaW58OTk5OTk5OTk5OQ==.deadbeef")
    assert client.get("/api/dashboard").status_code == 401


def test_login_throttled(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "admin", "password": "x"})
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin@123"}).status_code == 429
