"""
Strength math — the numbers behind the 1,000 lb total. All weights in POUNDS (set the athlete's unit in their wiki §1).

Primary model is the RPE-based %1RM table (RTS / Helms "reps-in-reserve" chart): the
%-of-1RM you can lift for R reps stopping at a given RPE. This is more accurate than a
pure rep formula because it uses the athlete's reported proximity to failure (RPE).
Epley/Brzycki kept as no-RPE cross-checks.

Everything here is deterministic and self-tested so an attempt weight or a projected
e1RM is never LLM mental math.
"""
from __future__ import annotations

# %1RM by (reps, RPE). RTS/Helms table. Columns RPE 10 → 6 in 0.5 steps.
_RPES = [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0]
_PCT = {
    1:  [100.0, 97.8, 95.5, 93.9, 92.2, 90.7, 89.2, 87.8, 86.3],
    2:  [95.5, 93.9, 92.2, 90.7, 89.2, 87.8, 86.3, 85.0, 83.7],
    3:  [92.2, 90.7, 89.2, 87.8, 86.3, 85.0, 83.7, 82.4, 81.1],
    4:  [89.2, 87.8, 86.3, 85.0, 83.7, 82.4, 81.1, 79.9, 78.6],
    5:  [86.3, 85.0, 83.7, 82.4, 81.1, 79.9, 78.6, 77.4, 76.2],
    6:  [83.7, 82.4, 81.1, 79.9, 78.6, 77.4, 76.2, 75.1, 73.9],
    7:  [81.1, 79.9, 78.6, 77.4, 76.2, 75.1, 73.9, 72.3, 70.7],
    8:  [78.6, 77.4, 76.2, 75.1, 73.9, 72.3, 70.7, 69.4, 68.0],
    9:  [76.2, 75.1, 73.9, 72.3, 70.7, 69.4, 68.0, 66.7, 65.3],
    10: [73.9, 72.3, 70.7, 69.4, 68.0, 66.7, 65.3, 64.0, 62.6],
    11: [70.7, 69.4, 68.0, 66.7, 65.3, 64.0, 62.6, 61.3, 59.9],
    12: [68.0, 66.7, 65.3, 64.0, 62.6, 61.3, 59.9, 58.6, 57.2],
}


def pct_1rm(reps: int, rpe: float) -> float:
    """%1RM for `reps` reps stopping at `rpe`. Interpolates 0.25-RPE granularity;
    clamps reps to 1..12 and RPE to 6..10 — a reps>12 set is treated as 12 reps,
    which UNDERESTIMATES the true 1RM (e1rm() flags this via `.clamped`)."""
    reps = max(1, min(12, int(reps)))
    rpe = max(6.0, min(10.0, float(rpe)))
    row = _PCT[reps]
    # RPE grid is descending in 0.5 steps from 10.0; interpolate linearly
    idx = (10.0 - rpe) / 0.5
    lo = int(idx)
    if lo >= len(row) - 1:
        return row[-1]
    frac = idx - lo
    return round(row[lo] + (row[lo + 1] - row[lo]) * frac, 2)


class E1RM(float):
    """A float e1RM estimate; `clamped` is True when reps>12 forced a table clamp
    (the estimate is then a floor, not a point estimate)."""
    clamped: bool = False


def e1rm(weight_lb: float, reps: int, rpe: float = 9.0) -> float:
    """Estimated 1RM from a set of `reps` @ `weight_lb` stopping at `rpe` (RTS table).
    Returns an E1RM float; `.clamped` is True when reps>12 (table clamped to 12 —
    treat the result as a lower bound)."""
    p = pct_1rm(reps, rpe)
    v = E1RM(round(weight_lb / (p / 100.0), 1))
    v.clamped = reps > 12
    return v


def epley_1rm(weight_lb: float, reps: int) -> float:
    """Epley (no RPE) — assumes the set was to failure (RPE 10). Cross-check only."""
    return round(weight_lb * (1 + reps / 30.0), 1)


def brzycki_1rm(weight_lb: float, reps: int) -> float:
    """Brzycki (no RPE), assumes failure. Cross-check only."""
    return round(weight_lb * 36.0 / (37.0 - reps), 1) if reps < 37 else float("nan")


def working_weight(one_rm: float, reps: int, rpe: float, step_lb: float = 5.0) -> float:
    """Prescribe the load for a target `reps` @ `rpe` from a known/est 1RM, rounded to
    the nearest `step_lb` (5 lb default; 2.5 for upper-body microloading)."""
    raw = one_rm * pct_1rm(reps, rpe) / 100.0
    return round_to_plate(raw, step_lb)


def round_to_plate(weight_lb: float, step_lb: float = 5.0) -> float:
    return round(weight_lb / step_lb) * step_lb


def total(squat_lb: float, bench_lb: float, deadlift_lb: float) -> float:
    """Powerlifting total."""
    return round(squat_lb + bench_lb + deadlift_lb, 1)


def gap_to(target_lb: float, squat_lb: float, bench_lb: float, deadlift_lb: float) -> dict:
    """Total, gap to `target_lb`, and each lift's share of the current total."""
    t = total(squat_lb, bench_lb, deadlift_lb)
    return {"total": t, "target": target_lb, "gap": round(target_lb - t, 1),
            "squat": squat_lb, "bench": bench_lb, "deadlift": deadlift_lb,
            "pct_of_target": round(t / target_lb * 100, 1)}


def next_progression(current_lb: float, lift: str = "lower", last_rpe: float = 8.0,
                     step_lb: float | None = None) -> float:
    """Progressive-overload next-session weight: +2.5 lb-ish upper / +5 lb lower when the
    last top set was RPE ≤ 8; hold if 8.5; deload -10% if ≥9 (Appendix F). Returns lb."""
    if step_lb is None:
        step_lb = 5.0 if lift.startswith("low") else 2.5
    if last_rpe >= 9.0:
        return round_to_plate(current_lb * 0.90, step_lb)  # deload
    if last_rpe >= 8.5:
        return round_to_plate(current_lb, step_lb)        # hold
    return round_to_plate(current_lb + step_lb, step_lb)  # progress


if __name__ == "__main__":
    # table anchors
    assert pct_1rm(1, 10) == 100.0
    assert pct_1rm(3, 9) == 89.2, pct_1rm(3, 9)     # matches wiki's "≈89% for 3@RPE9"
    assert pct_1rm(5, 8) == 81.1
    # half-RPE interpolation
    assert abs(pct_1rm(3, 9.25) - (89.2 + (90.7 - 89.2) * 0.5)) < 0.01
    # e1RM
    assert e1rm(315, 3, 9) == round(315 / 0.892, 1), e1rm(315, 3, 9)
    # working-weight round-trips against e1RM (within one plate step)
    rm = e1rm(315, 3, 9)
    assert abs(working_weight(rm, 3, 9) - 315) <= 5, working_weight(rm, 3, 9)
    # monotonicity: more reps at same RPE -> lower %1RM
    assert pct_1rm(1, 8) > pct_1rm(5, 8) > pct_1rm(10, 8)
    # diagonal identity across the whole table: pct(r, rpe) == pct(r+1, rpe+1)
    for _r in range(1, 12):
        for _k in range(len(_RPES) - 2):
            assert _PCT[_r + 1][_k] == _PCT[_r][_k + 2], (_r, _k)
    # reps>12 clamp is detectable
    assert e1rm(200, 15).clamped and not e1rm(315, 3, 9).clamped
    # total + gap
    g = gap_to(1000, squat_lb=355, bench_lb=300, deadlift_lb=385)
    assert g["total"] == 1040.0 and g["gap"] == -40.0, g
    # progression tiers
    assert next_progression(315, "lower", 7.5) == 320    # progress +5
    assert next_progression(315, "lower", 8.5) == 315    # hold
    assert next_progression(300, "lower", 9.5) == 270    # deload -10%
    assert next_progression(200, "upper", 7.0) == 202.5  # +2.5 upper
    assert next_progression(202.5, "upper", 9.5) == 182.5  # upper deload keeps 2.5 rounding
    # cross-checks differ from RTS by design (they assume failure)
    print(f"315x3@RPE9  RTS e1RM {e1rm(315,3,9)}  Epley {epley_1rm(315,3)}  Brzycki {brzycki_1rm(315,3)}")
    print(f"gap to 1000 from S355/B300/DL385: total {g['total']} ({g['pct_of_target']}%), gap {g['gap']}")
    print("strength self-test OK")
