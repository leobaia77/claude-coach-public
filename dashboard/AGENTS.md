# AI Coach Dashboard — Agent Guide

A self-contained web dashboard (the athlete's "coach cockpit"): a single-screen,
phone-friendly view of biometrics, the 1000 lb-Club goal, quick actions, configurable
plots, a TrainingPeaks-style compliance calendar, and an agent chat panel.

**Stack:** Vite + React 18 + TypeScript (frontend) · Express 4 + tsx (backend) ·
plain CSS · hand-rolled dependency-free SVG charts. No UI framework, no chart library.

---

## Run it

```bash
npm install

# UI work (recommended) — frontend only, renders off mock data in src/seed.ts.
# No backend, no API key, no real health data needed.
npm run dev:web          # → http://localhost:4280

# Full stack (only if you're touching the API)
npm run dev              # web :4280  +  api :8787

# Verify before you call a task done:
npm run typecheck        # tsc (frontend + server)
npm run build            # tsc --noEmit && vite build
```

The Vite dev server proxies `/api/*` → `http://localhost:8787`. When the API isn't
running, the frontend **falls back to the mock data in `src/seed.ts`** — so the whole
UI is buildable and previewable with zero backend.

---

## Where things live

```
src/                 FRONTEND — almost all UI work happens here
  main.tsx           React mount (tiny)
  App.tsx            Composition + state, 3-column layout, refresh / chat / day-click wiring
  components.tsx     ★ All panels + primitives (the big file)
  styles.css         ★ Entire design system: CSS variables, layout, every component style
  seed.ts            ★ TypeScript data models + mock/fallback data
  api.ts             Client: getState / getReports / streamChat (SSE), CoachState type
server/
  index.ts           BACKEND — Express: /api/state, /api/reports, /api/chat (Claude SDK)
data/
  coach-state.json   Live data contract the server serves  ⚠ REAL personal health data
deploy/  logs/  dist/  node_modules/   ← ops / build artifacts, ignore for UI work
```

### The four files you'll touch for UI
`src/components.tsx` (panels) · `src/styles.css` (all styling) · `src/App.tsx` (layout/state) ·
`src/seed.ts` (data shape + mock data).

### Components in `components.tsx`
- **Active:** `Header`, `BiometricsPanel`, `GoalsPanel`, `ActionsPanel`, `PlotsPanel`,
  `CompliancePanel`, `RecentChatsPanel`, `ChatPanel`, `Toast` — plus primitives
  `Icon`, `Sparkline`, `MiniViz`, `WorkingDots`.
- **Legacy / unused** (safe to ignore; do not build on them): `Chart`, `ReportsPanel`, `DayModal`.

---

## Conventions — match these

- **Light theme only.** Use the CSS variables in `:root` (top of `styles.css`):
  `--bg`, `--card`, `--border`, `--text`, `--muted`, `--accent` (`#e2562a` orange),
  `--good`/`--warn`/`--bad`/`--info`, `--radius`, `--shadow`. Don't hard-code colors;
  don't introduce a dark theme or gradients.
- **No new runtime dependencies.** Charts are hand-rolled inline SVG (`Sparkline`,
  `MiniViz`). Do **not** add Chart.js / Recharts / D3 / Tailwind / a component library /
  CSS-in-JS. Ask first if you think you need one.
- **Plain CSS** in `styles.css`, class-based, organized in commented sections. No inline
  style objects except tiny dynamic values (e.g. a computed width %).
- **TypeScript, typed props.** UI models live in `seed.ts`; the server contract lives in
  `api.ts` (`CoachState`). If you change the data shape, update **both** `api.ts` and
  `server/index.ts` so they stay in sync.
- **Layout:** 3 columns — `.col-left` (fixed) · `.col-mid` (grows) · `.col-right` (fixed).
  Panels sit in `Card` wrappers and should **flex to their content** (no large empty
  space). Configurable grids use `repeat(auto-fit, minmax(...))`.
- **Persisted prefs:** which biometrics/plots are shown is saved to `localStorage`
  (`coach.bioShown`, `coach.plotShown`). Preserve that behavior.
- **Keep it one screen.** It's a cockpit, not a scrolling page — dense, legible, fast.

---

## Out of scope / do not touch

- **`.env`** — contains an API key. Never read, print, log, or commit it. UI work never needs it.
- **`data/coach-state.json`** — REAL biometrics/lifts. Don't commit new real values and don't
  paste its contents into logs/PRs. For UI fixtures, edit the **mock data in `seed.ts`** instead.
- **`server/index.ts`, `deploy/`** — backend/ops. Leave them for UI tasks.

## Definition of done
`npm run typecheck` clean · `npm run build` succeeds · UI renders at `:4280` via `npm run dev:web`.
