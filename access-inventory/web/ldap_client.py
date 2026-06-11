from __future__ import annotations

import re
from typing import Any

from ldap3 import Connection
from ldap3.core.exceptions import LDAPException

from collector.ldap_tls import build_server

# Only allow characters safe in LDAP filter values to prevent injection
_SAFE_INPUT_RE = re.compile(r"^[a-zA-Z0-9._@\-]+$")

_SEARCH_ATTRS = [
    "mail", "displayName", "givenName", "sn",
    "title", "department", "employeeID",
]


def _sanitize(value: str) -> str:
    """Raise ValueError if value contains characters unsafe in an LDAP filter."""
    if not _SAFE_INPUT_RE.match(value):
        raise ValueError(
            f"Search input contains characters not allowed in LDAP queries: {value!r}"
        )
    return value


def search_by_email(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    bind_password: str,
    base_dn: str,
    email: str,
    ca_cert: str = "",
) -> list[dict]:
    """Search AD for users matching the given email prefix or full address.

    Returns a list of user dicts. Raises LDAPException on connection failure.
    Raises ValueError on unsafe input.
    """
    _sanitize(email)
    search_filter = f"(mail={email}*)"

    server = build_server(host, port, use_ssl, ca_cert)
    with Connection(
        server,
        user=bind_dn,
        password=bind_password,
        auto_bind=True,
    ) as conn:
        conn.search(
            search_base=base_dn,
            search_filter=search_filter,
            attributes=_SEARCH_ATTRS,
        )
        return [_map_entry(e) for e in conn.entries]


def _first(attrs: dict, key: str) -> str | None:
    vals = attrs.get(key, [])
    if not vals:
        return None
    v = vals[0]
    return str(v).strip() if v else None


def _map_entry(entry: Any) -> dict:
    attrs = entry.entry_attributes_as_dict
    return {
        "email": _first(attrs, "mail"),
        "full_name": _first(attrs, "displayName"),
        "first_name": _first(attrs, "givenName"),
        "last_name": _first(attrs, "sn"),
        "job_title": _first(attrs, "title"),
        "department": _first(attrs, "department"),
        "employee_id": _first(attrs, "employeeID"),
    }
