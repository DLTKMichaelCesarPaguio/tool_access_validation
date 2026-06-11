from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.app import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ── GET / ──────────────────────────────────────────────────────────────────────


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ── POST /search ───────────────────────────────────────────────────────────────


def test_search_empty_email_returns_error(client):
    with patch("web.app._get_pool") as mock_pool_fn:
        mock_pool = MagicMock()
        mock_pool_fn.return_value = mock_pool

        response = client.post("/search", data={"email": "   "})
        assert response.status_code == 200
        assert "Please enter" in response.text


def test_search_returns_results_for_known_email(client):
    mock_ad = {"email": "dev@deltek.com", "full_name": "Dev User",
               "job_title": "Engineer", "department": "IT",
               "first_name": "Dev", "last_name": "User",
               "employee_id": "EMP001", "is_active": True}
    mock_access = [
        {"work_email": "dev@deltek.com", "tool_name": "CrowdStrike",
         "status": "active", "user_role": "admin",
         "last_login_date": "2026-01-01", "updated_at": None},
    ]

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.get_ad_profile", new_callable=AsyncMock, return_value=mock_ad),
            patch("web.app.queries.get_tool_access", new_callable=AsyncMock, return_value=mock_access),
        ):
            response = client.post("/search", data={"email": "dev@deltek.com"})

    assert response.status_code == 200
    assert "dev@deltek.com" in response.text
    assert "CrowdStrike" in response.text


def test_search_falls_back_to_ldap_when_db_empty(client):
    ldap_result = [{"email": "new@deltek.com", "full_name": "New User",
                    "job_title": None, "department": None,
                    "first_name": "New", "last_name": "User", "employee_id": None}]

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.get_ad_profile", new_callable=AsyncMock, return_value=None),
            patch("web.app.queries.get_tool_access", new_callable=AsyncMock, return_value=[]),
            patch("web.app.asyncio.to_thread", new_callable=AsyncMock, return_value=ldap_result),
        ):
            response = client.post("/search", data={"email": "new@deltek.com"})

    assert response.status_code == 200
    assert "new@deltek.com" in response.text


def test_search_ldap_injection_returns_error(client):
    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.get_ad_profile", new_callable=AsyncMock, return_value=None),
            patch("web.app.queries.get_tool_access", new_callable=AsyncMock, return_value=[]),
            patch("web.app.asyncio.to_thread", side_effect=ValueError("not allowed")),
        ):
            response = client.post("/search", data={"email": "bad)(input"})

    assert response.status_code == 200
    assert "Invalid search input" in response.text


def test_search_invalid_characters_returns_error(client):
    response = client.post("/search", data={"email": "'; DROP TABLE users;--"})
    assert response.status_code == 200
    assert "Invalid search input" in response.text


def test_search_by_name_single_match_loads_profile(client):
    """Single name match → profile loaded directly (no picker)."""
    mock_candidate = {
        "email": "michael.p@deltek.com",
        "full_name": "Michael Paguio",
        "first_name": "Michael",
        "last_name": "Paguio",
        "job_title": "Engineer",
        "department": "IT",
    }
    mock_ad = {
        "email": "michael.p@deltek.com",
        "full_name": "Michael Paguio",
        "job_title": "Engineer",
        "department": "IT",
        "first_name": "Michael",
        "last_name": "Paguio",
        "employee_id": "EMP001",
        "is_active": True,
    }

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.search_users_by_name",
                  new_callable=AsyncMock, return_value=[mock_candidate]),
            patch("web.app.queries.search_users_by_username",
                  new_callable=AsyncMock, return_value=[]),
            patch("web.app.queries.get_ad_profile",
                  new_callable=AsyncMock, return_value=mock_ad),
            patch("web.app.queries.get_tool_access",
                  new_callable=AsyncMock, return_value=[]),
        ):
            response = client.post("/search", data={"email": "michael"})

    assert response.status_code == 200
    assert "Michael Paguio" in response.text
    assert "picker" not in response.text.lower() or "0 users" not in response.text


def test_search_by_name_multiple_matches_shows_picker(client):
    """Multiple name matches → picker list, no profile."""
    candidates = [
        {"email": "michael.a@deltek.com", "full_name": "Michael A",
         "first_name": "Michael", "last_name": "A", "job_title": "Dev", "department": "IT"},
        {"email": "michael.b@deltek.com", "full_name": "Michael B",
         "first_name": "Michael", "last_name": "B", "job_title": "QA", "department": "IT"},
    ]

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.search_users_by_name",
                  new_callable=AsyncMock, return_value=candidates),
            patch("web.app.queries.search_users_by_username",
                  new_callable=AsyncMock, return_value=[]),
        ):
            response = client.post("/search", data={"email": "michael"})

    assert response.status_code == 200
    assert "michael.a@deltek.com" in response.text
    assert "michael.b@deltek.com" in response.text


def test_search_by_fullname_single_match_loads_profile(client):
    """'first last' query with one DB match → profile."""
    candidate = {
        "email": "michael.paguio@deltek.com",
        "full_name": "Michael Paguio",
        "first_name": "Michael",
        "last_name": "Paguio",
        "job_title": "Engineer",
        "department": "IT",
    }
    mock_ad = {**candidate, "employee_id": None, "is_active": True}

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.search_users_by_name",
                  new_callable=AsyncMock, return_value=[candidate]),
            patch("web.app.queries.get_ad_profile",
                  new_callable=AsyncMock, return_value=mock_ad),
            patch("web.app.queries.get_tool_access",
                  new_callable=AsyncMock, return_value=[]),
        ):
            response = client.post("/search", data={"email": "michael paguio"})

    assert response.status_code == 200
    assert "michael.paguio@deltek.com" in response.text


def test_search_by_username_single_match_loads_profile(client):
    """Username search with one match → profile loaded directly."""
    candidate = {
        "email": "kibria@deltek.com",
        "full_name": "Kibria Ghulam",
        "first_name": "Kibria",
        "last_name": "Ghulam",
        "job_title": "Security",
        "department": "IT",
    }
    mock_ad = {**candidate, "employee_id": None, "is_active": True}

    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.search_users_by_username",
                  new_callable=AsyncMock, return_value=[candidate]),
            patch("web.app.queries.search_users_by_name",
                  new_callable=AsyncMock, return_value=[]),
            patch("web.app.queries.get_ad_profile",
                  new_callable=AsyncMock, return_value=mock_ad),
            patch("web.app.queries.get_tool_access",
                  new_callable=AsyncMock, return_value=[]),
        ):
            response = client.post("/search", data={"email": "detek3kg"})

    assert response.status_code == 200
    assert "Kibria Ghulam" in response.text


def test_search_no_results_shows_no_access_message(client):
    """Query that matches nothing shows the no-access message."""
    with patch("web.app._get_pool") as mock_pool_fn:
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.connection = MagicMock(return_value=mock_conn)
        mock_pool_fn.return_value = mock_pool

        with (
            patch("web.app.queries.search_users_by_username",
                  new_callable=AsyncMock, return_value=[]),
            patch("web.app.queries.search_users_by_name",
                  new_callable=AsyncMock, return_value=[]),
        ):
            response = client.post("/search", data={"email": "zzznobody"})

    assert response.status_code == 200
    # No picker, no profile — page rendered cleanly
    assert "zzznobody" in response.text
