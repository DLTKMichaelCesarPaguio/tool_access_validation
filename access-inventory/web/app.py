from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from psycopg_pool import AsyncConnectionPool

from collector import config
from web import ldap_client, queries

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
        {"query": "", "ad_profile": None, "tool_access": [], "error": None},
    )


@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    email: Annotated[str, Form()],
):
    email = email.strip()
    if not email:
        return _templates.TemplateResponse(
            request,
            "index.html",
            {"query": email, "ad_profile": None,
             "tool_access": [], "error": "Please enter an email address."},
        )

    pool = _get_pool()
    ad_profile: dict | None = None
    tool_access: list[dict] = []
    error: str | None = None

    try:
        # DB lookup and LDAP search run concurrently
        async with pool.connection() as conn:
            db_profile_task = asyncio.create_task(queries.get_ad_profile(conn, email))
            db_access_task = asyncio.create_task(queries.get_tool_access(conn, email))
            ad_profile, tool_access = await asyncio.gather(db_profile_task, db_access_task)
    except Exception as exc:
        error = f"Database error: {exc}"

    if ad_profile is None and not tool_access:
        # Fall back to live LDAP search for users not yet in the collector DB
        try:
            ldap_results = await asyncio.to_thread(
                ldap_client.search_by_email,
                host=config.LDAP_HOST,
                port=config.LDAP_PORT,
                use_ssl=config.LDAP_USE_SSL,
                bind_dn=config.LDAP_BIND_DN,
                bind_password=config.LDAP_BIND_PASSWORD,
                base_dn=config.LDAP_BASE_DN,
                email=email,
            )
            if ldap_results:
                ad_profile = ldap_results[0]
        except ValueError as exc:
            error = f"Invalid search input: {exc}"
        except Exception as exc:
            error = f"LDAP search error: {exc}"

    return _templates.TemplateResponse(
        request,
        "index.html",
        {
            "query": email,
            "ad_profile": ad_profile,
            "tool_access": tool_access,
            "error": error,
        },
    )
