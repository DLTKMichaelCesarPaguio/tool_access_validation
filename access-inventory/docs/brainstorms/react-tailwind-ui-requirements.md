# Access Inventory — React + Tailwind UI Redesign Requirements

**Created:** 2026-06-11  
**Status:** Ready for planning

---

## Problem Frame

The Access Inventory web UI is a plain HTML/Jinja2 template with hand-written CSS. It has no consistent branding, no dark mode, and no component reuse. The External Exposure Triage project (sister tool in the same security portfolio) has an established Deltek design system. Bringing the Access Inventory into that system makes the two tools feel like a cohesive platform and gives the Access Inventory a proper component foundation for future features.

---

## Actors

- **Security analysts** — primary users; look up user access during investigations or offboarding
- **Security engineers** — maintain the tool; need a clean component structure they can extend

---

## Goals

1. Redesign the frontend using **React + Tailwind CSS + Vite** — replaces the single Jinja2 `index.html`
2. Apply the **Deltek design system** from the External Exposure Triage project exactly — colors, typography, tokens, component patterns
3. Add a **three-way theme toggle** (Light / System / Dark) with localStorage persistence and no flash on load
4. FastAPI continues to own all data — the React app calls the existing `/search` endpoint (or a new JSON API equivalent) and renders the response
5. All existing features carry over: search input, AD profile card, tool access table with status badges, multi-match picker list

---

## Design System Reference

All tokens sourced from `External Exposure Triage` project (confirmed by codebase scan).

### Color Tokens

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--deltek-marine-blue` | `#1742F5` | `#1742F5` | Primary actions, links, focus rings |
| `--deltek-navy` | `#070D63` | `#070D63` | Header gradient end, hover states |
| `--deltek-rich-black` | `#00021D` | — | Body text on light |
| `--bg-primary` | `#FFFFFF` | `#0d0f1a` | Main surface |
| `--bg-secondary` | `#f9fafb` | `#111420` | Card headers, elevated surfaces |
| `--bg-tertiary` | `#f3f4f6` | `#1a1d2e` | Section backgrounds |
| `--text-primary` | `#00021D` | `#FFFFFF` | Body text |
| `--text-secondary` | `#3C454E` | `#9ca3af` | Secondary text |
| `--text-tertiary` | `#6b7280` | `#6b7280` | Muted/disabled |
| `--border-light` | `#e5e7eb` | `#1f2937` | Card borders |
| `--border-medium` | `#d1d5db` | `#374151` | Input borders |

### Status Badge Colors (match Triage badge pattern — tinted bg + colored text)

| Status | Text color | Background |
|---|---|---|
| active | `#1F8B3D` / `#3fb950` | `rgba(31,139,61,0.1)` |
| inactive | `#C7322B` / `#f85149` | `rgba(199,50,43,0.1)` |
| pending / other | `#3C454E` / `#9ca3af` | `rgba(60,69,78,0.1)` |
| Active Access (BlackDuck) | `#1742F5` | `rgba(23,66,245,0.1)` |

### Typography

- **Display / UI font**: Figtree (Google Fonts — weights 400, 500, 600, 700)
- **Monospace** (IPs, usernames, employee IDs): JetBrains Mono (weights 400, 500)

### Header

- `linear-gradient(135deg, #1742F5 0%, #070D63 100%)`
- Logo: `ProductSecurity_HD.png` from External Exposure Triage assets (copy into `web/static/img/`)
- `box-shadow: 0px 3px 10px 1px rgba(7,26,36,0.32)`
- `border-radius: 1rem`

### Tailwind Config Additions

Extend `tailwind.config` with:
- `colors.deltek-blue: '#1742F5'`
- `colors.deltek-navy: '#070D63'`
- `colors.deltek-black: '#00021D'`
- `fontFamily.sans: ['Figtree', ...defaultTheme.fontFamily.sans]`
- `fontFamily.mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono]`
- CSS variables for bg/text/border bridged via `@layer base` so dark mode tokens apply automatically

---

## Theme Toggle

### Behaviour
- Three states: **Light**, **System**, **Dark**
- Default: **System** (reads `prefers-color-scheme`)
- Persisted in `localStorage` key `theme`
- Applied via `data-theme` attribute on `<html>` element
- Pre-paint inline script in `index.html` reads `localStorage.theme` before React hydrates — prevents flash of wrong theme

### Implementation pattern (from Triage)
```js
// Inline in index.html <head> before any CSS
(function () {
  var t = localStorage.getItem('theme');
  if (t === 'light' || t === 'dark') {
    document.documentElement.setAttribute('data-theme', t);
  }
})();
```

```css
/* Tailwind darkMode: ['class', '[data-theme="dark"]'] */
/* System fallback via @media (prefers-color-scheme: dark) when no data-theme set */
```

### Toggle UI
- Three-button pill, same style as Triage: `[ ☀ Light | ⬤ System | ☾ Dark ]`
- Positioned top-right of the header card
- `role="radiogroup"`, each button `role="radio"` with `aria-checked`

---

## Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  HEADER  [gradient blue→navy]  [logo] [title] [toggle]  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  SEARCH BOX                                             │
│  [ Firstname Lastname, email, or username  ] [Search]   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  ERROR BANNER  (conditional)                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  PICKER LIST CARD  (when multiple matches)              │
│  "N users found for 'query'"                            │
│  ┌──────────┬──────────────┬────────────┬────────────┐  │
│  │ Full Name│ Email        │ Department │ Job Title  │  │
│  └──────────┴──────────────┴────────────┴────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  AD PROFILE CARD  (when profile found)                  │
│  Email · Full Name · Job Title · Dept · ID · AD Status  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  TOOL ACCESS CARD  (when profile found)                 │
│  ┌──────────────┬──────────┬────────┬──────┬──────────┐ │
│  │ Tool/Env     │ Username │ Status │ Role │ Last Login│ │
│  └──────────────┴──────────┴────────┴──────┴──────────┘ │
└─────────────────────────────────────────────────────────┘

Footer: "Deltek Global Information Security — Access Inventory v1"
```

---

## Components

| Component | Description |
|---|---|
| `Header` | Gradient header with logo, title, theme toggle |
| `ThemeToggle` | Three-way pill (Light/System/Dark) |
| `SearchBox` | Controlled input + submit, shows loading spinner |
| `ErrorBanner` | Red alert strip |
| `PickerList` | Multi-match results table; row click triggers new search |
| `ProfileCard` | AD profile fields in grid layout |
| `ToolAccessTable` | Tool access rows with `StatusBadge` per row |
| `StatusBadge` | Tinted pill — active/inactive/pending/other variants |
| `EmptyState` | "No access found" message when profile resolves but no tool rows |

---

## API Contract

FastAPI needs a JSON endpoint alongside (or replacing) the existing form POST. Two options — leave for planning to decide:

**Option A** — Add `GET /api/search?q=<term>` JSON endpoint; React calls it directly. Existing form POST stays for non-JS fallback (not required).

**Option B** — Convert existing `POST /search` to return JSON when `Accept: application/json`; React uses that.

Planning should pick one. The React app does not need SSR — FastAPI serves `index.html` for all routes, React handles routing client-side.

---

## Build & Serve

- **Frontend root**: `web/frontend/` (Vite project)
- **Build output**: `web/frontend/dist/`
- FastAPI mounts `dist/` as static files, serves `index.html` for `GET /`
- Dev: Vite dev server on `:5173` proxies `/api/*` to FastAPI on `:8001`
- `npm run build` produces the dist that FastAPI serves in production

---

## Scope Boundaries

**In scope:**
- Full visual redesign of `web/templates/index.html` → React components
- Deltek color tokens, Figtree font, dark/light/system toggle
- All existing features: search, AD profile, tool access table, picker list
- Static asset: copy `ProductSecurity_HD.png` into `web/static/img/`

**Deferred for later:**
- Pagination of tool access rows
- Keyboard navigation / accessible focus trap in picker
- Toast notifications for copy-to-clipboard actions

**Out of scope:**
- Changes to the collector, database, or any Python backend logic
- Authentication / login UI
- Mobile-optimised layout (responsive is nice-to-have, not blocking)

---

## Success Criteria

1. `npm run build` produces a working `dist/` that FastAPI serves
2. Theme toggle persists across page reloads with no flash of wrong theme
3. All three states (Light / System / Dark) render correctly
4. Search by email, name, and username all work end-to-end through the React frontend
5. Picker list click resolves to a profile view
6. Status badges match the color spec above
7. Header gradient and logo match the Triage dashboard visually
8. Existing Python tests (`pytest`) still pass — no backend changes
