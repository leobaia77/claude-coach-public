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

## Getting started

Two documents do the work:

| | |
|---|---|
| **[SETUP.md](SETUP.md)** | for **you** — prerequisites, connecting Garmin / Strava / Hevy / biometrics / calendar, and verification. ~40–60 min, mostly authorising integrations. |
| **[FIRST_RUN.md](FIRST_RUN.md)** | for **Claude** — it probes which integrations actually answered, pulls your real baselines, interviews you about goals and constraints, builds your wiki, and proposes a first week. |

The short version:

```bash
git clone https://github.com/leobaia77/claude-coach-public.git ~/Claude-coach
cd ~/Claude-coach
python3 -m pip install numpy matplotlib
./install-garmin.sh            # if you use Garmin
claude
```

then tell Claude:

```
Read FIRST_RUN.md and onboard me.
```

**You don't need every integration.** With Garmin and a calendar it already plans and writes
your week. Each additional source adds fidelity, and Claude will tell you what each gap costs
rather than quietly working around it.

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

## What's in here

```
claude-coach/
├── CLAUDE.md          # the coaching logic — rules, protocols, appendices (auto-loaded)
├── SETUP.md           # human setup: integrations, deps, verification
├── FIRST_RUN.md       # onboarding script addressed to Claude
├── coachcalc/         # deterministic maths — strength e1RM, nutrition, PMC, ride evaluation
├── bikeplan/          # race/route pacing: W'bal optimiser, CdA calibration, goal-time solver
├── scripts/           # charts, sleep archiving, recall, state builder, update check
├── templates/         # blank athlete wiki
└── .claude/
    ├── settings.json  # SessionStart + PreCompact hooks
    └── commands/      # /coach-setup, /weekly-checkin
```

**No UI.** This is the coaching engine — you talk to it through Claude Code. All the analysis,
planning and writeback lives in the files above.

**The maths is in modules, not in the model's head.** `coachcalc` and `bikeplan` are plain,
dependency-light Python with tests behind them; the coach is instructed to call them and cite
the output rather than estimate. That's what stops an e1RM or a TSS from being a guess.

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
