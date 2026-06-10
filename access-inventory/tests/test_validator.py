from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.validator import find_orphans, find_stale, _BLACKDUCK_NAME, _STALE_DAYS


def _make_conn(rows: list[tuple], columns: list[str]) -> AsyncMock:
    """Build a minimal mock AsyncConnection whose cursor returns fixed rows."""
    mock_cursor = AsyncMock()
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)
    mock_cursor.description = [(col,) for col in columns]

    async def aiter_rows():
        for row in rows:
            yield row

    mock_cursor.__aiter__ = lambda self: aiter_rows()
    mock_cursor.execute = AsyncMock()

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    return mock_conn


async def test_find_orphans_returns_rows_with_no_ad_match():
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    rows = [
        (1, "ghost@deltek.com", 3, "CrowdStrike GCE", "active", "admin", None, None, "active"),
    ]
    conn = _make_conn(rows, columns)

    result = await find_orphans(conn)
    assert len(result) == 1
    assert result[0]["work_email"] == "ghost@deltek.com"
    assert result[0]["tool_name"] == "CrowdStrike GCE"


async def test_find_orphans_empty_when_no_orphans():
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    conn = _make_conn([], columns)
    result = await find_orphans(conn)
    assert result == []


async def test_find_stale_returns_rows_past_threshold():
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    rows = [
        (2, "stale@deltek.com", 4, "Qualys Prod", "active", "user", "2024-01-01", "2024-01-01", "active"),
    ]
    conn = _make_conn(rows, columns)

    result = await find_stale(conn, days=90)
    assert len(result) == 1
    assert result[0]["work_email"] == "stale@deltek.com"
    assert result[0]["last_login_date"] == "2024-01-01"


async def test_find_stale_passes_days_parameter():
    """The SQL query receives the caller-supplied days, not a hardcoded value."""
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    conn = _make_conn([], columns)

    await find_stale(conn, days=30)

    # Verify execute was called with 30 somewhere in its args
    call_args = conn.cursor.return_value.__aenter__.return_value.execute.call_args
    assert 30 in call_args[0][1], "days=30 should appear in SQL params"


async def test_blackduck_pattern_passed_to_queries():
    """BlackDuck ILIKE pattern is derived from _BLACKDUCK_NAME constant."""
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    conn = _make_conn([], columns)

    await find_orphans(conn)

    call_args = conn.cursor.return_value.__aenter__.return_value.execute.call_args
    params = call_args[0][1]
    assert any(_BLACKDUCK_NAME in str(p) for p in params), (
        "BlackDuck ILIKE pattern must be passed as a query parameter"
    )


async def test_find_stale_blackduck_excluded_via_sql_param():
    """The stale query receives the BlackDuck exclusion pattern as a parameter."""
    columns = ["id", "work_email", "tool_id", "tool_name", "status",
               "user_role", "last_login_date", "display_last_login", "display_status"]
    conn = _make_conn([], columns)

    await find_stale(conn)

    call_args = conn.cursor.return_value.__aenter__.return_value.execute.call_args
    params = call_args[0][1]
    bd_params = [p for p in params if isinstance(p, str) and _BLACKDUCK_NAME in p]
    assert len(bd_params) >= 2, (
        "BlackDuck pattern should appear at least twice in stale query params "
        "(display override + exclusion filter)"
    )
