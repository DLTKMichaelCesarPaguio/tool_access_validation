from __future__ import annotations

import respx
from httpx import Response

from collector.collectors.burpsuite_usr import BurpSuiteCollector


def _collector() -> BurpSuiteCollector:
    return BurpSuiteCollector(
        api_key="burp-key", base_url="https://burp.example.com", tool_id=9
    )


@respx.mock
async def test_happy_path_list_response():
    respx.get("https://burp.example.com/api/v1/users").mock(
        return_value=Response(200, json=[
            {"email": "tester@deltek.com", "role": "standard", "last_login": None},
            {"email": "admin@deltek.com", "role": "admin", "last_login": "2026-01-01"},
        ])
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert rows[0]["work_email"] == "tester@deltek.com"
    assert rows[0]["status"] == "active"
    assert rows[1]["user_role"] == "admin"


@respx.mock
async def test_happy_path_dict_response_with_users_key():
    respx.get("https://burp.example.com/api/v1/users").mock(
        return_value=Response(200, json={
            "users": [{"email": "u@d.com", "role": "user", "last_login": None}]
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 1
    assert rows[0]["work_email"] == "u@d.com"


@respx.mock
async def test_empty_user_list_returns_empty():
    respx.get("https://burp.example.com/api/v1/users").mock(
        return_value=Response(200, json=[])
    )
    rows = await _collector().collect()
    assert rows == []


@respx.mock
async def test_http_error_returns_empty_list():
    respx.get("https://burp.example.com/api/v1/users").mock(
        return_value=Response(403, json={"error": "forbidden"})
    )
    rows = await _collector().collect()
    assert rows == []
