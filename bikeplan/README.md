# bikeplan — race power-plan tool (Tier 1)

Forward race planning for the coach: given a course + rider params + target intensity,
it models a **power plan, predicted time, NP/IF/TSS/kJ, fueling & hydration**, and exports
an **HTML report** + a **Garmin structured-workout JSON**. Adapted from Best Bike Split's
core feature set; dependency-free Python (stdlib only), matches the repo's `reports/*.py` pattern.

## Use
```bash
# real course:
python3 -m bikeplan.plan --gpx path/to/course.gpx \
    --ftp 273 --weight-lb 238 --target-if 0.80 --temp 24 \
    --out reports/2026-xx_<race>_plan.html --title "<Race name>"

# demo on the built-in synthetic 40 km course (no GPX needed):
python3 -m bikeplan.plan --title "Demo" --out reports/demo.html
```
Key flags: `--cda` (0.32 road hoods / ~0.24 aero bars), `--crr` (0.004 good road),
`--headwind` m/s, `--elevation` m, `--bike-kg` (default 9),
`--strategy optimized|heuristic` (default **optimized** = true time-minimizer),
`--w-prime` (anaerobic reserve J, default 20000), `--cp` (critical power W; default = `--target-if`×FTP),
`--goal-time H:MM:SS` (inverse-solve the sustainable power needed to hit a finish time, then build the plan to it).

Outputs: `<out>.html` (report) + `<out>_garmin.json` (push via the Garmin MCP
`manage_workouts` upload+schedule). See `example_plan.html` / `example_plan_garmin.json`.

## Modules
- `physics.py` — power⇄speed model (gravity + rolling + aero + drivetrain). `python3 -m bikeplan.physics` runs a sanity self-test.
- `course.py` — GPX parse + resample + grade smoothing + climb detection (>250 m, >3%). Has a synthetic-course generator.
- `fueling.py` — kJ + duration → carbs/fluid/sodium (Appendix D + Leo's electrolyte rules).
- `optimizer.py` — **true time-minimizing optimizer**: W'bal dynamic program over the critical-power model. `python3 -m bikeplan.optimizer` self-tests (must beat constant power, climbs ≥ flats, W'bal-feasible).
- `goaltime.py` — inverse solver: given a target finish time, bisect the optimizer to the sustainable power (CP/IF) that hits it. `python3 -m bikeplan.goaltime` self-tests (recovers the goal within a minute).
- `cda.py` — **CdA estimation from a real ride** (whole-ride energy balance / Chung virtual-elevation). Calibrates the optimizer's aero input so predicted times are trustworthy. Self-test round-trips a synthetic ride at known CdA.
- `analyze.py` — retrospective helpers against a plan: `gradient_distribution` (%time/power/speed by grade band), `mean_max_power` (power-duration curve), `plan_vs_actual` (align a committed plan to the executed ride → per-band + total deltas, incl. first-half/second-half fade %). Operates on plain arrays the coach pulls from Garmin/Strava streams.
- `plan.py` — orchestrator (calls the optimizer by default; grade-banded heuristic as `--strategy heuristic` fallback) + HTML report (KPIs, optimizer card, **race-day cheat sheet**, climb table, **gradient distribution**, fueling, sampled segments) + Garmin export + CLI.

## The optimizer (default)
Minimises total time subject to a physiological constraint (Skiba **W'bal ≥ 0** with the
critical-power model) and a power ceiling — solved by dynamic programming over the
remaining-reserve state (Sundström-style; the rigorous form of Gordon 2005 / the
variational approach). It rides climbs/headwinds harder and descents easier, spending W'
where it buys the most time and banking it downhill — and never exhausts the reserve.
On the built-in hilly demo it saves ~3% vs constant power (matches the literature's ~189 s).
`--target-if`×FTP is used as the sustainable anchor (CP); `--w-prime` is the surge reserve.

## Papers
- Gordon (2005), *Optimising distribution of power during a cycling time trial* — vary power with gradient.
- de Jong/Wolf et al., *A Variational Approach to Determine the Optimal Power Distribution*.
- Dahmen; Sundström et al. — optimal-control / DP with W'bal.
- Skiba et al. (2012) — W'bal (critical-power) model.

## Honest limits
- Pacing is now a **true optimizer**, but it's only as good as its inputs: CdA/Crr/W'/CP are estimates. `cda.py` now calibrates CdA from a real steady ride — do that before trusting predicted time to the second.
- Wind is a **single scalar** headwind (no direction-vs-heading yet).
- CdA estimate is cleanest from a **steady effort at real speed**; coasting/braking/soft-pedal sections bias it. It solves CdA at a fixed Crr (not both jointly).
- `plan_vs_actual` aligns by gradient band (route-agnostic), not point-by-point GPS — robust to lap/GPS drift, but per-second overlay isn't wired yet.
- Elevation smoothing is light — very noisy GPX may over/under-count gain.
- W/kg shown uses total system mass. Predicted time is a model, not a guarantee.
