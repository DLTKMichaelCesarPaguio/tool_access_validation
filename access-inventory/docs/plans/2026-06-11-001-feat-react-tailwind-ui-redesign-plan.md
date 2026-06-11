---
title: "feat: React + Tailwind v4 UI Redesign with Deltek Design System"
type: feat
status: active
date: 2026-06-11
origin: docs/brainstorms/react-tailwind-ui-requirements.md
---

# feat: React + Tailwind v4 UI Redesign with Deltek Design System

## Overview

Replace the single Jinja2 `index.html` template with a React 18 + Vite 5 + Tailwind CSS v4 frontend. Apply the Deltek design system from the External Exposure Triage project (marine blue `#1742F5`, navy `#070D63`, Figtree font, tinted status badges). Add a three-way theme toggle (Light / System / Dark) with localStorage persistence and no flash on load. FastAPI gains a `GET /api/search` JSON endpoint; the existing `POST /search` HTML form endpoint is preserved unchanged.

---

## Problem Frame

The Access Inventory UI is a plain Jinja2 template with hand-written Atlassian-blue CSS — no Deltek branding, no dark mode, no component structure. The sister tool (External Exposure Triage) has a mature Deltek design system. This plan migrates Access Inventory onto that system, making both tools feel like a cohesive security platform.

---

## Requirements Trace

- R1. React + Vite + Tailwind v4 frontend replaces `web/templates/index.html`
- R2. Deltek color tokens, Figtree font, gradient header applied exactly as in Triage
- R3. Three-way theme toggle (Light / System / Dark) with localStorage + data-theme, no FOUC
- R4. `GET /api/search?q=` JSON endpoint added to FastAPI; React calls it
- R5. All existing features carry over: search, AD profile card, tool access table with status badges, multi-match picker list
- R6. `npm run build` produces a `dist/` FastAPI can serve
- R7. Existing Python `pytest` suite passes unchanged

---

## Scope Boundaries

- No changes to collector, database, migrations, or any Python business logic
- No authentication / login UI
- Mobile-responsive layout is nice-to-have, not required for v1
- `POST /search` HTML form endpoint is preserved (not removed) for curl/testing convenience

### Deferred for Later

- Pagination of tool access rows
- Keyboard navigation / accessible focus trap in picker list
- Toast notifications for copy-to-clipboard

---

## Context & Research

### Relevant Code and Patterns

- `web/app.py` — FastAPI app; currently has `GET /` and `POST /search`; needs `GET /api/search` added and a static-file mount for `web/frontend/dist/`
- `web/queries.py` — `get_ad_profile()`, `get_tool_access()`, `search_users_by_name()`, `search_users_by_username()` — all return `list[dict]` or `dict | None`; these are the data sources the new JSON endpoint wraps
- `web/templates/index.html` — current template; kept as fallback but no longer the primary UI
- External Exposure Triage `frontend/static/css/styles.css` — CSS token source of truth (not copied, referenced)
- External Exposure Triage `frontend/static/img/ProductSecurity_HD.png` — logo asset to copy

### External References

- Tailwind CSS v4 dark mode: `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *))` in CSS replaces the v3 `darkMode` config key entirely
- Tailwind v4 theme bridging: `@theme { }` block maps Tailwind utility tokens to CSS vars; `@layer base` scopes CSS vars per data-theme selector
- Vite 5 + FastAPI: `server.proxy` with `target: 'http://localhost:8001'`, `changeOrigin: true`; keep `base: '/'`
- Pre-paint theme script: inline `<script>` (no `type="module"`) in `<head>` before React root — synchronous, blocks paint, Vite does not transform it

### Institutional Learnings

- None in `docs/solutions/` (directory does not exist yet)

---

## Key Technical Decisions

- **API contract: Option A** (`GET /api/search?q=`): Cleaner for React (`fetch` with query string), no content-negotiation complexity. Existing `POST /search` stays untouched so curl/test usage is unaffected.
- **Tailwind v4, not v3**: v3 is maintenance-only as of 2026. v4 eliminates `tailwind.config.js`, PostCSS, and `content` globs — simpler setup with `@tailwindcss/vite` plugin.
- **Dark mode via `@custom-variant`**: Requirements doc referenced v3 `darkMode: ['class', '[data-theme="dark"]']` — this does not exist in v4. Replaced with `@custom-variant dark` directive in `index.css`. HTML-side convention (`data-theme="dark"` on `<html>`) is unchanged.
- **`@vitejs/plugin-react-swc`** over `@vitejs/plugin-react`: SWC-based Fast Refresh is faster; no functional difference for this project.
- **FastAPI catch-all route**: Must be registered after all API routes so React Router can handle client-side navigation on direct URL access or refresh.
- **TypeScript**: Use `.tsx`/`.ts` throughout — consistent with modern Vite + React scaffolding; no additional runtime cost.
- **No SSR**: FastAPI serves `dist/index.html` for all non-API routes. React handles all routing client-side.

---

## Open Questions

### Resolved During Planning

- **Option A vs B for API contract**: Resolved as Option A (`GET /api/search?q=`). See Key Technical Decisions.
- **Tailwind v3 vs v4**: Resolved as v4. `@custom-variant` replaces `darkMode` config. See Key Technical Decisions.
- **PostCSS required?**: No — `@tailwindcss/vite` plugin handles everything. No `postcss.config.js` needed.

### Deferred to Implementation

- Exact Vite port for dev server (`:5173` default, may conflict if already in use — implementer chooses)
- Whether `web/templates/index.html` is kept or eventually removed (keep for now; decision at next iteration)

---

## Output Structure

```
web/
├── frontend/                    ← NEW: Vite project root
│   ├── index.html               ← Vite entry; contains pre-paint theme script
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx             ← React entry point
│   │   ├── index.css            ← Tailwind imports + @custom-variant + @theme + @layer base
│   │   ├── App.tsx              ← Root component; manages search state
│   │   ├── api.ts               ← fetch wrapper for /api/search
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── ThemeToggle.tsx
│   │       ├── SearchBox.tsx
│   │       ├── ErrorBanner.tsx
│   │       ├── PickerList.tsx
│   │       ├── ProfileCard.tsx
│   │       ├── ToolAccessTable.tsx
│   │       ├── StatusBadge.tsx
│   │       └── EmptyState.tsx
│   └── dist/                    ← Build output (git-ignored)
├── static/                      ← NEW: FastAPI static assets
│   └── img/
│       └── ProductSecurity_HD.png   ← Copied from External Exposure Triage
└── app.py                       ← Modified: add /api/search, mount dist/
```

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

**Theme switching flow:**

```
Browser load
  → <script> in <head> reads localStorage.theme
  → Sets document.documentElement.setAttribute('data-theme', value)
  → CSS @custom-variant dark selects [data-theme=dark] descendants
  → Tailwind dark: utilities activate
  → React hydrates; ThemeToggle reads current data-theme to show active state
  → User clicks toggle → ThemeToggle writes localStorage + sets data-theme
  → All dark: utilities reactivate instantly (no re-render needed for CSS)
```

**Data flow (search):**

```
SearchBox submits query
  → App.tsx calls api.ts fetch('/api/search?q=...')
  → FastAPI GET /api/search reads q param
  → Runs same detection logic as POST /search (email / fullname / username)
  → Returns JSON: { ad_profile, tool_access, picker_users, error }
  → App.tsx sets state
  → Renders PickerList (if picker_users) OR ProfileCard + ToolAccessTable (if ad_profile)
```

**FastAPI route registration order (critical):**

```
1. GET /api/search          ← registered first
2. GET /api/...             ← any future API routes
3. StaticFiles mount dist/  ← registered last; catch-all for SPA
```

---

## Implementation Units

- [ ] U1. **Vite + React + Tailwind v4 project scaffold**

**Goal:** Create the `web/frontend/` Vite project with React 18, TypeScript, Tailwind v4, and the pre-paint theme script in `index.html`. Running `npm run dev` should show an empty React app.

**Requirements:** R1, R6

**Dependencies:** None

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/tsconfig.json`
- Create: `web/frontend/vite.config.ts`
- Create: `web/frontend/index.html`
- Create: `web/frontend/src/main.tsx`
- Create: `web/frontend/src/index.css`
- Create: `web/frontend/src/App.tsx` (minimal shell)

**Approach:**
- Scaffold with Vite's React-TS template as the starting point (`vite@5`, `@vitejs/plugin-react-swc`, `react@18`, `react-dom@18`, TypeScript)
- Install `tailwindcss@4` and `@tailwindcss/vite@4` — no PostCSS, no `tailwind.config.js`
- Add `@tailwindcss/vite` to vite plugins array
- `index.css`: `@import "tailwindcss"`, then `@custom-variant dark` directive, then `@theme {}` block with Deltek color tokens, then `@layer base` with light/dark CSS variable assignments per `[data-theme]` selector
- `index.html`: add inline `<script>` (no `type="module"`) before the React root `<div>` that reads `localStorage.theme` and sets `data-theme` on `<html>` — prevents FOUC
- `vite.config.ts`: `base: '/'`, `server.proxy` targeting `http://localhost:8001`, `build.outDir: '../dist'` (relative to `web/frontend/`, outputs to `web/frontend/dist/`)
- Add `web/frontend/dist/` to `.gitignore`

**Patterns to follow:**
- Pre-paint script pattern from External Exposure Triage `frontend/templates/index.html` (reads `localStorage.getItem('theme')`, sets attribute if `'light'` or `'dark'`, no-ops for system)
- Tailwind v4 `@custom-variant dark` pattern (research confirmed)

**Test scenarios:**
- Test expectation: none — this unit is pure scaffolding with no behavioral logic. Verification is manual (dev server starts, empty app renders, `npm run build` succeeds).

**Verification:**
- `npm install` and `npm run dev` succeed with no errors
- Empty React app renders in browser
- `npm run build` produces `web/frontend/dist/index.html` and asset files
- `index.html` contains the pre-paint `<script>` block before `<div id="root">`

---

- [ ] U2. **Deltek design tokens and theme toggle component**

**Goal:** Implement the full Deltek CSS token layer in `index.css` and build the `ThemeToggle` component. Theme switching must work — toggling Light/System/Dark should visibly change colors with no page reload.

**Requirements:** R2, R3

**Dependencies:** U1

**Files:**
- Modify: `web/frontend/src/index.css`
- Create: `web/frontend/src/components/ThemeToggle.tsx`
- Create: `web/static/img/ProductSecurity_HD.png` (copy from External Exposure Triage)

**Approach:**
- In `index.css`, complete the `@theme {}` block mapping Tailwind tokens to CSS vars: `--color-bg-primary: var(--bg-primary)`, `--color-text-primary: var(--text-primary)`, etc.
- In `@layer base`, define CSS vars scoped to `[data-theme="light"]` and `[data-theme="dark"]` using exact token values from requirements doc
- System mode: when no `data-theme` attribute is set, use `@media (prefers-color-scheme: dark)` as fallback in `@layer base`
- `ThemeToggle`: three-button pill with `role="radiogroup"` / `role="radio"` / `aria-checked`; on click writes `localStorage.theme` and calls `document.documentElement.setAttribute('data-theme', value)` (or removes the attribute for System); reads initial state from `document.documentElement.getAttribute('data-theme')` or `localStorage.theme`

**Patterns to follow:**
- Triage theme button structure: `id="theme-light"`, `id="theme-system"`, `id="theme-dark"`, radio roles
- Triage pre-paint + toggle interaction pattern from `frontend/static/js/dashboard.js:194-201`

**Test scenarios:**
- Happy path: Click Dark → `data-theme="dark"` on `<html>`, `localStorage.theme === 'dark'`, dark: utilities activate
- Happy path: Click Light → `data-theme="light"` on `<html>`, light CSS vars activate
- Happy path: Click System → `data-theme` attribute removed from `<html>`, OS preference governs
- Persistence: Reload page after setting Dark → data-theme is set before React hydrates, no flash of light theme
- Edge case: `localStorage.theme` is a value other than `'light'` or `'dark'` (e.g. corrupted) → pre-paint script does nothing, System fallback applies

**Verification:**
- All three toggle states visibly change the page background and text colors
- Refreshing the page in Dark mode does not show a light flash before the dark styles apply
- `aria-checked` attribute on toggle buttons matches the active state

---

- [ ] U3. **Header and page shell**

**Goal:** Build the `Header` component (gradient, logo, title, ThemeToggle) and the top-level page shell in `App.tsx` with the search box slot and footer.

**Requirements:** R2, R5

**Dependencies:** U2

**Files:**
- Create: `web/frontend/src/components/Header.tsx`
- Modify: `web/frontend/src/App.tsx`

**Approach:**
- `Header`: flex row, `linear-gradient(135deg, #1742F5 0%, #070D63 100%)` as background (via Tailwind CSS — use `bg-gradient-to-br from-deltek-blue to-deltek-navy` or an inline style if gradient direction needs exact degrees), rounded-xl, shadow; left side has `ProductSecurity_HD.png` logo (fixed 140×140, right border divider); center has title text in Figtree white; top-right has `ThemeToggle`
- `App.tsx`: holds `query`, `adProfile`, `toolAccess`, `pickerUsers`, `error`, `loading` state; renders Header, SearchBox slot, conditional result sections, Footer

**Patterns to follow:**
- Triage `.header` + `.header-logo-block` + `.header-text-block` + `.theme-toggle` layout from `frontend/static/css/styles.css:212-359`

**Test scenarios:**
- Happy path: Header renders with logo, title "Access Inventory Lookup", and ThemeToggle visible
- Happy path: Page shell renders with footer text "Deltek Global Information Security — Access Inventory v1"
- Visual: gradient direction and logo size match Triage header (manual verification)

**Verification:**
- Header visible with gradient, logo, and toggle in browser
- Footer text correct
- No console errors

---

- [ ] U4. **FastAPI `GET /api/search` JSON endpoint**

**Goal:** Add a `GET /api/search?q=` endpoint to `web/app.py` that runs the same detection and search logic as `POST /search` but returns JSON instead of an HTML template.

**Requirements:** R4, R5

**Dependencies:** None (parallel with U1–U3)

**Files:**
- Modify: `web/app.py`
- Modify: `tests/test_web/test_app.py`

**Approach:**
- Extract the search detection and routing logic from `POST /search` into a shared private function `_run_search(pool, query) -> dict` that returns `{"ad_profile": ..., "tool_access": [...], "picker_users": [...], "error": ...}`
- `GET /api/search` calls `_run_search` and returns `JSONResponse`
- `POST /search` calls `_run_search` and passes the dict to the template (same behavior as today)
- Query parameter name: `q` (matches requirements doc Option A)
- Input validation: apply the same `_SAFE_QUERY_RE` check; return `{"error": "Invalid search input: ...", ...}` with HTTP 200 (consistent with existing POST behavior — error in payload, not HTTP status)
- Add FastAPI `StaticFiles` mount for `web/frontend/dist/` at path `/` — register after all API routes; serve `index.html` as catch-all for non-API paths

**Patterns to follow:**
- Existing `POST /search` detection logic in `web/app.py` (email / fullname / single-token branches)
- `asyncio.create_task` + `gather` pattern already used in the POST endpoint

**Test scenarios:**
- Happy path: `GET /api/search?q=kibria@deltek.com` returns JSON with `ad_profile` dict and `tool_access` list
- Happy path: `GET /api/search?q=michael` returns JSON with `picker_users` list when multiple matches
- Happy path: `GET /api/search?q=detek3kg` (username) returns JSON with single `ad_profile` resolved
- Happy path: `GET /api/search?q=michael paguio` (full name, space) returns JSON with single match profile
- Error path: `GET /api/search?q='; DROP TABLE` returns `{"error": "Invalid search input: ..."}` in JSON body
- Edge case: `GET /api/search` (missing `q`) — FastAPI 422 validation error (acceptable; document in test)
- Integration: `POST /search` still returns HTML after refactor (existing tests must pass)

**Verification:**
- `curl 'http://localhost:8001/api/search?q=test@deltek.com'` returns valid JSON
- All existing `pytest tests/test_web/` tests pass
- New tests for `GET /api/search` pass

---

- [ ] U5. **Search, results, and picker components**

**Goal:** Build `SearchBox`, `ErrorBanner`, `PickerList`, `ProfileCard`, `ToolAccessTable`, `StatusBadge`, `EmptyState`, and the `api.ts` fetch wrapper. Wire them into `App.tsx` so a full search round-trip works end-to-end.

**Requirements:** R5

**Dependencies:** U3, U4

**Files:**
- Create: `web/frontend/src/api.ts`
- Create: `web/frontend/src/components/SearchBox.tsx`
- Create: `web/frontend/src/components/ErrorBanner.tsx`
- Create: `web/frontend/src/components/PickerList.tsx`
- Create: `web/frontend/src/components/ProfileCard.tsx`
- Create: `web/frontend/src/components/ToolAccessTable.tsx`
- Create: `web/frontend/src/components/StatusBadge.tsx`
- Create: `web/frontend/src/components/EmptyState.tsx`
- Modify: `web/frontend/src/App.tsx`

**Approach:**
- `api.ts`: `searchUsers(q: string): Promise<SearchResult>` — `fetch('/api/search?q=...')`, returns typed result
- `SearchBox`: controlled input, submit button, loading spinner state; `placeholder="e.g. Firstname Lastname, email@deltek.com, or username"`; focus ring uses `ring-deltek-blue`
- `ErrorBanner`: red alert using `--text-error` / `--bg-error` tokens (map from Triage `.error-banner` pattern)
- `PickerList`: table with Full Name / Email / Department / Job Title columns; each row is clickable (calls `onSelect(email)` which triggers a new search); shows overflow notice when 50 results returned; header shows "N users found for 'query'"
- `ProfileCard`: grid layout with 6 fields (Email, Full Name, Job Title, Department, Employee ID, AD Status); AD Status uses `StatusBadge` with active/inactive
- `ToolAccessTable`: table with Tool/Environment / Username / Status / Role / Last Login columns; `StatusBadge` per row; username in JetBrains Mono font class
- `StatusBadge`: tinted pill; variants `active` (green), `inactive` (red), `active-access` (blue, for BlackDuck "Active Access" value), `other` (gray); use inline style for tint bg `rgba()` values — Tailwind utility classes cannot express dynamic rgba opacity without JIT arbitrary values
- `EmptyState`: "No active tool access found for **{query}**" paragraph

**Patterns to follow:**
- Triage `.result-card` / `.result-card-header` pattern for cards
- Triage `.badge-ip` / `.badge-domain` tinted badge pattern for StatusBadge
- Triage `.omx` compact table pattern for ToolAccessTable
- Triage `.form-input` focus/border transition pattern for SearchBox

**Test scenarios:**
- Happy path: SearchBox submit with valid email → loading state shown → ProfileCard and ToolAccessTable render with API response
- Happy path: Search with multiple matches → PickerList renders with correct row count header
- Happy path: PickerList row click → triggers new search for that email → profile loads
- Happy path: Search with no matches → EmptyState renders
- Happy path: StatusBadge renders correct color for `active`, `inactive`, `Active Access`, and unknown status values
- Edge case: `tool_access` is empty but `ad_profile` exists → ProfileCard renders, EmptyState renders below
- Edge case: API returns `error` string → ErrorBanner renders above picker/profile sections
- Edge case: Username with monospace font class applied in ToolAccessTable

**Verification:**
- Full search round-trip works in browser: type a name, see picker or profile
- Clicking a picker row loads the profile
- Status badges use the correct Deltek colors
- Dark mode toggling changes all card/table/badge colors correctly

---

- [ ] U6. **Production build wiring and FastAPI static serve**

**Goal:** Complete the FastAPI → Vite dist integration so `npm run build` produces a `dist/` that FastAPI serves correctly, including the SPA catch-all route.

**Requirements:** R1, R6, R7

**Dependencies:** U4, U5

**Files:**
- Modify: `web/app.py` (catch-all and StaticFiles mount — partially done in U4, finalized here)
- Create: `web/frontend/.gitignore` (ignore `dist/`, `node_modules/`)

**Approach:**
- In `web/app.py`, after all API routes, mount `web/frontend/dist/` as `StaticFiles(directory="web/frontend/dist", html=True)` at path `"/"`; the `html=True` flag enables directory index (serves `index.html` for unknown paths — the SPA catch-all)
- Add a guard: if `web/frontend/dist/` does not exist at startup, skip the mount and log a warning rather than crashing (allows FastAPI to start without a built frontend during backend-only development)
- Ensure `vite.config.ts` `build.outDir` resolves correctly relative to `web/frontend/` — confirm the dist ends up at `web/frontend/dist/`
- Verify `npm run build` then `uvicorn web.app:app` at port 8001 serves the React app at `/`

**Patterns to follow:**
- FastAPI `StaticFiles` with `html=True` for SPA serving (standard FastAPI pattern)

**Test scenarios:**
- Test expectation: none for automated tests — this unit is build/serve wiring. Verification is manual.
- Note: Existing `pytest` suite must still pass after the mount is added (confirmed by R7 requirement — the `GET /` route is now served by StaticFiles but existing tests mock the pool and don't test static file serving)

**Verification:**
- `npm run build` exits 0 and produces `web/frontend/dist/index.html`
- `uvicorn web.app:app --port 8001` starts without errors even when `dist/` exists
- Navigating to `http://localhost:8001` in browser shows the React app
- `http://localhost:8001/api/search?q=test` still returns JSON (API routes take precedence over static mount)
- Existing `pytest` passes: `python3 -m pytest -q`

---

## System-Wide Impact

- **Interaction graph:** `GET /` previously rendered Jinja2; after U6 it is handled by StaticFiles. `POST /search` is unchanged. `GET /api/search` is new. No callbacks, middleware, or observers are affected.
- **Error propagation:** API errors are returned in the JSON payload as `{"error": "..."}` — React renders `ErrorBanner`. HTTP-level errors (500, 422) are handled by the `api.ts` fetch wrapper with a generic error message surfaced to `ErrorBanner`.
- **State lifecycle risks:** None — no state persistence changes. The React frontend is stateless between sessions (search results not cached).
- **API surface parity:** `POST /search` HTML form endpoint is preserved unchanged. Existing curl/test workflows unaffected.
- **Integration coverage:** U4 tests cover `GET /api/search` end-to-end through FastAPI + mocked DB. U5 tests cover React component behavior with mocked API responses. A manual smoke test (U6 verification) confirms the full stack.
- **Unchanged invariants:** All Python collector logic, database schema, and migration files are untouched. The `pytest` suite covering collector and database code must continue to pass with no changes.

---

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Tailwind v4 `@custom-variant` dark mode is new — less StackOverflow coverage than v3 | Research confirmed the exact pattern; `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *))` is documented in Tailwind v4 official docs |
| FastAPI `StaticFiles(html=True)` catch-all may intercept `/api/search` if mounted in wrong order | U4 explicitly registers API routes before the static mount; `html=True` only fires for paths not matched earlier |
| `web/frontend/dist/` not present when FastAPI starts during backend-only dev | U6 adds a startup guard that skips the mount and logs a warning if `dist/` is absent |
| External Exposure Triage logo (`ProductSecurity_HD.png`, 961 KB) is a large asset | Copy directly — no processing needed. Vite hashes and caches it at build time |
| Vite dev server port conflict with existing processes | Default `:5173`; implementer can adjust in `vite.config.ts` if needed |

---

## Documentation / Operational Notes

- Add `web/frontend/` and `web/frontend/dist/` to `.gitignore` at repo root (or `web/frontend/.gitignore`)
- Dev workflow: start FastAPI (`uvicorn web.app:app --reload --port 8001`) in one terminal; start Vite (`npm run dev` in `web/frontend/`) in another; browser points to `:5173`
- Production: `npm run build` then restart uvicorn; FastAPI serves `dist/` directly — no Node.js needed in production
- `npm run build` should be added to any CI pipeline before running Python tests that check the full stack

---

## Sources & References

- **Origin document:** [docs/brainstorms/react-tailwind-ui-requirements.md](docs/brainstorms/react-tailwind-ui-requirements.md)
- Tailwind v4 dark mode: https://tailwindcss.com/docs/dark-mode
- Tailwind v4 theme variables: https://tailwindcss.com/docs/theme
- External Exposure Triage CSS tokens: `External Exposure Triage/frontend/static/css/styles.css`
- FastAPI StaticFiles + SPA pattern: https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/
