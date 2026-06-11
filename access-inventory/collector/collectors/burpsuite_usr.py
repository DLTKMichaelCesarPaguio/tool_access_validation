from __future__ import annotations

import logging

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)


class BurpSuiteCollector(BaseCollector):
    """Collects user accounts from Burp Suite Enterprise via API key auth."""

    def __init__(self, api_key: str, base_url: str, tool_id: int) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("BurpSuite: collection failed: %s", exc)
            return []
        except Exception as exc:
            logger.error("BurpSuite: unexpected error: %s", exc)
            return []

    async def _fetch(self) -> list[dict]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with make_client(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/users",
                headers=headers,
            )
            resp.raise_for_status()
            users = resp.json() if isinstance(resp.json(), list) else resp.json().get("users", [])

        rows: list[dict] = []
        for u in users:
            email = (u.get("email") or u.get("username") or "").lower()
            if not email:
                continue
            rows.append({
                "work_email": email,
                "status": "active",
                "user_role": u.get("role"),
                "last_login_date": u.get("last_login"),
            })

        logger.info("BurpSuite: collected %d users", len(rows))
        return rows
