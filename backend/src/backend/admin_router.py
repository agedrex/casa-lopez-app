import os
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.admin_auth import verify_session


router = APIRouter(prefix="/api/admin", tags=["admin"])


async def get_auth_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(2.0),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield client


@router.get("/status")
async def admin_status(
    request: Request,
    client: httpx.AsyncClient = Depends(get_auth_http_client),
) -> JSONResponse:
    headers = {"Cache-Control": "private, no-store"}
    cookie = request.headers.get("cookie")
    if not cookie:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required."},
            headers=headers,
        )

    status, session = await verify_session(
        cookie=cookie,
        verify_url=os.getenv("AUTH_VERIFY_URL"),
        internal_secret=os.getenv("AUTH_INTERNAL_SECRET"),
        client=client,
    )
    if status == 401:
        return JSONResponse(status_code=401, content={"detail": "Authentication required."}, headers=headers)
    if status == 503:
        return JSONResponse(
            status_code=503,
            content={"detail": "Authentication service unavailable."},
            headers=headers,
        )
    if status == 502 or session is None:
        return JSONResponse(
            status_code=502,
            content={"detail": "Authentication service returned an invalid response."},
            headers=headers,
        )
    if session["role"] != "admin":
        return JSONResponse(status_code=403, content={"detail": "Administrator access required."}, headers=headers)
    return JSONResponse(
        status_code=200,
        content={"authenticated": True, "user_id": session["user_id"], "role": session["role"]},
        headers=headers,
    )
