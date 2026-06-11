from __future__ import annotations

import pytest

from web.ldap_client import _sanitize, search_by_email, search_by_name


def test_sanitize_accepts_valid_email():
    assert _sanitize("user@deltek.com") == "user@deltek.com"


def test_sanitize_accepts_prefix():
    assert _sanitize("john.doe") == "john.doe"


def test_sanitize_accepts_space_for_name_search():
    assert _sanitize("michael paguio") == "michael paguio"


def test_sanitize_rejects_ldap_injection():
    with pytest.raises(ValueError, match="not allowed"):
        _sanitize("user)(|(password=*")


def test_sanitize_rejects_asterisk():
    with pytest.raises(ValueError, match="not allowed"):
        _sanitize("user*")


def test_sanitize_rejects_parentheses():
    with pytest.raises(ValueError, match="not allowed"):
        _sanitize("(user)")


def test_sanitize_rejects_null_byte():
    with pytest.raises(ValueError):
        _sanitize("user\x00admin")


def test_sanitize_rejects_backslash():
    with pytest.raises(ValueError):
        _sanitize("user\\admin")


def test_search_by_email_raises_value_error_on_unsafe_input():
    """search_by_email should propagate ValueError from _sanitize before any LDAP call."""
    with pytest.raises(ValueError):
        search_by_email(
            host="ldap.example.com",
            port=389,
            use_ssl=False,
            bind_dn="cn=svc,dc=test",
            bind_password="pass",
            base_dn="dc=test",
            email="bad)(input",
        )


def test_search_by_name_raises_value_error_on_unsafe_first_name():
    with pytest.raises(ValueError):
        search_by_name(
            host="ldap.example.com",
            port=389,
            use_ssl=False,
            bind_dn="cn=svc,dc=test",
            bind_password="pass",
            base_dn="dc=test",
            first_name="bad)(name",
            last_name="Smith",
        )


def test_search_by_name_raises_value_error_on_unsafe_last_name():
    with pytest.raises(ValueError):
        search_by_name(
            host="ldap.example.com",
            port=389,
            use_ssl=False,
            bind_dn="cn=svc,dc=test",
            bind_password="pass",
            base_dn="dc=test",
            first_name="John",
            last_name="bad)(name",
        )
