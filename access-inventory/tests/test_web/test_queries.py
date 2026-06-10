from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from web.queries import get_tool_access, get_ad_profile, _BLACKDUCK_NAME


def _make_cursor(rows, columns):
    cursor = AsyncMock()
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    cursor.description = [(col,) for col in columns]
    cursor.fetchone = AsyncMock(return_value=rows[0] if rows else None)

    async def aiter_rows():
        for row in rows:
            yield row

    cursor.__aiter__ = lambda self: aiter_rows()
    cursor.execute = AsyncMock()
    return cursor


def _make_conn(cursor):
    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    return conn


async def test_get_tool_access_returns_rows():
    cols = ["work_email", "tool_id", "tool_name", "status", "user_role",
            "last_login_date", "updated_at"]
    rows = [("dev@d.com", 1, "CrowdStrike", "active", "admin", "2026-01-01", None)]
    cursor = _make_cursor(rows, cols)
    conn = _make_conn(cursor)

    result = await get_tool_access(conn, "dev@d.com")
    assert len(result) == 1
    assert result[0]["work_email"] == "dev@d.com"
    assert result[0]["tool_name"] == "CrowdStrike"


async def test_get_tool_access_passes_blackduck_pattern():
    cols = ["work_email", "tool_id", "tool_name", "status", "user_role",
            "last_login_date", "updated_at"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    await get_tool_access(conn, "test@d.com")

    params = cursor.execute.call_args[0][1]
    assert any(_BLACKDUCK_NAME in str(p) for p in params), (
        "BlackDuck ILIKE pattern must be in query params"
    )


async def test_get_tool_access_empty_when_no_rows():
    cols = ["work_email", "tool_id", "tool_name", "status", "user_role",
            "last_login_date", "updated_at"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    result = await get_tool_access(conn, "nobody@d.com")
    assert result == []


async def test_get_ad_profile_returns_dict():
    cols = ["email", "full_name", "first_name", "last_name",
            "job_title", "department", "employee_id", "is_active"]
    row = ("dev@d.com", "Dev User", "Dev", "User", "Engineer", "IT", "EMP001", True)
    cursor = _make_cursor([row], cols)
    conn = _make_conn(cursor)

    result = await get_ad_profile(conn, "dev@d.com")
    assert result is not None
    assert result["email"] == "dev@d.com"
    assert result["full_name"] == "Dev User"


async def test_get_ad_profile_returns_none_when_not_found():
    cols = ["email", "full_name", "first_name", "last_name",
            "job_title", "department", "employee_id", "is_active"]
    cursor = _make_cursor([], cols)
    cursor.fetchone = AsyncMock(return_value=None)
    conn = _make_conn(cursor)

    result = await get_ad_profile(conn, "ghost@d.com")
    assert result is None
