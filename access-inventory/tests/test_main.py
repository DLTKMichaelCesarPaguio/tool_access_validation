from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.main import _build_collectors, _run_ad_collector, _run_vendor_collector, run_collection


# ── _build_collectors ──────────────────────────────────────────────────────────


def test_build_collectors_empty_when_no_credentials(monkeypatch):
    """No collectors are built when all credential env vars are absent."""
    credential_vars = [
        "CROWDSTRIKE_COMMERCIAL_CLIENT_ID", "CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET",
        "CROWDSTRIKE_GCE_CLIENT_ID", "CROWDSTRIKE_GCE_CLIENT_SECRET",
        "CROWDSTRIKE_GCCM_CLIENT_ID", "CROWDSTRIKE_GCCM_CLIENT_SECRET",
        "QUALYS_COMMERCIAL_PROD_USERNAME", "QUALYS_COMMERCIAL_DEV_USERNAME",
        "QUALYS_GCE_USERNAME", "QUALYS_GCCM_USERNAME",
        "SOPHOS_CLIENT_ID", "BURP_SUITE_API_KEY",
        "BLACKDUCK_API_TOKEN", "CHECKMARX_CLIENT_ID",
    ]
    for var in credential_vars:
        monkeypatch.setenv(var, "")

    import collector.config as cfg
    # Patch config attributes directly so module-level cache doesn't matter
    for attr in [
        "CROWDSTRIKE_COMMERCIAL_CLIENT_ID", "CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET",
        "CROWDSTRIKE_COMMERCIAL_TOOL_ID",
        "CROWDSTRIKE_GCE_CLIENT_ID", "CROWDSTRIKE_GCE_CLIENT_SECRET", "CROWDSTRIKE_GCE_TOOL_ID",
        "CROWDSTRIKE_GCCM_CLIENT_ID", "CROWDSTRIKE_GCCM_CLIENT_SECRET", "CROWDSTRIKE_GCCM_TOOL_ID",
        "QUALYS_COMMERCIAL_PROD_USERNAME", "QUALYS_COMMERCIAL_PROD_PASSWORD", "QUALYS_COMMERCIAL_PROD_TOOL_ID",
        "QUALYS_COMMERCIAL_DEV_USERNAME", "QUALYS_COMMERCIAL_DEV_PASSWORD", "QUALYS_COMMERCIAL_DEV_TOOL_ID",
        "QUALYS_GCE_USERNAME", "QUALYS_GCE_PASSWORD", "QUALYS_GCE_TOOL_ID",
        "QUALYS_GCCM_USERNAME", "QUALYS_GCCM_PASSWORD", "QUALYS_GCCM_TOOL_ID",
        "SOPHOS_CLIENT_ID", "SOPHOS_CLIENT_SECRET", "SOPHOS_TOOL_ID",
        "BURP_SUITE_API_KEY", "BURP_SUITE_TOOL_ID",
        "BLACKDUCK_API_TOKEN", "BLACKDUCK_TOOL_ID",
        "CHECKMARX_CLIENT_ID", "CHECKMARX_CLIENT_SECRET", "CHECKMARX_TOOL_ID",
    ]:
        monkeypatch.setattr(cfg, attr, "" if isinstance(getattr(cfg, attr), str) else 0)

    collectors = _build_collectors()
    assert collectors == []


def test_build_collectors_includes_crowdstrike_when_configured(monkeypatch):
    import collector.config as cfg
    monkeypatch.setattr(cfg, "CROWDSTRIKE_COMMERCIAL_CLIENT_ID", "cid")
    monkeypatch.setattr(cfg, "CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET", "csec")
    monkeypatch.setattr(cfg, "CROWDSTRIKE_COMMERCIAL_BASE_URL", "https://api.crowdstrike.com")
    monkeypatch.setattr(cfg, "CROWDSTRIKE_COMMERCIAL_TOOL_ID", 1)
    # Clear others
    for attr in [
        "CROWDSTRIKE_GCE_CLIENT_ID", "CROWDSTRIKE_GCE_TOOL_ID",
        "CROWDSTRIKE_GCCM_CLIENT_ID", "CROWDSTRIKE_GCCM_TOOL_ID",
        "QUALYS_COMMERCIAL_PROD_USERNAME", "QUALYS_COMMERCIAL_DEV_USERNAME",
        "QUALYS_GCE_USERNAME", "QUALYS_GCCM_USERNAME",
        "SOPHOS_CLIENT_ID", "BURP_SUITE_API_KEY",
        "BLACKDUCK_API_TOKEN", "CHECKMARX_CLIENT_ID",
    ]:
        val = getattr(cfg, attr)
        monkeypatch.setattr(cfg, attr, "" if isinstance(val, str) else 0)

    from collector.collectors.crowdstrike_usr import CrowdStrikeCollector
    collectors = _build_collectors()
    assert len(collectors) == 1
    assert isinstance(collectors[0], CrowdStrikeCollector)
    assert collectors[0].tool_id == 1


# ── _run_vendor_collector ──────────────────────────────────────────────────────


async def test_run_vendor_collector_happy_path():
    mock_collector = MagicMock()
    mock_collector.tool_id = 5
    mock_collector.collect = AsyncMock(return_value=[
        {"work_email": "a@d.com", "status": "active"},
    ])
    mock_conn = MagicMock()

    with (
        patch("collector.main.upsert_tool_access", new_callable=AsyncMock) as mock_upsert,
        patch("collector.main.soft_delete_absent", new_callable=AsyncMock) as mock_soft,
        patch("collector.main.update_last_sync", new_callable=AsyncMock) as mock_sync,
    ):
        await _run_vendor_collector(mock_collector, mock_conn)
        mock_upsert.assert_awaited_once_with(mock_conn, 5, [{"work_email": "a@d.com", "status": "active"}])
        mock_soft.assert_awaited_once_with(mock_conn, 5, ["a@d.com"])
        mock_sync.assert_awaited_once_with(mock_conn, 5)


async def test_run_vendor_collector_empty_result_skips_upsert():
    mock_collector = MagicMock()
    mock_collector.tool_id = 5
    mock_collector.collect = AsyncMock(return_value=[])
    mock_conn = MagicMock()

    with (
        patch("collector.main.upsert_tool_access", new_callable=AsyncMock) as mock_upsert,
        patch("collector.main.soft_delete_absent", new_callable=AsyncMock) as mock_soft,
        patch("collector.main.update_last_sync", new_callable=AsyncMock) as mock_sync,
    ):
        await _run_vendor_collector(mock_collector, mock_conn)
        mock_upsert.assert_not_awaited()
        mock_soft.assert_not_awaited()
        mock_sync.assert_awaited_once()


async def test_run_vendor_collector_exception_does_not_propagate():
    mock_collector = MagicMock()
    mock_collector.tool_id = 5
    mock_collector.collect = AsyncMock(side_effect=RuntimeError("boom"))
    mock_conn = MagicMock()

    with (
        patch("collector.main.upsert_tool_access", new_callable=AsyncMock),
        patch("collector.main.soft_delete_absent", new_callable=AsyncMock),
        patch("collector.main.update_last_sync", new_callable=AsyncMock),
    ):
        # Should not raise
        await _run_vendor_collector(mock_collector, mock_conn)


# ── run_collection ─────────────────────────────────────────────────────────────


async def test_run_collection_calls_ad_then_vendors():
    """AD collector runs first, then vendors are fanned out in parallel."""
    call_order: list[str] = []

    async def fake_ad(conn):
        call_order.append("ad")

    async def fake_vendor(collector, conn):
        call_order.append(f"vendor:{collector.tool_id}")

    mock_collector = MagicMock()
    mock_collector.tool_id = 1

    with (
        patch("collector.main._run_ad_collector", side_effect=fake_ad),
        patch("collector.main._run_vendor_collector", side_effect=fake_vendor),
        patch("collector.main._build_collectors", return_value=[mock_collector]),
        patch("collector.main.config.DATABASE_URL", "postgresql://fake/db"),
        patch("psycopg.AsyncConnection.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_connect.return_value = mock_conn

        await run_collection()

    assert call_order[0] == "ad", "AD collector must run before vendor collectors"
    assert "vendor:1" in call_order
