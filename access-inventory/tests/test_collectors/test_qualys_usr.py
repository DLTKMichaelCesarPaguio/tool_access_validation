from __future__ import annotations

import pytest
import respx
from httpx import Response

from collector.collectors.qualys_usr import QualysCollector


def _collector(**kwargs) -> QualysCollector:
    defaults = dict(
        env_name="Commercial Prod",
        username="quser",
        password="qpass",
        base_url="https://qualysapi.qualys.com",
        tool_id=4,
    )
    defaults.update(kwargs)
    return QualysCollector(**defaults)


_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<USER_LIST_OUTPUT>
  <USER_LIST>
    <USER>
      <USER_LOGIN>jdoe</USER_LOGIN>
      <USER_ROLE>Manager</USER_ROLE>
      <USER_STATUS>Active</USER_STATUS>
      <LAST_LOGIN_DATE>2026-01-15</LAST_LOGIN_DATE>
      <CONTACT_INFO>
        <FIRSTNAME>John</FIRSTNAME>
        <LASTNAME>Doe</LASTNAME>
        <EMAIL>john.doe@deltek.com</EMAIL>
      </CONTACT_INFO>
    </USER>
    <USER>
      <USER_LOGIN>asmith</USER_LOGIN>
      <USER_ROLE>Reader</USER_ROLE>
      <USER_STATUS>Inactive</USER_STATUS>
      <LAST_LOGIN_DATE/>
      <CONTACT_INFO>
        <FIRSTNAME>Alice</FIRSTNAME>
        <LASTNAME>Smith</LASTNAME>
        <EMAIL>alice.smith@deltek.com</EMAIL>
      </CONTACT_INFO>
    </USER>
  </USER_LIST>
</USER_LIST_OUTPUT>"""


@respx.mock
async def test_happy_path_parses_xml_users():
    respx.post("https://qualysapi.qualys.com/msp/user_list.php").mock(
        return_value=Response(200, text=_XML_RESPONSE)
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    assert rows[0]["work_email"] == "john.doe@deltek.com"
    assert rows[0]["status"] == "active"
    assert rows[0]["user_role"] == "Manager"
    assert rows[0]["last_login_date"] == "2026-01-15"
    assert rows[0]["username"] == "jdoe"
    assert rows[1]["work_email"] == "alice.smith@deltek.com"
    assert rows[1]["status"] == "inactive"
    assert rows[1]["username"] == "asmith"


@respx.mock
async def test_missing_fields_default_gracefully():
    xml = """<?xml version="1.0"?>
    <USER_LIST_OUTPUT><USER_LIST>
      <USER><LOGIN>noemail</LOGIN></USER>
    </USER_LIST></USER_LIST_OUTPUT>"""
    respx.post("https://qualysapi.qualys.com/msp/user_list.php").mock(
        return_value=Response(200, text=xml)
    )
    rows = await _collector().collect()
    # No email field → row skipped
    assert rows == []


@respx.mock
async def test_defusedxml_used_not_stdlib(monkeypatch):
    """Ensure defusedxml.ElementTree is used, not stdlib xml.etree."""
    import collector.collectors.qualys_usr as mod
    assert "defusedxml" in mod.__dict__ or hasattr(mod, "ET"), \
        "Module should import defusedxml.ElementTree as ET"
    # Verify the import source is defusedxml, not stdlib xml.etree
    import defusedxml.ElementTree as defused_ET
    assert mod.ET is defused_ET, "ET in qualys_usr must be defusedxml.ElementTree"


@respx.mock
async def test_http_error_returns_empty_list():
    respx.post("https://qualysapi.qualys.com/msp/user_list.php").mock(
        return_value=Response(403, text="Forbidden")
    )
    rows = await _collector().collect()
    assert rows == []


@respx.mock
async def test_invalid_xml_returns_empty_list():
    respx.post("https://qualysapi.qualys.com/msp/user_list.php").mock(
        return_value=Response(200, text="<not valid xml <<")
    )
    rows = await _collector().collect()
    assert rows == []


@respx.mock
async def test_multiple_logins_same_email_both_returned():
    """Each login for the same email becomes its own row with its own status."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<USER_LIST_OUTPUT><USER_LIST>
  <USER>
    <USER_LOGIN>user1a</USER_LOGIN>
    <USER_STATUS>Active</USER_STATUS>
    <USER_ROLE>Manager</USER_ROLE>
    <CONTACT_INFO><EMAIL>dup@deltek.com</EMAIL></CONTACT_INFO>
  </USER>
  <USER>
    <USER_LOGIN>user1b</USER_LOGIN>
    <USER_STATUS>Pending Activation</USER_STATUS>
    <USER_ROLE>Manager</USER_ROLE>
    <CONTACT_INFO><EMAIL>dup@deltek.com</EMAIL></CONTACT_INFO>
  </USER>
</USER_LIST></USER_LIST_OUTPUT>"""
    respx.post("https://qualysapi.qualys.com/msp/user_list.php").mock(
        return_value=Response(200, text=xml)
    )
    rows = await _collector().collect()
    assert len(rows) == 2
    by_login = {r["username"]: r for r in rows}
    assert by_login["user1a"]["status"] == "active"
    assert by_login["user1b"]["status"] == "pending"
    assert by_login["user1a"]["work_email"] == "dup@deltek.com"
    assert by_login["user1b"]["work_email"] == "dup@deltek.com"
