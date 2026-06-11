from __future__ import annotations

import logging
from base64 import b64encode

import defusedxml.ElementTree as ET
import httpx

from collector.collectors.base import BaseCollector, make_client

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

        async with make_client(timeout=60.0) as client:
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
            contact = user_el.find("CONTACT_INFO")
            email = self._text(contact, "EMAIL") if contact is not None else None
            if not email:
                continue

            raw_status = (self._text(user_el, "USER_STATUS") or "").strip()
            if raw_status == "Active":
                status = "active"
            elif raw_status == "Inactive":
                status = "inactive"
            else:
                status = "pending"

            rows.append({
                "work_email": email.lower(),
                "status": status,
                "user_role": self._text(user_el, "USER_ROLE"),
                "last_login_date": self._text(user_el, "LAST_LOGIN_DATE"),
                "first_name": self._text(contact, "FIRSTNAME"),
                "last_name": self._text(contact, "LASTNAME"),
                "username": self._text(user_el, "USER_LOGIN"),
                "external_user_id": self._text(user_el, "EXTERNAL_ID"),
                "granted_date": self._text(user_el, "CREATION_DATE"),
            })

        logger.info("Qualys[%s]: collected %d logins", self.env_name, len(rows))
        return rows

    @staticmethod
    def _text(el: ET.Element, tag: str) -> str | None:
        child = el.find(tag)
        if child is None or not child.text:
            return None
        return child.text.strip() or None
