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
                return await self._fetch_organization(client, token, whoami["id"])

            tenant_id = whoami["id"]
            api_host = (whoami.get("apiHosts") or {}).get("dataRegion") or \
                       (whoami.get("apiHosts") or {}).get("global") or \
                       "https://api.central.sophos.com"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id,
            }
            return await self._get_admins(client, headers, api_host)

    async def _fetch_organization(
        self, client: httpx.AsyncClient, token: str, organization_id: str
    ) -> list[dict]:
        """Organization-scoped credentials have no admins of their own —
        enumerate tenants under the org and collect each tenant's admins."""
        rows: list[dict] = []
        for tenant_id, api_host in await self._get_tenants(client, token, organization_id):
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id,
            }
            rows.extend(await self._get_admins(client, headers, api_host))
        return rows

    async def _get_tenants(
        self, client: httpx.AsyncClient, token: str, organization_id: str
    ) -> list[tuple[str, str]]:
        tenants: list[tuple[str, str]] = []
        page_token: str | None = None
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": organization_id,
        }

        while True:
            params: dict = {"pageSize": 100}
            if page_token:
                params["pageFromKey"] = page_token

            resp = await client.get(
                "https://api.central.sophos.com/organization/v1/tenants",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for tenant in data.get("items") or []:
                api_host = tenant.get("apiHost") or "https://api.central.sophos.com"
                tenants.append((tenant["id"], api_host))

            page_token = (data.get("pages") or {}).get("nextKey")
            if not page_token:
                break

        return tenants

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
