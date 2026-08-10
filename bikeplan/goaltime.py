"""
Goal-time solver — the inverse of the optimizer. "What sustainable power (CP anchor) do I
need to finish this course in T, or make a cutoff?" Bisects the optimizer's target power
until predicted time == goal.
"""
from __future__ import annotations
from bikeplan.optimizer import optimize


def solve_for_time(course, rider, rho, goal_time_s, headwind_mps=0.0,
                   w_prime_j=20000.0, cp_lo=100.0, cp_hi=None):
    """Find the CP anchor (sustainable power, W) whose optimized plan finishes in
    ~goal_time_s. Returns (cp_w, plan_metrics_dict). Predicted time is monotonic
    decreasing in CP, so bisect."""
    cp_hi = cp_hi if cp_hi else 1.3 * rider.ftp_w

    def time_at(cp):
        _, m, _ = optimize(course, rider, rho, target_avg_w=cp,
                           headwind_mps=headwind_mps, w_prime_j=w_prime_j, cp_w=cp)
        return m["opt_time_s"], m

    # ensure the goal is bracketed
    t_hi, _ = time_at(cp_hi)   # fastest
    t_lo, _ = time_at(cp_lo)   # slowest
    if goal_time_s <= t_hi:
        _, m = time_at(cp_hi)
        return cp_hi, {**m, "goal_time_s": goal_time_s, "achievable": False,
                       "note": f"Goal faster than max modeled ({cp_hi:.0f} W → {t_hi:.0f}s)."}
    if goal_time_s >= t_lo:
        _, m = time_at(cp_lo)
        return cp_lo, {**m, "goal_time_s": goal_time_s, "achievable": True,
                       "note": "Goal is easy — very low power suffices."}
    lo, hi = cp_lo, cp_hi
    m = None
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        t, m = time_at(mid)
        if t > goal_time_s:      # too slow -> need more power
            lo = mid
        else:
            hi = mid
    cp = 0.5 * (lo + hi)
    _, m = time_at(cp)
    m["goal_time_s"] = goal_time_s
    m["achievable"] = True
    m["required_cp_w"] = round(cp)
    m["required_if"] = round(cp / rider.ftp_w, 3)
    return cp, m


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bikeplan.physics import Rider, air_density
    from bikeplan.course import synthetic_rolling_course
    c = synthetic_rolling_course()
    r = Rider(mass_kg=86, cda=0.32, crr=0.004, ftp_w=273)
    rho = air_density(20, 100)
    goal = 5400  # 90 min
    cp, m = solve_for_time(c, r, rho, goal)
    print(f"goal {goal}s -> need CP ~{m.get('required_cp_w')}W (IF {m.get('required_if')}), "
          f"predicted {m['opt_time_s']:.0f}s")
    assert abs(m["opt_time_s"] - goal) < 60, m   # within a minute
    print("goaltime self-test OK")
