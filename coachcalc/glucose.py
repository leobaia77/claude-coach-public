"""
CGM state/event decomposition and the fasting-window refeed gate.

Two things kept getting done by hand and getting them wrong changed the prescription:

1. **State vs event.** A glucose trace is a slow physiological baseline (hepatic output,
   glycogen status) plus short excursions driven by meals and exercise. Averaging the two
   together is what made the 2026-08-26 night look like a failure: the whole-night mean was
   76.2 with a nadir of 59, but the *fasting* baseline was a clean 78.3 / nadir 69 and every
   low sat inside a 100-minute post-dinner tail. Those two readings demand opposite
   responses — eat less that late, versus eat more overall.
   (Same slow-state / event-residual split GlucoFM uses; see wiki 2026-08-26-glucofm-assessment.)

2. **Time-weighted, gap-aware minutes.** Counting samples ×5 min silently invents data across
   sensor gaps. Everything here integrates over real timestamps and refuses to bridge a gap
   longer than `max_gap_min`.

Samples are `(t_min, mg_dl)` pairs — minutes on any consistent clock, ascending.
Stdlib only. Self-test: `python3 -m coachcalc.glucose`.
"""
from __future__ import annotations

HYPO_L1 = 70.0          # ADA/ATTD level-1 hypoglycaemia
HYPO_L2 = 54.0          # level-2 (clinically significant)
LOW_NORMAL = 80.0
DEFAULT_MAX_GAP = 20.0  # minutes; Libre samples every 5

# How long after the last bite glucose still reflects digestion rather than hepatic output.
# 4 h is the usual figure. It is WRONG for a high-fat meal: on 2026-08-25 a pizza-plus-60 g-
# chocolate dinner at 19:30 produced absorption waves peaking at 20:03, 21:28 and **23:03**
# — the last one 3.5 h after eating — and the rebound off it did not bottom out until ~01:05,
# ~5.5 h post-meal. Scoring that night at post_meal_h=4 drags the dinner tail into the
# "fasting" window and turns a one-point miss into a false crash (nadir 59 vs 69).
POST_MEAL_H = 4.0
POST_MEAL_H_HIGH_FAT = 6.0


def post_meal_hours(high_fat: bool = False) -> float:
    """Post-prandial window to use for `refeed_gate`. Pass high_fat=True for a meal with
    substantial fat (fried/cheese/chocolate/large restaurant portion) — fat delays gastric
    emptying and stretches absorption into late waves."""
    return POST_MEAL_H_HIGH_FAT if high_fat else POST_MEAL_H


def _clean(samples):
    out = sorted((float(t), float(v)) for t, v in samples if v is not None)
    if len(out) < 2:
        raise ValueError("need at least 2 samples")
    return out


def _weights(samples, max_gap_min=DEFAULT_MAX_GAP):
    """Trapezoidal minute-weight per sample; a gap wider than max_gap_min contributes 0
    rather than being bridged (a 3-hour sensor dropout is not 3 hours of data)."""
    s = samples
    w = [0.0] * len(s)
    for i in range(len(s) - 1):
        d = s[i + 1][0] - s[i][0]
        if d <= 0 or d > max_gap_min:
            continue
        w[i] += d / 2.0
        w[i + 1] += d / 2.0
    return w


def coverage(samples, max_gap_min=DEFAULT_MAX_GAP):
    """(minutes_covered, span_minutes, fraction). Fraction well under 1.0 means the window
    is holed and its statistics are not comparable to a full night."""
    s = _clean(samples)
    cov = sum(_weights(s, max_gap_min))
    span = s[-1][0] - s[0][0]
    return round(cov, 1), round(span, 1), (round(cov / span, 3) if span > 0 else 0.0)


def decompose(samples, state_window_min=180.0, max_gap_min=DEFAULT_MAX_GAP):
    """Dual-stream split. Returns list of dicts {t, value, state, event}.

    `state` is a centred rolling MEDIAN over `state_window_min` — median, not mean, so a
    45-minute meal spike does not drag the baseline it is supposed to be measured against.
    `event` is the residual (value − state): positive = excursion above baseline."""
    s = _clean(samples)
    half = state_window_min / 2.0
    out = []
    for i, (t, v) in enumerate(s):
        win = [vv for tt, vv in s if abs(tt - t) <= half]
        win.sort()
        n = len(win)
        med = win[n // 2] if n % 2 else (win[n // 2 - 1] + win[n // 2]) / 2.0
        out.append({"t": t, "value": v, "state": round(med, 1), "event": round(v - med, 1)})
    return out


def time_below(samples, threshold, max_gap_min=DEFAULT_MAX_GAP):
    """Minutes strictly below `threshold`, time-weighted and gap-aware."""
    s = _clean(samples)
    w = _weights(s, max_gap_min)
    return round(sum(wi for (_, v), wi in zip(s, w) if v < threshold), 1)


def summarize(samples, max_gap_min=DEFAULT_MAX_GAP):
    """Time-weighted window summary: mean/nadir/peak, minutes under each threshold, CV."""
    s = _clean(samples)
    w = _weights(s, max_gap_min)
    tot = sum(w)
    if tot <= 0:
        raise ValueError("no covered time — window is all gaps")
    mean = sum(v * wi for (_, v), wi in zip(s, w)) / tot
    var = sum(wi * (v - mean) ** 2 for (_, v), wi in zip(s, w)) / tot
    sd = var ** 0.5
    vals = [v for _, v in s]
    cov, span, frac = coverage(s, max_gap_min)
    return {
        "n": len(s), "minutes": round(tot, 1), "coverage": frac,
        "mean": round(mean, 1), "sd": round(sd, 1),
        "cv_pct": round(100 * sd / mean, 1) if mean else 0.0,
        "nadir": min(vals), "peak": max(vals),
        "min_below_80": time_below(s, LOW_NORMAL, max_gap_min),
        "min_below_70": time_below(s, HYPO_L1, max_gap_min),
        "min_below_54": time_below(s, HYPO_L2, max_gap_min),
    }


def fasting_window(samples, last_food_t, wake_t=None, post_meal_h=POST_MEAL_H):
    """Samples from `last_food_t + post_meal_h` to `wake_t` — the stretch where glucose
    reflects hepatic output rather than digestion. This is the window the refeed gate reads."""
    s = _clean(samples)
    start = last_food_t + post_meal_h * 60.0
    end = wake_t if wake_t is not None else s[-1][0]
    return [(t, v) for t, v in s if start <= t <= end]


def refeed_gate(samples, last_food_t, wake_t=None, post_meal_h=POST_MEAL_H,
                nadir_min=HYPO_L1, max_min_below_60=0.0):
    """The exit criterion from `state/rules/glycogen-refeed-gate.md`, measured on the FASTING
    window only: **nadir ≥ 70 and 0 min < 60**.

    Revised 2026-08-26 — a whole-night mean cannot separate a post-meal crash from an empty
    liver, and those need opposite responses. Returns the verdict plus the post-prandial
    summary alongside it, because a fasting PASS with an ugly post-prandial tail is a
    meal-timing problem, not a repletion one."""
    fast = fasting_window(samples, last_food_t, wake_t, post_meal_h)
    if len(fast) < 2:
        return {"verdict": "NO DATA", "reason": "fasting window has <2 samples",
                "fasting": None, "post_prandial": None}
    f = summarize(fast)
    below60 = time_below(fast, 60.0)
    s = _clean(samples)
    end = wake_t if wake_t is not None else s[-1][0]
    pp = [(t, v) for t, v in s if last_food_t <= t < last_food_t + post_meal_h * 60.0 and t <= end]
    ppa = summarize(pp) if len(pp) >= 2 else None

    fails = []
    if f["nadir"] < nadir_min:
        fails.append(f"fasting nadir {f['nadir']:.0f} < {nadir_min:.0f}")
    if below60 > max_min_below_60:
        fails.append(f"{below60:.0f} min < 60 in the fasting window")
    verdict = "PASS" if not fails else "FAIL"
    note = None
    if verdict == "PASS" and ppa and ppa["nadir"] < HYPO_L1:
        note = ("fasting window PASSES but the post-prandial tail dropped to "
                f"{ppa['nadir']:.0f} — that is a meal timing/composition problem, "
                "not a repletion one")
    if f["coverage"] < 0.9:
        note = ((note + " · ") if note else "") + \
               f"fasting coverage only {100*f['coverage']:.0f}% — treat as provisional"
    return {"verdict": verdict, "reason": "; ".join(fails) if fails else "nadir and <60 both clear",
            "fasting": f, "post_prandial": ppa, "min_below_60": below60, "note": note}


def excursions(samples, min_rise=15.0, state_window_min=180.0):
    """Meal/fuel excursions: each run where the event residual rises ≥ `min_rise` above
    baseline. Returns start/peak/delta, minutes to peak, and the REBOUND nadir in the 2 h
    after the peak — the rebound is the part that matters for reactive hypoglycaemia."""
    d = decompose(samples, state_window_min)
    out, i, n = [], 0, len(d)
    while i < n:
        if d[i]["event"] >= min_rise:
            j = i
            while j < n and d[j]["event"] >= min_rise / 3.0:
                j += 1
            seg = d[i:j]
            pk = max(seg, key=lambda x: x["value"])
            after = [x for x in d[j:] if x["t"] <= pk["t"] + 120]
            reb = min((x["value"] for x in after), default=None)
            out.append({
                "start_t": seg[0]["t"], "start": seg[0]["value"],
                "peak_t": pk["t"], "peak": pk["value"],
                "delta": round(pk["value"] - seg[0]["value"], 1),
                "min_to_peak": round(pk["t"] - seg[0]["t"], 1),
                "rebound_nadir": reb,
                "rebound_drop": round(pk["value"] - reb, 1) if reb is not None else None,
            })
            i = j
        else:
            i += 1
    return out


if __name__ == "__main__":
    # --- gap-aware weighting: a dropout is not data -------------------------------------
    gapped = [(0, 100), (5, 100), (600, 60), (605, 60)]
    cov, span, frac = coverage(gapped)
    assert cov == 10.0 and span == 605.0 and frac < 0.05, (cov, span, frac)
    assert time_below(gapped, 70) == 5.0, time_below(gapped, 70)   # not 595

    # --- state/event: a spike must not drag its own baseline -----------------------------
    flat = [(t, 85.0) for t in range(0, 600, 5)]
    spike = [(t, 85.0 + (60 if 300 <= t <= 330 else 0)) for t in range(0, 600, 5)]
    ds, dsp = decompose(flat), decompose(spike)
    assert all(abs(x["state"] - 85) < .01 and abs(x["event"]) < .01 for x in ds)
    at_peak = [x for x in dsp if x["t"] == 315][0]
    assert abs(at_peak["state"] - 85) < .01, at_peak     # median ignores the spike
    assert at_peak["event"] == 60.0, at_peak

    # --- the gate separates a post-meal crash from an empty liver ------------------------
    # night A: dinner tail crashes to 59, fasting baseline healthy  -> PASS + note
    a = [(t, 100 - 41 * min(1, max(0, (t - 30) / 60))) for t in range(0, 120, 5)] + \
        [(t, 80.0) for t in range(120, 480, 5)]
    ga = refeed_gate(a, last_food_t=0, post_meal_h=2.0)
    assert ga["verdict"] == "PASS", ga
    assert ga["post_prandial"]["nadir"] <= 60, ga["post_prandial"]
    assert "meal timing" in (ga["note"] or ""), ga["note"]
    # night B: fasting baseline itself sags to 58 -> FAIL
    b = [(t, 95.0) for t in range(0, 120, 5)] + [(t, 58.0) for t in range(120, 480, 5)]
    gb = refeed_gate(b, last_food_t=0, post_meal_h=2.0)
    assert gb["verdict"] == "FAIL" and "nadir" in gb["reason"], gb

    # --- excursion + rebound -------------------------------------------------------------
    meal = [(t, 80.0) for t in range(0, 60, 5)] + \
           [(t, 80 + 40 * (1 - abs(t - 90) / 30)) for t in range(60, 121, 5)] + \
           [(t, 62.0) for t in range(125, 240, 5)] + [(t, 80.0) for t in range(240, 420, 5)]
    ex = excursions(meal)
    assert len(ex) == 1 and ex[0]["peak"] == 120.0, ex
    assert ex[0]["rebound_nadir"] == 62.0 and ex[0]["rebound_drop"] == 58.0, ex

    print("gapped coverage:", coverage(gapped))
    print("night A (post-meal crash, clean fasting):", ga["verdict"], "|", ga["note"])
    print("night B (sagging fasting baseline):      ", gb["verdict"], "|", gb["reason"])
    print("excursion:", ex[0])
    assert post_meal_hours() == 4.0 and post_meal_hours(high_fat=True) == 6.0
    print("post-meal window: normal", post_meal_hours(), "h · high-fat",
          post_meal_hours(high_fat=True), "h")
    print("glucose self-test OK")
