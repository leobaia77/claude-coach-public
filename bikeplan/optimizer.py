"""
True time-minimizing power optimizer via W'bal dynamic programming.

Problem (cycling-TT optimal control): minimise total time subject to a physiological
sustainability constraint expressed with the critical-power / W' model (Skiba), and a
power ceiling. This is the formulation solved by dynamic programming in Sundström et al.
and is the rigorous version of Gordon (2005) / the variational approach (de Jong-Wolf),
which showed the optimum varies power *with gradient* (harder uphill/into wind, ease
downhill) — mis-timed variation is worse than constant.

Model:
  - Sustainable anchor CP (here = the target average power, target_if*FTP): power at CP
    holds W'bal steady; above CP spends the anaerobic reserve W'; below CP recovers it.
      W'bal_next = min(W', W'bal + (CP - P_actual)*dt),   must stay ≥ 0
  - Ceiling P_max (default 1.5*FTP).

Why DP not a single Lagrange multiplier: W'bal ≥ 0 is a *path* constraint (depends on the
order and history of efforts), so a global energy/NP multiplier can't honour it — it just
drags the whole plan down. DP carries the remaining-reserve as state and decides each
segment's power accordingly: spend W' on the climbs, bank it on descents, never go
negative. This genuinely minimises time.

  state:  (segment i, W'bal bin)      decision: power P for segment i
  cost:   segment time t_i(P)         transition: W'bal update above
  V[i][b] = min_P ( t_i(P) + V[i+1][bin(W'bal')] ),  skip P if W'bal' < 0
  answer: V[0][full reserve], then forward-recover the power path.

Performance: physics evaluated once per (segment, power-sample) into a table; DP is
O(segments × W'bins × power-grid) — sub-second for a 400-segment course.
"""
from __future__ import annotations
from dataclasses import dataclass
from bikeplan.physics import Rider, power_for_speed, speed_for_power, normalized_power

N_P = 40   # power grid points per segment
K_W = 61   # W'bal discretisation bins


@dataclass
class OptSeg:
    start_m: float
    length_m: float
    grade: float
    power_w: float
    speed_mps: float
    time_s: float


def _seg_point(power_w, grade, r, rho, headwind, length_m):
    v = max(speed_for_power(power_w, grade, r, rho, headwind), 0.3)
    t = length_m / v
    p_act = max(min(power_w, power_for_speed(v, grade, r, rho, headwind)), 0.0)
    return t, v, p_act


def _tables(segs, r, rho, headwind, pmax):
    grid = [pmax * k / (N_P - 1) for k in range(N_P)]
    tabs = []
    for s in segs:
        ts, vs, pa = [], [], []
        for P in grid:
            t, v, p_act = _seg_point(P, s.grade, r, rho, headwind, s.length_m)
            ts.append(t); vs.append(v); pa.append(p_act)
        tabs.append({"seg": s, "t": ts, "v": vs, "pact": pa})
    return tabs


def _wbal_min(segs, cp, w_prime):
    wbal, lo = w_prime, w_prime
    for s in segs:
        wbal = min(w_prime, wbal + (cp - s.power_w) * s.time_s)
        lo = min(lo, wbal)
    return lo


def optimize(course, rider: Rider, rho: float, target_avg_w: float,
             headwind_mps: float = 0.0, pmax_frac: float = 1.5,
             cp_w: float | None = None, w_prime_j: float = 20000.0):
    """Fastest W'bal-feasible power plan. `target_avg_w` (= target_if*FTP) is used as the
    sustainable anchor CP; W' is the surge reserve. Returns (segs, metrics, baseline)."""
    segs = course.segments
    n = len(segs)
    cp = cp_w if cp_w else target_avg_w      # sustainable anchor
    w_prime = w_prime_j
    pmax = pmax_frac * rider.ftp_w
    tabs = _tables(segs, rider, rho, headwind_mps, pmax)

    step = w_prime / (K_W - 1)
    def to_bin(w):
        b = int(w // step)
        return 0 if b < 0 else (K_W - 1 if b > K_W - 1 else b)

    INF = float("inf")
    # backward DP
    V = [[0.0] * K_W for _ in range(n + 1)]
    pol = [[0] * K_W for _ in range(n)]
    for i in range(n - 1, -1, -1):
        ti, pai = tabs[i]["t"], tabs[i]["pact"]
        Vi1 = V[i + 1]
        for b in range(K_W):
            wbal = b * step
            best, bestj = INF, -1
            for j in range(N_P):
                wn = wbal + (cp - pai[j]) * ti[j]
                if wn < -1e-9:
                    continue                    # would exhaust reserve -> infeasible
                if wn > w_prime:
                    wn = w_prime
                val = ti[j] + Vi1[to_bin(wn)]
                if val < best:
                    best, bestj = val, j
            V[i][b] = best
            pol[i][b] = bestj if bestj >= 0 else 0

    # forward recover from full reserve
    out = []
    b = K_W - 1
    wbal = w_prime
    for i in range(n):
        j = pol[i][b]
        s = tabs[i]["seg"]
        out.append(OptSeg(s.start_m, s.length_m, s.grade,
                          tabs[i]["pact"][j], tabs[i]["v"][j], tabs[i]["t"][j]))
        wbal = min(w_prime, wbal + (cp - tabs[i]["pact"][j]) * tabs[i]["t"][j])
        b = to_bin(wbal)
    T = sum(s.time_s for s in out)
    W = sum(s.power_w * s.time_s for s in out)

    # fair baseline: constant power = CP (holds W'bal steady, always feasible)
    base = []
    for s in segs:
        t, v, p_act = _seg_point(cp, s.grade, rider, rho, headwind_mps, s.length_m)
        base.append(OptSeg(s.start_m, s.length_m, s.grade, p_act, v, t))
    T0 = sum(s.time_s for s in base)

    np_opt = normalized_power(_expand(out))
    wbmin = _wbal_min(out, cp, w_prime)
    metrics = {
        "opt_time_s": T, "const_time_s": T0, "time_saved_s": T0 - T,
        "work_kj": round(W / 1000, 1),
        "const_power_w": round(cp), "np_opt": round(np_opt), "np_target": round(target_avg_w),
        "cp_w": round(cp), "w_prime_j": round(w_prime), "pmax_w": round(pmax),
        "wbal_min_j": round(wbmin), "feasible": V[0][K_W - 1] < INF and wbmin >= -step,
        "if_opt": round(np_opt / rider.ftp_w, 3),
    }
    return out, metrics, base


def _expand(segs):
    ps = []
    for s in segs:
        cnt = max(1, int(round(s.time_s)))
        ps.extend([s.power_w] * min(cnt, 200000))
    return ps


if __name__ == "__main__":
    import sys, os, time
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bikeplan.physics import air_density
    from bikeplan.course import synthetic_rolling_course
    c = synthetic_rolling_course()
    r = Rider(mass_kg=86.0, cda=0.32, crr=0.004, ftp_w=273)
    rho = air_density(20, 100)
    t0 = time.time()
    o, m, base = optimize(c, r, rho, target_avg_w=0.80 * 273, w_prime_j=20000)
    print(f"solved in {time.time()-t0:.2f}s")
    print(f"baseline constant {m['const_power_w']}W (=CP): {m['const_time_s']:.0f}s")
    print(f"optimized: {m['opt_time_s']:.0f}s  NP {m['np_opt']}W IF {m['if_opt']}  "
          f"-> saved {m['time_saved_s']:.0f}s ({m['time_saved_s']/m['const_time_s']*100:.1f}%)")
    print(f"W'bal min {m['wbal_min_j']}J feasible={m['feasible']} · W' {m['w_prime_j']}J · pmax {m['pmax_w']}W")
    assert m["opt_time_s"] <= m["const_time_s"] + 1, "optimizer slower than constant!"
    assert m["feasible"], "infeasible!"
    climb = [s.power_w for s in o if s.grade > 0.04]
    flat = [s.power_w for s in o if abs(s.grade) < 0.01]
    print(f"climb avg {sum(climb)/len(climb):.0f}W vs flat {sum(flat)/len(flat):.0f}W")
    assert sum(climb)/len(climb) > sum(flat)/len(flat) - 1, "climbs should be >= flats"
    print("optimizer self-test OK")
