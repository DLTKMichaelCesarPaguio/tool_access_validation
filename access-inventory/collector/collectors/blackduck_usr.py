from __future__ import annotations

import logging

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)

_BD_USER_ACCEPT = "application/vnd.blackducksoftware.user-4+json"


class BlackDuckCollector(BaseCollector):
    """Collects user accounts from BlackDuck via token → bearer exchange."""

    def __init__(self, api_token: str, base_url: str, tool_id: int) -> None:
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("BlackDuck: collection failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("BlackDuck: unexpected error: %s", exc)
            return []

    async def _fetch(self) -> list[dict]:
        async with make_client(timeout=30.0) as client:
            bearer = await self._get_bearer(client)
            headers = {
                "Authorization": f"Bearer {bearer}",
                "Accept": _BD_USER_ACCEPT,
            }
            return await self._get_users(client, headers)

    async def _get_bearer(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.base_url}/api/tokens/authenticate",
            headers={"Authorization": f"token {self.api_token}"},
        )
        resp.raise_for_status()
        return resp.json()["bearerToken"]

    async def _get_users(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        limit = 100

        while True:
            resp = await client.get(
                f"{self.base_url}/api/users",
                headers=headers,
                params={"offset": offset, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items") or []

            for u in items:
                email = (u.get("email") or u.get("userName") or "").lower()
                if not email:
                    continue
                rows.append({
                    "work_email": email,
                    "status": "active",
                    "user_role": u.get("type"),
                    "last_login_date": None,
                })

            total = data.get("totalCount", 0)
            offset += len(items)
            if not items or offset >= total:
                break

        logger.info("BlackDuck: collected %d users", len(rows))
        return rows
