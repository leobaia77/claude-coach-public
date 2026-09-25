# Changelog

## [1.1.0] — 2026-09-26

**Shared repo is now functionality-only — no UI.**
- Removed `dashboard/` and `railway.json` from the published tree, plus the files that only
  made sense alongside them (`coach_bridge.py`, `render_chart.py`, `/audit-app`, `launch.json`).
  The coach is complete without a UI; you talk to it through Claude Code.
- **`CLAUDE.md` is now GENERATED** from the maintainer's copy by `make_public_claude.py`, so the
  shared coaching logic can no longer drift. The previous hand-maintained copy was six weeks
  behind. Athlete-specific IDs become placeholders; the CGM section ships the *method* for
  deriving glucose rules instead of one athlete's conclusions.
- **New `SETUP.md`** — integration-by-integration setup (Garmin, Strava, Hevy, biometrics,
  calendar, optional CGM), dependency checks, and a troubleshooting table.
- **New `FIRST_RUN.md`** — onboarding instructions addressed to Claude: probe which integrations
  actually answered, pull real baselines rather than asking the athlete to type them, interview
  for goals and constraints, build the wiki, agree recovery gates, propose week one.
- Ships everything added since 1.1: air-quality watch, sleep archiving/plots, state builder,
  nightly consolidation, `recall.sh`, ride/day/climb charts, report generator.
- Generic modules no longer name the maintainer's athlete in docstrings.


All notable changes to claude-coach. Format follows [Keep a Changelog](https://keepachangelog.com/);
versioning is [semver](https://semver.org/).

The in-app update checker reads the bullet list from the latest GitHub release, so keep release
notes in the same bullet style as the entries below.

---

## [1.0.0] — 2026-08-09

First public release. An AI coaching system for endurance athletes who also lift, built on
Claude Code with MCP integrations, a deterministic calculation layer, and a local dashboard.

### Added — deterministic calculation engine
- `coachcalc.strength` — RPE-based e1RM (RTS %1RM table, Epley/Brzycki cross-check), working-weight
  prescription with plate rounding, total/gap tracking, progress-hold-deload logic
- `coachcalc.nutrition` — day-type × effort macro targets, bodyweight scaling, deficit application
  with a protein floor, and actual-vs-target comparison
- `coachcalc.pmc` — CTL/ATL/TSB from daily TSS (42/7-day EWMAs), form-state and ramp-rate reads
- `coachcalc.rideeval` — NP/IF/TSS/VI, mean-max power curve, Pw:HR decoupling, terrain distribution
- `coachcalc.strain` — physiological strain index, session/acute load, next-day prediction
- `coachcalc.datastore` — idempotent daily/session upserts with CSV export

### Added — race planning (`bikeplan`)
- Physics model (gravity + rolling + aero + inertia) over a GPX course
- **W′bal dynamic-programming optimizer** (Skiba critical-power model) that minimises time while
  never exhausting the anaerobic reserve — ~3% faster than constant power on hilly courses
- Goal-time solver: inverse-solves the sustainable power needed to hit a target finish
- CdA estimation from a real ride (energy balance / virtual elevation)
- Gradient distribution, mean-max power curve, and plan-vs-actual with first/second-half fade
- Self-contained HTML race report + Garmin structured-workout JSON export

### Added — integrations
- Garmin Connect, Strava, Hevy, Oura/biometrics, CGM (FreeStyle Libre 3 via LibreLinkUp),
  Google Calendar, Gmail
- Nightly CGM capture with granular CSV archiving
- Ride and sleep overlay charts (power + HR + glucose; hypnogram + HR + glucose)

### Added — dashboard
- React + Express dashboard with Claude Agent SDK chat, compliance calendar, configurable plots
- Optional multi-user mode: SQLite + auth + invite codes + per-user data isolation

### Added — this release
- `VERSION`, `CHANGELOG.md`, and an **update checker** (`scripts/check_update.mjs`) that compares
  your version against the latest GitHub release and shows what changed
- `scripts/upgrade.sh` — pulls, updates deps, verifies modules. Never touches personal data.

### Notes
- Personal training data is gitignored by default. See `.gitignore` and the Privacy section
  of the README — nothing about you leaves your machine.
- The update checker makes one unauthenticated request to the GitHub public API and sends
  no telemetry. Disable with `COACH_NO_UPDATE_CHECK=1`.
