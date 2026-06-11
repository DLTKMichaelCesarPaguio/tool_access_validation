from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.database import (
    soft_delete_absent,
    update_last_sync,
    upsert_tool_access,
    upsert_users,
)

FAKE_UUID = "d5121a30-51e0-4612-abc7-70d71c6651e9"


def _mock_conn():
    """Return (conn, cursor) with async context manager support."""
    cursor = AsyncMock()
    conn = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock(return_value=False)
    return conn, cursor


# ── upsert_users ──────────────────────────────────────────────────────────────

class TestUpsertUsers:
    async def test_happy_path_three_rows(self):
        conn, cursor = _mock_conn()
        rows = [
            {"email": "a@d.com", "first_name": "A", "last_name": "",
             "job_title": "Eng", "department": "IT", "employee_id": "1", "is_active": True},
            {"email": "b@d.com", "first_name": "B", "last_name": "",
             "job_title": "", "department": "", "employee_id": "2", "is_active": True},
            {"email": "c@d.com", "first_name": "C", "last_name": "",
             "job_title": "", "department": "", "employee_id": "3", "is_active": True},
        ]
        await upsert_users(conn, rows)
        assert cursor.execute.call_count == 3

    async def test_sql_contains_on_conflict(self):
        conn, cursor = _mock_conn()
        rows = [{"email": "a@d.com", "first_name": "A",
                 "last_name": "", "job_title": "", "department": "", "employee_id": "1",
                 "is_active": True}]
        await upsert_users(conn, rows)
        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql.upper()
        assert "IS DISTINCT FROM" in sql.upper()

    async def test_empty_list_makes_no_db_calls(self):
        conn, cursor = _mock_conn()
        await upsert_users(conn, [])
        cursor.execute.assert_not_called()


# ── upsert_tool_access ────────────────────────────────────────────────────────

class TestUpsertToolAccess:
    async def test_happy_path_new_rows(self):
        conn, cursor = _mock_conn()
        rows = [
            {"work_email": "a@d.com", "status": "active", "user_role": "admin",
             "last_login_date": None},
        ]
        await upsert_tool_access(conn, tool_id=FAKE_UUID, rows=rows)
        cursor.execute.assert_called_once()

    async def test_sql_conflict_on_tool_id_and_email(self):
        conn, cursor = _mock_conn()
        rows = [{"work_email": "a@d.com", "status": "active",
                 "user_role": "user", "last_login_date": None}]
        await upsert_tool_access(conn, tool_id=FAKE_UUID, rows=rows)
        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql.upper()
        assert "tool_id" in sql
        assert "work_email" in sql

    async def test_sql_contains_is_distinct_from(self):
        conn, cursor = _mock_conn()
        rows = [{"work_email": "a@d.com", "status": "active",
                 "user_role": "user", "last_login_date": None}]
        await upsert_tool_access(conn, tool_id=FAKE_UUID, rows=rows)
        sql = cursor.execute.call_args[0][0]
        assert "IS DISTINCT FROM" in sql.upper()

    async def test_empty_rows_makes_no_db_calls(self):
        conn, cursor = _mock_conn()
        await upsert_tool_access(conn, tool_id=FAKE_UUID, rows=[])
        cursor.execute.assert_not_called()


# ── soft_delete_absent ────────────────────────────────────────────────────────

class TestSoftDeleteAbsent:
    async def test_uses_audit_log_timestamp_when_present(self):
        conn, cursor = _mock_conn()
        ts = datetime(2025, 8, 1, tzinfo=timezone.utc)
        cursor.fetchall.return_value = [("gone@d.com",)]
        cursor.fetchone.return_value = (ts,)

        await soft_delete_absent(conn, tool_id=FAKE_UUID, present_emails=["active@d.com"])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        params = update_calls[0][0][1]
        assert ts in params

    async def test_falls_back_to_now_when_no_audit_log(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [("gone@d.com",)]
        cursor.fetchone.return_value = None

        await soft_delete_absent(conn, tool_id=FAKE_UUID, present_emails=["active@d.com"])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        params = update_calls[0][0][1]
        datetime_params = [p for p in params if isinstance(p, datetime)]
        assert datetime_params, "Expected a datetime fallback when no audit log entry"

    async def test_no_update_when_all_emails_present(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = []

        await soft_delete_absent(conn, tool_id=FAKE_UUID, present_emails=["a@d.com", "b@d.com"])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 0

    async def test_soft_delete_sets_inactive_status(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [("gone@d.com",)]
        cursor.fetchone.return_value = None

        await soft_delete_absent(conn, tool_id=FAKE_UUID, present_emails=[])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        sql = update_calls[0][0][0]
        assert "inactive" in sql.lower()


# ── update_last_sync ──────────────────────────────────────────────────────────

class TestUpdateLastSync:
    async def test_executes_update_with_tool_id(self):
        conn, cursor = _mock_conn()
        await update_last_sync(conn, tool_id=FAKE_UUID)
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "UPDATE" in sql.upper()
        assert "last_sync_at" in sql
        assert FAKE_UUID in params
