from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Required environment variable {name!r} is not set.")
    return val


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = _require("DATABASE_URL")

# ── LDAP / Active Directory ───────────────────────────────────────────────────
LDAP_HOST: str = _require("LDAP_HOST")
LDAP_PORT: int = int(_get("LDAP_PORT", "389"))
LDAP_USE_SSL: bool = _get("LDAP_USE_SSL", "false").lower() == "true"
LDAP_BIND_DN: str = _require("LDAP_BIND_DN")
LDAP_BIND_PASSWORD: str = _require("LDAP_BIND_PASSWORD")
LDAP_BASE_DN: str = _require("LDAP_BASE_DN")
LDAP_SEARCH_ATTRIBUTE: str = _get("LDAP_SEARCH_ATTRIBUTE", "mail")
LDAP_CA_CERT: str = _get("LDAP_CA_CERT", "")

# ── Web App ───────────────────────────────────────────────────────────────────
WEB_PORT: int = int(_get("WEB_PORT", "8001"))

# ── CrowdStrike ───────────────────────────────────────────────────────────────
CROWDSTRIKE_COMMERCIAL_CLIENT_ID: str = _get("CROWDSTRIKE_COMMERCIAL_CLIENT_ID")
CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET: str = _get("CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET")
CROWDSTRIKE_COMMERCIAL_BASE_URL: str = _get(
    "CROWDSTRIKE_COMMERCIAL_BASE_URL", "https://api.crowdstrike.com"
)
CROWDSTRIKE_COMMERCIAL_TOOL_NAME: str = _get("CROWDSTRIKE_COMMERCIAL_TOOL_NAME", "CrowdStrike Commercial")

CROWDSTRIKE_GCE_CLIENT_ID: str = _get("CROWDSTRIKE_GCE_CLIENT_ID")
CROWDSTRIKE_GCE_CLIENT_SECRET: str = _get("CROWDSTRIKE_GCE_CLIENT_SECRET")
CROWDSTRIKE_GCE_BASE_URL: str = _get(
    "CROWDSTRIKE_GCE_BASE_URL", "https://api.laggar.gcw.crowdstrike.com"
)
CROWDSTRIKE_GCE_TOOL_NAME: str = _get("CROWDSTRIKE_GCE_TOOL_NAME", "CrowdStrike GCE")

CROWDSTRIKE_GCCM_CLIENT_ID: str = _get("CROWDSTRIKE_GCCM_CLIENT_ID")
CROWDSTRIKE_GCCM_CLIENT_SECRET: str = _get("CROWDSTRIKE_GCCM_CLIENT_SECRET")
CROWDSTRIKE_GCCM_BASE_URL: str = _get(
    "CROWDSTRIKE_GCCM_BASE_URL", "https://api.crowdstrike.com"
)
CROWDSTRIKE_GCCM_TOOL_NAME: str = _get("CROWDSTRIKE_GCCM_TOOL_NAME", "CrowdStrike GCCM")

# ── Qualys ────────────────────────────────────────────────────────────────────
QUALYS_COMMERCIAL_PROD_USERNAME: str = _get("QUALYS_COMMERCIAL_PROD_USERNAME")
QUALYS_COMMERCIAL_PROD_PASSWORD: str = _get("QUALYS_COMMERCIAL_PROD_PASSWORD")
QUALYS_COMMERCIAL_PROD_BASE_URL: str = _get(
    "QUALYS_COMMERCIAL_PROD_BASE_URL", "https://qualysapi.qualys.com"
)
QUALYS_COMMERCIAL_PROD_TOOL_NAME: str = _get("QUALYS_COMMERCIAL_PROD_TOOL_NAME", "Qualys Commercial Prod")

QUALYS_COMMERCIAL_DEV_USERNAME: str = _get("QUALYS_COMMERCIAL_DEV_USERNAME")
QUALYS_COMMERCIAL_DEV_PASSWORD: str = _get("QUALYS_COMMERCIAL_DEV_PASSWORD")
QUALYS_COMMERCIAL_DEV_BASE_URL: str = _get(
    "QUALYS_COMMERCIAL_DEV_BASE_URL", "https://qualysapi.qualys.com"
)
QUALYS_COMMERCIAL_DEV_TOOL_NAME: str = _get("QUALYS_COMMERCIAL_DEV_TOOL_NAME", "Qualys Commercial Dev/Test")

QUALYS_GCE_USERNAME: str = _get("QUALYS_GCE_USERNAME")
QUALYS_GCE_PASSWORD: str = _get("QUALYS_GCE_PASSWORD")
QUALYS_GCE_BASE_URL: str = _get(
    "QUALYS_GCE_BASE_URL", "https://qualysapi.qg3.apps.qualys.com"
)
QUALYS_GCE_TOOL_NAME: str = _get("QUALYS_GCE_TOOL_NAME", "Qualys GCE")

QUALYS_GCCM_USERNAME: str = _get("QUALYS_GCCM_USERNAME")
QUALYS_GCCM_PASSWORD: str = _get("QUALYS_GCCM_PASSWORD")
QUALYS_GCCM_BASE_URL: str = _get(
    "QUALYS_GCCM_BASE_URL", "https://qualysapi.qg4.apps.qualys.com"
)
QUALYS_GCCM_TOOL_NAME: str = _get("QUALYS_GCCM_TOOL_NAME", "Qualys GCCM")

# ── Sophos ────────────────────────────────────────────────────────────────────
SOPHOS_CLIENT_ID: str = _get("SOPHOS_CLIENT_ID")
SOPHOS_CLIENT_SECRET: str = _get("SOPHOS_CLIENT_SECRET")
SOPHOS_TOOL_NAME: str = _get("SOPHOS_TOOL_NAME", "Sophos Central")

# ── Burp Suite Enterprise ─────────────────────────────────────────────────────
BURP_SUITE_API_KEY: str = _get("BURP_SUITE_API_KEY")
BURP_SUITE_BASE_URL: str = _get("BURP_SUITE_BASE_URL", "https://burp.example.com")
BURP_SUITE_TOOL_NAME: str = _get("BURP_SUITE_TOOL_NAME", "Burp Suite Enterprise")

# ── BlackDuck ─────────────────────────────────────────────────────────────────
BLACKDUCK_API_TOKEN: str = _get("BLACKDUCK_API_TOKEN")
BLACKDUCK_BASE_URL: str = _get("BLACKDUCK_BASE_URL", "https://blackduck.example.com")
BLACKDUCK_TOOL_NAME: str = _get("BLACKDUCK_TOOL_NAME", "Blackduck")

# ── Checkmarx Enterprise (CxSAST) ─────────────────────────────────────────────
CHECKMARX_BASE_URL: str = _get("CHECKMARX_BASE_URL", "https://checkmarx.example.com")
CHECKMARX_USERNAME: str = _get("CHECKMARX_USERNAME")
CHECKMARX_PASSWORD: str = _get("CHECKMARX_PASSWORD")
CHECKMARX_TOOL_NAME: str = _get("CHECKMARX_TOOL_NAME", "Checkmarx")
