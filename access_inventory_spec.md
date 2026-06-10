# Access Inventory — Project Specification

**Project:** User Access Inventory & Validator  
**Date:** 2026-06-10  
**Status:** Approved for build  

---

## 0. Overall Goal

The Deltek Global Information Security team manages user access across 11 security tool environments spanning three network enclaves — Commercial, GCE, and GCCM. Today, access data is collected and queried through two n8n workflows that are fragile, email-dependent, and difficult to maintain. Access questions require submitting a form and waiting for an email. There is no persistent audit view, no change history, and no way to detect stale or orphaned accounts without running the workflow manually.

**This project replaces both workflows with a maintainable, self-contained Python system that:**

- Automatically collects user access records from all 11 tool environments and keeps them current in a Postgres database using non-destructive upserts — so history is never lost
- Validates those records continuously against Active Directory, surfacing orphaned accounts (in a tool but not in AD) and stale access (inactive employee still provisioned)
- Lets any team member open a browser, type a name or email address, and instantly see that person's complete access profile across every tool — replacing the email workflow with an on-screen result
- Preserves the existing database schema so no data migration is required and downstream tooling is unaffected
- Is built to grow — the `<vendor>_usr.py` file naming convention ensures that future host, vulnerability, and alert collectors for the same vendors can be added or merged from other systems without naming conflicts

---

## 1. Background

Two n8n workflows currently handle user access management at Deltek:

| Workflow ID | Name | Purpose |
|---|---|---|
| `63WHIl0bD5691vOS` | Tools Access Masterlist | Collects user lists from all security tools, clears and repopulates Postgres |
| `OqJfVOAA5N2qKP2n` | Application Access Lookup | Form-based lookup that queries AD + Postgres and emails results to a recipient |

**Decision:** Remove n8n entirely. Replace both workflows with a standalone Python service and a FastAPI web application backed by the same Postgres database.

---

## 2. Goals

- Replace both n8n workflows with a standalone Python service and FastAPI web application
- Replicate all data collection currently performed by n8n, with all 11 tool environments
- Replace the email output of the lookup workflow with an instant in-browser display
- Retain the existing Postgres schema unchanged — one additive migration only (unique constraint)
- Switch from destructive truncate-and-reload to non-destructive upserts that preserve history
- Soft-delete removed accounts (`status = inactive`) rather than deleting rows, using audit log history to determine the accurate deactivation date
- Keep the `users` table as a locally synchronised mirror of Active Directory — used for orphan detection, result enrichment, and historical records of former employees
- Support future merging with other collector systems via the `<vendor>_usr.py` naming convention

---

## 3. System Components

### Component 1 — Collector

A Python async service that replaces workflow `63WHIl0bD5691vOS`. Runs on a schedule or manually.

**Responsibilities:**
- Sync user records from Active Directory into the `users` table
- Collect user lists from all 11 tool environments in parallel
- Write results to `user_tool_access` using upsert logic
- Mark accounts removed from a tool as `inactive` rather than deleting them
- Update `tools.last_sync_at` after each successful collection

**Scheduling:** Linux cron or manual CLI trigger (replaces n8n Schedule Trigger / Manual Execute)

### Component 2 — Validator

Runs automatically after each collection cycle.

**Responsibilities:**
- Cross-reference `user_tool_access` against `users`
- Flag accounts in tools that have no matching employee record (`users` table miss)
- Flag inactive employees who still have active tool access
- Write findings to `access_audit_log`

### Component 3 — Web Application

A FastAPI web app at `http://localhost:8001` that replaces workflow `OqJfVOAA5N2qKP2n`.

**Replaces the n8n form + LDAP + Postgres + email chain with a single search page.**

---

## 4. n8n Workflow Mapping

### 4.1 Workflow `63WHIl0bD5691vOS` — Tools Access Masterlist

| n8n Node | Python Replacement |
|---|---|
| Schedule Trigger | cron job or `python main.py` |
| When clicking Execute workflow | `python main.py` (manual) |
| Clear Existing users Data | `database.py` → upsert (no truncate) |
| Clear Existing user_tool_access Data | `database.py` → upsert (no truncate) |
| Wait (fan-out) | `asyncio.gather()` — parallel execution |
| Call User Information | `collectors/ad_usr.py` |
| Call CrowdStrike Commercial Users | `collectors/crowdstrike_usr.py` (env=Commercial) |
| Call Crowdstrike GCE | `collectors/crowdstrike_usr.py` (env=GCE) |
| Call Crowdstrike GCCM | `collectors/crowdstrike_usr.py` (env=GCCM) |
| Call Qualys Prod Users | `collectors/qualys_usr.py` (env=Commercial Prod) |
| Call Qualys Commercial Dev/Test Users | `collectors/qualys_usr.py` (env=Commercial Dev/Test) |
| Call Qualys GCE Users | `collectors/qualys_usr.py` (env=GCE) |
| Call Qualys GCCM Users | `collectors/qualys_usr.py` (env=GCCM) |
| Call Sophos Users | `collectors/sophos_usr.py` |
| Call Burp Suite Users | `collectors/burpsuite_usr.py` |
| Call Blackduck Users | `collectors/blackduck_usr.py` |
| Call Checkmarx Users | `collectors/checkmarx_usr.py` |

### 4.2 Workflow `OqJfVOAA5N2qKP2n` — Application Access Lookup

| n8n Node | Python / Web Replacement |
|---|---|
| On form submission | `GET /` — search form in browser |
| ADS Deltek (LDAP) | `web/ldap_client.py` |
| Check LDAP Results | `web/ldap_client.py` — validation logic |
| Edit Fields | `web/queries.py` — field normalisation |
| Search User Tool Access | `web/queries.py` — Postgres query |
| Check if Tool Access Found | `web/app.py` — routing logic |
| Consolidated Single Email Formatter | `web/templates/index.html` — rendered in browser |
| Format User No Tool Access | `web/templates/index.html` — "no tools" state |
| Handle No User Found Error | `web/templates/index.html` — "not found" state |
| Send Consolidated Email | **Removed** — results displayed on page instead |

---

## 5. Web Application — Detailed Specification

### 5.1 Input

A single search field on the page. Accepts any of:

| Input type | Example |
|---|---|
| First name | `David` |
| Last name | `Bogatek` |
| Full name | `David Bogatek` |
| Email (full) | `DavidBogatek@deltek.com` |
| Email (partial) | `davidbogatek` |

Search is case-insensitive and partial-match. AD is queried first (LDAP `mail` attribute), then Postgres is queried using the resolved email.

### 5.2 Output States

Mirrors the three states from the n8n email formatter exactly:

**State 1 — User found, has tool access**

Displays employee profile card and tool access table:

```
Full Name        Job Title · Department
work_email@deltek.com

┌──────────────────────┬─────────────────────┬────────────┬──────────────┬────────────┐
│ Tool Name            │ Category            │ Status     │ Role         │ Last Login │
├──────────────────────┼─────────────────────┼────────────┼──────────────┼────────────┤
│ Sophos Central       │ EDR                 │ active     │ Enterprise   │ —          │
│ Burp Suite Ent.      │ Application Sec.    │ active     │ standard     │ —          │
└──────────────────────┴─────────────────────┴────────────┴──────────────┴────────────┘
```

**State 2 — User found, no tool access**

```
⚠ No tools assigned — contact administrator to assign tool access.
```

**State 3 — User not found in AD**

```
✕ No user found for "<searched value>" in Active Directory.
```

### 5.3 Business Rules Carried Over from n8n

- **BlackDuck override:** If `tool_name` contains `"blackduck"` (case-insensitive), force `status = "Active Access"` and `last_login = "N/A"`. This is applied in `queries.py` at query time, not stored in the database.
- **Email case normalisation:** All email comparisons use `LOWER()` on both sides. Mixed-case emails (13 of 91 current records) are handled transparently.
- **Recipient email field removed:** The n8n form had a second field "email address for results" (the person who receives the email). This is removed — results are shown on screen to whoever performed the search.

### 5.4 Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve search page |
| `POST` | `/search` | Run LDAP + Postgres lookup, return results |
| `GET` | `/health` | Liveness check |

### 5.5 Port

`http://localhost:8001`

---

## 6. Database Changes

### 6.1 Schema Retained

All 14 existing tables are retained unchanged:

`users`, `user_tool_access`, `tools`, `auth_providers`, `user_data_sources`, `access_audit_log`, `departments`, `job_positions`, `organizations`, `roles`, `teams`, `user_assignments`, `user_role_assignments`, `user_team_memberships`

#### Role of the `users` table

The `users` table is **not** a source of truth — Active Directory is. It is a locally synchronised mirror of AD, kept current by `ad_usr.py` on each collection run. It serves three purposes in this system:

| Purpose | Detail |
|---|---|
| **Orphan detection** | The validator joins `user_tool_access` against `users` to find tool accounts with no matching AD record. Without this table, every orphan check would require a live LDAP round-trip per account. |
| **Web app enrichment** | The search result card shows `job_title`, `department`, and `is_active` sourced from `users`, avoiding a second LDAP call after the initial name/email lookup. |
| **Historical record** | When an employee leaves, their AD account is removed. The `users` row is marked `is_active = false` but retained, so `user_tool_access` rows remain meaningful and auditable after the person is gone from AD. |

All FK references to `users.user_id` from other tables (`access_audit_log.changed_by`, `user_tool_access.deactivated_by`, `user_assignments`, `user_role_assignments`, `user_team_memberships`) are currently unpopulated (0 rows). They are retained for potential future use but are not part of this project's scope.

#### Role of the `users` table

The `users` table is **not** a source of truth — Active Directory is. It is a **locally synchronised mirror of AD**, kept current by `ad_usr.py` on every collection run. Its purpose is narrow and specific:

| Purpose | Detail |
|---|---|
| Orphan detection | The validator cross-references `user_tool_access.work_email` against `users.email` entirely in Postgres, without needing a live AD query per record |
| Web app enrichment | The profile card (full name, job title, department) is pulled from `users` rather than making a second LDAP round-trip after the initial search |
| Historical record | After an employee leaves and their AD account is removed, their `user_tool_access` rows remain meaningful because `users` retains their details with `is_active = false` |

All other foreign keys pointing at `users.user_id` (`access_audit_log.changed_by`, `user_tool_access.deactivated_by`, `user_assignments`, `user_role_assignments`, `user_team_memberships`) are currently unpopulated and belong to future functionality outside this project's scope.

### 6.2 Migration Required

One migration adds a unique constraint to enable upsert on `user_tool_access`:

```sql
-- migrations/001_add_upsert_constraint.sql
ALTER TABLE user_tool_access
  ADD CONSTRAINT uq_tool_user UNIQUE (tool_id, work_email);
```

**Safe to apply:** current data has no duplicates on `(tool_id, work_email)` — confirmed by query.

### 6.3 Upsert Strategy — Replacing Truncate + Reload

**Previous behaviour (n8n):** `TRUNCATE users`, `TRUNCATE user_tool_access` before every run.

**New behaviour:** `INSERT ... ON CONFLICT DO UPDATE ... WHERE IS DISTINCT FROM` — only rows that have actually changed are updated. `updated_at` only changes when field values change.

**users table** — upsert key: `email` (existing `UNIQUE` constraint)

```sql
INSERT INTO users (email, full_name, first_name, last_name, ...)
ON CONFLICT (email) DO UPDATE SET
  full_name  = EXCLUDED.full_name,
  job_title  = EXCLUDED.job_title,
  department = EXCLUDED.department,
  is_active  = EXCLUDED.is_active,
  updated_at = NOW()
WHERE (full_name, job_title, department, is_active)
   IS DISTINCT FROM
      (users.full_name, users.job_title, users.department, users.is_active)
```

**user_tool_access table** — upsert key: `(tool_id, work_email)` (new constraint from migration)

```sql
INSERT INTO user_tool_access (tool_id, work_email, status, user_role, ...)
ON CONFLICT (tool_id, work_email) DO UPDATE SET
  user_role       = EXCLUDED.user_role,
  status          = EXCLUDED.status,
  last_login_date = EXCLUDED.last_login_date,
  updated_at      = NOW()
WHERE (user_role, status, last_login_date)
   IS DISTINCT FROM
      (user_tool_access.user_role, user_tool_access.status,
       user_tool_access.last_login_date)
```

### 6.4 Soft Delete — Accounts Removed From a Tool

When a user no longer appears in a tool's API response during collection:

1. Look up `access_audit_log` for a `DELETE` record matching `(tool_id, work_email)` — the `old_values` JSONB column on DELETE rows contains the full prior record including `change_timestamp`
2. Use `change_timestamp` from the log as `deactivation_date`
3. If no log entry is found, use `NOW()` as `deactivation_date`
4. Set `status = 'inactive'`
5. **Do not delete the row** — history is preserved

```sql
UPDATE user_tool_access
SET
  status           = 'inactive',
  deactivation_date = <change_timestamp from log, or NOW()>,
  updated_at        = NOW()
WHERE tool_id   = $1
  AND work_email = $2
  AND status    != 'inactive'
```

---

## 7. Active Directory Integration

### 7.1 Connection

| Parameter | Value |
|---|---|
| Protocol | LDAP (confirmed from n8n node) |
| Host | `ads.deltek.com` |
| Base DN | `OU=accounts,DC=ads,DC=deltek,DC=com` |
| Search attribute | `mail` |
| Library | `ldap3` (Python) |

### 7.2 Fields Retrieved

`dn`, `cn`, `sn`, `givenName`, `displayName`, `mail`, `title`, `department`, `employeeID`, `distinguishedName`

### 7.3 Search Modes

The `ad_usr.py` collector searches by `mail` attribute. The web `ldap_client.py` accepts any of: email, first name, last name, full name — and builds the appropriate LDAP filter dynamically.

---

## 8. File Structure

```
access-inventory/
│
├── collector/
│   ├── main.py                    orchestrator — run manually or via cron
│   ├── config.py                  all credentials loaded from .env
│   ├── database.py                all Postgres upsert / soft-delete operations
│   ├── validator.py               post-collection validation logic
│   └── collectors/
│       ├── base.py                BaseCollector abstract class
│       ├── ad_usr.py              Active Directory → users table
│       ├── crowdstrike_usr.py     CrowdStrike Commercial + GCE + GCCM
│       ├── qualys_usr.py          Qualys Prod + Dev/Test + GCE + GCCM
│       ├── sophos_usr.py          Sophos Central
│       ├── burpsuite_usr.py       Burp Suite Enterprise
│       ├── blackduck_usr.py       BlackDuck
│       └── checkmarx_usr.py       Checkmarx One
│
├── web/
│   ├── app.py                     FastAPI — GET / and POST /search
│   ├── ldap_client.py             LDAP lookup (replaces ADS Deltek n8n node)
│   ├── queries.py                 Postgres read queries + BlackDuck override
│   └── templates/
│       └── index.html             search form + results (all 3 states)
│
├── migrations/
│   └── 001_add_upsert_constraint.sql
│
├── .env                           credentials (not committed to source control)
├── requirements.txt
└── README.md
```

### 8.1 Naming Convention

The `_usr` suffix on all collector files identifies them as **user/identity collectors** specifically. This disambiguates them from other collector types that may be added later or merged from other systems:

| Suffix | Data type | Example |
|---|---|---|
| `_usr` | User accounts & access | `crowdstrike_usr.py` |
| `_host` | Host / device inventory | `crowdstrike_host.py` (future) |
| `_vuln` | Vulnerability findings | `qualys_vuln.py` (future) |
| `_alert` | Detections / alerts | `crowdstrike_alert.py` (future) |

Files sort by vendor in directory listings, keeping all files for a given vendor together.

---

## 9. Collector File Descriptions

### `ad_usr.py`
Connects to `ads.deltek.com` via LDAP. Queries `OU=accounts,DC=ads,DC=deltek,DC=com` for all active user accounts. Upserts into `users` table. Upsert key: `email`.

### `crowdstrike_usr.py`
Handles three environments: Commercial, GCE, GCCM. Each uses a separate client ID/secret and base URL. OAuth2 token auth. Endpoints: `GET /user-management/queries/users/v1` (paginated IDs) then `POST /user-management/entities/users/GET/v1` (details in batches of 100).

### `qualys_usr.py`
Handles four environments: Commercial Prod, Commercial Dev/Test, GCE, GCCM. Basic auth. Endpoint: `POST /msp/user_list.php` (XML response parsed with `xml.etree`).

### `sophos_usr.py`
Single environment. OAuth2 client credentials → whoami for tenant ID → `GET /common/v1/admins` (paginated).

### `burpsuite_usr.py`
API key auth. Endpoint: `GET /api/v1/users`.

### `blackduck_usr.py`
Token → bearer exchange → `GET /api/users` (paginated). Accept header: `application/vnd.blackducksoftware.user-4+json`.

### `checkmarx_usr.py`
OAuth2 client credentials against IAM tenant → `GET /api/1.0/users` (paginated).

---

## 10. Environment Variables (`.env`)

```bash
# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://pgadmin:password@localhost:5432/access_inventory

# ─── LDAP / Active Directory ──────────────────────────────────────────────────
LDAP_HOST=ads.deltek.com
LDAP_PORT=389
LDAP_USE_SSL=false
LDAP_BIND_DN=CN=your-service-account,OU=Service Accounts,DC=ads,DC=deltek,DC=com
LDAP_BIND_PASSWORD=your-bind-password
LDAP_BASE_DN=OU=accounts,DC=ads,DC=deltek,DC=com
LDAP_SEARCH_ATTRIBUTE=mail

# ─── Web App ──────────────────────────────────────────────────────────────────
WEB_PORT=8001

# ─── CrowdStrike ──────────────────────────────────────────────────────────────
CROWDSTRIKE_COMMERCIAL_CLIENT_ID=
CROWDSTRIKE_COMMERCIAL_CLIENT_SECRET=
CROWDSTRIKE_COMMERCIAL_BASE_URL=https://api.crowdstrike.com

CROWDSTRIKE_GCE_CLIENT_ID=
CROWDSTRIKE_GCE_CLIENT_SECRET=
CROWDSTRIKE_GCE_BASE_URL=https://api.laggar.gcw.crowdstrike.com

CROWDSTRIKE_GCCM_CLIENT_ID=
CROWDSTRIKE_GCCM_CLIENT_SECRET=
CROWDSTRIKE_GCCM_BASE_URL=https://api.crowdstrike.com

# ─── Qualys ───────────────────────────────────────────────────────────────────
QUALYS_COMMERCIAL_PROD_USERNAME=
QUALYS_COMMERCIAL_PROD_PASSWORD=
QUALYS_COMMERCIAL_PROD_BASE_URL=https://qualysapi.qualys.com

QUALYS_COMMERCIAL_DEV_USERNAME=
QUALYS_COMMERCIAL_DEV_PASSWORD=
QUALYS_COMMERCIAL_DEV_BASE_URL=https://qualysapi.qualys.com

QUALYS_GCE_USERNAME=
QUALYS_GCE_PASSWORD=
QUALYS_GCE_BASE_URL=https://qualysapi.qg3.apps.qualys.com

QUALYS_GCCM_USERNAME=
QUALYS_GCCM_PASSWORD=
QUALYS_GCCM_BASE_URL=https://qualysapi.qg4.apps.qualys.com

# ─── Sophos ───────────────────────────────────────────────────────────────────
SOPHOS_CLIENT_ID=
SOPHOS_CLIENT_SECRET=

# ─── Burp Suite Enterprise ────────────────────────────────────────────────────
BURP_SUITE_API_KEY=
BURP_SUITE_BASE_URL=https://burp.example.com

# ─── BlackDuck ────────────────────────────────────────────────────────────────
BLACKDUCK_API_TOKEN=
BLACKDUCK_BASE_URL=https://blackduck.example.com

# ─── Checkmarx ────────────────────────────────────────────────────────────────
CHECKMARX_CLIENT_ID=
CHECKMARX_CLIENT_SECRET=
CHECKMARX_TENANT=
CHECKMARX_BASE_URL=https://eu.iam.checkmarx.net
CHECKMARX_API_BASE_URL=https://eu.ast.checkmarx.net
```

---

## 11. Confirmed Decisions

| # | Decision | Answer |
|---|---|---|
| 1 | AD connection type | LDAP via `ldap3` — `ads.deltek.com`, `OU=accounts,DC=ads,DC=deltek,DC=com` |
| 2 | Unique constraint on `(tool_id, work_email)` | **Yes — safe to add, no existing duplicates** |
| 3 | Web app port | **8001** |
| 4 | Removed accounts | **Set `status = inactive`, look up `access_audit_log` for `change_timestamp` as `deactivation_date`, fall back to `NOW()`** |
| 5 | LDAP credentials | **Provided via `.env` — see section 10** |
| 6 | User directory source | **AD directly via LDAP — no external HR API** |
| 7 | Report output | **Live web page at `localhost:8001` — no static HTML file, no email** |
| 8 | Collector file naming | **`<vendor>_usr.py` pattern** |
| 9 | BlackDuck override | **Carry over from n8n — force `status = Active Access`, `last_login = N/A`** |
| 10 | `users` table | **Retained as a locally synchronised AD mirror — not a source of truth. Used for orphan detection, web app enrichment, and historical records of former employees** |

---

## 12. Tools Inventory

| Tool Name | Vendor | Category | Environments |
|---|---|---|---|
| CrowdStrike Commercial | CrowdStrike | Endpoint Detection and Response | Commercial |
| CrowdStrike GCE | CrowdStrike | Endpoint Detection and Response | GCE |
| CrowdStrike GCCM | CrowdStrike | Endpoint Detection and Response | GCCM |
| Qualys Commercial Prod | Qualys | Vulnerability Management | Commercial |
| Qualys Commercial Dev/Test | Qualys | Vulnerability Management | Commercial |
| Qualys GCE | Qualys | Vulnerability Management | GCE |
| Qualys GCCM | Qualys | Vulnerability Management | GCCM |
| Sophos Central | Sophos | Endpoint Detection and Response | Commercial |
| Burp Suite Enterprise | Burp | Application Security | Commercial |
| Blackduck | BlackDuck | Application Security | Commercial |
| Checkmarx | Checkmarx | Application Security | Commercial |

---

## 13. Current Database State (as of 2026-06-10)

| Table | Record count | Notes |
|---|---|---|
| `users` | 4,131 | All active employees, populated from prior n8n runs |
| `user_tool_access` | 91 | Sophos Central (54) + Burp Suite Enterprise (37) |
| `tools` | 11 | All environments registered |
| `auth_providers` | 3 | Blackduck, Burp Suite, Checkmarx |
| `access_audit_log` | 83,945 | Full DELETE/INSERT history since 2025-07-24 |
| `user_data_sources` | 0 | Unused — collector will populate via `ad_usr.py` |

**Orphan accounts** (in `user_tool_access` with no matching `users` record): 8 accounts identified, including test accounts and possible former employees.

---

*End of specification*
