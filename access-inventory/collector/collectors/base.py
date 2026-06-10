from __future__ import annotations

from abc import ABC, abstractmethod


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
