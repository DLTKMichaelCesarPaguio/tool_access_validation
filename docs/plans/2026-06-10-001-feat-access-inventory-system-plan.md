---
title: "feat: Build Access Inventory System — Collector, Validator, and Web App"
type: feat
status: active
date: 2026-06-10
origin: tool_access_validation/access_inventory_spec.md
---

# feat: Build Access Inventory System — Collector, Validator, and Web App

## Overview

Replace two fragile n8n workflows with a self-contained Python system consisting of three components: an async collector service that pulls user records from 11 security tool environments and Active Directory into Postgres, a validator that surfaces orphaned and stale accounts, and a FastAPI web application that provides instant in-browser access lookups. The existing Postgres schema is preserved; one additive migration enables upsert semantics.

---

## Problem Frame

The Deltek Global Information Security team currently manages user access across 11 security tool environments via two n8n workflows. These are email-dependent, fragile, provide no persistent audit view, no change history, and require manual intervention for orphan or stale account detection. This project replaces both workflows (`63WHIl0bD5691vOS` — Tools Access Masterlist; `OqJfVOAA5N2qKP2n` — Application Access Lookup) with a maintainable Python service and FastAPI web app backed by the same Postgres database.

---

## Requirements Trace

- R1. Replace n8n workflow `63WHIl0bD5691vOS` — collect user records from all 11 tool environments into Postgres via non-destructive upserts
- R2. Sync Active Directory users into the `users` table on every collection run
- R3. Run all 11 tool collectors in parallel via `asyncio.gather()`
- R4. Mark accounts removed from a tool as `status = 'inactive'` (soft-delete) — never delete rows
- R5. Use `access_audit_log` DELETE records to determine accurate `deactivation_date`; fall back to `NOW()`
- R6. Replace n8n workflow `OqJfVOAA5N2qKP2n` — provide instant browser-based access lookup replacing email output
- R7. Support search by first name, last name, full name, full email, or partial email (case-insensitive, partial-match)
- R8. Render three output states: user found with tool access; user found with no tool access; user not found in AD
- R9. Apply BlackDuck override at query time: force `status = 'Active Access'`, `last_login = 'N/A'` when `tool_name` contains `'blackduck'`
- R10. Add one migration: `UNIQUE (tool_id, work_email)` constraint on `user_tool_access` to enable upsert
- R11. Retain all 14 existing database tables unchanged; no data migration required
- R12. Validate post-collection: flag orphaned accounts (tool access with no matching `users` record); flag inactive employees with active tool access; write findings to `access_audit_log`
- R13. Use `<vendor>_usr.py` naming convention on all collector files to support future merging with other systems
- R14. Load all credentials from `.env` via `python-dotenv` — never hardcode or commit secrets

---

## Scope Boundaries

- No ORM — raw SQL via psycopg v3 throughout
- No Alembic setup — the schema already exists; only the single `ALTER TABLE ADD CONSTRAINT` migration is needed
- No authentication on the web app — it is an internal tool on `localhost:8001`
- No static HTML file or email output — results rendered live in the browser only
- The "recipient email" field from the n8n form is removed entirely
- All foreign keys pointing at `users.user_id` (`access_audit_log.changed_by`, `user_tool_access.deactivated_by`, `user_assignments`, `user_role_assignments`, `user_team_memberships`) remain unpopulated — future scope only
- `user_data_sources` table remains empty during collection — will be populated by `ad_usr.py` only if explicitly specified; not a hard requirement for v1 (see Deferred to Follow-Up Work)

### Deferred to Follow-Up Work

- `user_data_sources` population by `ad_usr.py`: the table is currently empty; wiring it is a post-v1 enhancement
- Future `_host`, `_vuln`, `_alert` collectors: naming convention is established here but out of scope
- Role-based access control or authentication on the web app: not needed while internal

---

## Context & Research

### Relevant Code and Patterns

- Sibling project: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/backend/utils/inventory_db.py` — production-verified psycopg v3 upsert with `IS DISTINCT FROM`; adapt this for `database.py`
- Sibling project: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/backend/utils/crowdstrike_inventory.py` — CrowdStrike OAuth2 token fetch + multi-console fan-out pattern; logging filter that strips `access_token` from log records
- Sibling project: `requirements.txt` format — `>=x.y,<z.0` pinned ranges, category groupings via inline comments, no pyproject.toml
- LDAP auth spec: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/docs/specs/2026-05-24-auth-ldap-roles-permissions-spec.md` — Deltek AD server, bind DN, Simple bind, two-step bind pattern, LDAP injection prevention (`^[a-zA-Z0-9._@-]+$` filter)
- Qualys API contract: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/docs/solutions/documentation-gaps/qualys-csam-report-download-api-contract-2026-05-14.md` — `Bearer` prefix requirement, 201 success status, JWT 4h TTL (refresh at 3h45m). **Note:** that doc covers the CSAM/gateway host; this project uses the VM/PC endpoints (`qualysapi.qualys.com`, `qualysapi.qg3.apps.qualys.com`, `qualysapi.qg4.apps.qualys.com`) which use basic auth per spec section 9 — apply the `Bearer`/status lessons selectively

### Institutional Learnings

- **CrowdStrike OAuth2 tokens must never be logged or persisted.** Apply a `logging.Filter` that strips `Authorization` headers and any response body containing `access_token`. A leaked Falcon token means full EDR fleet exposure from all three environments (Commercial, GCE, GCCM). (see: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/docs/plans/2026-05-09-001-feat-postgres-asset-store-plan.md`)
- **Async fan-out must propagate errors into the structured result, not only log them.** In `asyncio.gather(return_exceptions=True)`, each exception must be written as a structured failure entry in the results — not swallowed with `logger.warning()`. A silent failure leaves operators with no actionable signal. (see: `aws-tls-retry-and-cloud-timeout-surfacing-2026-05-14.md`)
- **psycopg v3 pool must be initialized lazily inside the app lifespan, not at module import.** In an async FastAPI app use `psycopg_pool.AsyncConnectionPool`; initialize in the FastAPI `@asynccontextmanager` lifespan function. For the short-lived CLI collector process, a simple `psycopg.connect()` per run is appropriate.
- **LDAP injection prevention at the boundary.** Sanitize search input to `^[a-zA-Z0-9._@-]+$` before building any LDAP filter. Reject anything that doesn't match before the query is constructed.
- **`ldap3` is synchronous.** Wrap all LDAP calls in `asyncio.to_thread()` in any async context (web app) to avoid blocking the event loop.
- **Qualys VM/PC endpoints** (`msp/user_list.php`) use basic auth, not JWT. The `Bearer`/201-status lessons from the CSAM doc do not apply here, but the XML response parsing (use `defusedxml.ElementTree`, not stdlib `xml.etree`) and the per-environment credential pattern do.

### External References

- FastAPI docs: lifespan events for connection pool management
- psycopg v3 docs: `AsyncConnectionPool` initialization
- `ldap3` docs: `Connection`, `Server`, `SIMPLE` auth, `SUBTREE` search scope
- httpx docs: `AsyncClient` — prefer over `aiohttp` for consistency with FastAPI ecosystem

---

## Key Technical Decisions

- **No ORM, raw psycopg v3**: Matches sibling project convention; upsert SQL is already specified in the spec and matches the team's production-verified pattern.
- **`requirements.txt` (not pyproject.toml)**: Matches sibling convention; no toolchain change required.
- **Plain `.sql` migration file** (not Alembic): Schema already exists in production; only one `ALTER TABLE ADD CONSTRAINT` is needed. Alembic overhead is unjustified.
- **`asyncio.gather(return_exceptions=True)` in the collector**: Each collector is a coroutine. Exceptions are collected as results, not raised, so one failing collector does not abort all others. Each exception is logged with the collector name and written as a structured failure entry.
- **Soft-delete via `access_audit_log` lookup**: Before marking an account `inactive`, query the audit log for a DELETE record matching `(tool_id, work_email)` and use its `change_timestamp` as `deactivation_date`. Fall back to `NOW()`. This preserves accurate deactivation dates from historical data.
- **BlackDuck override at query time, not storage time**: `status = 'Active Access'` and `last_login = 'N/A'` are applied in `queries.py` during the web lookup, not written to the database. This preserves raw data integrity.
- **`ldap3` synchronous, wrapped in `asyncio.to_thread()`**: The web app is async; LDAP calls must not block the event loop. The collector is CLI-only and can use synchronous LDAP directly.
- **pytest + pytest-asyncio for testing**: New dependency vs. sibling project (`pytest-asyncio` not present there). Required because collector coroutines need `@pytest.mark.asyncio` coverage.
- **`from __future__ import annotations`** at the top of every module: matches sibling convention.
- **`logging.getLogger(__name__)`** module-level loggers everywhere: matches sibling convention.
- **`httpx.AsyncClient` for all tool API calls**: Standard FastAPI-ecosystem async HTTP client; consistent across all collectors.
- **LDAP search for web app accepts name or email**: build LDAP filter dynamically — `(mail=*{term}*)` for email-shaped input, `(|(givenName=*{term}*)(sn=*{term}*)(cn=*{term}*))` for name-shaped input. Input sanitized before filter construction.

---

## Open Questions

### Resolved During Planning

- **Migration safety**: Confirmed by spec — no existing duplicates on `(tool_id, work_email)`. Safe to apply additive constraint.
- **LDAP credentials**: Provided via `.env` (spec section 10). Service account DN pattern mirrors `dcoprodSecldap` from the existing Deltek LDAP spec.
- **BlackDuck override**: Carry over from n8n. Apply at query time, not at storage time.
- **Soft-delete deactivation date**: Use `access_audit_log` DELETE record `change_timestamp`; fall back to `NOW()`.
- **Port**: `localhost:8001` confirmed.
- **Search type**: Case-insensitive partial-match. AD queried first (LDAP `mail`), then Postgres by resolved email.

### Deferred to Implementation

- **Exact LDAP filter construction for multi-word names**: Determine whether `cn` search covers "First Last" adequately or if a compound `(&(givenName=*first*)(sn=*last*))` parse is needed for two-word queries.
- **Pagination handling per collector**: Each API has different pagination shapes (cursor, offset, page token). Exact loop logic is execution-time work.
- **`access_audit_log` schema for validator writes**: Confirm which columns are required/nullable before writing validation findings; read the current table definition at implementation time.
- **`ldap3` connection reuse across multiple LDAP calls in a single web request**: Determine whether to open one connection per request or hold a longer-lived connection. Implementation-time decision based on `ldap3` behavior under load.

---

## Output Structure

```
access-inventory/
├── collector/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── validator.py
│   └── collectors/
│       ├── base.py
│       ├── ad_usr.py
│       ├── crowdstrike_usr.py
│       ├── qualys_usr.py
│       ├── sophos_usr.py
│       ├── burpsuite_usr.py
│       ├── blackduck_usr.py
│       └── checkmarx_usr.py
├── web/
│   ├── app.py
│   ├── ldap_client.py
│   ├── queries.py
│   └── templates/
│       └── index.html
├── migrations/
│   └── 001_add_upsert_constraint.sql
├── tests/
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_validator.py
│   ├── test_queries.py
│   ├── test_ldap_client.py
│   ├── test_collectors/
│   │   ├── test_ad_usr.py
│   │   ├── test_crowdstrike_usr.py
│   │   ├── test_qualys_usr.py
│   │   ├── test_sophos_usr.py
│   │   ├── test_burpsuite_usr.py
│   │   ├── test_blackduck_usr.py
│   │   └── test_checkmarx_usr.py
│   └── test_app.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Collector Fan-Out Flow

```
main.py
  │
  ├─ ad_usr.py ──────────────────────────── upsert → users table
  │
  └─ asyncio.gather(return_exceptions=True)
       ├─ crowdstrike_usr.py (Commercial)
       ├─ crowdstrike_usr.py (GCE)
       ├─ crowdstrike_usr.py (GCCM)
       ├─ qualys_usr.py (Commercial Prod)
       ├─ qualys_usr.py (Commercial Dev/Test)
       ├─ qualys_usr.py (GCE)
       ├─ qualys_usr.py (GCCM)
       ├─ sophos_usr.py
       ├─ burpsuite_usr.py
       ├─ blackduck_usr.py
       └─ checkmarx_usr.py
            │
            each: upsert active rows → user_tool_access
                  soft-delete absent rows (status='inactive')
                  update tools.last_sync_at on success
            │
  └─ collect errors → log as structured failures
  │
  └─ validator.py ──────────────────────── write findings → access_audit_log
```

### Web App Request Flow

```
Browser GET /
  └─ render search form (index.html)

Browser POST /search  ?query=<term>
  └─ ldap_client.py
       ├─ sanitize input
       ├─ asyncio.to_thread(ldap_search)
       └─ returns: user dict or None
  └─ queries.py
       ├─ if user found: SELECT from user_tool_access JOIN tools WHERE work_email = LOWER(result_email)
       ├─ apply BlackDuck override (tool_name ILIKE '%blackduck%')
       └─ returns: list of access rows (may be empty)
  └─ app.py
       ├─ State 1: user found + rows → render profile card + table
       ├─ State 2: user found + no rows → render "no tools" message
       └─ State 3: user not found → render "not found" message
  └─ TemplateResponse(index.html, context)
```

---

## Implementation Units

- [ ] U1. **Project scaffold — directory structure, `requirements.txt`, `config.py`, `.env.example`**

**Goal:** Create the `access-inventory/` root layout, dependency manifest, and configuration module. All subsequent units build on top of this.

**Requirements:** R13, R14

**Dependencies:** None

**Files:**
- Create: `access-inventory/requirements.txt`
- Create: `access-inventory/collector/config.py`
- Create: `access-inventory/.env.example`
- Create: `access-inventory/collector/__init__.py`
- Create: `access-inventory/collector/collectors/__init__.py`
- Create: `access-inventory/web/__init__.py`
- Create: `access-inventory/migrations/001_add_upsert_constraint.sql`

**Approach:**
- `requirements.txt` groups dependencies by category with inline comments: core (fastapi, uvicorn, httpx, psycopg[binary], psycopg_pool, ldap3, python-dotenv, jinja2, defusedxml), dev/test (pytest, pytest-asyncio, pytest-mock, pytest-cov, black, flake8, mypy)
- `config.py` uses `python-dotenv` to load `.env` at import time; exposes typed settings as module-level constants or a `Settings` dataclass — all values read from environment variables only; no defaults for secrets
- `.env.example` is a copy of spec section 10 with all secret values replaced by placeholder strings (e.g., `your-value-here`)
- `migrations/001_add_upsert_constraint.sql` contains exactly the `ALTER TABLE ... ADD CONSTRAINT uq_tool_user UNIQUE (tool_id, work_email)` statement from spec section 6.2

**Test scenarios:**
- Test expectation: none — this unit is scaffolding only; correctness is validated by subsequent units importing `config.py` successfully

**Verification:**
- `pip install -r requirements.txt` completes without errors
- `python -c "from collector.config import DATABASE_URL"` succeeds when `.env` is present
- Migration SQL file is syntactically valid (can be parsed by `psql --dry-run` or reviewed manually)

---

- [ ] U2. **`BaseCollector` abstract class and `database.py` — upsert and soft-delete operations**

**Goal:** Define the shared collector interface and the Postgres write layer used by all collectors. This is the critical data persistence module.

**Requirements:** R1, R4, R5, R10, R11

**Dependencies:** U1

**Files:**
- Create: `access-inventory/collector/collectors/base.py`
- Create: `access-inventory/collector/database.py`
- Test: `access-inventory/tests/test_database.py`

**Approach:**
- `base.py` defines `BaseCollector` as an abstract class with one abstract coroutine: `async def collect() -> list[dict]`. Each concrete collector implements this and returns a list of normalised user records with at minimum: `work_email`, `tool_id`, `status`, `user_role`, `last_login_date`. No HTTP logic in the base class.
- `database.py` exposes:
  - `upsert_users(conn, rows)` — upsert into `users` on conflict `email` with `IS DISTINCT FROM` guard (spec section 6.3)
  - `upsert_tool_access(conn, tool_id, rows)` — upsert into `user_tool_access` on conflict `(tool_id, work_email)` with `IS DISTINCT FROM` guard (spec section 6.3)
  - `soft_delete_absent(conn, tool_id, present_emails)` — for each row in `user_tool_access` where `tool_id = $1 AND status != 'inactive' AND work_email NOT IN (present_emails)`, look up the `access_audit_log` for a DELETE record, use `change_timestamp` as `deactivation_date`, fall back to `NOW()` (spec section 6.4)
  - `update_last_sync(conn, tool_id)` — `UPDATE tools SET last_sync_at = NOW() WHERE id = $1`
- All functions take an explicit `conn` parameter (psycopg v3 `Connection`) — no global connection state; callers manage connection lifecycle

**Execution note:** Implement `test_database.py` test-first using `unittest.mock.patch` on `psycopg.connect`. Write failing tests for each database function before implementing the function body.

**Patterns to follow:**
- Sibling project `inventory_db.py` for psycopg v3 upsert with `IS DISTINCT FROM`
- Sibling project upsert pattern: `INSERT ... ON CONFLICT (...) DO UPDATE SET ... WHERE (...) IS DISTINCT FROM (...)`

**Test scenarios:**
- Happy path: `upsert_users` called with 3 rows executes 3 INSERT statements with correct ON CONFLICT clause; cursor `execute` called with each row's values
- Happy path: `upsert_tool_access` called with new rows executes INSERT ON CONFLICT on `(tool_id, work_email)`
- Edge case: `upsert_tool_access` with a row whose values are unchanged — `IS DISTINCT FROM` guard means `updated_at` is not updated; verify the WHERE clause is present in executed SQL
- Edge case: `upsert_users` with empty list — no database calls made
- Happy path: `soft_delete_absent` with audit log entry present — uses `change_timestamp` from log as `deactivation_date`
- Happy path: `soft_delete_absent` with no audit log entry — uses `NOW()` as `deactivation_date`
- Edge case: `soft_delete_absent` called when no accounts are absent (all emails in `present_emails`) — no UPDATE executed
- Happy path: `update_last_sync` executes UPDATE on correct `tool_id`

**Verification:**
- All test scenarios pass with mocked psycopg connections
- No real database connection required for tests

---

- [ ] U3. **Active Directory collector — `ad_usr.py`**

**Goal:** Sync all active AD user accounts into the `users` table using LDAP.

**Requirements:** R2

**Dependencies:** U1, U2

**Files:**
- Create: `access-inventory/collector/collectors/ad_usr.py`
- Test: `access-inventory/tests/test_collectors/test_ad_usr.py`

**Approach:**
- Connects to `ads.deltek.com` via `ldap3` using Simple bind with service account credentials from config
- Searches `OU=accounts,DC=ads,DC=deltek,DC=com` with scope `SUBTREE`, filter `(mail=*)`, retrieving: `dn`, `cn`, `sn`, `givenName`, `displayName`, `mail`, `title`, `department`, `employeeID`, `distinguishedName`
- Maps LDAP attributes to `users` table columns (email → `mail`, full_name → `displayName`, first_name → `givenName`, last_name → `sn`, job_title → `title`, department → `department`, employee_id → `employeeID`, is_active → `True` for all records returned by the query)
- This collector is synchronous (not a coroutine) because it runs before the parallel fan-out; called directly from `main.py` before `asyncio.gather()`
- Passes normalized rows to `database.upsert_users()`

**Patterns to follow:**
- LDAP bind pattern from `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/docs/specs/2026-05-24-auth-ldap-roles-permissions-spec.md` — two-step bind: service account first, note that for read-only AD queries (not user authentication) a single service-account bind is sufficient; two-step bind is only required when verifying user credentials

**Test scenarios:**
- Happy path: mock `ldap3.Connection` returns 5 user entries → `upsert_users` called with 5 normalised dicts
- Happy path: each entry maps `mail` → `email`, `displayName` → `full_name`, `givenName` → `first_name`, `sn` → `last_name`, `title` → `job_title`, `department` → `department`
- Edge case: LDAP entry with no `title` or `department` → fields default to `None` or empty string, no KeyError raised
- Error path: `ldap3.Connection` raises `LDAPException` → exception propagates with a descriptive log message; collector does not call `upsert_users`

**Verification:**
- All test scenarios pass with mocked `ldap3`
- Module is importable without a live LDAP connection

---

- [ ] U4. **CrowdStrike, Qualys, Sophos, Burp Suite, BlackDuck, Checkmarx async collectors**

**Goal:** Implement all 7 vendor collectors (11 logical environments) as async coroutines extending `BaseCollector`.

**Requirements:** R1, R3, R13

**Dependencies:** U1, U2

**Files:**
- Create: `access-inventory/collector/collectors/crowdstrike_usr.py`
- Create: `access-inventory/collector/collectors/qualys_usr.py`
- Create: `access-inventory/collector/collectors/sophos_usr.py`
- Create: `access-inventory/collector/collectors/burpsuite_usr.py`
- Create: `access-inventory/collector/collectors/blackduck_usr.py`
- Create: `access-inventory/collector/collectors/checkmarx_usr.py`
- Test: `access-inventory/tests/test_collectors/test_crowdstrike_usr.py`
- Test: `access-inventory/tests/test_collectors/test_qualys_usr.py`
- Test: `access-inventory/tests/test_collectors/test_sophos_usr.py`
- Test: `access-inventory/tests/test_collectors/test_burpsuite_usr.py`
- Test: `access-inventory/tests/test_collectors/test_blackduck_usr.py`
- Test: `access-inventory/tests/test_collectors/test_checkmarx_usr.py`

**Approach:**
- Each collector is a class extending `BaseCollector`, instantiated with environment-specific config values from `config.py`
- All use `httpx.AsyncClient` as the HTTP transport
- **CrowdStrike** (3 envs): OAuth2 client credentials → `GET /user-management/queries/users/v1` (paginated IDs) → `POST /user-management/entities/users/GET/v1` (details, batch 100). One class, instantiated 3 times with different env credentials. Apply logging filter to strip `access_token` from all log output (CrowdStrike token = full EDR fleet access — critical security requirement)
- **Qualys** (4 envs): Basic auth → `POST /msp/user_list.php` → parse XML via `defusedxml.ElementTree` (not stdlib `xml.etree` — vulnerable to XXE and billion-laughs attacks). One class, instantiated 4 times with different env credentials and base URLs
- **Sophos**: OAuth2 client credentials → `GET /whoami/v1` for tenant ID → `GET /common/v1/admins` (paginated)
- **Burp Suite**: API key in header → `GET /api/v1/users`
- **BlackDuck**: Token → bearer exchange → `GET /api/users` paginated, `Accept: application/vnd.blackducksoftware.user-4+json`
- **Checkmarx**: OAuth2 client credentials against IAM tenant → `GET /api/1.0/users` paginated
- Each collector returns a list of dicts with at minimum `work_email`, `status` (normalize to lowercase `'active'`/`'inactive'`), `user_role`, `last_login_date`
- Error handling: `httpx.HTTPError` and `httpx.TimeoutException` are caught; exception is logged with collector name and env; an empty list is returned so the soft-delete pass does not incorrectly deactivate all users for that tool. This failure is also returned as a structured result (see institutional learning on fan-out error propagation)

**Execution note:** Mock `httpx.AsyncClient` in all tests via `respx` or `unittest.mock.patch`. Never make real HTTP calls in tests.

**Patterns to follow:**
- CrowdStrike multi-console pattern and token-in-logs prevention from sibling project's CrowdStrike collector
- `asyncio.gather(return_exceptions=True)` error-as-structured-result pattern from the AWS fan-out learning

**Test scenarios (per collector — apply all that are relevant):**
- Happy path: mock HTTP response returns paginated user list → `collect()` returns correctly normalized list
- Happy path: pagination — first page returns `next_cursor`/`page` token, second page returns last batch → both pages fetched, results merged
- Edge case: empty user list (tool has zero users) → `collect()` returns empty list, no error
- Edge case: token/auth response returns unexpected status → exception raised with clear message; no user rows returned
- Error path: `httpx.HTTPError` during data fetch → exception caught; empty list returned; error logged with env name
- Error path: `httpx.TimeoutException` → same as above
- **CrowdStrike specific**: verify `access_token` value does not appear in any log output at any level (INFO, DEBUG, WARNING) — assert via `caplog` that the token value is absent
- **Qualys specific**: XML response parsed correctly using `defusedxml.ElementTree`; missing fields default gracefully
- **BlackDuck specific**: `Accept` header is set to `application/vnd.blackducksoftware.user-4+json` in all requests

**Verification:**
- All tests pass with mocked HTTP clients
- No real network calls in tests

---

- [ ] U5. **Orchestrator — `main.py`**

**Goal:** Wire together the AD sync, parallel collector fan-out, per-collector database writes, and validator invocation into a single runnable entry point.

**Requirements:** R1, R2, R3, R4, R5, R12

**Dependencies:** U2, U3, U4

**Files:**
- Create: `access-inventory/collector/main.py`
- Test: `access-inventory/tests/test_main.py` (integration-style, mocked DB and collectors)

**Approach:**
- Entry point: `python -m collector.main` or `python main.py` (cron-compatible)
- Sequence:
  1. Load config; establish synchronous psycopg connection for the AD + sequential DB writes phase
  2. Run `ad_usr.py` synchronously; call `database.upsert_users()`
  3. Instantiate all 11 collector instances (CrowdStrike ×3, Qualys ×4, Sophos, Burp Suite, BlackDuck, Checkmarx)
  4. Run `asyncio.run(gather_all(collectors))` — each coroutine calls `collect()`, then on success: `upsert_tool_access()`, `soft_delete_absent()`, `update_last_sync()`; on failure: log structured error with tool name
  5. After gather completes, run `validator.run(conn)`
  6. Exit 0 on success; exit 1 if any collector raised an exception (partial failure is not a silent success)
- `asyncio.gather(return_exceptions=True)` — never propagate one collector's exception to others; always attempt all collectors
- Structured failure logging: when a collector raises an exception, log `{tool_name: ..., env: ..., error: str(exc), traceback: ...}` at ERROR level

**Test scenarios:**
- Happy path: all 11 collectors succeed → `upsert_tool_access` called 11 times, `update_last_sync` called 11 times, `validator.run` called once
- Error path: one collector raises `httpx.HTTPError` → remaining 10 collectors still complete; structured error logged for the failing one; process exits with code 1
- Edge case: AD sync raises `LDAPException` → entire run aborted with error message; tool collectors not started

**Verification:**
- All test scenarios pass with mocked collectors and mocked database functions
- `python -m collector.main` runs without error when `.env` is populated (manual verification)

---

- [ ] U6. **Validator — `validator.py`**

**Goal:** Post-collection cross-reference of `user_tool_access` against `users` to surface orphaned and stale accounts, writing findings to `access_audit_log`.

**Requirements:** R12

**Dependencies:** U2

**Files:**
- Create: `access-inventory/collector/validator.py`
- Test: `access-inventory/tests/test_validator.py`

**Approach:**
- `run(conn)` function takes a psycopg connection
- **Orphan detection**: `SELECT uta.work_email, uta.tool_id FROM user_tool_access uta LEFT JOIN users u ON LOWER(uta.work_email) = LOWER(u.email) WHERE uta.status = 'active' AND u.user_id IS NULL` → write each result to `access_audit_log` with a finding type indicating "no AD record"
- **Stale access detection**: `SELECT uta.work_email, uta.tool_id FROM user_tool_access uta JOIN users u ON LOWER(uta.work_email) = LOWER(u.email) WHERE uta.status = 'active' AND u.is_active = false` → write each result to `access_audit_log` with a finding type indicating "inactive employee with active access"
- Audit log write schema is determined at implementation time by reading the current `access_audit_log` table definition (see Deferred to Implementation)
- Returns a summary dict `{orphans: int, stale: int}` for logging in `main.py`

**Test scenarios:**
- Happy path: mock query returns 2 orphan rows and 1 stale row → audit log `execute` called 3 times; summary returns `{orphans: 2, stale: 1}`
- Edge case: no orphans, no stale → audit log not written; summary returns `{orphans: 0, stale: 0}`
- Edge case: mixed-case emails are matched correctly by `LOWER()` comparison — verify SQL contains `LOWER()` on both sides
- Error path: DB query raises exception → exception propagates with log message; does not silently swallow

**Verification:**
- All test scenarios pass with mocked psycopg connection
- Summary logging in `main.py` is visible at INFO level

---

- [ ] U7. **Web app — `app.py`, `ldap_client.py`, `queries.py`**

**Goal:** FastAPI application providing the search interface that replaces the n8n email workflow.

**Requirements:** R6, R7, R8, R9

**Dependencies:** U1

**Files:**
- Create: `access-inventory/web/app.py`
- Create: `access-inventory/web/ldap_client.py`
- Create: `access-inventory/web/queries.py`
- Test: `access-inventory/tests/test_app.py`
- Test: `access-inventory/tests/test_ldap_client.py`
- Test: `access-inventory/tests/test_queries.py`

**Approach:**
- `app.py`: FastAPI app with three routes (spec section 5.4): `GET /` serves form, `POST /search` orchestrates lookup, `GET /health` returns `{"status": "ok"}`. Uses `psycopg_pool.AsyncConnectionPool` initialized in FastAPI `@asynccontextmanager` lifespan — never at module import. Uses `Jinja2Templates` for `index.html`.
- `ldap_client.py`: `async def search_user(term: str) -> dict | None`
  - Sanitize `term` against `^[a-zA-Z0-9._@\\-\\.\\s]+$` before use — reject at boundary if invalid
  - Detect input type: if `@` present → email search (`(mail=*{term}*)`), else → name search (`(|(givenName=*{term}*)(sn=*{term}*)(cn=*{term}*))`)
  - Wrap `ldap3.Connection.search()` in `asyncio.to_thread()` to avoid blocking the event loop
  - Return dict with: `email`, `full_name`, `job_title`, `department`, `is_active`; return `None` if no result
- `queries.py`: `async def get_tool_access(conn, email: str) -> list[dict]`
  - Query: `SELECT uta.*, t.name as tool_name, t.category FROM user_tool_access uta JOIN tools t ON uta.tool_id = t.id WHERE LOWER(uta.work_email) = LOWER($1) ORDER BY t.name`
  - Apply BlackDuck override: for any row where `tool_name ILIKE '%blackduck%'`, set `status = 'Active Access'`, `last_login_date = 'N/A'`
  - Return list of dicts; empty list if no access found
- `POST /search` routing logic in `app.py`:
  - Call `ldap_client.search_user(query)` → if `None` → State 3 (not found)
  - Call `queries.get_tool_access(conn, result_email)` → if empty list → State 2 (no tools)
  - Otherwise → State 1 (profile card + table)

**Patterns to follow:**
- FastAPI lifespan pattern for connection pool (FastAPI docs)
- LDAP injection prevention from the LDAP spec learning above

**Test scenarios:**
- Happy path (State 1): mock LDAP returns user, mock query returns 3 tool rows → response contains profile card and 3 table rows
- Happy path (State 2): mock LDAP returns user, mock query returns empty list → response contains "no tools" message
- Happy path (State 3): mock LDAP returns `None` → response contains "not found" message with searched term
- `GET /health` returns 200 with `{"status": "ok"}`
- `GET /` returns 200 with search form
- **BlackDuck override**: mock query returns a row with `tool_name = 'BlackDuck'` → response shows `status = 'Active Access'` and `last_login = 'N/A'`
- **BlackDuck override**: case-insensitive — `tool_name = 'blackduck'` and `tool_name = 'BLACKDUCK'` both trigger the override
- Edge case (LDAP): input containing LDAP special characters (e.g., `(`, `)`, `*`) → sanitizer rejects input before LDAP query; returns State 3 or validation error
- Edge case (queries): `email` with uppercase characters → `LOWER()` applied; matches rows with different casing
- **ldap_client**: `asyncio.to_thread` is used for all `ldap3` calls — verify the LDAP `search()` is never called directly in a coroutine context (check for `await asyncio.to_thread(...)` wrapping)

**Verification:**
- All test scenarios pass with mocked `ldap3` and mocked Postgres connection pool
- `uvicorn web.app:app --port 8001` starts without error when `.env` is present (manual verification)

---

- [ ] U8. **HTML template — `index.html`**

**Goal:** Single-page Jinja2 template rendering the search form and all three output states.

**Requirements:** R6, R7, R8

**Dependencies:** U7

**Files:**
- Create: `access-inventory/web/templates/index.html`

**Approach:**
- Single template; search form always visible at top
- State rendering via Jinja2 conditionals on context variables passed from `app.py`
- **State 1** (user + tools): employee profile card (full name, job title, department, email) + tool access table with columns: Tool Name, Category, Status, Role, Last Login. Rows sorted by tool name.
- **State 2** (user + no tools): profile card + warning banner "No tools assigned — contact administrator to assign tool access."
- **State 3** (not found): error message "No user found for '{searched_value}' in Active Directory."
- No external CSS frameworks required — plain HTML with inline or `<style>` block is sufficient for an internal tool. Table should be readable without styling.
- Search query pre-filled in the form after submission

**Test scenarios:**
- Test expectation: none — template rendering is validated by U7's test scenarios which verify State 1/2/3 response content; no additional unit tests needed for the template itself

**Verification:**
- All three states render correctly in a browser (manual verification)
- Profile card shows correct fields from mock data
- Tool table displays Tool Name, Category, Status, Role, Last Login columns

---

## System-Wide Impact

- **Interaction graph:** `main.py` is the sole orchestrator; no inter-module callbacks. `validator.py` reads `user_tool_access` and `users` but only writes to `access_audit_log`. Web app only reads (`SELECT`); no writes.
- **Error propagation:** Collector exceptions are caught by `asyncio.gather(return_exceptions=True)` and logged as structured failures. One failing collector does not abort others. Validator exceptions propagate to `main.py` and cause a non-zero exit.
- **State lifecycle risks:** The `IS DISTINCT FROM` upsert guard means `updated_at` only changes when field values actually change — no spurious timestamp updates on re-runs. Soft-delete is idempotent: calling `soft_delete_absent` for an already-inactive account is a no-op (the `AND status != 'inactive'` guard).
- **API surface parity:** The web app is read-only — it makes no writes to any table. All mutation is in the collector path. BlackDuck override is applied at query time only; the stored value in `user_tool_access` is whatever the BlackDuck API returned.
- **Integration coverage:** The AD sync (`ad_usr.py`) must complete before validator orphan detection produces meaningful results — orphan detection joins against `users`, which `ad_usr.py` populates. Sequence in `main.py` ensures AD runs first.
- **Unchanged invariants:** All 14 existing tables retain their schema. The only DDL change is the additive `ADD CONSTRAINT uq_tool_user UNIQUE (tool_id, work_email)` migration. All existing downstream tooling that reads from these tables is unaffected. `updated_at` on unchanged rows does not advance.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| CrowdStrike OAuth2 token logged to file | Apply `logging.Filter` that strips `access_token` from all log records; tested explicitly via `caplog` assertion in `test_crowdstrike_usr.py` |
| Qualys XML parse failure (unexpected response shape) | Use `defusedxml.ElementTree` (not stdlib `xml.etree`); wrap parse in try/except; return empty list and structured error on failure |
| LDAP injection via search input | Sanitize input against `^[a-zA-Z0-9._@\-\.\s]+$` before building any LDAP filter; tested explicitly in `test_ldap_client.py` |
| One collector failure silently deactivates all users for that tool | `soft_delete_absent` is only called on collector success; on exception the collector returns early without calling it |
| `asyncio.to_thread` wrapping missed for LDAP in web app | Explicit test assertion that `ldap3` `search()` is wrapped in `asyncio.to_thread` |
| Migration applied to prod with existing duplicates | Spec confirms no duplicates on `(tool_id, work_email)` — safe; migration file comment documents this confirmation |
| `access_audit_log` schema mismatch for validator writes | Read actual table DDL at implementation time before writing validator insert SQL |
| psycopg3 `AsyncConnectionPool` initialized at module import (fork-safety) | Initialize only in FastAPI lifespan context; tested by verifying pool is None at import time |

---

## Documentation / Operational Notes

- Apply migration `001_add_upsert_constraint.sql` manually before first run: `psql $DATABASE_URL -f migrations/001_add_upsert_constraint.sql`
- Add cron entry for periodic collection: `0 */6 * * * cd /path/to/access-inventory && python -m collector.main >> /var/log/access-inventory.log 2>&1`
- Web app started with: `uvicorn web.app:app --host 0.0.0.0 --port 8001`
- `.env` file must never be committed — `.env.example` is the committed reference
- CrowdStrike tokens are never persisted; they are fetched fresh on each collector run

---

## Sources & References

- **Origin document:** [tool_access_validation/access_inventory_spec.md](../../tool_access_validation/access_inventory_spec.md)
- Sibling project patterns: `/mnt/c/Users/MichaelCesarPaguio/External Exposure Triage/backend/utils/inventory_db.py`
- CrowdStrike token security learning: `External Exposure Triage/docs/plans/2026-05-09-001-feat-postgres-asset-store-plan.md`
- Async fan-out error propagation learning: `External Exposure Triage/docs/solutions/integration-issues/aws-tls-retry-and-cloud-timeout-surfacing-2026-05-14.md`
- LDAP/AD spec: `External Exposure Triage/docs/specs/2026-05-24-auth-ldap-roles-permissions-spec.md`
- Qualys API contract: `External Exposure Triage/docs/solutions/documentation-gaps/qualys-csam-report-download-api-contract-2026-05-14.md`
