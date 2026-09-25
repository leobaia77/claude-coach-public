"""
Fueling & hydration plan derived from the race model's energy cost + duration.
Grounded in the coach's nutrition rules (Appendix D) + the athlete's electrolyte rules
(sodium 500-800 mg/h before+during, more in heat — bilateral-cramp history).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class FuelPlan:
    duration_h: float
    kj: float
    carbs_g_per_h: int
    carbs_g_total: int
    fluid_ml_per_h: int
    fluid_ml_total: int
    sodium_mg_per_h: int
    sodium_mg_total: int
    notes: list[str]


def build_fuel_plan(kj: float, duration_s: float, temp_c: float = 22.0,
                    intensity_if: float = 0.75) -> FuelPlan:
    h = duration_s / 3600.0
    notes: list[str] = []

    # Carbs/hr: scale with duration + intensity. <90 min can run lower; long/hard rides
    # push toward the 90 g/h gut-training ceiling.
    if h < 1.0:
        carbs = 40
    elif h < 2.0:
        carbs = 60
    elif h < 3.0:
        carbs = 75
    else:
        carbs = 90
    if intensity_if >= 0.82:
        carbs = min(90, carbs + 10)
        notes.append("High IF — carbs pushed up; front-load before each major climb.")

    # Fluid: ~500-750 ml/h baseline, +250 in heat.
    fluid = 600
    if temp_c >= 28:
        fluid = 850
        notes.append(f"Heat ({temp_c:.0f}°C) — fluid raised to ~850 ml/h.")
    elif temp_c >= 24:
        fluid = 750

    # Sodium: reference rule 500-800 mg/h; take the HIGH end in heat / given cramp history.
    sodium = 600
    if temp_c >= 24:
        sodium = 800
    notes.append("Sodium is your cramp countermeasure — take it BEFORE the start, not just during.")

    return FuelPlan(
        duration_h=round(h, 2),
        kj=round(kj),
        carbs_g_per_h=carbs,
        carbs_g_total=round(carbs * h),
        fluid_ml_per_h=fluid,
        fluid_ml_total=round(fluid * h),
        sodium_mg_per_h=sodium,
        sodium_mg_total=round(sodium * h),
        notes=notes,
    )
