from __future__ import annotations

import respx
from httpx import Response

from collector.collectors.blackduck_usr import BlackDuckCollector, _BD_USER_ACCEPT


def _collector() -> BlackDuckCollector:
    return BlackDuckCollector(
        api_token="bd-token",
        base_url="https://blackduck.example.com",
        tool_id=10,
    )


@respx.mock
async def test_happy_path_returns_users():
    respx.post("https://blackduck.example.com/api/tokens/authenticate").mock(
        return_value=Response(200, json={"bearerToken": "btoken"})
    )
    respx.get("https://blackduck.example.com/api/users").mock(
        return_value=Response(200, json={
            "items": [
                {"email": "dev@deltek.com", "userName": "dev@deltek.com", "type": "EXTERNAL"},
            ],
            "totalCount": 1,
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 1
    assert rows[0]["work_email"] == "dev@deltek.com"
    assert rows[0]["status"] == "active"


@respx.mock
async def test_accept_header_is_vendor_specific():
    """Every request to /api/users must carry the BlackDuck Accept header."""
    captured_headers = []

    def capture(request):
        captured_headers.append(dict(request.headers))
        return Response(200, json={"items": [], "totalCount": 0})

    respx.post("https://blackduck.example.com/api/tokens/authenticate").mock(
        return_value=Response(200, json={"bearerToken": "btoken"})
    )
    respx.get("https://blackduck.example.com/api/users").mock(side_effect=capture)

    await _collector().collect()
    assert captured_headers, "No requests captured"
    for hdrs in captured_headers:
        accept = hdrs.get("accept", "")
        assert _BD_USER_ACCEPT in accept, (
            f"Expected Accept header to contain {_BD_USER_ACCEPT!r}, got {accept!r}"
        )


@respx.mock
async def test_pagination_fetches_all_pages():
    respx.post("https://blackduck.example.com/api/tokens/authenticate").mock(
        return_value=Response(200, json={"bearerToken": "btoken"})
    )
    call_count = 0

    def users_handler(request):
        nonlocal call_count
        call_count += 1
        offset = int(request.url.params.get("offset", 0))
        if offset == 0:
            return Response(200, json={
                "items": [{"email": "a@d.com", "type": "INT"}],
                "totalCount": 2,
            })
        return Response(200, json={
            "items": [{"email": "b@d.com", "type": "EXT"}],
            "totalCount": 2,
        })

    respx.get("https://blackduck.example.com/api/users").mock(side_effect=users_handler)
    rows = await _collector().collect()
    assert len(rows) == 2
    assert call_count == 2


@respx.mock
async def test_http_error_returns_empty_list():
    respx.post("https://blackduck.example.com/api/tokens/authenticate").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    rows = await _collector().collect()
    assert rows == []
