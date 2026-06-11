from __future__ import annotations

import asyncio
import logging
from typing import Any

import psycopg
from dotenv import load_dotenv

from collector import config
from collector.database import (
    soft_delete_absent,
    update_last_sync,
    upsert_tool_access,
    upsert_users,
)
from collector.collectors.ad_usr import AdCollector
from collector.collectors.blackduck_usr import BlackDuckCollector
from collector.collectors.burpsuite_usr import BurpSuiteCollector
from collector.collectors.checkmarx_usr import CheckmarxCollector
from collector.collectors.crowdstrike_usr import CrowdStrikeCollector
from collector.collectors.qualys_usr import QualysCollector
from collector.collectors.sophos_usr import SophosCollector

load_dotenv()

logger = logging.getLogger(__name__)


def _build_collectors() -> list[Any]:
    """Instantiate collectors for each configured environment.

    A collector is skipped when its required credentials are missing (tool_id == 0
    or blank credentials), so a partial .env still works without errors.
    """
    collectors: list[Any] = []

    # CrowdStrike — up to 3 environments
    cs_envs = [
        (
            config.CROWDSTRIKE_COMMERCIAL_TOOL_NAME,
            config.CROWDSTRIKE_COMMERCIAL_CLIENT_ID,
            config.CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET,
            config.CROWDSTRIKE_COMMERCIAL_BASE_URL,
        ),
        (
            config.CROWDSTRIKE_GCE_TOOL_NAME,
            config.CROWDSTRIKE_GCE_CLIENT_ID,
            config.CROWDSTRIKE_GCE_CLIENT_SECRET,
            config.CROWDSTRIKE_GCE_BASE_URL,
        ),
        (
            config.CROWDSTRIKE_GCCM_TOOL_NAME,
            config.CROWDSTRIKE_GCCM_CLIENT_ID,
            config.CROWDSTRIKE_GCCM_CLIENT_SECRET,
            config.CROWDSTRIKE_GCCM_BASE_URL,
        ),
    ]
    for tool_name, client_id, client_secret, base_url in cs_envs:
        if client_id and client_secret:
            collectors.append(CrowdStrikeCollector(
                env_name=tool_name,
                client_id=client_id,
                client_secret=client_secret,
                base_url=base_url,
                tool_id=tool_name,
            ))

    # Qualys — up to 4 environments
    q_envs = [
        (
            config.QUALYS_COMMERCIAL_PROD_TOOL_NAME,
            config.QUALYS_COMMERCIAL_PROD_USERNAME,
            config.QUALYS_COMMERCIAL_PROD_PASSWORD,
            config.QUALYS_COMMERCIAL_PROD_BASE_URL,
        ),
        (
            config.QUALYS_COMMERCIAL_DEV_TOOL_NAME,
            config.QUALYS_COMMERCIAL_DEV_USERNAME,
            config.QUALYS_COMMERCIAL_DEV_PASSWORD,
            config.QUALYS_COMMERCIAL_DEV_BASE_URL,
        ),
        (
            config.QUALYS_GCE_TOOL_NAME,
            config.QUALYS_GCE_USERNAME,
            config.QUALYS_GCE_PASSWORD,
            config.QUALYS_GCE_BASE_URL,
        ),
        (
            config.QUALYS_GCCM_TOOL_NAME,
            config.QUALYS_GCCM_USERNAME,
            config.QUALYS_GCCM_PASSWORD,
            config.QUALYS_GCCM_BASE_URL,
        ),
    ]
    for tool_name, username, password, base_url in q_envs:
        if username and password:
            collectors.append(QualysCollector(
                env_name=tool_name,
                username=username,
                password=password,
                base_url=base_url,
                tool_id=tool_name,
            ))

    # Sophos
    if config.SOPHOS_CLIENT_ID and config.SOPHOS_CLIENT_SECRET:
        collectors.append(SophosCollector(
            client_id=config.SOPHOS_CLIENT_ID,
            client_secret=config.SOPHOS_CLIENT_SECRET,
            tool_id=config.SOPHOS_TOOL_NAME,
        ))

    # Burp Suite
    if config.BURP_SUITE_API_KEY:
        collectors.append(BurpSuiteCollector(
            api_key=config.BURP_SUITE_API_KEY,
            base_url=config.BURP_SUITE_BASE_URL,
            tool_id=config.BURP_SUITE_TOOL_NAME,
        ))

    # BlackDuck
    if config.BLACKDUCK_API_TOKEN:
        collectors.append(BlackDuckCollector(
            api_token=config.BLACKDUCK_API_TOKEN,
            base_url=config.BLACKDUCK_BASE_URL,
            tool_id=config.BLACKDUCK_TOOL_NAME,
        ))

    # Checkmarx
    if (config.CHECKMARX_CLIENT_ID and config.CHECKMARX_CLIENT_SECRET
            and config.CHECKMARX_TENANT):
        collectors.append(CheckmarxCollector(
            client_id=config.CHECKMARX_CLIENT_ID,
            client_secret=config.CHECKMARX_CLIENT_SECRET,
            iam_base_url=config.CHECKMARX_BASE_URL,
            api_base_url=config.CHECKMARX_API_BASE_URL,
            tenant=config.CHECKMARX_TENANT,
            tool_id=config.CHECKMARX_TOOL_NAME,
        ))

    return collectors


async def _resolve_tool_uuid(conn: psycopg.AsyncConnection, tool_name: str) -> str | None:
    """Look up the UUID for a tool by its name in the tools table."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT tool_id FROM tools WHERE tool_name = %s LIMIT 1", (tool_name,)
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return str(row[0])


async def _run_vendor_collector(collector: Any, conn: psycopg.AsyncConnection) -> None:
    tool_name: str = collector.tool_id  # tool_id holds tool_name string until resolved
    collector_class: str = type(collector).__name__
    try:
        tool_uuid = await _resolve_tool_uuid(conn, tool_name)
        if tool_uuid is None:
            logger.warning("%s: tool_name=%r not found in tools table, skipping", collector_class, tool_name)
            return
        rows = await collector.collect()
        if rows:
            await upsert_tool_access(conn, tool_uuid, rows)
            present_logins = [
                (r["work_email"], r.get("username"))
                for r in rows if r.get("work_email")
            ]
            await soft_delete_absent(conn, tool_uuid, present_logins)
        await update_last_sync(conn, tool_uuid)
        logger.info("%s (%s): synced %d records", collector_class, tool_name, len(rows) if rows else 0)
    except Exception as exc:
        logger.error("%s: unhandled error during sync: %s", collector_class, exc)


async def _run_ad_collector(conn: psycopg.AsyncConnection) -> None:
    try:
        ad = AdCollector(
            host=config.LDAP_HOST,
            port=config.LDAP_PORT,
            use_ssl=config.LDAP_USE_SSL,
            bind_dn=config.LDAP_BIND_DN,
            bind_password=config.LDAP_BIND_PASSWORD,
            base_dn=config.LDAP_BASE_DN,
            ca_cert=config.LDAP_CA_CERT,
        )
        rows = await asyncio.to_thread(ad.fetch)
        await upsert_users(conn, rows)
        logger.info("AdCollector: synced %d users from AD", len(rows))
    except Exception as exc:
        logger.error("AdCollector: unhandled error during sync: %s", exc)


async def run_collection() -> None:
    """Full collection cycle: AD first, then vendor tools in parallel."""
    dsn = config.DATABASE_URL
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        async with conn.transaction():
            await _run_ad_collector(conn)

            collectors = _build_collectors()
            if collectors:
                tasks = [_run_vendor_collector(c, conn) for c in collectors]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            "Collector %s raised: %s",
                            type(collectors[i]).__name__,
                            result,
                        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_collection())


if __name__ == "__main__":
    main()
