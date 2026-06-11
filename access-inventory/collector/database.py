from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def upsert_users(conn: Any, rows: list[dict]) -> None:
    """Upsert user rows into the `users` table.

    Upsert key: `email` (existing UNIQUE constraint).
    Only updates rows whose field values have actually changed.
    Note: full_name is a GENERATED column (first_name || ' ' || last_name) — not inserted.
    """
    if not rows:
        return

    sql = """
        INSERT INTO users (
            email, first_name, last_name,
            job_title, department, employee_id, is_employee, is_active, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (email) DO UPDATE SET
            first_name  = EXCLUDED.first_name,
            last_name   = EXCLUDED.last_name,
            job_title   = EXCLUDED.job_title,
            department  = EXCLUDED.department,
            employee_id = EXCLUDED.employee_id,
            is_employee = EXCLUDED.is_employee,
            is_active   = EXCLUDED.is_active,
            updated_at  = NOW()
        WHERE (users.first_name, users.last_name,
               users.job_title, users.department, users.is_active)
           IS DISTINCT FROM
              (EXCLUDED.first_name, EXCLUDED.last_name,
               EXCLUDED.job_title, EXCLUDED.department, EXCLUDED.is_active)
    """
    # Fallback when employee_id collides with another AD entry (duplicate employeeID in AD)
    sql_no_empid = """
        INSERT INTO users (
            email, first_name, last_name,
            job_title, department, is_employee, is_active, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (email) DO UPDATE SET
            first_name  = EXCLUDED.first_name,
            last_name   = EXCLUDED.last_name,
            job_title   = EXCLUDED.job_title,
            department  = EXCLUDED.department,
            is_employee = EXCLUDED.is_employee,
            is_active   = EXCLUDED.is_active,
            updated_at  = NOW()
        WHERE (users.first_name, users.last_name,
               users.job_title, users.department, users.is_active)
           IS DISTINCT FROM
              (EXCLUDED.first_name, EXCLUDED.last_name,
               EXCLUDED.job_title, EXCLUDED.department, EXCLUDED.is_active)
    """

    import psycopg as _psycopg
    async with conn.cursor() as cur:
        for row in rows:
            employee_id = row.get("employee_id")
            await cur.execute("SAVEPOINT upsert_user")
            try:
                await cur.execute(sql, (
                    row.get("email"),
                    row.get("first_name"),
                    row.get("last_name"),
                    row.get("job_title"),
                    row.get("department"),
                    employee_id,
                    row.get("is_employee", employee_id is not None),
                    row.get("is_active", True),
                ))
                await cur.execute("RELEASE SAVEPOINT upsert_user")
            except _psycopg.errors.UniqueViolation:
                # Duplicate employee_id from another AD entry — insert without it
                await cur.execute("ROLLBACK TO SAVEPOINT upsert_user")
                await cur.execute("RELEASE SAVEPOINT upsert_user")
                await cur.execute(sql_no_empid, (
                    row.get("email"),
                    row.get("first_name"),
                    row.get("last_name"),
                    row.get("job_title"),
                    row.get("department"),
                    False,
                    row.get("is_active", True),
                ))

    logger.info("upsert_users: processed %d rows", len(rows))


async def upsert_tool_access(conn: Any, tool_id: str, rows: list[dict]) -> None:
    """Upsert tool access rows into `user_tool_access`.

    Upsert key: (tool_id, work_email, COALESCE(username, '')) — one row per
    login, so a user with multiple vendor accounts gets one row each.
    Requires the uq_tool_user expression index from
    migrations/002_multi_login_per_user.sql.
    tool_id is a UUID string.
    """
    if not rows:
        return

    sql = """
        INSERT INTO user_tool_access (
            tool_id, work_email, username, external_user_id,
            first_name, last_name, granted_date,
            status, user_role, last_login_date, updated_at
        )
        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (tool_id, work_email, COALESCE(username, '')) DO UPDATE SET
            external_user_id = EXCLUDED.external_user_id,
            first_name       = EXCLUDED.first_name,
            last_name        = EXCLUDED.last_name,
            user_role        = EXCLUDED.user_role,
            status           = EXCLUDED.status,
            last_login_date  = EXCLUDED.last_login_date,
            updated_at       = NOW()
        WHERE (user_tool_access.external_user_id, user_tool_access.first_name,
               user_tool_access.last_name, user_tool_access.user_role,
               user_tool_access.status, user_tool_access.last_login_date)
           IS DISTINCT FROM
              (EXCLUDED.external_user_id, EXCLUDED.first_name,
               EXCLUDED.last_name, EXCLUDED.user_role,
               EXCLUDED.status, EXCLUDED.last_login_date)
    """
    async with conn.cursor() as cur:
        for row in rows:
            await cur.execute(sql, (
                tool_id,
                row.get("work_email"),
                row.get("username"),
                row.get("external_user_id"),
                row.get("first_name"),
                row.get("last_name"),
                row.get("granted_date"),
                row.get("status"),
                row.get("user_role"),
                row.get("last_login_date"),
            ))

    logger.info("upsert_tool_access: tool_id=%s processed %d rows", tool_id, len(rows))


async def soft_delete_absent(
    conn: Any, tool_id: str, present_logins: list[tuple[str, str | None]]
) -> None:
    """Mark as inactive any active tool access rows not in `present_logins`.

    `present_logins` is a list of (work_email, username) tuples — one entry
    per login row returned by the collector this run. Rows whose
    (work_email, COALESCE(username,'')) pair is absent from that list are
    soft-deleted so that only the specific vanished login is deactivated,
    not all logins for the same email.

    Looks up `access_audit_log` for a DELETE record to get the accurate
    deactivation date. Falls back to NOW() when no log entry exists.
    """
    find_sql = """
        SELECT work_email, username
        FROM user_tool_access
        WHERE tool_id = %s::uuid
          AND status != 'inactive'
          AND (work_email, COALESCE(username, '')) != ALL(%s::text[])
    """
    audit_sql = """
        SELECT change_timestamp
        FROM access_audit_log
        WHERE (old_values->>'tool_id')::uuid = %s::uuid
          AND old_values->>'work_email' = %s
          AND old_values->>'username' IS NOT DISTINCT FROM %s
          AND action = 'DELETE'
        ORDER BY change_timestamp DESC
        LIMIT 1
    """
    update_sql = """
        UPDATE user_tool_access
        SET status            = 'inactive',
            deactivation_date = %s,
            updated_at        = NOW()
        WHERE tool_id                    = %s::uuid
          AND work_email                 = %s
          AND COALESCE(username, '')     = COALESCE(%s, '')
          AND status                    != 'inactive'
    """

    # Build the exclusion array as "email\x1fusername" composite strings so
    # Postgres can compare (work_email, COALESCE(username,'')) != ALL(array).
    SEP = "\x1f"
    present_set = [
        f"{email}{SEP}{uname or ''}"
        for email, uname in present_logins
    ]

    async with conn.cursor() as cur:
        # Rewrite find_sql to avoid the composite != ALL trick —
        # use a simpler NOT IN subquery with the separator approach.
        find_sql2 = """
            SELECT work_email, username
            FROM user_tool_access
            WHERE tool_id = %s::uuid
              AND status != 'inactive'
              AND (work_email || %s || COALESCE(username, '')) != ALL(%s)
        """
        await cur.execute(find_sql2, (tool_id, SEP, present_set))
        absent_rows = await cur.fetchall()

        for row in absent_rows:
            email, uname = row[0], row[1]

            await cur.execute(audit_sql, (tool_id, email, uname))
            log_entry = await cur.fetchone()

            deactivation_date = (
                log_entry[0] if (log_entry and log_entry[0])
                else datetime.now(timezone.utc)
            )

            await cur.execute(update_sql, (deactivation_date, tool_id, email, uname))
            logger.info(
                "soft_delete_absent: marked %s/%s inactive for tool_id=%s (date=%s)",
                email, uname, tool_id, deactivation_date,
            )


async def update_last_sync(conn: Any, tool_id: str) -> None:
    """Update `tools.last_sync_at` to NOW() for the given tool UUID."""
    sql = "UPDATE tools SET last_sync_at = NOW() WHERE tool_id = %s::uuid"
    async with conn.cursor() as cur:
        await cur.execute(sql, (tool_id,))
    logger.debug("update_last_sync: tool_id=%s", tool_id)
