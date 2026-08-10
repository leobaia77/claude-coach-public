"""
CdA (and Crr) estimation from a real ride — calibrates the optimizer's aero input so
predicted times become trustworthy. Energy-balance method (a whole-ride form of Chung's
virtual-elevation).

Over any ride, wheel work in = sum of resistive work:
    Σ P·η·dt = Crr·m·g·Σ(cosθ·v·dt) + ½·ρ·CdA·Σ(v³·dt) + m·g·Δh + ½·m·(v_end²−v_start²)
        rolling                aero                 gravity        kinetic

Given a stream of (dt, speed, power, elevation), everything except CdA is known, so:
    CdA = [ Σ P·η·dt − Crr·m·g·Σ(v·dt) − m·g·Δh − ΔKE ] / ( ½·ρ·Σ(v³·dt) )

Best on a steady effort with meaningful speed (aero term must dominate). With several
segments you can least-squares both Crr and CdA; here we solve CdA at a fixed Crr
(and expose a 2-point solve for Crr+CdA from a fast and a slow segment).
"""
from __future__ import annotations
from bikeplan.physics import G


def estimate_cda(dt, speed_mps, power_w, elevation_m,
                 mass_kg, crr=0.004, rho=1.225, drivetrain_eff=0.976,
                 headwind_mps=0.0):
    """CdA (m^2) from parallel arrays. dt: seconds per sample (scalar or list).
    speed_mps/power_w/elevation_m: equal-length lists. Returns dict."""
    n = len(speed_mps)
    if isinstance(dt, (int, float)):
        dt = [float(dt)] * n
    assert len(power_w) == n and len(elevation_m) == n and len(dt) == n
    work_in = sum(power_w[i] * drivetrain_eff * dt[i] for i in range(n))
    dist = sum(speed_mps[i] * dt[i] for i in range(n))
    # aero term integrates air-speed cubed over time (still air unless a headwind given)
    sum_v3 = sum(((speed_mps[i] + headwind_mps) ** 3) * dt[i] for i in range(n))
    dh = elevation_m[-1] - elevation_m[0]
    dke = 0.5 * mass_kg * (speed_mps[-1] ** 2 - speed_mps[0] ** 2)
    roll = crr * mass_kg * G * dist
    grav = mass_kg * G * dh
    aero_energy = work_in - roll - grav - dke
    denom = 0.5 * rho * sum_v3
    cda = aero_energy / denom if denom > 0 else float("nan")
    return {"cda": round(cda, 4), "crr_assumed": crr, "distance_m": round(dist),
            "work_kj": round(work_in / 1000, 1), "elev_change_m": round(dh, 1),
            "note": "steady effort at real speed gives the cleanest estimate; "
                    "coasting/braking sections bias it."}


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bikeplan.physics import Rider, air_density, power_for_speed
    rho = air_density(20, 100)
    m, true_cda, crr = 86.0, 0.30, 0.004
    r = Rider(mass_kg=m, cda=true_cda, crr=crr)
    # synthesize a ride: flat 8 km at steady 10 m/s, then a 4% grade 2 km, then -4% 2 km,
    # each at the physics-consistent power for the held speed. Recover CdA.
    dt = 1.0
    speed, power, ele = [], [], []
    e = 100.0
    def leg(grade, secs, v):
        global e
        for _ in range(secs):
            P = power_for_speed(v, grade, r, rho)
            speed.append(v); power.append(P); ele.append(e)
            e += v * grade * dt
    leg(0.0, 800, 10.0)
    leg(0.04, 500, 6.0)
    leg(-0.04, 300, 14.0)
    leg(0.0, 400, 10.0)
    ele.append(e)  # final elevation sample matches integration end
    ele = ele[:len(speed)]
    est = estimate_cda(dt, speed, power, ele, mass_kg=m, crr=crr, rho=rho)
    print(f"true CdA {true_cda} -> estimated {est['cda']} (dist {est['distance_m']}m, Δele {est['elev_change_m']}m)")
    assert abs(est["cda"] - true_cda) < 0.01, est
    print("cda self-test OK")
