"""
Cycling power/speed physics — the core model behind race planning.

Standard steady-state cycling power equation (per road segment):

    P_wheel = v_g * ( F_roll + F_grav + F_aero )
    P_rider = P_wheel / drivetrain_efficiency

where
    F_roll = Crr * m * g * cos(theta)          # rolling resistance
    F_grav = m * g * sin(theta)                # gravity along slope
    F_aero = 0.5 * rho * CdA * v_air^2         # aerodynamic drag
    theta  = atan(grade)                       # road angle from grade (rise/run)
    v_g    = ground speed (m/s)
    v_air  = air speed = v_g + headwind_component (m/s)

Two directions:
  - power_for_speed(v, ...)  -> watts       (direct, closed form)
  - speed_for_power(P, ...)  -> v (m/s)      (inverse, numeric — bisection)

Everything is SI internally. Callers convert lb/mph/kmh at the edges.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

G = 9.80665  # m/s^2


@dataclass
class Rider:
    mass_kg: float          # total system mass: rider + bike + kit + bottles
    cda: float = 0.32       # drag area m^2 (road hoods ~0.32; aero bars ~0.24)
    crr: float = 0.004      # rolling resistance (good road tire ~0.004)
    drivetrain_eff: float = 0.976
    ftp_w: float = 265.0


def air_density(temp_c: float = 20.0, elevation_m: float = 100.0) -> float:
    """Approx air density (kg/m^3) from temperature + elevation.
    Barometric pressure lapse + ideal gas. Good enough for pacing (±~1%)."""
    # pressure at elevation (Pa), sea-level 101325, scale height ~8400 m
    p = 101325.0 * math.exp(-elevation_m / 8400.0)
    t_k = temp_c + 273.15
    R = 287.05  # specific gas constant dry air
    return p / (R * t_k)


def power_for_speed(v_g: float, grade: float, r: Rider, rho: float,
                    headwind_mps: float = 0.0) -> float:
    """Watts required to hold ground speed v_g (m/s) on a given grade.
    grade = rise/run (0.05 = 5%). headwind_mps positive = into the wind."""
    if v_g <= 0:
        return 0.0
    theta = math.atan(grade)
    v_air = v_g + headwind_mps
    f_roll = r.crr * r.mass_kg * G * math.cos(theta)
    f_grav = r.mass_kg * G * math.sin(theta)
    # aero always opposes motion through the air; sign of v_air^2 term follows air direction
    f_aero = 0.5 * rho * r.cda * v_air * abs(v_air)
    p_wheel = v_g * (f_roll + f_grav + f_aero)
    return p_wheel / r.drivetrain_eff


def speed_for_power(power_w: float, grade: float, r: Rider, rho: float,
                    headwind_mps: float = 0.0) -> float:
    """Ground speed (m/s) achievable at a given rider power on a grade.
    Solved by bisection on power_for_speed (monotonic in v for realistic ranges).
    Handles steep descents where gravity alone drives speed at ~0 power."""
    # On steep descents power_for_speed(0+) can already exceed the target (coasting
    # faster than the pedaling power implies) -> rider coasts; return the coasting speed
    # where required power == 0.
    if power_for_speed(0.01, grade, r, rho, headwind_mps) > power_w and grade < 0:
        # find coasting speed: power_for_speed(v) == 0
        lo, hi = 0.01, 40.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if power_for_speed(mid, grade, r, rho, headwind_mps) > 0:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)
    lo, hi = 0.01, 40.0  # 0..144 km/h search bracket
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if power_for_speed(mid, grade, r, rho, headwind_mps) < power_w:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def normalized_power(power_series_w: list[float], dt_s: float = 1.0) -> float:
    """NP: 4th root of the 30s-rolling-average-power, 4th-powered, averaged.
    power_series_w should be ~1 Hz. Falls back gracefully for short series."""
    if not power_series_w:
        return 0.0
    win = max(1, int(round(30.0 / dt_s)))
    if len(power_series_w) < win:
        avg = sum(power_series_w) / len(power_series_w)
        return avg
    # 30s rolling average
    roll = []
    acc = sum(power_series_w[:win])
    roll.append(acc / win)
    for i in range(win, len(power_series_w)):
        acc += power_series_w[i] - power_series_w[i - win]
        roll.append(acc / win)
    fourth = sum(p ** 4 for p in roll) / len(roll)
    return fourth ** 0.25


def tss(np_w: float, if_: float, duration_s: float, ftp_w: float) -> float:
    """Training Stress Score."""
    if ftp_w <= 0:
        return 0.0
    return (duration_s * np_w * if_) / (ftp_w * 3600.0) * 100.0


# ---- sanity self-test ---------------------------------------------------------
if __name__ == "__main__":
    rho = air_density(20, 100)
    r = Rider(mass_kg=86.0, cda=0.32, crr=0.004, ftp_w=273)
    # Flat, 250 W, no wind -> expect ~37 km/h
    v = speed_for_power(250, 0.0, r, rho)
    kmh = v * 3.6
    print(f"flat 250W -> {kmh:.1f} km/h (expect ~36-38)")
    assert 35 <= kmh <= 39, kmh
    # round-trip: power_for_speed(speed_for_power(P)) == P
    assert abs(power_for_speed(v, 0.0, r, rho) - 250) < 0.5
    # 8% climb at 250W -> slow (~10-12 km/h)
    vc = speed_for_power(250, 0.08, r, rho) * 3.6
    print(f"8% climb 250W -> {vc:.1f} km/h (expect ~9-13)")
    assert 8 <= vc <= 14, vc
    # steep descent -8% at 0W -> coasting fast
    vd = speed_for_power(0, -0.08, r, rho) * 3.6
    print(f"-8% descent 0W coast -> {vd:.1f} km/h")
    assert vd > 30, vd
    # NP of steady 200W = 200
    assert abs(normalized_power([200.0] * 600) - 200) < 1
    print("physics self-test OK")
