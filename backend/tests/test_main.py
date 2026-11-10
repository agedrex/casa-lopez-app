from importlib import reload

import pytest
from fastapi.testclient import TestClient

import backend.main as backend_main

app = backend_main.app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_health_check_without_a_database_is_unavailable():
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_demo_resources_route_no_longer_exists():
    assert client.get("/api/demo/resources").status_code == 404
    assert "/api/demo/resources" not in app.openapi()["paths"]


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


def test_cors_allows_configured_frontend_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend-staging.example.com")
    app = reload(backend_main).app
    configured_client = TestClient(app)

    response = configured_client.options(
        "/api/health",
        headers={
            "Origin": "https://frontend-staging.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "https://frontend-staging.example.com"


def test_cors_wildcard_does_not_allow_unrelated_origin(monkeypatch):
    try:
        with monkeypatch.context() as env:
            env.setenv("CORS_ALLOWED_ORIGINS", "*")
            configured_client = TestClient(reload(backend_main).app)
            response = configured_client.options(
                "/api/health",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert response.status_code == 400
            assert response.text == "Disallowed CORS origin"
            assert "access-control-allow-origin" not in response.headers
    finally:
        reload(backend_main)
