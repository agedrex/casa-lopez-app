import asyncio
from functools import wraps

import httpx
import pytest

from backend.admin_auth import verify_session


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        asyncio.run(function(*args, **kwargs))

    return run


@async_test
async def test_verify_session_forwards_only_cookie_and_server_secret():
    received = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["request"] = request
        return httpx.Response(200, json={"user_id": "user-7", "role": "admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await verify_session(
            cookie="session=browser-token",
            verify_url="https://auth.example.test/api/internal/auth/session",
            internal_secret="server-secret",
            client=client,
        )

    request = received["request"]
    assert request.method == "POST"
    assert str(request.url) == "https://auth.example.test/api/internal/auth/session"
    assert request.headers["cookie"] == "session=browser-token"
    assert request.headers["authorization"] == "Bearer server-secret"
    assert "x-untrusted-role" not in request.headers
    assert "x-user-id" not in request.headers
    assert request.content == b""
    assert result == (200, {"user_id": "user-7", "role": "admin"})


@async_test
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(401), (401, None)),
        (httpx.Response(200, json={"user_id": "user-8", "role": "user"}), (200, {"user_id": "user-8", "role": "user"})),
        (httpx.Response(200, json={"user_id": "", "role": "admin"}), (502, None)),
        (httpx.Response(200, json={"user_id": "user-8", "role": 7}), (502, None)),
        (httpx.Response(200, content=b"not-json"), (502, None)),
        (httpx.Response(302), (502, None)),
        (httpx.Response(500), (503, None)),
    ],
)
async def test_verify_session_maps_upstream_results(response, expected):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
        result = await verify_session(
            cookie="session=browser-token",
            verify_url="https://auth.example.test/api/internal/auth/session",
            internal_secret="server-secret",
            client=client,
        )

    assert result == expected


@async_test
async def test_verify_session_fails_closed_when_upstream_is_unreachable():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive upstream details")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await verify_session(
            cookie="session=browser-token",
            verify_url="https://auth.example.test/api/internal/auth/session",
            internal_secret="server-secret",
            client=client,
        )

    assert result == (503, None)


@async_test
async def test_verify_session_fails_closed_on_timeout():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive timeout details")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await verify_session(
            cookie="session=browser-token",
            verify_url="https://auth.example.test/api/internal/auth/session",
            internal_secret="server-secret",
            client=client,
        )

    assert result == (503, None)


@async_test
@pytest.mark.parametrize(
    ("verify_url", "internal_secret"),
    [(None, "secret"), ("https://auth.example.test/session", None)],
)
async def test_verify_session_rejects_missing_configuration_without_network(
    verify_url, internal_secret
):
    class UnexpectedClient:
        async def post(self, *args, **kwargs):
            pytest.fail("configuration errors must not make a network request")

    result = await verify_session(
        cookie="session=browser-token",
        verify_url=verify_url,
        internal_secret=internal_secret,
        client=UnexpectedClient(),
    )

    assert result == (503, None)
