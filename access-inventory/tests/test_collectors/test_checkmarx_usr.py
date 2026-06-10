from __future__ import annotations

import respx
from httpx import Response

from collector.collectors.checkmarx_usr import CheckmarxCollector


def _collector() -> CheckmarxCollector:
    return CheckmarxCollector(
        client_id="cx-client",
        client_secret="cx-secret",
        iam_base_url="https://iam.checkmarx.net",
        api_base_url="https://ast.checkmarx.net",
        tenant="deltek",
        tool_id=11,
    )


@respx.mock
async def test_happy_path_returns_users():
    respx.post("https://iam.checkmarx.net/auth/realms/deltek/protocol/openid-connect/token").mock(
        return_value=Response(200, json={"access_token": "cx-token"})
    )
    respx.get("https://ast.checkmarx.net/api/1.0/users").mock(
        return_value=Response(200, json={
            "users": [
                {"email": "dev@deltek.com", "roles": ["ROLE_AST_VIEWER"], "active": True},
                {"email": "admin@deltek.com", "roles": ["ROLE_AST_ADMIN"], "active": True},
            ],
            "totalCount": 2,
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert rows[0]["work_email"] == "dev@deltek.com"
    assert rows[0]["status"] == "active"
    assert "ROLE_AST_VIEWER" in rows[0]["user_role"]


@respx.mock
async def test_pagination_fetches_all_pages():
    respx.post("https://iam.checkmarx.net/auth/realms/deltek/protocol/openid-connect/token").mock(
        return_value=Response(200, json={"access_token": "cx-token"})
    )
    call_count = 0

    def users_handler(request):
        nonlocal call_count
        call_count += 1
        offset = int(request.url.params.get("offset", 0))
        if offset == 0:
            return Response(200, json={
                "users": [{"email": "a@d.com", "roles": [], "active": True}],
                "totalCount": 2,
            })
        return Response(200, json={
            "users": [{"email": "b@d.com", "roles": [], "active": False}],
            "totalCount": 2,
        })

    respx.get("https://ast.checkmarx.net/api/1.0/users").mock(side_effect=users_handler)
    rows = await _collector().collect()
    assert len(rows) == 2
    assert call_count == 2


@respx.mock
async def test_inactive_user_reflected_in_status():
    respx.post("https://iam.checkmarx.net/auth/realms/deltek/protocol/openid-connect/token").mock(
        return_value=Response(200, json={"access_token": "cx-token"})
    )
    respx.get("https://ast.checkmarx.net/api/1.0/users").mock(
        return_value=Response(200, json={
            "users": [{"email": "gone@deltek.com", "roles": [], "active": False}],
            "totalCount": 1,
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 1
    assert rows[0]["status"] == "inactive"


@respx.mock
async def test_empty_user_list_returns_empty():
    respx.post("https://iam.checkmarx.net/auth/realms/deltek/protocol/openid-connect/token").mock(
        return_value=Response(200, json={"access_token": "cx-token"})
    )
    respx.get("https://ast.checkmarx.net/api/1.0/users").mock(
        return_value=Response(200, json={"users": [], "totalCount": 0})
    )
    rows = await _collector().collect()
    assert rows == []


@respx.mock
async def test_http_error_returns_empty_list():
    respx.post("https://iam.checkmarx.net/auth/realms/deltek/protocol/openid-connect/token").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    rows = await _collector().collect()
    assert rows == []
