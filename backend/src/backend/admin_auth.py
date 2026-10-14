import ipaddress
from urllib.parse import urlsplit

import httpx


def _valid_verify_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if not hostname or parsed.scheme not in {"http", "https"}:
            return False
        if parsed.username or parsed.password or parsed.fragment:
            return False
        if parsed.scheme == "https":
            return True

        normalized_host = hostname.rstrip(".").lower()
        if normalized_host == "localhost" or normalized_host.endswith((".localhost", ".internal", ".railway.internal")):
            return True
        try:
            return ipaddress.ip_address(normalized_host).is_private or ipaddress.ip_address(normalized_host).is_loopback
        except ValueError:
            return False
    except ValueError:
        return False


async def verify_session(
    *,
    cookie: str,
    verify_url: str | None,
    internal_secret: str | None,
    client: httpx.AsyncClient,
) -> tuple[int, dict[str, str] | None]:
    if not verify_url or not internal_secret or not _valid_verify_url(verify_url):
        return 503, None

    try:
        response = await client.post(
            verify_url,
            headers={"Cookie": cookie, "Authorization": f"Bearer {internal_secret}"},
        )
    except (httpx.TimeoutException, httpx.RequestError):
        return 503, None

    if response.status_code == 401:
        return 401, None
    if response.status_code >= 500:
        return 503, None
    if response.status_code != 200:
        return 502, None

    try:
        payload = response.json()
    except ValueError:
        return 502, None
    if not isinstance(payload, dict):
        return 502, None

    user_id = payload.get("user_id")
    role = payload.get("role")
    if not isinstance(user_id, str) or not user_id.strip() or not isinstance(role, str) or not role.strip():
        return 502, None
    return 200, {"user_id": user_id, "role": role}
