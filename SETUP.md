# Setup — run the AI Coach on another computer

This repo is a **portable clone of the coach**: rules, data, memory, and the dashboard.
Follow these steps to pull on a new machine and run with the latest data.

> Clone to **`~/Claude-coach`** (the hooks and dashboard assume this path).

```bash
git clone https://github.com/leobaia77/claude-coach-public.git ~/Claude-coach
cd ~/Claude-coach
```

## What's in the repo (synced via git)
- `CLAUDE.md` — the coach's full operating instructions (the "rules").
- `state/current.md` — **canonical current state** (this week's plan, flags). Auto-injected at session start.
- `wiki.md` — the athlete's full training/health log (profile, baselines, zones, goals, logs).
- `memory/` — durable coach memories, incl. `genome-insights.md` and `health-confidential-handling.md`.
- `charts/`, `reports/`, `hevy_routines/` — historical artifacts.
- `dashboard/` — the web cockpit (code + `data/coach-state.json`).
- `.claude/settings.json` — the three hooks (SessionStart / PreCompact / Stop), written portably.
- `.claude/commands/` — `/coach-setup`, `/weekly-checkin`.

## What is NOT in the repo (recreate locally)
1. **Secrets** — `dashboard/.env` (Anthropic API key). Recreate it:
   ```bash
   cp dashboard/.env.example dashboard/.env   # if an example exists; else create it
   # set ANTHROPIC_API_KEY=... and COACH_MODEL=claude-sonnet-4-6
   ```
2. **Build artifacts** — regenerate:
   ```bash
   cd dashboard && npm install && npm run build
   ```
3. **MCP servers** — Garmin, Hevy, Strava, Nori, Google Calendar, Gmail are configured per-machine
   (not in this repo). Re-add them with `claude mcp add ...` (see your MCP configs) so live data pulls work.

## Activate the coach's memory (one-time, important)
Claude Code's auto-memory reads from `~/.claude/projects/<sanitized-cwd>/memory/`, NOT from this
repo's `memory/`. To make the memories active on the new machine, copy them in once:
```bash
DEST="$HOME/.claude/projects/$(echo "$HOME/Claude-coach" | sed 's#/#-#g')/memory"
mkdir -p "$DEST"
cp -R ~/Claude-coach/memory/. "$DEST/"
```
After this, the `Stop` hook keeps repo `memory/` and the live auto-memory dir in sync automatically.

## Hooks (already portable)
`.claude/settings.json` carries the hooks and uses `$CLAUDE_PROJECT_DIR` + a computed memory path,
so they work under any username. On first run, open `/hooks` once (or restart `claude`) so Claude Code
loads them. From then on:
- **SessionStart** injects `state/current.md` into every session (survives compaction).
- **PreCompact** reminds the model the state file overrides the summary.
- **Stop** mirrors memory → repo and auto-commits + pushes to `origin/main`.

> Per-machine permission grants live in `.claude/settings.local.json` (gitignored) — you'll approve
> tool permissions again on the new machine; that's expected.

## Daily use
Just run `claude` from `~/Claude-coach`. The coach reads `state/current.md` + `wiki.md` at startup,
pulls live data from Hevy/Garmin/Nori, and auto-syncs changes back to GitHub when the session ends.
