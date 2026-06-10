from __future__ import annotations

import asyncio
import logging

import psycopg
from dotenv import load_dotenv

from collector import config

load_dotenv()

logger = logging.getLogger(__name__)

# BlackDuck tool name fragment — overrides applied at query time, not stored
_BLACKDUCK_NAME = "blackduck"

# Days of inactivity after which an account is considered stale
_STALE_DAYS = 90


_ORPHAN_SQL = """
SELECT
    uta.id,
    uta.work_email,
    uta.tool_id,
    t.tool_name,
    uta.status,
    uta.user_role,
    uta.last_login_date,
    CASE WHEN t.tool_name ILIKE %s THEN 'N/A' ELSE uta.last_login_date END AS display_last_login,
    CASE WHEN t.tool_name ILIKE %s THEN 'Active Access' ELSE uta.status END AS display_status
FROM user_tool_access uta
JOIN tools t ON t.id = uta.tool_id
LEFT JOIN users u ON lower(u.email) = lower(uta.work_email)
WHERE uta.status = 'active'
  AND u.email IS NULL
ORDER BY t.tool_name, uta.work_email
"""

_STALE_SQL = """
SELECT
    uta.id,
    uta.work_email,
    uta.tool_id,
    t.tool_name,
    uta.status,
    uta.user_role,
    uta.last_login_date,
    CASE WHEN t.tool_name ILIKE %s THEN 'N/A' ELSE uta.last_login_date END AS display_last_login,
    CASE WHEN t.tool_name ILIKE %s THEN 'Active Access' ELSE uta.status END AS display_status
FROM user_tool_access uta
JOIN tools t ON t.id = uta.tool_id
LEFT JOIN users u ON lower(u.email) = lower(uta.work_email)
WHERE uta.status = 'active'
  AND t.tool_name NOT ILIKE %s
  AND (
        uta.last_login_date IS NOT NULL
        AND uta.last_login_date != ''
        AND uta.last_login_date != 'N/A'
        AND TO_DATE(uta.last_login_date, 'YYYY-MM-DD') < NOW() - INTERVAL '%s days'
  )
ORDER BY uta.last_login_date, t.tool_name, uta.work_email
"""


async def find_orphans(conn: psycopg.AsyncConnection) -> list[dict]:
    """Return active tool access rows with no matching AD user record."""
    bd_pattern = f"%{_BLACKDUCK_NAME}%"
    async with conn.cursor() as cur:
        await cur.execute(_ORPHAN_SQL, (bd_pattern, bd_pattern))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) async for row in cur]


async def find_stale(conn: psycopg.AsyncConnection, days: int = _STALE_DAYS) -> list[dict]:
    """Return active tool access rows whose last login exceeds the stale threshold."""
    bd_pattern = f"%{_BLACKDUCK_NAME}%"
    async with conn.cursor() as cur:
        await cur.execute(_STALE_SQL, (bd_pattern, bd_pattern, bd_pattern, days))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) async for row in cur]


def _print_report(orphans: list[dict], stale: list[dict]) -> None:
    print(f"\n=== Access Validation Report ===")
    print(f"\nOrphaned accounts (active access, no AD user): {len(orphans)}")
    for row in orphans:
        print(f"  {row['work_email']:<40} {row['tool_name']:<30} {row['display_status']}")

    print(f"\nStale accounts (no login in >{_STALE_DAYS} days): {len(stale)}")
    for row in stale:
        print(f"  {row['work_email']:<40} {row['tool_name']:<30} {row['display_last_login']}")


async def run_validation() -> None:
    dsn = config.DATABASE_URL
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        orphans, stale = await asyncio.gather(
            find_orphans(conn),
            find_stale(conn),
        )
    _print_report(orphans, stale)
    logger.info("Validation complete: %d orphans, %d stale", len(orphans), len(stale))


def main() -> None:
    import logging as _logging
    _logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_validation())


if __name__ == "__main__":
    main()
