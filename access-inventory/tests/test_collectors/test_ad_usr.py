from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.collectors.ad_usr import AdCollector


def _make_ldap_entry(attrs: dict) -> MagicMock:
    entry = MagicMock()
    entry.entry_attributes_as_dict = attrs
    return entry


def _make_connection(entries: list) -> MagicMock:
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.entries = entries
    conn.search.return_value = True
    conn.result = {"controls": {}}
    return conn


def _make_paged_connection(pages: list[list]) -> MagicMock:
    """Simulate a server that returns entries across multiple pages via
    the paged-results cookie, ending when the server returns an empty cookie."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    state = {"page": 0}

    def _search(*args, **kwargs):
        idx = state["page"]
        conn.entries = pages[idx]
        is_last_page = idx == len(pages) - 1
        cookie = b"" if is_last_page else f"cookie-{idx}".encode()
        conn.result = {
            "controls": {
                "1.2.840.113556.1.4.319": {"value": {"cookie": cookie}}
            }
        }
        state["page"] += 1
        return True

    conn.search.side_effect = _search
    return conn


class TestAdCollector:
    def _collector(self) -> AdCollector:
        return AdCollector(
            host="ads.deltek.com",
            port=389,
            use_ssl=False,
            bind_dn="CN=svc,DC=ads,DC=deltek,DC=com",
            bind_password="secret",
            base_dn="OU=accounts,DC=ads,DC=deltek,DC=com",
        )

    def test_happy_path_five_users_fetch_returns_five_dicts(self):
        entries = [
            _make_ldap_entry({
                "mail": ["user1@deltek.com"],
                "displayName": ["User One"],
                "givenName": ["User"],
                "sn": ["One"],
                "title": ["Engineer"],
                "department": ["IT"],
                "employeeID": ["E001"],
            })
            for _ in range(5)
        ]
        mock_conn = _make_connection(entries)

        with patch("collector.collectors.ad_usr.Connection", MagicMock(return_value=mock_conn)), \
             patch("collector.ldap_tls.build_server", return_value=MagicMock()):
            rows = self._collector().fetch()
            assert len(rows) == 5

    def test_field_mapping(self):
        entry = _make_ldap_entry({
            "mail": ["david@deltek.com"],
            "displayName": ["David Bogatek"],
            "givenName": ["David"],
            "sn": ["Bogatek"],
            "title": ["Manager"],
            "department": ["Security"],
            "employeeID": ["E999"],
        })
        mock_conn = _make_connection([entry])

        with patch("collector.collectors.ad_usr.Connection", MagicMock(return_value=mock_conn)), \
             patch("collector.ldap_tls.build_server", return_value=MagicMock()):
            rows = self._collector().fetch()
            row = rows[0]
            assert row["email"] == "david@deltek.com"
            assert row["full_name"] == "David Bogatek"
            assert row["first_name"] == "David"
            assert row["last_name"] == "Bogatek"
            assert row["job_title"] == "Manager"
            assert row["department"] == "Security"
            assert row["employee_id"] == "E999"
            assert row["is_active"] is True

    def test_missing_optional_fields_default_gracefully(self):
        entry = _make_ldap_entry({
            "mail": ["nojob@deltek.com"],
            "displayName": ["No Job"],
            "givenName": ["No"],
            "sn": ["Job"],
            "employeeID": [],
        })
        mock_conn = _make_connection([entry])

        with patch("collector.collectors.ad_usr.Connection", MagicMock(return_value=mock_conn)), \
             patch("collector.ldap_tls.build_server", return_value=MagicMock()):
            rows = self._collector().fetch()
            row = rows[0]
            assert row["job_title"] is None
            assert row["department"] is None
            assert row["employee_id"] is None

    def test_fetch_pages_past_1000_result_server_cap(self):
        """AD's non-paged search silently caps at 1000 entries (MaxResultSetSize).
        fetch() must use paged search so counts above that cap aren't truncated."""
        page1 = [
            _make_ldap_entry({
                "mail": [f"user{i}@deltek.com"],
                "displayName": [f"User {i}"],
                "givenName": ["User"],
                "sn": [str(i)],
                "employeeID": [f"E{i:04d}"],
            })
            for i in range(1000)
        ]
        page2 = [
            _make_ldap_entry({
                "mail": [f"user{i}@deltek.com"],
                "displayName": [f"User {i}"],
                "givenName": ["User"],
                "sn": [str(i)],
                "employeeID": [f"E{i:04d}"],
            })
            for i in range(1000, 1243)
        ]
        mock_conn = _make_paged_connection([page1, page2])

        with patch("collector.collectors.ad_usr.Connection", MagicMock(return_value=mock_conn)), \
             patch("collector.ldap_tls.build_server", return_value=MagicMock()):
            rows = self._collector().fetch()
            assert len(rows) == 1243
            assert mock_conn.search.call_count == 2

    def test_ldap_exception_propagates(self):
        from ldap3.core.exceptions import LDAPException

        with patch("collector.collectors.ad_usr.Connection") as conn_cls, \
             patch("collector.ldap_tls.build_server", return_value=MagicMock()):
            conn_cls.return_value.__enter__ = MagicMock(
                side_effect=LDAPException("bind failed")
            )
            conn_cls.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(Exception):
                self._collector().fetch()
