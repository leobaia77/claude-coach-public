"""
Strain index — a coach-side analog to Oura's Symptom Radar, but with the two things Oura
structurally lacks: TRAINING LOAD and CAUSAL ATTRIBUTION.

Design (see the backtest at the bottom for the honest limits):
  - It is a MORNING signal computed from last night's physiology, fused with the accumulated
    training load through *yesterday* — because the overnight recovery window lags the load
    by ~24h (a hot/hard ride can take ~48h). So it can be predicted a day early from the plan.
  - Physiology piece mirrors Oura's "combination" idea: single-metric deviations inside the
    normal range are downweighted; strain engages when ≥2 metrics drift adversely together.
  - The load piece (Foster session-RPE for lifts + TSS for rides, heat-adjusted, EWMA-acute
    over a chronic baseline) is the coach's edge — Oura never sees it.
  - Attribution names the likely driver: training (which session), sleep, or — when physiology
    is adverse but load is low — possible non-training/illness (watch temp/resp).

HONEST SCOPE: body temperature and RHR (two of Oura's own inputs) are NOT exposed by the
data feed, and Symptom Radar's label isn't pullable — so this does not and cannot *replicate*
Oura day-for-day. It is a complementary, load-aware, attributable signal. Feed it temp if a
source ever provides it (TEMP weight is already wired).
"""
from __future__ import annotations
import math

# adverse direction per metric: does a LOW value mean worse recovery, or a HIGH value?
DIRECTION = {"hrv": "low_bad", "sleep_efficiency": "low_bad", "deep_sleep": "low_bad",
             "total_sleep": "low_bad", "resp": "high_bad", "rhr": "high_bad", "temp": "high_bad"}
WEIGHT = {"hrv": 1.0, "sleep_efficiency": 0.9, "deep_sleep": 0.7, "total_sleep": 0.5,
          "resp": 0.8, "rhr": 0.9, "temp": 1.2}
ADVERSE_Z = 0.75          # a metric counts as "adverse" past this many SDs the wrong way


def adverse_z(value, median, sd, direction):
    if value is None or sd in (None, 0):
        return None
    z = (value - median) / sd
    return z if direction == "high_bad" else -z    # positive = worse recovery


def physio_strain(metrics: dict, baselines: dict) -> dict:
    """metrics/baselines keyed by metric name; baselines[m] = (median, sd).
    Returns adverse z per metric, n_adverse, and a combination-gated physiology score."""
    zs, contrib = {}, 0.0
    for m, v in metrics.items():
        if m not in baselines:
            continue
        med, sd = baselines[m]
        z = adverse_z(v, med, sd, DIRECTION.get(m, "low_bad"))
        if z is None:
            continue
        zs[m] = round(z, 2)
        contrib += max(0.0, z) * WEIGHT.get(m, 1.0)
    n_adverse = sum(1 for z in zs.values() if z >= ADVERSE_Z)
    # combination gate: mirror Oura — one metric alone is downweighted; ≥2 = full weight
    gate = 1.0 if n_adverse >= 2 else (0.5 if n_adverse == 1 else 0.0)
    return {"z": zs, "n_adverse": n_adverse, "score": round(contrib * gate, 2),
            "dominant": max(zs, key=zs.get) if zs else None}


def session_load(kind: str, tss: float = 0.0, avg_rpe: float = 0.0,
                 duration_min: float = 0.0, ride_temp_c: float | None = None) -> float:
    """One session → strain-load units (SLU), roughly TSS-scaled so lifts and rides combine.
      ride: SLU = TSS, +10% if hot (≥28°C).
      strength: Foster session-RPE load (avg_rpe × minutes) ÷ 5 to land on the TSS scale."""
    if kind == "ride":
        slu = tss * (1.10 if (ride_temp_c or 0) >= 28 else 1.0)
    elif kind == "strength":
        slu = (avg_rpe * duration_min) / 5.0
    else:
        slu = 0.0
    return round(slu, 1)


def acute_load(daily_loads, tc: float = 2.0, seed: float | None = None):
    """EWMA of daily SLU (acute fatigue). Returns the running series (one value per day)."""
    a = 1.0 - math.exp(-1.0 / tc)
    lvl = seed if seed is not None else (daily_loads[0] if daily_loads else 0.0)
    out = []
    for x in daily_loads:
        lvl = lvl + (x - lvl) * a
        out.append(round(lvl, 1))
    return out


def strain_index(physio: dict, acute: float, chronic: float,
                 recent_drivers: list | None = None) -> dict:
    """Fuse physiology + load into a 0–100 morning strain index with level + attribution.
    `acute`/`chronic` are SLU (acute = through yesterday). recent_drivers: list of
    (label, slu) for the last ~2 days, to name the cause."""
    load_ratio = acute / chronic if chronic else 1.0
    load_z = max(0.0, (load_ratio - 1.0) / 0.25)          # 25% over chronic ≈ 1.0
    p = physio["score"]
    score = min(100.0, 12.0 * p + 18.0 * load_z)
    level = "major" if score >= 55 else "minor" if score >= 25 else "none"

    # attribution
    load_driven = load_z >= 0.6
    physio_driven = p >= 1.0
    if load_driven and physio_driven:
        cause = "training strain (load + physiology both elevated)"
    elif load_driven:
        cause = "training load (physiology still holding)"
    elif physio_driven and load_ratio < 1.05:
        cause = "NON-training — sleep or possible early illness (watch temp/resp)"
    elif physio_driven:
        cause = "mixed — sleep/recovery"
    else:
        cause = "nothing notable"
    driver_name = None
    if load_driven and recent_drivers:
        driver_name = max(recent_drivers, key=lambda d: d[1])[0]
    return {"score": round(score, 1), "level": level, "load_z": round(load_z, 2),
            "load_ratio": round(load_ratio, 2), "physio_score": p,
            "cause": cause, "top_load_driver": driver_name}


def predict_tomorrow(planned_load: float, daily_loads: list, chronic: float,
                     tc: float = 2.0) -> dict:
    """Predict tomorrow's *load-driven* strain floor from the plan (physiology unknown yet)."""
    series = acute_load(daily_loads + [planned_load], tc=tc)
    acute = series[-1]
    load_ratio = acute / chronic if chronic else 1.0
    load_z = max(0.0, (load_ratio - 1.0) / 0.25)
    floor = min(100.0, 18.0 * load_z)
    return {"predicted_acute": acute, "load_ratio": round(load_ratio, 2),
            "load_floor_score": round(floor, 1),
            "predicted_level_from_load": "minor+" if floor >= 25 else "none-so-far"}


if __name__ == "__main__":
    B = {"hrv": (41.0, 5.7), "sleep_efficiency": (88.0, 6.0), "deep_sleep": (60.0, 15.0),
         "total_sleep": (6.7, 0.94), "resp": (13.25, 0.44)}
    # clearly strained day: low HRV + low eff + low deep (≥2 adverse) + high load
    strained = physio_strain({"hrv": 30, "sleep_efficiency": 78, "deep_sleep": 38, "resp": 13.3}, B)
    assert strained["n_adverse"] >= 2 and strained["score"] > 2, strained
    si = strain_index(strained, acute=140, chronic=90,
                      recent_drivers=[("Deadlift", 80), ("hot ride", 160)])
    assert si["level"] in ("minor", "major") and si["load_z"] > 0.6, si
    assert si["top_load_driver"] == "hot ride", si

    # single-metric deviation inside range → downweighted (combination gate), clean day
    single = physio_strain({"hrv": 41, "sleep_efficiency": 88, "deep_sleep": 60, "resp": 14.4}, B)
    assert single["n_adverse"] == 1, single
    calm = strain_index(single, acute=85, chronic=90)
    assert calm["level"] == "none", calm

    # illness-like: physiology adverse (≥2) but load LOW → non-training attribution
    ill = physio_strain({"hrv": 31, "sleep_efficiency": 79, "deep_sleep": 42, "resp": 15.0}, B)
    si2 = strain_index(ill, acute=60, chronic=90)
    assert "NON-training" in si2["cause"], si2

    # load-only foresight: a big planned block raises tomorrow's floor
    pt = predict_tomorrow(160, [90, 90, 90], chronic=90)
    assert pt["load_floor_score"] > 0, pt
    print("strained day:", strain_index(strained, 140, 90, [("hot ride",160)]))
    print("illness-like:", si2["cause"])
    print("predict tomorrow (planned 160 SLU):", pt)
    print("strain self-test OK")
