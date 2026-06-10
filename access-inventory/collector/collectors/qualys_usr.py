from __future__ import annotations

import logging
from base64 import b64encode

import defusedxml.ElementTree as ET
import httpx

from collector.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class QualysCollector(BaseCollector):
    """Collects user accounts from one Qualys environment via basic auth.

    Uses defusedxml to parse XML responses — stdlib xml.etree is vulnerable
    to XXE and billion-laughs attacks.
    """

    def __init__(
        self,
        env_name: str,
        username: str,
        password: str,
        base_url: str,
        tool_id: int,
    ) -> None:
        self.env_name = env_name
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.tool_id = tool_id

    async def collect(self) -> list[dict]:
        try:
            return await self._fetch()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error(
                "Qualys[%s]: collection failed: %s", self.env_name, exc
            )
            return []
        except ET.ParseError as exc:
            logger.error(
                "Qualys[%s]: XML parse error: %s", self.env_name, exc
            )
            return []
        except Exception as exc:
            logger.error(
                "Qualys[%s]: unexpected error: %s", self.env_name, exc
            )
            return []

    async def _fetch(self) -> list[dict]:
        creds = b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {creds}",
            "X-Requested-With": "AccessInventoryCollector",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/msp/user_list.php",
                headers=headers,
            )
            resp.raise_for_status()
            return self._parse_xml(resp.text)

    def _parse_xml(self, xml_text: str) -> list[dict]:
        root = ET.fromstring(xml_text)
        rows: list[dict] = []

        for user_el in root.iter("USER"):
            email = self._text(user_el, "EMAIL")
            if not email:
                continue
            rows.append({
                "work_email": email.lower(),
                "status": "active",
                "user_role": self._text(user_el, "USER_ROLE"),
                "last_login_date": self._text(user_el, "LAST_LOGIN_DATE"),
            })

        logger.info("Qualys[%s]: collected %d users", self.env_name, len(rows))
        return rows

    @staticmethod
    def _text(el: ET.Element, tag: str) -> str | None:
        child = el.find(tag)
        if child is None or not child.text:
            return None
        return child.text.strip() or None
