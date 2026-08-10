"""
Race plan orchestrator — the Tier-1 "plan_race" capability.

Given a course (GPX or synthetic) + rider params + a target intensity, it:
  1. assigns a grade-aware power target to each segment (ride climbs a touch harder,
     soft-pedal descents) — a transparent heuristic, NOT a full optimizer (BBS does
     true optimization; this is an honest v1),
  2. scales the whole plan so realized NP == target (IF x FTP),
  3. computes per-segment speed/time via the physics model -> total time, NP, IF, TSS, kJ,
  4. builds a fueling/hydration plan,
  5. renders a self-contained HTML report + a Garmin structured-workout JSON.

CLI:
  python3 -m bikeplan.plan --gpx course.gpx --ftp 273 --weight-lb 238 \
      --target-if 0.80 --temp 24 --out reports/2026-xx_raceplan.html
  (omit --gpx to run on the built-in synthetic course for a demo)
"""
from __future__ import annotations
import argparse, base64, io, json, os, sys
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bikeplan.physics import Rider, air_density, power_for_speed, speed_for_power, normalized_power, tss
from bikeplan.course import Course, synthetic_rolling_course, build_course, _parse_trackpoints
from bikeplan.fueling import build_fuel_plan

LB_TO_KG = 1 / 2.20462


def grade_factor(grade: float) -> float:
    """Pacing shape (multiple of base power) by grade. Ride climbs harder, ease
    on flats-downhill, coast steep descents. Capped to avoid blowing up on climbs."""
    if grade >= 0.07:
        return 1.18
    if grade >= 0.03:
        return 1.12
    if grade >= 0.0:
        return 1.0
    if grade >= -0.02:
        return 0.80
    return 0.25  # real descent — soft-pedal/coast; physics gives gravity speed


@dataclass
class SegPlan:
    start_km: float
    length_m: float
    grade: float
    power_w: int
    speed_kmh: float
    time_s: float


def make_plan(course: Course, rider: Rider, target_if: float,
              temp_c: float = 22.0, elevation_m: float = 100.0,
              headwind_mps: float = 0.0, strategy: str = "optimized",
              w_prime_j: float = 20000.0, cp_w: float | None = None):
    rho = air_density(temp_c, elevation_m)
    ftp_cap = 1.20 * rider.ftp_w
    opt_meta = None

    def pseries_of(segs):
        ps = []
        for sp in segs:
            n = max(1, int(round(sp.time_s)))
            ps.extend([sp.power_w] * min(n, 100000))
        return ps

    if strategy == "optimized":
        # TRUE time-minimizing optimizer (Gordon/variational): minimize time at the
        # same total work as riding constant (target_if*FTP), W'bal-feasible.
        from bikeplan.optimizer import optimize
        target_avg = target_if * rider.ftp_w
        oseg, opt_meta, _base = optimize(course, rider, rho, target_avg,
                                         headwind_mps=headwind_mps,
                                         cp_w=cp_w, w_prime_j=w_prime_j)
        segs = [SegPlan(round(s.start_m / 1000, 2), s.length_m, s.grade,
                        round(s.power_w), round(s.speed_mps * 3.6, 1), s.time_s)
                for s in oseg]
        total_t = sum(s.time_s for s in segs)
        pseries = pseries_of(segs)
    else:
        # grade-banded heuristic scaled to target NP (v1 fallback)
        def simulate(base: float):
            segs, pseries, total_t = [], [], 0.0
            for s in course.segments:
                tgt = max(min(base * grade_factor(s.grade), ftp_cap), 0.0)
                v = max(speed_for_power(tgt, s.grade, rider, rho, headwind_mps), 0.5)
                t = s.length_m / v
                p_actual = min(tgt, power_for_speed(v, s.grade, rider, rho, headwind_mps))
                segs.append(SegPlan(round(s.start_m / 1000, 2), s.length_m, s.grade,
                                    round(tgt), round(v * 3.6, 1), t))
                n = max(1, int(round(t)))
                pseries.extend([p_actual] * min(n, 100000))
                total_t += t
            return segs, pseries, total_t
        target_np = target_if * rider.ftp_w
        lo, hi = 0.4 * rider.ftp_w, 1.1 * rider.ftp_w
        segs = pseries = None; total_t = 0.0
        for _ in range(24):
            base = 0.5 * (lo + hi)
            segs, pseries, total_t = simulate(base)
            if normalized_power(pseries) < target_np:
                lo = base
            else:
                hi = base

    np_ = normalized_power(pseries)
    avg_p = sum(sp.power_w * sp.time_s for sp in segs) / total_t
    work_kj = sum(sp.power_w * sp.time_s for sp in segs) / 1000.0
    if_ = np_ / rider.ftp_w
    tss_ = tss(np_, if_, total_t, rider.ftp_w)
    fuel = build_fuel_plan(work_kj, total_t, temp_c, if_)

    # gradient distribution (%time / power / speed by grade band)
    from bikeplan.analyze import gradient_distribution
    grad_dist = gradient_distribution([
        {"grade": sp.grade, "length_m": sp.length_m, "power_w": sp.power_w,
         "speed_mps": sp.speed_kmh / 3.6, "time_s": sp.time_s} for sp in segs])

    # climb-by-climb power summary
    climb_rows = []
    for cl in course.climbs:
        cs = [sp for sp in segs if cl.start_m <= sp.start_km * 1000 < cl.end_m]
        if not cs:
            continue
        ct = sum(c.time_s for c in cs)
        cavg = sum(c.power_w * c.time_s for c in cs) / ct if ct else 0
        cvel = (cl.length_m / ct) * 3.6 if ct else 0
        climb_rows.append({
            "name": cl.name or f"Climb @ {cl.start_m/1000:.1f}km",
            "start_m": round(cl.start_m),
            "length_m": round(cl.length_m), "avg_grade": round(cl.avg_grade * 100, 1),
            "gain_m": round(cl.gain_m), "power_w": round(cavg),
            "wkg": round(cavg / rider.mass_kg, 2), "speed_kmh": round(cvel, 1),
            "time_min": round(ct / 60, 1),
        })

    return {
        "total_km": round(course.total_m / 1000, 1),
        "gain_m": round(course.total_gain_m),
        "time_s": total_t, "time_str": _hms(total_t),
        "avg_power": round(avg_p), "np": round(np_), "if": round(if_, 3),
        "tss": round(tss_), "work_kj": round(work_kj),
        "avg_speed_kmh": round(course.total_m / total_t * 3.6, 1),
        "segments": segs, "climbs": climb_rows, "fuel": fuel,
        "grad_dist": grad_dist, "strategy": strategy, "opt": opt_meta,
        "rider": {"mass_kg": round(rider.mass_kg, 1), "ftp": rider.ftp_w,
                  "cda": rider.cda, "crr": rider.crr},
        "conditions": {"temp_c": temp_c, "elevation_m": elevation_m,
                       "headwind_mps": headwind_mps, "target_if": target_if},
    }


def _hms(s: float) -> str:
    s = int(round(s)); h = s // 3600; m = (s % 3600) // 60; sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


def _parse_time(txt: str) -> float:
    """'H:MM:SS' / 'MM:SS' -> seconds; a bare number -> minutes."""
    txt = txt.strip()
    if ":" in txt:
        parts = [float(p) for p in txt.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0.0)
        h, m, s = parts[-3], parts[-2], parts[-1]
        return h * 3600 + m * 60 + s
    return float(txt) * 60.0


def garmin_workout(plan: dict, name: str) -> dict:
    """Export the plan as a Garmin structured cycling workout: one power-target
    step per climb + steady blocks between. Matches the manage_workouts payload
    shape (power.zone targets in watts). Ready to push via the Garmin MCP."""
    steps = []
    order = 1
    # simple approach: a step per climb (target = climb avg ±) and steady steps between
    segs = plan["segments"]
    climbs = plan["climbs"]
    # Steady target = the optimizer's own time-weighted power on non-climbing
    # terrain (|grade| < 3%). Using whole-ride NP here (the previous behaviour)
    # inflated the steady step above the sustained-climb targets, making the
    # workout look inverted — flats harder than climbs. (fixed 2026-08-07)
    flats = [s for s in segs if abs(s.grade) < 0.03 and s.time_s > 0]
    ft = sum(s.time_s for s in flats)
    steady = round(sum(s.power_w * s.time_s for s in flats) / ft) if ft else plan["np"]
    # build alternating steady/climb by distance
    covered = 0.0
    for cr in climbs:
        # steady lead-in up to this climb — distance is the gap since the last
        # climb ended. Emitting meters=None here produced a malformed
        # distance-duration step that Garmin rejects (fixed 2026-08-07).
        lead_m = round(cr["start_m"] - covered)
        if lead_m > 0:
            steps.append({"stepOrder": order, "type": "interval", "durationType": "distance",
                          "meters": lead_m, "targetType": "power.zone",
                          "targetLow": int(steady * 0.9), "targetHigh": int(steady * 1.05),
                          "description": "Steady — hold target, spin ≥85 rpm on the flats"})
            order += 1
        covered = cr["start_m"] + cr["length_m"]
        steps.append({"stepOrder": order, "type": "interval", "durationType": "distance",
                      "meters": round(cr["length_m"]), "targetType": "power.zone",
                      "targetLow": int(cr["power_w"] * 0.95), "targetHigh": int(cr["power_w"] * 1.05),
                      "description": f"{cr['name']} — {cr['avg_grade']}% for {cr['length_m']}m @ ~{cr['power_w']}W ({cr['wkg']} W/kg)"})
        order += 1
    steps.append({"stepOrder": order, "type": "cooldown", "durationType": "open",
                  "targetType": "power.zone", "targetLow": int(steady * 0.85),
                  "targetHigh": int(steady * 1.02), "description": "Run it home at target"})
    return {"workoutName": name, "sportType": "cycling", "steps": steps,
            "estimated_time_s": plan["time_s"], "note": "targets in watts; push via manage_workouts upload+schedule"}


def render_html(plan: dict, title: str) -> str:
    f = plan["fuel"]
    seg_rows = "".join(
        f"<tr><td>{sp.start_km:.1f}</td><td>{sp.grade*100:+.1f}%</td>"
        f"<td>{sp.power_w}</td><td>{sp.speed_kmh:.1f}</td></tr>"
        for sp in plan["segments"][::max(1, len(plan["segments"])//60)]  # sample ~60 rows
    )
    climb_rows = "".join(
        f"<tr><td>{c['name']}</td><td>{c['length_m']} m</td><td>{c['avg_grade']}%</td>"
        f"<td>{c['power_w']} W</td><td>{c['wkg']}</td><td>{c['speed_kmh']} km/h</td><td>{c['time_min']} min</td></tr>"
        for c in plan["climbs"]
    ) or "<tr><td colspan=7 class=muted>No sustained climbs detected.</td></tr>"
    notes = "".join(f"<li>{n}</li>" for n in f.notes)
    cond = plan["conditions"]; rd = plan["rider"]

    # gradient distribution rows + inline bar
    gd = plan.get("grad_dist", {})
    gd_rows = "".join(
        f"<tr><td>{name}</td><td>{d['pct_time']}%</td><td>{d['dist_km']} km</td>"
        f"<td>{d['avg_power_w']} W</td><td>{round(d['avg_power_w']/rd['mass_kg'],2)}</td>"
        f"<td>{d['avg_speed_kmh']} km/h</td>"
        f"<td><span style='display:inline-block;height:9px;border-radius:3px;background:var(--ac);"
        f"width:{max(2,round(d['pct_time']*1.6))}px'></span></td></tr>"
        for name, d in gd.items()
    ) or "<tr><td colspan=7 class=muted>—</td></tr>"

    # race-day cheat sheet: glanceable per-climb power card + key numbers
    cheat_climbs = "".join(
        f"<div class='cc'><b>{c['name']}</b><span>{c['power_w']} W · {c['wkg']} W/kg · "
        f"{c['avg_grade']}% · {c['time_min']} min</span></div>"
        for c in plan["climbs"]
    ) or "<div class='cc muted'>No sustained climbs — hold steady target throughout.</div>"
    opt_html = ""
    if plan.get("opt"):
        m = plan["opt"]
        mins = m["time_saved_s"] / 60.0
        pct = m["time_saved_s"] / m["const_time_s"] * 100 if m["const_time_s"] else 0
        feas = "feasible ✓" if m["feasible"] else "INFEASIBLE ⚠"
        opt_html = f"""<div class="card"><h2>⚡ Optimized pacing (W'bal dynamic programming)</h2>
<p>True time-minimizing power distribution: power varies <b>with gradient</b> (harder on
climbs, ease on descents), spending the anaerobic reserve W' where it buys the most time
and banking it on descents. <b>Saves ~{mins:.1f} min</b> ({m['time_saved_s']:.0f} s, {pct:.1f}%)
vs riding a constant {m['const_power_w']} W.</p>
<p class="muted">Optimized NP {m['np_opt']} W / IF {m['if_opt']} · anaerobic model CP {m['cp_w']} W,
W' {m['w_prime_j']} J → min W'bal {m['wbal_min_j']} J ({feas}) · surge ceiling {m['pmax_w']} W.
Method: Sundström-style DP over W'bal state (Gordon/variational optimal-control). Time saved
is course-specific — larger on hilly/surgy courses, smaller on flat steady ones. Predicted
time is a model, not a guarantee.</p></div>"""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
:root{{--bg:#0f1420;--card:#182234;--bd:#26324a;--tx:#e6ebf5;--mut:#93a1bd;--ac:#4f8cff;--ok:#35c07f}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.5}}
.w{{max-width:900px;margin:0 auto;padding:26px 18px 60px}}
h1{{font-size:23px;margin:0 0 2px}} .sub{{color:var(--mut);font-size:13.5px;margin-bottom:16px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}
@media(max-width:640px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:var(--card);border:1px solid var(--bd);border-radius:11px;padding:12px}}
.kpi .v{{font-size:20px;font-weight:700}} .kpi .l{{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:13px;padding:16px 18px;margin:14px 0}}
h2{{font-size:16px;margin:0 0 10px;color:var(--ac)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid var(--bd)}}
th{{color:var(--mut);font-weight:600}} .muted{{color:var(--mut)}}
li{{font-size:13.5px;color:var(--mut)}} .fuel{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
@media(max-width:640px){{.fuel{{grid-template-columns:1fr}}}}
.cheat{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
@media(max-width:640px){{.cheat{{grid-template-columns:1fr}}}}
.cc{{background:var(--bg);border:1px solid var(--bd);border-radius:9px;padding:9px 11px;font-size:13px;display:flex;flex-direction:column}}
.cc span{{color:var(--mut);font-size:12px;margin-top:2px}}
</style></head><body><div class="w">
<h1>🚴 {title}</h1>
<div class="sub">Race power plan · {plan['total_km']} km · {plan['gain_m']} m gain · target IF {cond['target_if']} · {rd['mass_kg']} kg @ FTP {rd['ftp']} W · CdA {rd['cda']} · {cond['temp_c']}°C</div>
<div class="kpis">
 <div class="kpi"><div class="v">{plan['time_str']}</div><div class="l">Predicted time</div></div>
 <div class="kpi"><div class="v">{plan['np']} W</div><div class="l">Normalized power</div></div>
 <div class="kpi"><div class="v">{plan['if']}</div><div class="l">Intensity factor</div></div>
 <div class="kpi"><div class="v">{plan['tss']}</div><div class="l">TSS</div></div>
 <div class="kpi"><div class="v">{plan['avg_power']} W</div><div class="l">Avg power</div></div>
 <div class="kpi"><div class="v">{plan['avg_speed_kmh']} km/h</div><div class="l">Avg speed</div></div>
 <div class="kpi"><div class="v">{plan['work_kj']}</div><div class="l">Work (kJ)</div></div>
 <div class="kpi"><div class="v">{cond['headwind_mps']} m/s</div><div class="l">Headwind</div></div>
</div>
{opt_html}
<div class="card"><h2>📋 Race-day cheat sheet</h2>
<p class="muted" style="margin:0 0 10px">Hold NP <b>{plan['np']} W</b> (IF {plan['if']}) · avg {plan['avg_power']} W · {plan['avg_speed_kmh']} km/h · ~{plan['time_str']}. Ride the climbs at these targets; ease the descents.</p>
<div class="cheat">{cheat_climbs}</div></div>
<div class="card"><h2>Climb-by-climb power targets</h2>
<table><tr><th>Climb</th><th>Length</th><th>Grade</th><th>Power</th><th>W/kg</th><th>Speed</th><th>Time</th></tr>{climb_rows}</table></div>
<div class="card"><h2>Gradient distribution</h2>
<p class="muted" style="margin:0 0 8px">Where the time and power go, by grade band.</p>
<table><tr><th>Band</th><th>% time</th><th>Dist</th><th>Avg power</th><th>W/kg</th><th>Speed</th><th></th></tr>{gd_rows}</table></div>
<div class="card"><h2>Fueling &amp; hydration ({f.duration_h} h)</h2>
<div class="fuel">
 <div><b>{f.carbs_g_per_h} g/h</b> carbs<br><span class="muted">~{f.carbs_g_total} g total</span></div>
 <div><b>{f.fluid_ml_per_h} ml/h</b> fluid<br><span class="muted">~{f.fluid_ml_total} ml total</span></div>
 <div><b>{f.sodium_mg_per_h} mg/h</b> sodium<br><span class="muted">~{f.sodium_mg_total} mg total</span></div>
</div><ul style="margin-top:10px">{notes}</ul></div>
<div class="card"><h2>Segment power targets (sampled)</h2>
<table><tr><th>km</th><th>grade</th><th>target W</th><th>km/h</th></tr>{seg_rows}</table></div>
<div class="sub" style="margin-top:20px">Generated by the coach bikeplan tool. Pacing is a grade-banded heuristic scaled to target NP — a v1, not a full optimizer. Physics: gravity + rolling + aero + drivetrain.</div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpx"); ap.add_argument("--ftp", type=float, default=273)
    ap.add_argument("--weight-lb", type=float, default=238)
    ap.add_argument("--bike-kg", type=float, default=9.0)
    ap.add_argument("--cda", type=float, default=0.32); ap.add_argument("--crr", type=float, default=0.004)
    ap.add_argument("--target-if", type=float, default=0.80)
    ap.add_argument("--temp", type=float, default=22.0); ap.add_argument("--elevation", type=float, default=100.0)
    ap.add_argument("--headwind", type=float, default=0.0)
    ap.add_argument("--strategy", choices=["optimized", "heuristic"], default="optimized",
                    help="optimized = true time-minimizing (default); heuristic = grade-banded v1")
    ap.add_argument("--w-prime", type=float, default=20000.0, help="anaerobic work capacity W' (J)")
    ap.add_argument("--cp", type=float, default=None, help="critical power (W); default ~0.97*FTP")
    ap.add_argument("--goal-time", default=None,
                    help="target finish time (HH:MM:SS, MM:SS, or minutes). Inverse-solves the "
                         "required sustainable power and builds the plan to hit it.")
    ap.add_argument("--out", default="reports/raceplan.html")
    ap.add_argument("--title", default="Race Plan")
    a = ap.parse_args()

    course = build_course(_parse_trackpoints(a.gpx)) if a.gpx else synthetic_rolling_course()
    mass = a.weight_lb * LB_TO_KG + a.bike_kg
    rider = Rider(mass_kg=mass, cda=a.cda, crr=a.crr, ftp_w=a.ftp)

    target_if = a.target_if
    if a.goal_time:
        from bikeplan.goaltime import solve_for_time
        goal_s = _parse_time(a.goal_time)
        rho = air_density(a.temp, a.elevation)
        cp, gm = solve_for_time(course, rider, rho, goal_s, headwind_mps=a.headwind,
                                w_prime_j=a.w_prime)
        target_if = round(cp / rider.ftp_w, 3)
        if not gm.get("achievable", True):
            print(f"⚠ goal {a.goal_time} not achievable within the model — capping at max "
                  f"modeled power ({gm.get('note','')}).")
        print(f"goal-time {_hms(goal_s)} -> required CP ~{round(cp)}W (IF {target_if}); "
              f"building plan at that intensity.")

    plan = make_plan(course, rider, target_if, a.temp, a.elevation, a.headwind,
                     strategy=a.strategy, w_prime_j=a.w_prime, cp_w=a.cp)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write(render_html(plan, a.title))
    gw = garmin_workout(plan, a.title)
    gpath = a.out.rsplit(".", 1)[0] + "_garmin.json"
    with open(gpath, "w") as fh:
        json.dump(gw, fh, indent=2)

    print(f"{a.title} [{plan['strategy']}]: {plan['total_km']} km / {plan['gain_m']}m -> "
          f"{plan['time_str']}  NP {plan['np']}W  IF {plan['if']}  TSS {plan['tss']}  {plan['work_kj']}kJ")
    if plan.get("opt"):
        m = plan["opt"]
        feas = "feasible" if m["feasible"] else "INFEASIBLE"
        print(f"optimizer (W'bal DP): saved {m['time_saved_s']:.0f}s "
              f"({m['time_saved_s']/m['const_time_s']*100:.1f}%) vs constant {m['const_power_w']}W · "
              f"opt NP {m['np_opt']}W / IF {m['if_opt']} · "
              f"W'bal min {m['wbal_min_j']}J ({feas}) · CP {m['cp_w']}W · W' {m['w_prime_j']}J")
    print(f"fuel: {plan['fuel'].carbs_g_per_h}g carbs/h · {plan['fuel'].fluid_ml_per_h}ml/h · {plan['fuel'].sodium_mg_per_h}mg sodium/h")
    print(f"report: {a.out}")
    print(f"garmin: {gpath}")


if __name__ == "__main__":
    main()
