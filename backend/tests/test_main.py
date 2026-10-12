from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_check_is_healthy():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "demo"}


def test_demo_resources_are_explicitly_non_production():
    response = client.get("/api/demo/resources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    assert payload["disclaimer"]
    assert len(payload["resources"]) >= 1
    assert all("name" in resource and "description" in resource for resource in payload["resources"])


def test_cors_is_limited_to_local_frontend_origin():
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    denied = client.options(
        "/api/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers
