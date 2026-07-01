from __future__ import annotations

import logging

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://id.sophos.com/api/v2/oauth2/token"


class SophosCollector(BaseCollector):
    """Collects admin accounts from Sophos Central."""

    def __init__(self, client_id: str, client_secret: str, tool_id: int) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("Sophos: collection failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Sophos: unexpected error: %s", exc)
            return []

    async def _fetch(self) -> list[dict]:
        async with make_client(timeout=30.0) as client:
            token = await self._get_token(client)
            whoami = await self._get_whoami(client, token)

            if whoami.get("idType") == "organization":
                return await self._get_organization_admins(client, token, whoami["id"])

            tenant_id = whoami["id"]
            api_host = (whoami.get("apiHosts") or {}).get("dataRegion") or \
                       (whoami.get("apiHosts") or {}).get("global") or \
                       "https://api.central.sophos.com"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id,
            }
            return await self._get_admins(client, headers, api_host)

    async def _get_organization_admins(
        self, client: httpx.AsyncClient, token: str, organization_id: str
    ) -> list[dict]:
        """Enterprise-level admins (Global Settings > Admins and Roles) live
        at /organization/v1/admins — a single cross-tenant roster, distinct
        from any individual tenant's /common/v1/admins list. Paginated by
        page number, not by cursor, unlike the other Sophos endpoints."""
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": organization_id,
        }
        rows: list[dict] = []
        page = 1

        while True:
            resp = await client.get(
                "https://api.central.sophos.com/organization/v1/admins",
                headers=headers,
                params={"pageSize": 100, "page": page, "pageTotal": True},
            )
            resp.raise_for_status()
            data = resp.json()

            for admin in data.get("items") or []:
                email = (admin.get("username") or "").lower()
                if not email:
                    continue
                roles = admin.get("roleAssignments") or []
                rows.append({
                    "work_email": email,
                    "username": (admin.get("profile") or {}).get("name") or email,
                    "status": "active",
                    "user_role": roles[0]["scope"]["type"] if roles else None,
                    "last_login_date": None,
                })

            pages = data.get("pages") or {}
            if page >= (pages.get("total") or 1):
                break
            page += 1

        logger.info("Sophos: collected %d organization admins", len(rows))
        return rows

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def _get_whoami(self, client: httpx.AsyncClient, token: str) -> dict:
        resp = await client.get(
            "https://api.central.sophos.com/whoami/v1",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def _get_admins(
        self, client: httpx.AsyncClient, headers: dict, api_host: str
    ) -> list[dict]:
        rows: list[dict] = []
        page_token: str | None = None

        while True:
            params: dict = {"pageSize": 100}
            if page_token:
                params["pageFromKey"] = page_token

            resp = await client.get(
                f"{api_host}/common/v1/admins",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for admin in data.get("items") or []:
                email = (admin.get("email") or "").lower()
                if not email:
                    continue
                rows.append({
                    "work_email": email,
                    "username": admin.get("name") or email or None,
                    "status": "active",
                    "user_role": admin.get("roleType"),
                    "last_login_date": None,
                })

            page_token = (data.get("pages") or {}).get("nextKey")
            if not page_token:
                break

        logger.info("Sophos: collected %d admins", len(rows))
        return rows
