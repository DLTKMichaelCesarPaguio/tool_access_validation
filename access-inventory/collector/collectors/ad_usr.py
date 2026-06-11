from __future__ import annotations

import logging
from typing import Any

from ldap3 import Connection
from ldap3.core.exceptions import LDAPException

from collector import database
from collector.ldap_tls import build_server

logger = logging.getLogger(__name__)

_ATTRIBUTES = [
    "cn", "sn", "givenName", "displayName",
    "mail", "title", "department", "employeeID", "distinguishedName",
]


def _first(attrs: dict, key: str) -> str | None:
    """Return first value from an LDAP multi-value attribute list, or None."""
    vals = attrs.get(key, [])
    if not vals:
        return None
    v = vals[0]
    return str(v).strip() if v else None


class AdCollector:
    """Synchronous LDAP collector — syncs all AD users into the `users` table.

    Runs before the async tool collector fan-out so the `users` table is
    current before orphan detection or web app enrichment occurs.
    """

    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool,
        bind_dn: str,
        bind_password: str,
        base_dn: str,
        ca_cert: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.bind_dn = bind_dn
        self.bind_password = bind_password
        self.base_dn = base_dn
        self.ca_cert = ca_cert

    def fetch(self) -> list[dict]:
        """Fetch all AD users and return them as a list of dicts (no DB call)."""
        server = build_server(self.host, self.port, self.use_ssl, self.ca_cert)

        with Connection(
            server,
            user=self.bind_dn,
            password=self.bind_password,
            auto_bind=True,
        ) as ldap_conn:
            ldap_conn.search(
                search_base=self.base_dn,
                search_filter="(mail=*)",
                attributes=_ATTRIBUTES,
            )
            entries = ldap_conn.entries

        rows = [self._map(e) for e in entries]
        return [r for r in rows if r.get("email")]

    def run(self, conn: Any) -> int:
        """Kept for backwards compatibility with sync callers (tests)."""
        import asyncio
        rows = self.fetch()
        asyncio.get_event_loop().run_until_complete(database.upsert_users(conn, rows))
        logger.info("ad_usr: synced %d users from AD", len(rows))
        return len(rows)

    @staticmethod
    def _map(entry: Any) -> dict:
        attrs = entry.entry_attributes_as_dict
        employee_id = _first(attrs, "employeeID")
        return {
            "email": _first(attrs, "mail"),
            "full_name": _first(attrs, "displayName"),
            "first_name": _first(attrs, "givenName"),
            "last_name": _first(attrs, "sn"),
            "job_title": _first(attrs, "title"),
            "department": _first(attrs, "department"),
            "employee_id": employee_id,
            "is_employee": employee_id is not None,
            "is_active": True,
        }
