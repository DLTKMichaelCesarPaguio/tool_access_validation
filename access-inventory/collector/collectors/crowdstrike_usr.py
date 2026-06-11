from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from collector.collectors.base import BaseCollector, make_client

logger = logging.getLogger(__name__)

# ── Token scrubbing ───────────────────────────────────────────────────────────
# A leaked CrowdStrike token = full EDR fleet exfil. Scrub from all log output.

_ACCESS_TOKEN_RE = re.compile(
    r'(access_token["\']?\s*[:=]\s*["\']?)([^"\',\s}]+)', re.IGNORECASE
)
_AUTH_HEADER_RE = re.compile(
    r'(authorization["\']?\s*[:=]\s*["\']?)((?:bearer|basic|token)\s+)?([^"\',\s}]+)',
    re.IGNORECASE,
)


class _TokenScrubFilter(logging.Filter):
    REDACTION = "<redacted>"

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            scrubbed = _AUTH_HEADER_RE.sub(
                lambda m: m.group(1) + (m.group(2) or "") + self.REDACTION, msg
            )
            scrubbed = _ACCESS_TOKEN_RE.sub(
                lambda m: m.group(1) + self.REDACTION, scrubbed
            )
            if scrubbed != msg:
                record.msg = scrubbed
                record.args = None
        except Exception:
            return False
        return True


def _install_scrub_filter() -> None:
    scrub = _TokenScrubFilter()
    for name in (None, "httpx", "httpcore", __name__):
        lg = logging.getLogger(name)
        if not any(isinstance(f, _TokenScrubFilter) for f in lg.filters):
            lg.addFilter(scrub)


_install_scrub_filter()


class CrowdStrikeCollector(BaseCollector):
    """Collects user accounts from one CrowdStrike environment.

    Instantiate once per environment (Commercial, GCE, GCCM).
    """

    def __init__(
        self,
        env_name: str,
        client_id: str,
        client_secret: str,
        base_url: str,
        tool_id: int,
    ) -> None:
        self.env_name = env_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error(
                "CrowdStrike[%s]: collection failed: %s", self.env_name, exc
            )
            return []
        except Exception as exc:
            logger.error(
                "CrowdStrike[%s]: unexpected error: %s", self.env_name, exc
            )
            return []

    async def _fetch(self) -> list[dict]:
        async with make_client(timeout=30.0) as client:
            token = await self._get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            user_ids = await self._get_user_ids(client, headers)
            if not user_ids:
                return []
            return await self._get_user_details(client, headers, user_ids)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.base_url}/oauth2/token",
            data={"client_id": self.client_id, "client_secret": self.client_secret},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def _get_user_ids(
        self, client: httpx.AsyncClient, headers: dict
    ) -> list[str]:
        ids: list[str] = []
        offset = 0
        limit = 500
        while True:
            resp = await client.get(
                f"{self.base_url}/user-management/queries/users/v1",
                headers=headers,
                params={"offset": offset, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            page_ids = data.get("resources") or []
            ids.extend(page_ids)
            meta = data.get("meta") or {}
            pagination = meta.get("pagination") or {}
            total = pagination.get("total", 0)
            offset += len(page_ids)
            if not page_ids or offset >= total:
                break
        return ids

    async def _get_user_details(
        self, client: httpx.AsyncClient, headers: dict, user_ids: list[str]
    ) -> list[dict]:
        rows: list[dict] = []
        batch_size = 100
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i : i + batch_size]
            resp = await client.post(
                f"{self.base_url}/user-management/entities/users/GET/v1",
                headers=headers,
                json={"ids": batch},
            )
            resp.raise_for_status()
            resources = resp.json().get("resources") or []
            for u in resources:
                rows.append({
                    "work_email": (u.get("uid") or "").lower(),
                    "status": "active",
                    "user_role": u.get("roles", [None])[0] if u.get("roles") else None,
                    "last_login_date": u.get("last_login_at"),
                })
        logger.info(
            "CrowdStrike[%s]: collected %d users", self.env_name, len(rows)
        )
        return rows
