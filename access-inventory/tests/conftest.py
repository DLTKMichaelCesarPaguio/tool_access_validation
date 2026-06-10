from __future__ import annotations

import os

import pytest

# Ensure all required env vars are populated before any module imports config.py
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("LDAP_HOST", "ads.deltek.com")
os.environ.setdefault("LDAP_BIND_DN", "CN=svc,DC=ads,DC=deltek,DC=com")
os.environ.setdefault("LDAP_BIND_PASSWORD", "test-password")
os.environ.setdefault("LDAP_BASE_DN", "OU=accounts,DC=ads,DC=deltek,DC=com")
