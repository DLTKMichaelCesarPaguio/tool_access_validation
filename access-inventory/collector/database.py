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
            job_title, department, employee_id, is_active, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (email) DO UPDATE SET
            first_name  = EXCLUDED.first_name,
            last_name   = EXCLUDED.last_name,
            job_title   = EXCLUDED.job_title,
            department  = EXCLUDED.department,
            employee_id = EXCLUDED.employee_id,
            is_active   = EXCLUDED.is_active,
            updated_at  = NOW()
        WHERE (users.first_name, users.last_name,
               users.job_title, users.department, users.is_active)
           IS DISTINCT FROM
              (EXCLUDED.first_name, EXCLUDED.last_name,
               EXCLUDED.job_title, EXCLUDED.department, EXCLUDED.is_active)
    """
    async with conn.cursor() as cur:
        for row in rows:
            await cur.execute(sql, (
                row.get("email"),
                row.get("first_name"),
                row.get("last_name"),
                row.get("job_title"),
                row.get("department"),
                row.get("employee_id"),
                row.get("is_active", True),
            ))

    logger.info("upsert_users: processed %d rows", len(rows))


async def upsert_tool_access(conn: Any, tool_id: str, rows: list[dict]) -> None:
    """Upsert tool access rows into `user_tool_access`.

    Upsert key: (tool_id, work_email) — requires the uq_tool_user constraint
    from migrations/001_add_upsert_constraint.sql.
    Only updates rows whose field values have actually changed.
    tool_id is a UUID string.
    """
    if not rows:
        return

    sql = """
        INSERT INTO user_tool_access (
            tool_id, work_email, status, user_role, last_login_date, updated_at
        )
        VALUES (%s::uuid, %s, %s, %s, %s, NOW())
        ON CONFLICT (tool_id, work_email) DO UPDATE SET
            user_role       = EXCLUDED.user_role,
            status          = EXCLUDED.status,
            last_login_date = EXCLUDED.last_login_date,
            updated_at      = NOW()
        WHERE (user_tool_access.user_role, user_tool_access.status,
               user_tool_access.last_login_date)
           IS DISTINCT FROM
              (EXCLUDED.user_role, EXCLUDED.status, EXCLUDED.last_login_date)
    """
    async with conn.cursor() as cur:
        for row in rows:
            await cur.execute(sql, (
                tool_id,
                row.get("work_email"),
                row.get("status"),
                row.get("user_role"),
                row.get("last_login_date"),
            ))

    logger.info("upsert_tool_access: tool_id=%s processed %d rows", tool_id, len(rows))


async def soft_delete_absent(
    conn: Any, tool_id: str, present_emails: list[str]
) -> None:
    """Mark as inactive any active tool access rows not in `present_emails`.

    Looks up `access_audit_log` for a DELETE record to get the accurate
    deactivation date. Falls back to NOW() when no log entry exists.
    """
    find_sql = """
        SELECT work_email
        FROM user_tool_access
        WHERE tool_id = %s::uuid
          AND status != 'inactive'
          AND work_email != ALL(%s)
    """
    audit_sql = """
        SELECT change_timestamp
        FROM access_audit_log
        WHERE (old_values->>'tool_id')::uuid = %s::uuid
          AND old_values->>'work_email' = %s
          AND change_type = 'DELETE'
        ORDER BY change_timestamp DESC
        LIMIT 1
    """
    update_sql = """
        UPDATE user_tool_access
        SET status            = 'inactive',
            deactivation_date = %s,
            updated_at        = NOW()
        WHERE tool_id   = %s::uuid
          AND work_email = %s
          AND status    != 'inactive'
    """

    async with conn.cursor() as cur:
        await cur.execute(find_sql, (tool_id, list(present_emails)))
        absent_rows = await cur.fetchall()

        for row in absent_rows:
            email = row[0]

            await cur.execute(audit_sql, (tool_id, email))
            log_entry = await cur.fetchone()

            if log_entry and log_entry[0]:
                deactivation_date = log_entry[0]
            else:
                deactivation_date = datetime.now(timezone.utc)

            await cur.execute(update_sql, (deactivation_date, tool_id, email))
            logger.info(
                "soft_delete_absent: marked %s inactive for tool_id=%s (date=%s)",
                email, tool_id, deactivation_date,
            )


async def update_last_sync(conn: Any, tool_id: str) -> None:
    """Update `tools.last_sync_at` to NOW() for the given tool UUID."""
    sql = "UPDATE tools SET last_sync_at = NOW() WHERE tool_id = %s::uuid"
    async with conn.cursor() as cur:
        await cur.execute(sql, (tool_id,))
    logger.debug("update_last_sync: tool_id=%s", tool_id)
