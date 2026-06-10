from __future__ import annotations

import pytest
import respx
from httpx import Response

from collector.collectors.sophos_usr import SophosCollector


def _collector() -> SophosCollector:
    return SophosCollector(client_id="sid", client_secret="ssecret", tool_id=8)


@respx.mock
async def test_happy_path_returns_admins():
    respx.post("https://id.sophos.com/api/v2/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "stok"})
    )
    respx.get("https://api.central.sophos.com/whoami/v1").mock(
        return_value=Response(200, json={"id": "tenant-123"})
    )
    respx.get("https://api.central.sophos.com/common/v1/admins").mock(
        return_value=Response(200, json={
            "items": [
                {"email": "Admin@deltek.com", "roleType": "superAdmin"},
                {"email": "viewer@deltek.com", "roleType": "readOnly"},
            ],
            "pages": {},
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert rows[0]["work_email"] == "admin@deltek.com"
    assert rows[0]["status"] == "active"
    assert rows[0]["user_role"] == "superAdmin"


@respx.mock
async def test_pagination_follows_next_key():
    respx.post("https://id.sophos.com/api/v2/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "stok"})
    )
    respx.get("https://api.central.sophos.com/whoami/v1").mock(
        return_value=Response(200, json={"id": "t1"})
    )
    call_count = 0

    def admins_handler(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(200, json={
                "items": [{"email": "a@d.com", "roleType": "admin"}],
                "pages": {"nextKey": "page2key"},
            })
        return Response(200, json={
            "items": [{"email": "b@d.com", "roleType": "user"}],
            "pages": {},
        })

    respx.get("https://api.central.sophos.com/common/v1/admins").mock(
        side_effect=admins_handler
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert call_count == 2


@respx.mock
async def test_http_error_returns_empty_list():
    respx.post("https://id.sophos.com/api/v2/oauth2/token").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    rows = await _collector().collect()
    assert rows == []
