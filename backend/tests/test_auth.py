"""Session verifier: Better Auth is asked through a fake transport, never over the network."""

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.auth import Usuario, get_verifier, make_verifier, require_role, require_user
from backend.main import app

URL = "http://front.test/api/auth/get-session"
COOKIE = "better-auth.session_token=very-secret-token"
SESSION = {
    "session": {"id": "s1"},
    "user": {"id": "u1", "email": "contacto@agedrex.com", "name": "Usuario", "role": "admin"},
}


def build_app(handler, *, roles: tuple[str, ...] | None = None) -> tuple[TestClient, list[httpx.Request]]:
    """A tiny app guarded by a verifier whose transport records what it was sent."""
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    verifier = make_verifier(URL, transport=httpx.MockTransport(record))
    api = FastAPI()
    api.dependency_overrides[get_verifier] = lambda: verifier

    @api.get("/me")
    def me(usuario: Usuario = Depends(require_user)):
        return {"id": usuario.id, "email": usuario.email, "role": usuario.role}

    if roles is not None:
        @api.get("/solo", dependencies=[Depends(require_role(*roles))])
        def solo():
            return {"ok": True}

    return TestClient(api), seen


def test_valid_session_authenticates_and_exposes_the_user():
    client, seen = build_app(lambda request: httpx.Response(200, json=SESSION))
    response = client.get("/me", headers={"cookie": COOKIE})
    assert response.status_code == 200
    assert response.json() == {"id": "u1", "email": "contacto@agedrex.com", "role": "admin"}
    assert len(seen) == 1
    assert str(seen[0].url) == URL


def test_the_cookie_and_authorization_headers_are_forwarded():
    client, seen = build_app(lambda request: httpx.Response(200, json=SESSION))
    client.get("/me", headers={"cookie": COOKIE, "authorization": "Bearer abc"})
    assert seen[0].headers["cookie"] == COOKIE
    assert seen[0].headers["authorization"] == "Bearer abc"


def test_a_request_without_credentials_is_rejected_without_calling_the_session_endpoint():
    client, seen = build_app(lambda request: httpx.Response(200, json=SESSION))
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado."}
    assert seen == []


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, json=None),  # Better Auth answers `null` when there is no session
        httpx.Response(200, json={"session": None, "user": None}),
        httpx.Response(200, json={"user": {"email": "sin-id@example.com"}}),
        httpx.Response(200, json=["not", "a", "session"]),
        httpx.Response(200, content=b"<html>not json</html>"),
        httpx.Response(401, json={"message": "Unauthorized"}),
        httpx.Response(500, json=SESSION),
        httpx.Response(302, headers={"location": "http://front.test/login"}),
    ],
    ids=["null", "null-user", "user-without-id", "wrong-shape", "bad-json", "401", "500", "redirect"],
)
def test_anything_but_a_session_with_a_user_is_a_401(answer):
    client, _ = build_app(lambda request: answer)
    response = client.get("/me", headers={"cookie": COOKIE})
    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado."}


@pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), RuntimeError("boom")])
def test_timeouts_and_network_errors_are_a_401(error):
    def fail(request: httpx.Request) -> httpx.Response:
        raise error

    client, _ = build_app(fail)
    response = client.get("/me", headers={"cookie": COOKIE})
    assert response.status_code == 401


def test_cookies_are_never_logged(caplog):
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach host with {COOKIE}")

    client, _ = build_app(fail)
    with caplog.at_level("DEBUG"):
        client.get("/me", headers={"cookie": COOKIE})
    assert "very-secret-token" not in caplog.text


def test_the_timeout_is_three_seconds():
    assert auth.AUTH_VERIFY_TIMEOUT == 3.0
    client, seen = build_app(lambda request: httpx.Response(200, json=SESSION))
    client.get("/me", headers={"cookie": COOKIE})
    assert seen[0].extensions["timeout"] == {"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0}


def test_without_the_env_var_there_is_no_verifier_and_the_real_app_is_closed(monkeypatch):
    monkeypatch.delenv("AUTH_VERIFY_URL", raising=False)
    assert get_verifier() is None
    with TestClient(app) as client:
        response = client.get("/productos", headers={"cookie": COOKIE})
    assert response.status_code == 401


def test_a_blank_env_var_counts_as_missing(monkeypatch):
    monkeypatch.setenv("AUTH_VERIFY_URL", "   ")
    assert get_verifier() is None


def test_the_env_var_wires_a_real_verifier(monkeypatch):
    monkeypatch.setenv("AUTH_VERIFY_URL", URL)
    assert callable(get_verifier())


def test_require_role_allows_a_matching_role():
    client, _ = build_app(lambda request: httpx.Response(200, json=SESSION), roles=("admin",))
    assert client.get("/solo", headers={"cookie": COOKIE}).status_code == 200


def test_require_role_accepts_any_of_several_roles_in_a_comma_separated_value():
    body = {"user": {"id": "u2", "role": "consulta,cotizador"}}
    client, _ = build_app(lambda request: httpx.Response(200, json=body), roles=("admin", "cotizador"))
    assert client.get("/solo", headers={"cookie": COOKIE}).status_code == 200


def test_require_role_rejects_the_wrong_role_with_403():
    body = {"user": {"id": "u3", "role": "consulta"}}
    client, _ = build_app(lambda request: httpx.Response(200, json=body), roles=("admin",))
    response = client.get("/solo", headers={"cookie": COOKIE})
    assert response.status_code == 403
    assert response.json() == {"detail": "No tenés permiso para esta acción."}


def test_require_role_still_answers_401_when_not_signed_in():
    client, _ = build_app(lambda request: httpx.Response(200, json=None), roles=("admin",))
    assert client.get("/solo", headers={"cookie": COOKIE}).status_code == 401


def test_a_user_without_role_holds_no_roles():
    assert Usuario(id="u").roles == frozenset()
    assert Usuario(id="u", role=" admin , cotizador ").roles == frozenset({"admin", "cotizador"})
