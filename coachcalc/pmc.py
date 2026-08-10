"""
Performance Management Chart — CTL / ATL / TSB (Banister/TrainingPeaks impulse-response).

  CTL (Chronic Training Load, "Fitness")  = EWMA of daily TSS, 42-day time constant
  ATL (Acute Training Load, "Fatigue")     = EWMA of daily TSS, 7-day time constant
  TSB (Training Stress Balance, "Form")    = CTL_yesterday − ATL_yesterday

Computed from the athlete's own daily TSS history (Garmin/bikeplan) so the coach doesn't
depend on whatever Garmin happens to surface. Missing days are treated as TSS 0 (rest).
"""
from __future__ import annotations
import math

CTL_TC = 42
ATL_TC = 7


def _alpha(tc: int) -> float:
    return 1.0 - math.exp(-1.0 / tc)


def compute_pmc(daily_tss, ctl_tc: int = CTL_TC, atl_tc: int = ATL_TC,
                ctl0: float = 0.0, atl0: float = 0.0):
    """daily_tss: chronological list of daily TSS (fill rest days with 0).
    Returns list of dicts per day: {tss, ctl, atl, tsb}. TSB uses *yesterday's* CTL−ATL
    (the standard convention). Seed with ctl0/atl0 if continuing a known history."""
    a_ctl, a_atl = _alpha(ctl_tc), _alpha(atl_tc)
    ctl, atl = float(ctl0), float(atl0)
    out = []
    for tss in daily_tss:
        tsb = round(ctl - atl, 1)                 # form = yesterday's fitness − fatigue
        ctl = ctl + (tss - ctl) * a_ctl
        atl = atl + (tss - atl) * a_atl
        out.append({"tss": round(tss, 1), "ctl": round(ctl, 1),
                    "atl": round(atl, 1), "tsb": tsb})
    return out


def form_state(tsb: float) -> str:
    """Interpret TSB (form) the usual way."""
    if tsb > 25:   return "very fresh / detraining risk"
    if tsb > 5:    return "fresh / race-ready"
    if tsb >= -10: return "neutral / productive training"
    if tsb >= -30: return "fatigued / building (overreach if sustained)"
    return "very fatigued / high injury-illness risk"


def ramp_rate(pmc, days: int = 7) -> float:
    """CTL change over the last `days` (TrainingPeaks 'ramp rate'; >~8/wk = aggressive)."""
    if len(pmc) < days + 1:
        return round(pmc[-1]["ctl"] - pmc[0]["ctl"], 1) if pmc else 0.0
    return round(pmc[-1]["ctl"] - pmc[-1 - days]["ctl"], 1)


if __name__ == "__main__":
    # constant TSS T for a long time -> CTL, ATL both converge to T, TSB -> 0
    T = 80
    pmc = compute_pmc([T] * 400)
    assert abs(pmc[-1]["ctl"] - T) < 0.5 and abs(pmc[-1]["atl"] - T) < 0.5, pmc[-1]
    assert abs(pmc[-1]["tsb"]) < 0.5, pmc[-1]
    # a hard block spikes ATL faster than CTL -> TSB goes negative
    block = compute_pmc([50] * 60 + [200] * 5)
    assert block[-1]["atl"] > block[-1]["ctl"], block[-1]
    assert block[-1]["tsb"] < 0, block[-1]
    # then a taper (rest) -> ATL falls fast, TSB climbs positive (peaking)
    taper = compute_pmc([50] * 60 + [200] * 5 + [0] * 10)
    assert taper[-1]["tsb"] > taper[-6]["tsb"], "taper should raise form"
    # ramp rate positive during a build
    build = compute_pmc([40] * 20 + [90] * 14)
    assert ramp_rate(build, 7) > 0, ramp_rate(build, 7)
    print(f"steady @80: {pmc[-1]}")
    print(f"after 5x200 block: {block[-1]} -> {form_state(block[-1]['tsb'])}")
    print(f"after 10d taper:   {taper[-1]} -> {form_state(taper[-1]['tsb'])}")
    print(f"build ramp/7d: +{ramp_rate(build,7)} CTL")
    print("pmc self-test OK")
