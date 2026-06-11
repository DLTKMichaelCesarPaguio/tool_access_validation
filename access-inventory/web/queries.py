from __future__ import annotations

from typing import Any

import psycopg

_BLACKDUCK_NAME = "blackduck"
_PICKER_LIMIT = 50

_TOOL_ACCESS_SQL = """
SELECT
    uta.work_email,
    uta.tool_id,
    t.tool_name,
    CASE WHEN t.tool_name ILIKE %s THEN 'Active Access' ELSE uta.status END AS status,
    uta.user_role,
    uta.username,
    CASE WHEN t.tool_name ILIKE %s THEN 'N/A' ELSE uta.last_login_date END AS last_login_date,
    uta.updated_at
FROM user_tool_access uta
JOIN tools t ON t.tool_id = uta.tool_id
WHERE lower(uta.work_email) = lower(%s)
ORDER BY t.tool_name, uta.username NULLS LAST
"""

_AD_PROFILE_SQL = """
SELECT
    email,
    full_name,
    first_name,
    last_name,
    job_title,
    department,
    employee_id,
    is_active
FROM users
WHERE lower(email) = lower(%s)
LIMIT 1
"""


async def get_tool_access(conn: psycopg.AsyncConnection, email: str) -> list[dict]:
    """Return all tool access rows for a given email address."""
    bd_pattern = f"%{_BLACKDUCK_NAME}%"
    async with conn.cursor() as cur:
        await cur.execute(_TOOL_ACCESS_SQL, (bd_pattern, bd_pattern, email))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) async for row in cur]


async def get_ad_profile(conn: psycopg.AsyncConnection, email: str) -> dict | None:
    """Return the AD user profile for a given email, or None if not found."""
    async with conn.cursor() as cur:
        await cur.execute(_AD_PROFILE_SQL, (email,))
        cols = [d[0] for d in cur.description]
        row = await cur.fetchone()
        if row is None:
            return None
        return dict(zip(cols, row))


_SEARCH_BY_NAME_SQL = """
SELECT
    email, full_name, first_name, last_name, job_title, department
FROM users
WHERE (
    first_name ILIKE %s
    OR last_name  ILIKE %s
    OR full_name  ILIKE %s
)
ORDER BY last_name, first_name
LIMIT %s
"""

_SEARCH_BY_FULLNAME_SQL = """
SELECT
    email, full_name, first_name, last_name, job_title, department
FROM users
WHERE first_name ILIKE %s
  AND last_name  ILIKE %s
ORDER BY last_name, first_name
LIMIT %s
"""

_SEARCH_BY_USERNAME_SQL = """
SELECT DISTINCT
    u.email, u.full_name, u.first_name, u.last_name, u.job_title, u.department
FROM user_tool_access uta
JOIN users u ON lower(u.email) = lower(uta.work_email)
WHERE uta.username ILIKE %s
ORDER BY u.last_name, u.first_name
LIMIT %s
"""


async def search_users_by_name(
    conn: psycopg.AsyncConnection,
    term: str,
    *,
    first: str | None = None,
    last: str | None = None,
) -> list[dict]:
    """Search the users table by name fragment or first+last split.

    When both `first` and `last` are provided the query matches both columns
    (full-name split search).  Otherwise `term` is matched against first_name,
    last_name, and full_name as a prefix.
    """
    pattern = f"{term}%"
    async with conn.cursor() as cur:
        if first is not None and last is not None:
            await cur.execute(
                _SEARCH_BY_FULLNAME_SQL,
                (f"{first}%", f"{last}%", _PICKER_LIMIT),
            )
        else:
            await cur.execute(
                _SEARCH_BY_NAME_SQL,
                (pattern, pattern, pattern, _PICKER_LIMIT),
            )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) async for row in cur]


async def search_users_by_username(
    conn: psycopg.AsyncConnection, term: str
) -> list[dict]:
    """Search user_tool_access for a username prefix, return distinct user rows."""
    pattern = f"{term}%"
    async with conn.cursor() as cur:
        await cur.execute(_SEARCH_BY_USERNAME_SQL, (pattern, _PICKER_LIMIT))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) async for row in cur]
