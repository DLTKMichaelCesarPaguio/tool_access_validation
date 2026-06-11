from __future__ import annotations

import logging

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)


class CheckmarxCollector(BaseCollector):
    """Collects user accounts from Checkmarx One via OAuth2 client credentials."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant: str,
        iam_base_url: str,
        api_base_url: str,
        tool_id: int,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant = tenant
        self.iam_base_url = iam_base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
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
            return await self._get_users(client, headers)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.iam_base_url}/auth/realms/{self.tenant}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def _get_users(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        limit = 100
        total: int | None = None

        while True:
            resp = await client.get(
                f"{self.api_base_url}/api/1.0/users",
                headers=headers,
                params={"offset": offset, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            # Checkmarx may return a list or a dict with a users key + totalCount
            if isinstance(data, list):
                items = data
            else:
                items = data.get("users") or []
                if total is None:
                    total = data.get("totalCount")

            for u in items:
                email = (u.get("email") or "").lower()
                if not email:
                    continue
                is_active = u.get("active", True)
                rows.append({
                    "work_email": email,
                    "status": "active" if is_active else "inactive",
                    "user_role": ", ".join(u.get("roles") or []) or u.get("role"),
                    "last_login_date": u.get("lastLoginDate"),
                })

            offset += len(items)
            # Stop when we've fetched all known records, or there were no items
            if not items:
                break
            if total is not None and offset >= total:
                break
            if len(items) < limit and total is None:
                break

        logger.info("Checkmarx: collected %d users", len(rows))
        return rows
