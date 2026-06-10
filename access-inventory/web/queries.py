from __future__ import annotations

from typing import Any

import psycopg

_BLACKDUCK_NAME = "blackduck"

_TOOL_ACCESS_SQL = """
SELECT
    uta.work_email,
    uta.tool_id,
    t.tool_name,
    CASE WHEN t.tool_name ILIKE %s THEN 'Active Access' ELSE uta.status END AS status,
    uta.user_role,
    CASE WHEN t.tool_name ILIKE %s THEN 'N/A' ELSE uta.last_login_date END AS last_login_date,
    uta.updated_at
FROM user_tool_access uta
JOIN tools t ON t.id = uta.tool_id
WHERE lower(uta.work_email) = lower(%s)
ORDER BY t.tool_name
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
