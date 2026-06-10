from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from collector.database import (
    soft_delete_absent,
    update_last_sync,
    upsert_tool_access,
    upsert_users,
)


def _mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


# ── upsert_users ──────────────────────────────────────────────────────────────

class TestUpsertUsers:
    def test_happy_path_three_rows(self):
        conn, cursor = _mock_conn()
        rows = [
            {"email": "a@d.com", "full_name": "A", "first_name": "A", "last_name": "",
             "job_title": "Eng", "department": "IT", "employee_id": "1", "is_active": True},
            {"email": "b@d.com", "full_name": "B", "first_name": "B", "last_name": "",
             "job_title": "", "department": "", "employee_id": "2", "is_active": True},
            {"email": "c@d.com", "full_name": "C", "first_name": "C", "last_name": "",
             "job_title": "", "department": "", "employee_id": "3", "is_active": True},
        ]
        upsert_users(conn, rows)
        assert cursor.execute.call_count == 3

    def test_sql_contains_on_conflict(self):
        conn, cursor = _mock_conn()
        rows = [{"email": "a@d.com", "full_name": "A", "first_name": "A",
                 "last_name": "", "job_title": "", "department": "", "employee_id": "1",
                 "is_active": True}]
        upsert_users(conn, rows)
        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql.upper()
        assert "IS DISTINCT FROM" in sql.upper()

    def test_empty_list_makes_no_db_calls(self):
        conn, cursor = _mock_conn()
        upsert_users(conn, [])
        cursor.execute.assert_not_called()


# ── upsert_tool_access ────────────────────────────────────────────────────────

class TestUpsertToolAccess:
    def test_happy_path_new_rows(self):
        conn, cursor = _mock_conn()
        rows = [
            {"work_email": "a@d.com", "status": "active", "user_role": "admin",
             "last_login_date": None},
        ]
        upsert_tool_access(conn, tool_id=1, rows=rows)
        cursor.execute.assert_called_once()

    def test_sql_conflict_on_tool_id_and_email(self):
        conn, cursor = _mock_conn()
        rows = [{"work_email": "a@d.com", "status": "active",
                 "user_role": "user", "last_login_date": None}]
        upsert_tool_access(conn, tool_id=1, rows=rows)
        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql.upper()
        assert "tool_id" in sql
        assert "work_email" in sql

    def test_sql_contains_is_distinct_from(self):
        conn, cursor = _mock_conn()
        rows = [{"work_email": "a@d.com", "status": "active",
                 "user_role": "user", "last_login_date": None}]
        upsert_tool_access(conn, tool_id=1, rows=rows)
        sql = cursor.execute.call_args[0][0]
        assert "IS DISTINCT FROM" in sql.upper()

    def test_empty_rows_makes_no_db_calls(self):
        conn, cursor = _mock_conn()
        upsert_tool_access(conn, tool_id=1, rows=[])
        cursor.execute.assert_not_called()


# ── soft_delete_absent ────────────────────────────────────────────────────────

class TestSoftDeleteAbsent:
    def _make_cursor_with_active_rows(self, emails: list[str]):
        """Return (conn, cursor) where fetchall returns active rows for given emails."""
        conn, cursor = _mock_conn()
        # First fetchall: returns active rows not in present_emails
        cursor.fetchall.return_value = [
            {"work_email": e, "tool_id": 1} for e in emails
        ]
        # Second fetchone (audit log lookup): returns None by default
        cursor.fetchone.return_value = None
        return conn, cursor

    def test_uses_audit_log_timestamp_when_present(self):
        conn, cursor = _mock_conn()
        ts = datetime(2025, 8, 1, tzinfo=timezone.utc)
        # First call: absent rows query
        cursor.fetchall.return_value = [{"work_email": "gone@d.com", "tool_id": 1}]
        # Second call: audit log lookup returns a record with change_timestamp
        cursor.fetchone.return_value = {"change_timestamp": ts}

        soft_delete_absent(conn, tool_id=1, present_emails=["active@d.com"])

        # Verify the UPDATE was called and used the audit log timestamp
        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        # The timestamp from the audit log should appear in the params
        params = update_calls[0][0][1]
        assert ts in params

    def test_falls_back_to_now_when_no_audit_log(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [{"work_email": "gone@d.com", "tool_id": 1}]
        cursor.fetchone.return_value = None  # no audit log entry

        soft_delete_absent(conn, tool_id=1, present_emails=["active@d.com"])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        params = update_calls[0][0][1]
        # Should contain a datetime fallback (not None)
        datetime_params = [p for p in params if isinstance(p, datetime)]
        assert datetime_params, "Expected a datetime fallback when no audit log entry"

    def test_no_update_when_all_emails_present(self):
        conn, cursor = _mock_conn()
        # No absent rows returned
        cursor.fetchall.return_value = []

        soft_delete_absent(conn, tool_id=1, present_emails=["a@d.com", "b@d.com"])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 0

    def test_soft_delete_sets_inactive_status(self):
        conn, cursor = _mock_conn()
        cursor.fetchall.return_value = [{"work_email": "gone@d.com", "tool_id": 1}]
        cursor.fetchone.return_value = None

        soft_delete_absent(conn, tool_id=1, present_emails=[])

        update_calls = [c for c in cursor.execute.call_args_list
                        if "UPDATE" in str(c[0][0]).upper()]
        assert len(update_calls) == 1
        sql = update_calls[0][0][0]
        assert "inactive" in sql.lower() or "inactive" in str(update_calls[0][0][1]).lower()


# ── update_last_sync ──────────────────────────────────────────────────────────

class TestUpdateLastSync:
    def test_executes_update_with_tool_id(self):
        conn, cursor = _mock_conn()
        update_last_sync(conn, tool_id=5)
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "UPDATE" in sql.upper()
        assert "last_sync_at" in sql
        assert 5 in params
