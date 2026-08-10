"""
Ride-evaluation math (Appendix B) — the single deterministic source of truth for every
number a ride report cites. Report scripts (reports/generate_*.py) should import this
instead of recomputing NP/decoupling/terrain inline, so two rides never use subtly
different formulas.

Reuses the tested bikeplan primitives (normalized_power, tss, mean_max_power,
gradient_distribution) and adds Pw:HR decoupling + a one-call evaluate_ride() wrapper.
Operates on per-sample stream arrays the coach pulls from Garmin/Strava.
"""
from __future__ import annotations
from bikeplan.physics import normalized_power, tss as _tss
from bikeplan.analyze import mean_max_power, gradient_distribution


def decoupling(power_w, hr_bpm, dt=1.0) -> float:
    """Pw:HR decoupling %: how much aerobic efficiency (power/HR) fell from the first half
    to the second. >5% developing, >10% base needs work. Positive = HR drifted up for the
    same power (fatigue)."""
    n = min(len(power_w), len(hr_bpm))
    if n < 4:
        return 0.0
    half = n // 2
    def ef(a, b):
        p = sum(power_w[a:b]); h = sum(hr_bpm[a:b])
        return (p / (b - a)) / (h / (b - a)) if h > 0 else 0.0
    ef1, ef2 = ef(0, half), ef(half, n)
    return round((ef1 - ef2) / ef1 * 100, 1) if ef1 > 0 else 0.0


def _stream_segments(stream, dt):
    """Adapt a per-sample stream to gradient_distribution's segment shape."""
    grade = stream.get("grade"); sp = stream.get("speed_mps"); pw = stream["power_w"]
    n = len(pw)
    if isinstance(dt, (int, float)):
        dt = [float(dt)] * n
    segs = []
    for i in range(n):
        v = sp[i] if sp else 0.0
        segs.append({"grade": grade[i] if grade else 0.0, "length_m": v * dt[i],
                     "power_w": pw[i], "speed_mps": v, "time_s": dt[i]})
    return segs


def evaluate_ride(stream, ftp_w: float, mass_kg: float | None = None) -> dict:
    """Full deterministic metric set for a ride.
    stream: {'power_w':[...], optional 'hr_bpm','speed_mps','grade','dt'}.
    Returns NP/IF/TSS/VI, avg/max power, W/kg, mean-max curve, decoupling, terrain dist."""
    pw = stream["power_w"]
    dt = stream.get("dt", 1.0)
    n = len(pw)
    dt_list = [float(dt)] * n if isinstance(dt, (int, float)) else dt
    dur_s = sum(dt_list)
    avg = sum(pw[i] * dt_list[i] for i in range(n)) / dur_s if dur_s else 0.0
    np_ = normalized_power(pw)
    if_ = np_ / ftp_w if ftp_w else 0.0
    out = {
        "duration_s": round(dur_s),
        "avg_power_w": round(avg),
        "max_power_w": round(max(pw)) if pw else 0,
        "np_w": round(np_),
        "if": round(if_, 3),
        "vi": round(np_ / avg, 3) if avg else 0.0,        # variability index
        "tss": round(_tss(np_, if_, dur_s, ftp_w)) if ftp_w else None,
        "work_kj": round(avg * dur_s / 1000),
        "peak_power_curve": mean_max_power(pw, dt=dt_list[0] if dt_list else 1.0),
    }
    if mass_kg:
        out["wkg_avg"] = round(avg / mass_kg, 2)
        out["wkg_np"] = round(np_ / mass_kg, 2)
    if stream.get("hr_bpm"):
        out["avg_hr"] = round(sum(stream["hr_bpm"]) / len(stream["hr_bpm"]))
        out["decoupling_pct"] = decoupling(pw, stream["hr_bpm"], dt)
    if stream.get("grade") is not None and stream.get("speed_mps") is not None:
        out["terrain"] = gradient_distribution(_stream_segments(stream, dt))
    return out


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # synthetic Z2 ride that decouples: steady 200 W, HR drifts 130 -> 145 (fatigue)
    n = 3600
    power = [200] * n
    hr = [130 + int(15 * i / n) for i in range(n)]
    grade = [0.0] * 1800 + [0.05] * 900 + [-0.05] * 900
    speed = [9.0] * 1800 + [5.0] * 900 + [14.0] * 900
    stream = {"power_w": power, "hr_bpm": hr, "grade": grade, "speed_mps": speed, "dt": 1.0}
    ev = evaluate_ride(stream, ftp_w=273, mass_kg=86)
    assert ev["np_w"] == 200 and ev["avg_power_w"] == 200, ev   # steady -> NP≈avg, VI≈1
    assert ev["vi"] == 1.0, ev
    assert ev["decoupling_pct"] > 5, ev                          # HR drift caught
    assert "climb" in ev["terrain"] or "steep climb" in ev["terrain"], ev["terrain"]
    assert ev["tss"] is not None and ev["wkg_np"] == round(200/86, 2), ev
    # a surgy ride has VI > 1
    surgy = {"power_w": ([100]*1800 + [300]*1800)}
    assert evaluate_ride(surgy, ftp_w=273)["vi"] > 1.03
    print("NP", ev["np_w"], "IF", ev["if"], "VI", ev["vi"], "TSS", ev["tss"],
          "decoup", ev["decoupling_pct"], "%", "W/kg-NP", ev["wkg_np"])
    print("peak power curve:", {k: v for k, v in ev["peak_power_curve"].items() if k != "_ride_s"})
    print("rideeval self-test OK")
