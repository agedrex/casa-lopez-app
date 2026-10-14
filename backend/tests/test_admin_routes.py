import asyncio
from functools import wraps

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.database import get_session
from backend.main import app


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        asyncio.run(function(*args, **kwargs))

    return run


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_VERIFY_URL", "https://auth.example.test/api/internal/auth/session")
    monkeypatch.setenv("AUTH_INTERNAL_SECRET", "server-secret")
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def set_auth_transport(monkeypatch, handler):
    from backend import admin_router

    async def client_dependency():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    app.dependency_overrides[admin_router.get_auth_http_client] = client_dependency


def test_admin_status_allows_admin_and_is_not_cacheable(admin_client, monkeypatch):
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json={"user_id": "user-7", "role": "admin"})

    set_auth_transport(monkeypatch, handler)
    response = admin_client.get(
        "/api/admin/status",
        headers={"Cookie": "session=browser-token", "X-Untrusted-Role": "admin", "X-User-Id": "attacker"},
    )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "user_id": "user-7", "role": "admin"}
    assert response.headers["cache-control"] == "private, no-store"
    assert seen["request"].headers["cookie"] == "session=browser-token"
    assert seen["request"].headers["authorization"] == "Bearer server-secret"
    assert "x-untrusted-role" not in seen["request"].headers
    assert "x-user-id" not in seen["request"].headers


@pytest.mark.parametrize(
    ("status", "payload", "expected_status"),
    [
        (401, None, 401),
        (200, {"user_id": "user-8", "role": "user"}, 403),
        (200, {"user_id": "user-8"}, 502),
    ],
)
def test_admin_status_denies_invalid_non_admin_and_malformed_sessions(
    admin_client, monkeypatch, status, payload, expected_status
):
    set_auth_transport(
        monkeypatch,
        lambda _: httpx.Response(status, json=payload) if payload is not None else httpx.Response(status),
    )
    response = admin_client.get("/api/admin/status", headers={"Cookie": "session=browser-token"})

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "private, no-store"
    assert "server-secret" not in response.text


def test_admin_status_without_cookie_does_not_call_auth_service(admin_client, monkeypatch):
    set_auth_transport(monkeypatch, lambda _: pytest.fail("missing cookies must not make a request"))

    response = admin_client.get("/api/admin/status")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"


def test_admin_status_configuration_failure_is_generic_and_not_cacheable(admin_client, monkeypatch):
    monkeypatch.delenv("AUTH_INTERNAL_SECRET")
    response = admin_client.get("/api/admin/status", headers={"Cookie": "session=browser-token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable."}
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("upstream_status", [500, 503])
def test_admin_status_session_service_failure_is_sanitized(admin_client, monkeypatch, upstream_status):
    set_auth_transport(
        monkeypatch,
        lambda _: httpx.Response(upstream_status, json={"error": "sensitive database details"}),
    )
    response = admin_client.get("/api/admin/status", headers={"Cookie": "session=browser-token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable."}
    assert response.headers["cache-control"] == "private, no-store"


@async_test
async def test_auth_client_disables_redirects_environment_proxies_and_uses_short_timeout(monkeypatch):
    from backend import admin_router

    received = {}

    class FakeClient:
        def __init__(self, **kwargs):
            received.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(admin_router.httpx, "AsyncClient", FakeClient)
    generator = admin_router.get_auth_http_client()
    await anext(generator)
    await generator.aclose()

    assert received["follow_redirects"] is False
    assert received["trust_env"] is False
    assert received["timeout"].read == 2.0


def test_four_existing_endpoint_contracts_remain_available(admin_client, monkeypatch):
    response = admin_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "demo"}

    response = admin_client.get("/api/demo/resources")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"

    session = type("Session", (), {"execute": lambda self, query: type("Result", (), {
        "mappings": lambda self: self,
        "all": lambda self: [{"codigo": "CUERO"}],
    })()})()
    app.dependency_overrides[get_session] = lambda: session
    response = admin_client.get("/catalogo/etapas")
    assert response.status_code == 200
    assert response.json() == [{"codigo": "CUERO"}]

    class DatabaseResult:
        def one(self):
            return "0002_semillas", 11

    class DatabaseSession:
        def execute(self, query):
            return DatabaseResult()

    app.dependency_overrides[get_session] = lambda: DatabaseSession()
    response = admin_client.get("/db/estado")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "alembic_revision": "0002_semillas", "tablas_costos": 11}
