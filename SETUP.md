# Setup

Getting the coach running against your own data. Budget **40–60 minutes** — most of it is
authorising integrations, not configuration.

You do **not** need to do all of it. The coach degrades gracefully: with only Garmin and a
calendar it still plans and writes your week. Everything else adds fidelity.

---

## 0. What you're setting up

```
  your devices ──► MCP servers ──► Claude Code ──► your athlete wiki (local, private)
                                        │
                                        └──► Calendar / Hevy / Garmin  (writes, consent-gated)
```

Claude reads live data every session, reasons against the rules in `CLAUDE.md`, and writes
plans back to your calendar and apps **only after you approve them**.

---

## 1. Prerequisites

```bash
# Claude Code
# https://claude.ai/code

git clone https://github.com/leobaia77/claude-coach-public.git ~/Claude-coach
cd ~/Claude-coach
```

**Python 3.11+ with numpy and matplotlib** — the ride/sleep analysis and all charts need them.

```bash
python3 -m pip install numpy matplotlib
python3 -c "import numpy, matplotlib; print('ok')"
```

> ⚠️ If you have several Pythons (Homebrew, pyenv, system), make sure the one on your `PATH`
> is the one with numpy. A mismatch here is the single most common setup failure — the
> coaching still works, the charts silently don't. Test with the line above before moving on.

**Node 18+** for the update checker and the optional CGM capture script.

---

## 2. Connect your data sources

Each of these is independent. Add the ones you have.

### Garmin — cycling, running, HR, power, sleep, daily readiness
The richest single source. Install the fork that supports **scheduling** workouts to your
device (upstream can only upload):

```bash
./install-garmin.sh
```

It will ask for your Garmin Connect credentials and write a session locally. If a call later
returns `Failed to initialize Garmin client`, the session expired — re-run this script.

### Strava — segments, per-second streams
Needed for terrain-segmented ride analysis (gradient bands, climb-by-climb) and for segment
PRs. Create an API application at <https://www.strava.com/settings/api>, then:

```bash
mkdir -p ~/.config/strava-mcp
cat > ~/.config/strava-mcp/config.json <<'JSON'
{ "clientId": "...", "clientSecret": "...", "accessToken": "...", "refreshToken": "...", "expiresAt": 0 }
JSON
chmod 600 ~/.config/strava-mcp/config.json
```

Tokens expire hourly; the coach refreshes them itself when it sees `expiresAt` in the past.

### Hevy — strength training
Gets your API key from **Hevy → Settings → Developer**:

```bash
mkdir -p ~/.config && printf '%s' 'YOUR_HEVY_API_KEY' > ~/.config/hevy_api_key
chmod 600 ~/.config/hevy_api_key
```

Then create a folder in the Hevy app for coach-written routines (the reference setup calls it
`claude_coach`) and note its ID — Claude will ask for it and store it in your wiki.

### Biometrics — HRV, sleep, RHR, weight, labs
The reference setup uses a health-aggregator connector that pulls Oura, Apple Health and
clinical records. Any MCP that exposes daily HRV / sleep stages / RHR works; tell Claude which
tool names it should call and it will adapt.

> **Oura specifically cannot be scheduled.** It's a remote connector, so sleep has to be pulled
> inside a live session. If a morning pull comes back empty, open the Oura app to force a sync.

### Calendar and email
Connect Google Calendar and Gmail through your Claude connector settings.

> 🔴 **Create a SEPARATE calendar for training** and give Claude its ID. Do not point it at your
> work calendar. The coach writes full day-menus into event descriptions.

### Optional — CGM
If you wear one, a LibreLink MCP gives Claude live glucose. Without it the coach uses
clock-based fuelling and will say so rather than guessing.

---

## 3. Tell Claude who you are

```bash
cd ~/Claude-coach && claude
```

Then paste this:

```
Read FIRST_RUN.md and onboard me.
```

That file is written for Claude, not for you. It will check which integrations actually
responded, interview you about your sport, goals, injuries and schedule, pull your real
baselines rather than asking you to type them, and build your athlete wiki. See
[FIRST_RUN.md](FIRST_RUN.md) if you want to read it first.

---

## 4. Hooks

`.claude/settings.json` ships two hooks:

- **SessionStart** — injects `state/current.md` into every session, so your current week
  survives context compaction.
- **PreCompact** — reminds the model that the state file beats any conversation summary.

Restart `claude` once after setup so they load.

> The author's private setup has a third `Stop` hook that auto-commits and pushes. **It is
> deliberately not shipped** — combined with a public remote it would publish your health data.
> See the README before adding anything like it.

---

## 5. Daily use

Run `claude` from `~/Claude-coach` and talk to it.

| you say | it does |
|---|---|
| "pull and analyse my sleep" | Oura/biometrics → chart → interpretation → saved to your wiki |
| "review today's ride" | Garmin + Strava streams → terrain-segmented analysis vs the plan |
| "/weekly-checkin" | the full Sunday cycle: pull, evaluate, ask, propose, then push on your OK |
| "pull my workout" | Hevy sets, e1RM via the strength module, progression call |

**Nothing is written to your calendar, Garmin or Hevy without showing you the payload first.**

---

## 6. Verify

```bash
python3 -c "from coachcalc import strength, nutrition, pmc, rideeval; print('coachcalc ok')"
python3 -c "import bikeplan.plan; print('bikeplan ok')"
python3 -c "import numpy, matplotlib; print('charts ok')"
node scripts/check_update.mjs
```

Then ask Claude: **"which of my integrations are actually live right now?"** It will call each
one and report what answered — better than assuming.

---

## Troubleshooting

| symptom | cause |
|---|---|
| `No module named numpy` when charting | wrong Python on `PATH` — see §1 |
| `Failed to initialize Garmin client` | session expired → re-run `./install-garmin.sh` |
| Sleep pull returns empty | Oura hasn't synced — open the phone app |
| Strava 401 | token expired; the coach refreshes it, but check `expiresAt` in the config |
| Hevy `Unrecognized key(s) in object: 'rpe'` | RPE is a *workout* field, not a *routine* field — put targets in exercise notes |
| Claude writes to the wrong calendar | you gave it the wrong ID; fix it in your wiki §1 |
