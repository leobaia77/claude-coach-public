# coachcalc — deterministic coaching math

Every number the coach can derive from a formula or table lives here, self-tested, so
prescriptions and projections are **reproducible and not LLM mental math**. Dependency-free
Python (stdlib only); mirrors the `bikeplan` package pattern. Interpretation/judgment stays
with the coach — this is only the arithmetic.

Run any module's self-test: `python3 -m coachcalc.<module>`.

## Modules
- **`strength.py`** — the 1,000 lb total math. `e1rm(weight, reps, rpe)` (RPE-based RTS/Helms
  %1RM table; Epley/Brzycki cross-checks), `working_weight(1rm, reps, rpe)` (prescribe a
  plate-rounded load), `pct_1rm(reps, rpe)`, `total()`, `gap_to(target, s, b, dl)`,
  `next_progression(current, lift, last_rpe)` (progress/hold/deload). Pounds.
- **`nutrition.py`** — Appendix D as a function. `targets(day_type, effort, bodyweight_lb,
  deficit_kcal)` → kcal/C/P/F (preserves stated kcal, applies effort carb deltas, scales by
  bodyweight, trims deficit fat-then-carbs holding the 185 g protein floor).
  `compare_to_target(...)` vs Nori actuals.
- **`pmc.py`** — Performance Management Chart. `compute_pmc(daily_tss)` → per-day
  CTL/ATL/TSB (42/7-day EWMAs, Banister impulse-response); `form_state(tsb)`,
  `ramp_rate(pmc)`.
- **`rideeval.py`** — Appendix B ride metrics, the single source of truth for report scripts.
  `evaluate_ride(stream, ftp_w, mass_kg)` → NP/IF/TSS/VI, avg/max, W/kg, mean-max power
  curve, terrain distribution, Pw:HR `decoupling(...)`. Reuses the `bikeplan` primitives.
- **`strain.py`** — coach-side analog to Oura's Symptom Radar. `physio_strain()` (combination-
  gated multivariate deviation vs personal baselines), `session_load()`/`acute_load()` (Foster
  sRPE for lifts + heat-adjusted TSS for rides → EWMA acute load), `strain_index()` (0–100
  morning score + **causal attribution**: training vs sleep vs possible-illness), and
  `predict_tomorrow()` (load-driven strain floor from the plan, a day early).
  **Honest scope:** body temperature and RHR — two of Oura's own inputs — are NOT exposed by
  the data feed, and the Symptom Radar label itself isn't pullable, so this does not replicate
  Oura day-for-day. Its edge is the load + attribution + prediction Oura structurally lacks.

- **`datastore.py`** — structured local daily-data store (writes `metrics/daily.csv` +
  `metrics/sessions.csv`). Idempotent `upsert_daily()` / `upsert_sessions()`, `load_*()`,
  and `export(which, dest)` to drop a clean CSV for Sheets/Excel. See `metrics/README.md`.

## Boundary — what is NOT here (stays coach judgment)
Session selection, which weak point to attack, deload/autoregulation calls, race A/B/C
classification, menu suggestions, and all narrative interpretation. Those are decisions, not
calculations.
