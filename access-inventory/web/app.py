from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg_pool import AsyncConnectionPool

from collector import config
from web import ldap_client, queries

# Input validation: same character set as ldap_client._SAFE_INPUT_RE (includes space)
_SAFE_QUERY_RE = re.compile(r"^[a-zA-Z0-9._@\- ]+$")

_pool: AsyncConnectionPool | None = None
_templates = Jinja2Templates(directory="web/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=config.DATABASE_URL,
        min_size=1,
        max_size=10,
        open=False,
    )
    await _pool.open()
    yield
    await _pool.close()


app = FastAPI(title="Access Inventory", lifespan=lifespan)


def _get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — lifespan not entered.")
    return _pool


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _templates.TemplateResponse(
        request,
        "index.html",
        {"query": "", "ad_profile": None, "tool_access": [], "picker_users": [], "error": None},
    )


@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    email: Annotated[str, Form()],
):
    query = email.strip()
    if not query:
        return _templates.TemplateResponse(
            request,
            "index.html",
            {
                "query": query,
                "ad_profile": None,
                "tool_access": [],
                "picker_users": [],
                "error": "Please enter a name, email, or username.",
            },
        )

    if not _SAFE_QUERY_RE.match(query):
        return _templates.TemplateResponse(
            request,
            "index.html",
            {
                "query": query,
                "ad_profile": None,
                "tool_access": [],
                "picker_users": [],
                "error": "Invalid search input: only letters, digits, spaces, '.', '_', '@', '-' are allowed.",
            },
        )

    pool = _get_pool()
    ad_profile: dict | None = None
    tool_access: list[dict] = []
    picker_users: list[dict] = []
    error: str | None = None
    resolved_email: str | None = None

    is_email = "@" in query
    is_fullname = not is_email and " " in query

    if is_email:
        # ── Email search (existing behaviour) ──────────────────────────────────
        resolved_email = query
        try:
            async with pool.connection() as conn:
                db_profile_task = asyncio.create_task(queries.get_ad_profile(conn, query))
                db_access_task = asyncio.create_task(queries.get_tool_access(conn, query))
                ad_profile, tool_access = await asyncio.gather(db_profile_task, db_access_task)
        except Exception as exc:
            error = f"Database error: {exc}"

        if ad_profile is None and not tool_access:
            try:
                ldap_results = await asyncio.to_thread(
                    ldap_client.search_by_email,
                    host=config.LDAP_HOST,
                    port=config.LDAP_PORT,
                    use_ssl=config.LDAP_USE_SSL,
                    bind_dn=config.LDAP_BIND_DN,
                    bind_password=config.LDAP_BIND_PASSWORD,
                    base_dn=config.LDAP_BASE_DN,
                    email=query,
                    ca_cert=config.LDAP_CA_CERT,
                )
                if ldap_results:
                    ad_profile = ldap_results[0]
            except ValueError as exc:
                error = f"Invalid search input: {exc}"
            except Exception as exc:
                error = f"LDAP search error: {exc}"

    elif is_fullname:
        # ── Full-name search ("first last") ────────────────────────────────────
        parts = query.split(None, 1)
        first, last = parts[0], parts[1]
        try:
            async with pool.connection() as conn:
                candidates = await queries.search_users_by_name(
                    conn, query, first=first, last=last
                )
        except Exception as exc:
            error = f"Database error: {exc}"
            candidates = []

        if len(candidates) == 1:
            resolved_email = candidates[0]["email"]
        elif len(candidates) > 1:
            picker_users = candidates
        else:
            # Nothing in DB — try LDAP
            try:
                ldap_results = await asyncio.to_thread(
                    ldap_client.search_by_name,
                    host=config.LDAP_HOST,
                    port=config.LDAP_PORT,
                    use_ssl=config.LDAP_USE_SSL,
                    bind_dn=config.LDAP_BIND_DN,
                    bind_password=config.LDAP_BIND_PASSWORD,
                    base_dn=config.LDAP_BASE_DN,
                    first_name=first,
                    last_name=last,
                    ca_cert=config.LDAP_CA_CERT,
                )
                if len(ldap_results) == 1:
                    resolved_email = ldap_results[0].get("email")
                elif len(ldap_results) > 1:
                    picker_users = ldap_results
            except ValueError as exc:
                error = f"Invalid search input: {exc}"
            except Exception as exc:
                error = f"LDAP search error: {exc}"

    else:
        # ── Single-token: try username first, then single-name fragment ────────
        try:
            async with pool.connection() as conn:
                by_username = await queries.search_users_by_username(conn, query)
                by_name = await queries.search_users_by_name(conn, query)
        except Exception as exc:
            error = f"Database error: {exc}"
            by_username = []
            by_name = []

        # Merge: username matches first, then name matches (deduplicate by email)
        seen: set[str] = set()
        candidates = []
        for u in by_username + by_name:
            key = (u.get("email") or "").lower()
            if key and key not in seen:
                seen.add(key)
                candidates.append(u)

        if len(candidates) == 1:
            resolved_email = candidates[0]["email"]
        elif len(candidates) > 1:
            picker_users = candidates

    # ── If we have a resolved email, load the full profile ─────────────────────
    if resolved_email and not picker_users and error is None:
        try:
            async with pool.connection() as conn:
                db_profile_task = asyncio.create_task(
                    queries.get_ad_profile(conn, resolved_email)
                )
                db_access_task = asyncio.create_task(
                    queries.get_tool_access(conn, resolved_email)
                )
                ad_profile, tool_access = await asyncio.gather(
                    db_profile_task, db_access_task
                )
        except Exception as exc:
            error = f"Database error: {exc}"

    return _templates.TemplateResponse(
        request,
        "index.html",
        {
            "query": query,
            "ad_profile": ad_profile,
            "tool_access": tool_access,
            "picker_users": picker_users,
            "error": error,
        },
    )
