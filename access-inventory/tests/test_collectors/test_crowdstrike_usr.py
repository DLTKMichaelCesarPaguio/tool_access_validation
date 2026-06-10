from __future__ import annotations

import logging

import pytest
import respx
from httpx import Response

from collector.collectors.crowdstrike_usr import CrowdStrikeCollector


def _collector(**kwargs) -> CrowdStrikeCollector:
    defaults = dict(
        env_name="Commercial",
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.crowdstrike.com",
        tool_id=1,
    )
    defaults.update(kwargs)
    return CrowdStrikeCollector(**defaults)


@respx.mock
async def test_happy_path_returns_normalised_users():
    respx.post("https://api.crowdstrike.com/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok123"})
    )
    respx.get("https://api.crowdstrike.com/user-management/queries/users/v1").mock(
        return_value=Response(200, json={
            "resources": ["uid1", "uid2"],
            "meta": {"pagination": {"total": 2, "offset": 0}},
        })
    )
    respx.post(
        "https://api.crowdstrike.com/user-management/entities/users/GET/v1"
    ).mock(
        return_value=Response(200, json={
            "resources": [
                {"uid": "user1@deltek.com", "roles": ["admin"], "last_login_at": None},
                {"uid": "user2@deltek.com", "roles": ["user"], "last_login_at": None},
            ]
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert rows[0]["work_email"] == "user1@deltek.com"
    assert rows[0]["status"] == "active"
    assert rows[0]["user_role"] == "admin"


@respx.mock
async def test_pagination_fetches_all_pages():
    respx.post("https://api.crowdstrike.com/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok"})
    )
    call_count = 0

    def id_handler(request):
        nonlocal call_count
        call_count += 1
        offset = int(request.url.params.get("offset", 0))
        if offset == 0:
            return Response(200, json={
                "resources": ["id1"],
                "meta": {"pagination": {"total": 2, "offset": 0}},
            })
        return Response(200, json={
            "resources": ["id2"],
            "meta": {"pagination": {"total": 2, "offset": 1}},
        })

    respx.get(
        "https://api.crowdstrike.com/user-management/queries/users/v1"
    ).mock(side_effect=id_handler)
    respx.post(
        "https://api.crowdstrike.com/user-management/entities/users/GET/v1"
    ).mock(
        return_value=Response(200, json={
            "resources": [
                {"uid": "a@d.com", "roles": [], "last_login_at": None},
                {"uid": "b@d.com", "roles": [], "last_login_at": None},
            ]
        })
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert call_count == 2


@respx.mock
async def test_empty_user_list_returns_empty():
    respx.post("https://api.crowdstrike.com/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok"})
    )
    respx.get("https://api.crowdstrike.com/user-management/queries/users/v1").mock(
        return_value=Response(200, json={
            "resources": [],
            "meta": {"pagination": {"total": 0}},
        })
    )
    rows = await _collector().collect()
    assert rows == []


@respx.mock
async def test_http_error_returns_empty_list():
    respx.post("https://api.crowdstrike.com/oauth2/token").mock(
        return_value=Response(401, json={"error": "unauthorized"})
    )
    rows = await _collector().collect()
    assert rows == []


async def test_access_token_not_in_logs(caplog):
    """The literal token value must never appear in log output at any level."""
    with caplog.at_level(logging.DEBUG):
        with respx.mock:
            respx.post("https://api.crowdstrike.com/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "SUPERSECRETTOKEN"})
            )
            respx.get(
                "https://api.crowdstrike.com/user-management/queries/users/v1"
            ).mock(
                return_value=Response(200, json={
                    "resources": [],
                    "meta": {"pagination": {"total": 0}},
                })
            )
            await _collector().collect()

    for record in caplog.records:
        assert "SUPERSECRETTOKEN" not in record.getMessage(), (
            f"Token leaked in log record: {record.getMessage()}"
        )
