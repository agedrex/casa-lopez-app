"""Authentication gate for the costing API.

Fail-closed: until a verifier is configured, `require_user` answers 401 to everybody.
The real session check (Better Auth) is task T4; this module does not guess its protocol.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request


@dataclass(frozen=True)
class Usuario:
    id: str


Verificador = Callable[[Request], Usuario | None]


def get_verifier() -> Verificador | None:
    """Return the configured session verifier, or None while none is configured.

    T4: replace this with the Better Auth session check (it must return a callable that maps
    a request to a `Usuario`, or None when the request has no valid session). Tests and the
    future wiring can also swap it through `app.dependency_overrides[get_verifier]`.
    """
    return None


def require_user(request: Request, verificador: Verificador | None = Depends(get_verifier)) -> Usuario:
    usuario = verificador(request) if verificador is not None else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return usuario
