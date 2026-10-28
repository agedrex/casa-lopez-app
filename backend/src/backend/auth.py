"""Authentication gate for the costing API.

Sessions belong to Better Auth, which runs in the Next.js app. This module does not read
the session database: it forwards the caller's credentials (`Cookie`, `Authorization`) to
`AUTH_VERIFY_URL` (Better Auth's `GET /api/auth/get-session`) and trusts only a 200 answer
whose JSON body carries a user.

Fail-closed: without `AUTH_VERIFY_URL`, or on any timeout, network error, non-200 status,
null session or unreadable body, `require_user` answers 401 to everybody.
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

AUTH_VERIFY_TIMEOUT = 3.0  # seconds, applied to connect, read, write and pool waits
FORWARDED_HEADERS = ("cookie", "authorization")


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str | None = None
    role: str | None = None  # Better Auth keeps several roles as a comma separated string

    @property
    def roles(self) -> frozenset[str]:
        return frozenset(part.strip() for part in (self.role or "").split(",") if part.strip())


Verificador = Callable[[Request], Usuario | None]


def _usuario_desde(body: object) -> Usuario | None:
    if not isinstance(body, dict):
        return None
    user = body.get("user")
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if not isinstance(user_id, str) or not user_id:
        return None
    email = user.get("email")
    role = user.get("role")
    return Usuario(
        id=user_id,
        email=email if isinstance(email, str) else None,
        role=role if isinstance(role, str) else None,
    )


def make_verifier(
    url: str,
    *,
    timeout: float = AUTH_VERIFY_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> Verificador:
    """Build a verifier that asks `url` whether the request carries a valid session.

    `transport` exists so tests can answer without a network.
    """
    client = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False)

    def verificar(request: Request) -> Usuario | None:
        headers = {"accept": "application/json"}
        for name in FORWARDED_HEADERS:
            value = request.headers.get(name)
            if value:
                headers[name] = value
        if len(headers) == 1:  # nothing to prove who the caller is
            return None
        try:
            response = client.get(url, headers=headers)
        except Exception as error:  # noqa: BLE001 - every failure must close the door
            # Log the error class only: the request headers carry session cookies.
            logger.warning("Session verification unavailable: %s", type(error).__name__)
            return None
        if response.status_code != 200:
            return None
        try:
            body = response.json()
        except ValueError:
            return None
        return _usuario_desde(body)

    return verificar


@lru_cache(maxsize=4)
def _verifier_for(url: str) -> Verificador:
    return make_verifier(url)


def get_verifier() -> Verificador | None:
    """Return the session verifier, or None while `AUTH_VERIFY_URL` is not configured.

    Tests can swap it through `app.dependency_overrides[get_verifier]`.
    """
    url = os.getenv("AUTH_VERIFY_URL", "").strip()
    return _verifier_for(url) if url else None


def require_user(request: Request, verificador: Verificador | None = Depends(get_verifier)) -> Usuario:
    usuario = verificador(request) if verificador is not None else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return usuario


def require_role(*roles: str) -> Callable[..., Usuario]:
    """Dependency factory: the signed-in user must hold at least one of `roles` (else 403).

    Usage: `Depends(require_role("admin"))`. Not attached to any route yet.
    """
    allowed = frozenset(roles)

    def dependency(usuario: Usuario = Depends(require_user)) -> Usuario:
        if not allowed & usuario.roles:
            raise HTTPException(status_code=403, detail="No tiene permiso para esta acción.")
        return usuario

    return dependency
