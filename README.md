# AI Coach for Claude Code

A personal AI coaching system for endurance athletes and strength training — powered by Claude Code with live integrations to your health data, calendar, and communication tools.

**What it does each week:**
- Pulls your biometrics (HRV, sleep, weight, VO2max) and training data automatically
- Analyzes recovery and training load
- Asks for your subjective check-in via Slack + email
- Proposes next week's training plan
- Creates detailed calendar events with full meal plans (gram weights, per-meal macros, pre/post workout timing)
- Tracks your progress in a persistent athlete wiki


---

## 🔒 Privacy — read this first

**This repo ships code only. Your training and health data never leaves your machine.**

- `wiki.md`, `state/`, `memory/`, `metrics/`, `charts/`, `reports/`, `routes/` are **gitignored by
  default**. Fork this, push it anywhere, and none of your data travels with it.
- Route files (`.gpx`/`.fit`/`.tcx`) are ignored because their start/end coordinates reveal your
  home and workplace.
- Raw genetic exports are blocked by multiple patterns.
- API keys live outside the repo (`~/.config/...`) and `.env*` is ignored.
- The update checker makes **one unauthenticated GET** to the GitHub public API. It sends no
  telemetry, no identifiers, and nothing about you. Disable with `COACH_NO_UPDATE_CHECK=1`.

**If you want your own data version-controlled**, put it in a *separate private repo*. Do not
un-ignore those paths in a public fork.

### ⚠️ Optional: auto-sync your data

The author's personal setup uses a `Stop` hook that copies coach memory into the repo and runs
`git add -A && git push`. **That hook is deliberately NOT shipped here**, because combined with a
public remote it would publish your health data.

If you want it, you must consciously: (1) verify your remote is **private**, (2) decide which
personal paths to un-ignore, and (3) add the hook yourself in `.claude/settings.json`. Defaults
in this repo are safe by design.

---

## ⬆️ Updating

The coach checks for a new release once a day at session start and prints what changed.

```bash
node scripts/check_update.mjs        # check now
./scripts/upgrade.sh                 # pull + update deps + verify modules
```

`upgrade.sh` refuses to run if you have uncommitted changes to tracked files, and never touches
your personal data (it's untracked). See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- A Claude account (Pro or above recommended for MCP integrations)

---

## Step 1 — Clone this repo

```bash
git clone https://github.com/leobaia77/claude-coach-public.git
cd claude-coach-public
```

Or download the ZIP and extract it into a folder.

---

## Step 2 — Connect your integrations (MCP servers)

Open **Claude Code** → **Settings** → **Integrations**. Connect the services you use.

### Required (core functionality)
| Integration | What it's used for |
|------------|-------------------|
| **Google Calendar** | Create training events on your private calendar |
| **Nori** | Biometrics — HRV, sleep, weight, VO2max, activity data |

### Recommended
| Integration | What it's used for |
|------------|-------------------|
| **Garmin Connect** | Cardio sessions in detail — HR, power, training effect/load, performance metrics, HR + power zones — plus upload and scheduling of structured workouts straight to your watch. Recommended for cyclists, runners, and triathletes. *Manual install — see below.* |
| **Strava** | Segment exploration only — discovering routes, starred segments, and segment efforts on specific rides. Activity metrics come from Garmin Connect. |
| **Gmail** | Weekly review emails |
| **Slack** | Check-in messages and confirmations |
| **Hevy** | Strength training sessions (exercises, sets, reps, weights) |

### Optional
| Integration | What it's used for |
|------------|-------------------|
| **BodySpec** | DEXA body composition scans |

> **Note:** The system works with whatever you have connected. If an integration is missing, that feature is gracefully skipped. You can add integrations later and they'll be picked up automatically.

### Garmin Connect — manual install

Garmin Connect doesn't have an official Claude Code integration. Install the community MCP fork:

```bash
git clone https://github.com/leobaia77/garmin-connect-mcp.git ~/projects/garmin-connect-mcp
uv sync --directory ~/projects/garmin-connect-mcp
uv run --directory ~/projects/garmin-connect-mcp garmin-connect-mcp-auth   # prompts for Garmin email + password
claude mcp add --scope user garmin -- uv run --directory ~/projects/garmin-connect-mcp garmin-connect-mcp
```

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv). The fork at [leobaia77/garmin-connect-mcp](https://github.com/leobaia77/garmin-connect-mcp) adds `schedule` / `unschedule` actions to `manage-workouts` (not in upstream) so the coach can pin workouts to your Garmin calendar in one step. OAuth tokens persist to `~/.garminconnect/` after first auth.

---

## Step 3 — Open the project in Claude Code

```bash
# In the claude-coach folder:
claude
```

Or open the folder via **Claude Code desktop app** → **Open folder**.

The `CLAUDE.md` file activates automatically — Claude will behave as your coach whenever you're in this folder.

---

## Step 4 — Run the setup wizard

Type this in Claude Code:

```
/coach-setup
```

The setup wizard will:
1. Check which integrations are connected
2. Ask about your sport, goals, training frequency, and body stats
3. Pull your existing data (biometrics, workouts, DEXA scans if available)
4. Create your personal athlete wiki at `~/.coach_memory/wiki.md`
5. Generate personalized daily nutrition targets by day type
6. Optionally plan your first training week and create calendar events

Setup takes about 5–10 minutes.

---

## Weekly Usage

Every week, run:

```
/weekly-checkin
```

This triggers the full coaching cycle:
1. Pulls this week's biometrics and training data
2. Sends you check-in questions via Slack + Gmail
3. Waits for your subjective feedback
4. Proposes next week's plan
5. Creates calendar events with full meal plans once you confirm
6. Updates your athlete wiki

---

## File Structure

```
claude-coach/
├── CLAUDE.md                        # Core coaching instructions (auto-loaded)
├── README.md                        # This file
├── LICENSE                          # MIT
├── .claude/
│   └── commands/
│       ├── coach-setup.md           # Onboarding wizard (/coach-setup)
│       └── weekly-checkin.md        # Weekly coaching cycle (/weekly-checkin)
└── templates/
    └── wiki-template.md             # Blank athlete wiki (used by setup)
```

**Your athlete data lives outside this repo:**
- Wiki: `~/.coach_memory/wiki.md` — your persistent coaching memory
- Calendar events: your private Google Calendar (never your work calendar)

---

## Customization

### Change nutrition targets
After setup, edit Section 6 of your wiki (`~/.coach_memory/wiki.md`). The coach reads targets from the wiki, not from hardcoded values.

### Change the default week structure
Edit Section 7 of your wiki. The coach uses this as the template for every week.

### Add a new sport or discipline
Tell the coach in conversation. It will update your wiki and adjust zone prescriptions.

### Add a race
Tell the coach the date and name. It will update Section 5 of your wiki and start building toward it automatically.

---

## Privacy — at runtime

(For what is and isn't committed to git, see **🔒 Privacy — read this first** near the top.)

- Your athlete wiki (`~/.coach_memory/wiki.md`) is stored locally on your machine, not in this repo
- Training calendar events are created on your **private** calendar (not your work/primary calendar) — setup will confirm this
- Conversation contents (including pulled biometrics and training data) are processed by Claude during each coaching session — same as any Claude Code conversation
- Beyond Claude itself, no data leaves your machine except through the integrations you explicitly connect (Google Calendar, Gmail, Slack, etc.)

---

## Troubleshooting

**"I don't see the /coach-setup command"**
Make sure you're running Claude Code from inside the `claude-coach` folder. The slash commands in `.claude/commands/` are project-scoped — they only appear when Claude Code is opened in this directory.

**"Calendar events are going to my work calendar"**
During setup, you'll be asked to provide a private training calendar ID. If you skipped this, re-run `/coach-setup` or tell the coach: "My calendar events are going to the wrong calendar" and provide your private calendar ID.

**"An integration isn't working"**
Go to Claude Code Settings → Integrations and reconnect the integration. Then retry.

**"I want to reset and start over"**
Delete `~/.coach_memory/wiki.md` and run `/coach-setup` again.

---

## Contributing

Found a bug or want to improve the coaching logic? PRs welcome. The core coaching behavior lives in `CLAUDE.md` — that's the main file to edit for behavior changes.
