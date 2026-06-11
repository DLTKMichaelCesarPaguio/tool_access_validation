from __future__ import annotations

import logging

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)


class CheckmarxCollector(BaseCollector):
    """Collects user accounts from Checkmarx Enterprise (CxSAST) via REST API."""

    def __init__(self, base_url: str, username: str, password: str, tool_id: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("Checkmarx: collection failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("Checkmarx: unexpected error: %s", exc)
            return []

    async def _fetch(self) -> list[dict]:
        async with make_client(timeout=30.0) as client:
            token = await self._get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            role_map = await self._get_role_map(client, headers)
            return await self._get_users(client, headers, role_map)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.base_url}/cxrestapi/auth/identity/connect/token",
            data={
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
                "client_id": "resource_owner_client",
                "client_secret": "014DF517-39D1-4453-B7B3-9930C563627C",
                "scope": "sast_rest_api access_control_api",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def _get_role_map(
        self, client: httpx.AsyncClient, headers: dict
    ) -> dict[int, str]:
        resp = await client.get(
            f"{self.base_url}/cxrestapi/auth/Roles",
            headers=headers,
        )
        resp.raise_for_status()
        return {r["id"]: r["name"] for r in resp.json()}

    async def _get_users(
        self, client: httpx.AsyncClient, headers: dict, role_map: dict[int, str]
    ) -> list[dict]:
        resp = await client.get(
            f"{self.base_url}/cxrestapi/auth/Users",
            headers=headers,
        )
        resp.raise_for_status()
        items = resp.json()

        rows: list[dict] = []
        for u in items:
            email = (u.get("email") or "").lower()
            if not email:
                continue
            role_ids = u.get("roleIds") or []
            role_names = ", ".join(role_map[rid] for rid in role_ids if rid in role_map)
            rows.append({
                "work_email": email,
                "status": "active" if u.get("active", True) else "inactive",
                "user_role": role_names or None,
                "last_login_date": u.get("lastLoginDate"),
            })

        logger.info("Checkmarx: collected %d users", len(rows))
        return rows
