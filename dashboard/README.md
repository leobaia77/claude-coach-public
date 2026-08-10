# Coach Dashboard

A self-hosted personal cockpit for the AI Coach — biometrics, goals, reports, and
agent chat in one always-on place, reachable from your phone.

## Stack
- **Vite + React + TypeScript** (frontend, dependency-light, hand-built charts via SVG — no chart lib)
- Plain CSS design system (dark theme, responsive 3-column → single-column on mobile)
- Phase 2+ adds a Node backend (data API) and the Claude Agent SDK (chat brain)

## Run it (dev)
```bash
npm install --prefix dashboard
npm run dev --prefix dashboard          # runs BOTH: Vite (4280) + data API (8787)
# open http://localhost:4280
# on your phone (same Wi-Fi): http://<your-mac-LAN-IP>:4280
```
`npm run dev` uses `concurrently` to run the frontend and the backend together.
The Vite dev server proxies `/api/*` → the backend on :8787.

## API endpoints (Phase 2)
| Route | Returns |
|-------|---------|
| `GET /api/state` | athlete + biometrics + goals + plots + chats, with Big-3/weight **parsed live from `wiki.md`** over the `coach-state.json` snapshot |
| `GET /api/reports` | list of `reports/*.html` (date, title, type, auto-extracted summary) |
| `GET /api/reports/file/:name` | serves a report HTML (opens in a new tab from the dashboard) |
| `GET /api/charts` · `/api/charts/:name` | list + serve `charts/*.png` |
| `GET /api/health` | source availability check |

**Data contract:** `data/coach-state.json` is the structured snapshot the dashboard
reads. The coach keeps it current; `/api/state` overlays whatever it can parse live
from `wiki.md` (so the canonical wiki always wins for the Big-3 + bodyweight).

## Verify
```bash
npm run typecheck --prefix dashboard   # tsc --noEmit
npm run build --prefix dashboard       # tsc + vite build → dist/
```

## Build phases
| Phase | Status | Deliverable |
|-------|--------|-------------|
| **1** | ✅ done | Responsive dashboard shell, all 6 panels, seeded with real data, editable biometrics + configurable plots |
| **2** | ✅ done | Node/Express data API — parses `wiki.md` (Big-3 + weight live), serves `reports/` + `charts/`, structured `coach-state.json` contract. Frontend reads it with graceful fallback to the seed snapshot. |
| **3** | ✅ done | Claude Agent SDK chat — `/api/chat` SSE streaming, `CLAUDE.md` loaded via `settingSources:['project']`, Analyze buttons feed the chat. **Needs one-time `claude setup-token` → `dashboard/.env`** for subscription auth (headless creds), else shows a setup hint. |
| **4** | ✅ done | Always-on via launchd (`com.leo.coach-dashboard`, plist in `deploy/`) — prod server on :8787, RunAtLoad + KeepAlive. Remote-from-anywhere options (Tailscale / Cloudflare named tunnel + Access) in `deploy/REMOTE-ACCESS.md` (one-time login). |

## Layout (matches the wireframe)
```
┌─ Biometrics ─┐ ┌─ Quick actions ─┐ ┌─ Recent chats ─┐
│  (editable)  │ ├─ Visualizations ┤ │                │
├─ Goals ──────┤ │  (configurable) │ ├─ Coach chat ───┤
│  & progress  │ ├─ Reports ───────┤ │                │
└──────────────┘ └─────────────────┘ └────────────────┘
```
On phone: panels stack — actions, goals, biometrics, chat, plots, reports, history.

## Files
- `src/seed.ts` — data model + real seeded values (Phase 2 replaces with live API)
- `src/components.tsx` — all panels + dependency-free SVG charts
- `src/App.tsx` — composition + interaction state (toasts, show/hide toggles)
- `src/styles.css` — design system + responsive grid

## Notes
- This is **framework code** (no PII) — safe to commit. The `wiki.md`, `charts/`,
  and `reports/` it will read in Phase 2 stay gitignored.
- Health data never leaves your Mac (the reason for self-hosting over cloud).
