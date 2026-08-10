"""
Ride-analysis helpers that extend the coach's retrospective toolkit *forward* against a plan.

Three functions, all pure (operate on plain arrays the coach pulls from Garmin/Strava streams):
  - gradient_distribution : %time / power / speed by gradient bin (course plan OR real ride)
  - mean_max_power        : power-duration curve (best avg power over each duration window)
  - plan_vs_actual        : align a committed plan to the executed ride → per-band + total deltas

These directly serve Leo's documented overreach/pacing pattern: did he ride the plan, or
blow the early climbs and fade?
"""
from __future__ import annotations

# gradient bins (fraction grade). Matches Appendix B terrain buckets, finer on climbs.
BINS = [
    ("steep descent", -1.0, -0.07),
    ("descent",       -0.07, -0.02),
    ("flat",          -0.02, 0.02),
    ("rolling up",     0.02, 0.04),
    ("climb",          0.04, 0.07),
    ("steep climb",    0.07, 1.0),
]


def _bin(grade):
    for name, lo, hi in BINS:
        if lo <= grade < hi:
            return name
    return "flat"


def gradient_distribution(segments):
    """segments: iterable of objects/dicts with .grade, .length_m, .power_w, .speed_mps, .time_s.
    Returns per-bin dict {time_s, dist_m, avg_power_w, avg_speed_kmh, pct_time}."""
    def g(s, k):
        return getattr(s, k) if hasattr(s, k) else s[k]
    acc = {name: {"time_s": 0.0, "dist_m": 0.0, "p_ws": 0.0, "v_ms": 0.0}
           for name, _, _ in BINS}
    total_t = 0.0
    for s in segments:
        t = g(s, "time_s")
        b = acc[_bin(g(s, "grade"))]
        b["time_s"] += t
        b["dist_m"] += g(s, "length_m")
        b["p_ws"] += g(s, "power_w") * t          # time-weighted power
        b["v_ms"] += g(s, "speed_mps") * t
        total_t += t
    out = {}
    for name, _, _ in BINS:
        b = acc[name]
        if b["time_s"] <= 0:
            continue
        out[name] = {
            "time_s": round(b["time_s"]),
            "dist_km": round(b["dist_m"] / 1000, 2),
            "avg_power_w": round(b["p_ws"] / b["time_s"]),
            "avg_speed_kmh": round(b["v_ms"] / b["time_s"] * 3.6, 1),
            "pct_time": round(b["time_s"] / total_t * 100, 1) if total_t else 0.0,
        }
    return out


def mean_max_power(power_w, dt=1.0, durations_s=(5, 15, 30, 60, 300, 1200, 3600)):
    """Best average power sustained over each duration window (the mean-max / power-duration
    curve). power_w: per-sample watts; dt: seconds/sample (assumed uniform). Returns
    {duration_s: best_avg_w or None if the ride is shorter than that window}."""
    n = len(power_w)
    total = n * dt
    # prefix sums for O(1) window averages
    pref = [0.0] * (n + 1)
    for i in range(n):
        pref[i + 1] = pref[i] + power_w[i]
    out = {}
    for d in durations_s:
        w = int(round(d / dt))
        if w < 1 or w > n:
            out[d] = None
            continue
        best = max((pref[i + w] - pref[i]) / w for i in range(0, n - w + 1))
        out[d] = round(best)
    out["_ride_s"] = round(total)
    return out


def plan_vs_actual(plan_segments, actual_stream, mass_kg=None):
    """Compare a committed plan to the executed ride, bucketed by gradient band.

    plan_segments: the plan's OptSeg-like list (.grade/.length_m/.power_w/.speed_mps/.time_s).
    actual_stream: dict of parallel arrays from Garmin/Strava:
        {'dt': s|list, 'grade': [...], 'power_w': [...], 'speed_mps': [...]}  (per sample)
    Returns {bands: {band: {plan_w, actual_w, delta_w, plan_kmh, actual_kmh}}, totals:{...}}.
    Aligns by gradient band (route-agnostic) — robust to GPS/lap misalignment.
    """
    plan_dist = gradient_distribution(plan_segments)
    n = len(actual_stream["power_w"])
    dt = actual_stream.get("dt", 1.0)
    if isinstance(dt, (int, float)):
        dt = [float(dt)] * n
    grade = actual_stream["grade"]
    pw = actual_stream["power_w"]
    sp = actual_stream["speed_mps"]
    acc = {name: {"time_s": 0.0, "p_ws": 0.0, "v_ms": 0.0} for name, _, _ in BINS}
    for i in range(n):
        b = acc[_bin(grade[i])]
        b["time_s"] += dt[i]
        b["p_ws"] += pw[i] * dt[i]
        b["v_ms"] += sp[i] * dt[i]
    bands = {}
    for name, _, _ in BINS:
        a = acc[name]
        p = plan_dist.get(name)
        if a["time_s"] <= 0 and not p:
            continue
        actual_w = round(a["p_ws"] / a["time_s"]) if a["time_s"] > 0 else None
        actual_kmh = round(a["v_ms"] / a["time_s"] * 3.6, 1) if a["time_s"] > 0 else None
        plan_w = p["avg_power_w"] if p else None
        bands[name] = {
            "plan_w": plan_w, "actual_w": actual_w,
            "delta_w": (actual_w - plan_w) if (plan_w and actual_w) else None,
            "plan_kmh": p["avg_speed_kmh"] if p else None, "actual_kmh": actual_kmh,
            "actual_time_s": round(a["time_s"]),
        }
    plan_t = sum(_g(s, "time_s") for s in plan_segments)
    plan_work = sum(_g(s, "power_w") * _g(s, "time_s") for s in plan_segments)
    act_t = sum(dt)
    act_work = sum(pw[i] * dt[i] for i in range(n))
    totals = {
        "plan_time_s": round(plan_t), "actual_time_s": round(act_t),
        "time_delta_s": round(act_t - plan_t),
        "plan_avg_w": round(plan_work / plan_t) if plan_t else None,
        "actual_avg_w": round(act_work / act_t) if act_t else None,
        "plan_kj": round(plan_work / 1000), "actual_kj": round(act_work / 1000),
    }
    # pacing read: did actual fade? compare first vs second half avg power
    half = n // 2
    if half > 0:
        w1 = sum(pw[i] * dt[i] for i in range(half)) / sum(dt[i] for i in range(half))
        w2 = sum(pw[i] * dt[i] for i in range(half, n)) / sum(dt[i] for i in range(half, n))
        totals["first_half_w"] = round(w1)
        totals["second_half_w"] = round(w2)
        totals["fade_pct"] = round((w1 - w2) / w1 * 100, 1) if w1 else 0.0
    return {"bands": bands, "totals": totals}


def _g(s, k):
    return getattr(s, k) if hasattr(s, k) else s[k]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bikeplan.physics import Rider, air_density
    from bikeplan.course import synthetic_rolling_course
    from bikeplan.optimizer import optimize

    c = synthetic_rolling_course()
    r = Rider(mass_kg=86, cda=0.32, crr=0.004, ftp_w=273)
    rho = air_density(20, 100)
    plan, m, _ = optimize(c, r, rho, target_avg_w=0.80 * 273, w_prime_j=20000)

    # 1) gradient distribution of the plan
    gd = gradient_distribution(plan)
    assert "flat" in gd and gd["flat"]["pct_time"] > 0, gd
    print("gradient dist bands:", {k: v["pct_time"] for k, v in gd.items()})
    assert abs(sum(v["pct_time"] for v in gd.values()) - 100) < 0.5

    # 2) mean-max power on a synthetic surge-y stream
    pw = ([150] * 600) + ([400] * 60) + ([200] * 600)
    mm = mean_max_power(pw, dt=1.0)
    assert mm[5] >= mm[300], mm       # short windows >= long (valid windows only)
    assert mm[3600] is None and mm[1200] is not None, mm   # 3600s window > ride length
    assert mm[300] >= mm[1200], mm                          # monotonic over valid windows
    assert mm[30] >= 380, mm   # the 60s surge dominates the 30s window
    print("mean-max:", {k: v for k, v in mm.items() if k != "_ride_s"})

    # 3) plan-vs-actual: synthesize an "actual" ride that FADED (rode plan then dropped 15%)
    actual = {"dt": 1.0, "grade": [], "power_w": [], "speed_mps": []}
    for idx, s in enumerate(plan):
        secs = max(1, int(round(s.time_s)))
        fade = 1.0 if idx < len(plan) / 2 else 0.85   # 15% fade in 2nd half
        for _ in range(secs):
            actual["grade"].append(s.grade)
            actual["power_w"].append(s.power_w * fade)
            actual["speed_mps"].append(s.speed_mps * (1.0 if fade == 1.0 else 0.93))
    pva = plan_vs_actual(plan, actual)
    print("plan vs actual totals:", pva["totals"])
    assert pva["totals"]["fade_pct"] > 5, pva["totals"]   # detects the fade
    assert pva["totals"]["actual_time_s"] > pva["totals"]["plan_time_s"]  # fading = slower
    print("analyze self-test OK")
