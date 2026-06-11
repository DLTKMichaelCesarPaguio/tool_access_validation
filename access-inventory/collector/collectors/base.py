from __future__ import annotations

import os
import ssl
from abc import ABC, abstractmethod

import httpx

# Deltek Prisma/Zscaler proxy CA chain — used for all outbound HTTPS
_PROXY_CA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deltek_proxy_ca.pem")


def make_client(**kwargs) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient trusting both the system CA store and the Deltek proxy CA."""
    if os.path.exists(_PROXY_CA):
        # Load system CAs first, then add the Deltek Prisma/Zscaler bundle on top.
        # This lets public-cert sites (CrowdStrike) and Zscaler-intercepted sites
        # (Qualys) both verify correctly.
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.load_verify_locations(cafile=_PROXY_CA)
        verify: ssl.SSLContext | bool = ssl_ctx
    else:
        verify = True
    return httpx.AsyncClient(verify=verify, **kwargs)


class BaseCollector(ABC):
    """Abstract base for all vendor user collectors.

    Each subclass implements `collect()` and returns a flat list of normalised
    user dicts with at minimum:
      - work_email: str
      - status: str  (lowercase 'active' or 'inactive')
      - user_role: str | None
      - last_login_date: str | None
    """

    @abstractmethod
    async def collect(self) -> list[dict]:
        """Fetch users from the vendor API and return normalised rows."""
