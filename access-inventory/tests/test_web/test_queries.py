from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from web.queries import (
    get_tool_access,
    get_ad_profile,
    search_users_by_name,
    search_users_by_username,
    _BLACKDUCK_NAME,
    _PICKER_LIMIT,
)


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


# ── search_users_by_name ───────────────────────────────────────────────────────

async def test_search_users_by_name_returns_rows():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    rows = [
        ("michael.p@d.com", "Michael Paguio", "Michael", "Paguio", "Engineer", "IT"),
        ("michael.c@d.com", "Michael Cruz", "Michael", "Cruz", "Analyst", "Finance"),
    ]
    cursor = _make_cursor(rows, cols)
    conn = _make_conn(cursor)

    result = await search_users_by_name(conn, "michael")
    assert len(result) == 2
    assert result[0]["first_name"] == "Michael"


async def test_search_users_by_name_fullname_split():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    rows = [("michael.p@d.com", "Michael Paguio", "Michael", "Paguio", "Engineer", "IT")]
    cursor = _make_cursor(rows, cols)
    conn = _make_conn(cursor)

    result = await search_users_by_name(conn, "michael paguio", first="michael", last="paguio")
    assert len(result) == 1
    assert result[0]["last_name"] == "Paguio"

    # Fullname query uses different SQL — both first% and last% must be in params
    params = cursor.execute.call_args[0][1]
    param_strs = [str(p) for p in params]
    assert any("michael" in s.lower() for s in param_strs)
    assert any("paguio" in s.lower() for s in param_strs)


async def test_search_users_by_name_passes_limit():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    await search_users_by_name(conn, "mark")
    params = cursor.execute.call_args[0][1]
    assert _PICKER_LIMIT in params


async def test_search_users_by_name_empty_result():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    result = await search_users_by_name(conn, "zzznobody")
    assert result == []


# ── search_users_by_username ───────────────────────────────────────────────────

async def test_search_users_by_username_returns_rows():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    rows = [("kibria@d.com", "Kibria Ghulam", "Kibria", "Ghulam", "Security", "IT")]
    cursor = _make_cursor(rows, cols)
    conn = _make_conn(cursor)

    result = await search_users_by_username(conn, "detek3kg")
    assert len(result) == 1
    assert result[0]["email"] == "kibria@d.com"


async def test_search_users_by_username_passes_limit():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    await search_users_by_username(conn, "detek")
    params = cursor.execute.call_args[0][1]
    assert _PICKER_LIMIT in params


async def test_search_users_by_username_empty_result():
    cols = ["email", "full_name", "first_name", "last_name", "job_title", "department"]
    cursor = _make_cursor([], cols)
    conn = _make_conn(cursor)

    result = await search_users_by_username(conn, "zzznobody")
    assert result == []
