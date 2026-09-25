"""
Nutrition targets — Appendix D encoded as a function, not a table I read by eye.

Day-type base macros (calibrated ~230 lb male, fat-loss phase) + effort-based carb
adjustment + fat-loss deficit + protein floor. Optionally scales calories/carbs by the
athlete's bodyweight vs the 230 lb calibration point (protein stays at a g/lb floor).
"""
from __future__ import annotations

CALIBRATION_LB = 230.0
PROTEIN_FLOOR_G = 185          # never below this (lean-mass preservation)

# day_type -> (kcal, carbs_g, protein_g, fat_g)
DAY_TYPES = {
    "strength":       (2700, 200, 200, 75),
    "double":         (3000, 260, 190, 82),   # strength + sport
    "sport_1h":       (2850, 250, 185, 78),
    "long":           (3050, 285, 185, 80),   # 90 min+
    "rest":           (2100, 130, 200, 72),
}

# effort level -> carb delta (g), applied on top of the day-type base
EFFORT_CARB_DELTA = {
    "easy":       -50,   # Z1/easy <45 min, RPE <5
    "standard":     0,   # Z2 / RPE 6-7
    "heavy_legs":  35,   # heavy leg day RPE 8+
    "tempo":       50,   # Z3/tempo RPE 7-8
    "back_to_back": 0,   # maintenance (deficit removed separately)
}


def targets(day_type: str, effort: str = "standard", bodyweight_lb: float | None = None,
            deficit_kcal: float = 0.0) -> dict:
    """Macro/calorie targets for a day. `deficit_kcal` (rest/easy days only) is subtracted
    from calories by trimming fat then carbs, never protein below the floor.
    Returns kcal/carbs_g/protein_g/fat_g + the applied adjustments."""
    if day_type not in DAY_TYPES:
        raise ValueError(f"unknown day_type {day_type!r}; one of {list(DAY_TYPES)}")
    kcal, carb, prot, fat = DAY_TYPES[day_type]

    # NOTE: Appendix D's stated kcal are the prescription and intentionally exceed 4/4/9
    # of the listed macros (fiber/real-food slack). Preserve the table kcal as the target
    # and adjust it incrementally — do NOT recompute from macros (that would silently
    # under-prescribe, e.g. strength day 2700 -> 2275).

    # scale energy + macros by bodyweight vs calibration (protein handled by floor)
    if bodyweight_lb:
        s = bodyweight_lb / CALIBRATION_LB
        kcal = round(kcal * s)
        carb = round(carb * s)
        fat = round(fat * s)
        prot = max(PROTEIN_FLOOR_G, round(prot * s))
        kcal = max(kcal, carb * 4 + prot * 4 + fat * 9)  # floor engaged -> keep kcal >= macro sum

    delta = EFFORT_CARB_DELTA.get(effort, 0)
    carb = max(0, carb + delta)
    kcal += delta * 4                      # carbs added/removed shift kcal at 4 kcal/g

    applied_deficit = 0.0
    if deficit_kcal > 0:
        # trim fat first (down to a 50 g floor), then carbs (down to 0), never protein;
        # the applied deficit is capped at what those floors can absorb
        fat_floor = 50
        cut_fat = min(deficit_kcal, max(0, (fat - fat_floor) * 9))
        cut_carb = min(deficit_kcal - cut_fat, carb * 4)
        fat -= round(cut_fat / 9)
        carb -= round(cut_carb / 4)
        applied_deficit = cut_fat + cut_carb
        kcal = round(kcal - applied_deficit)

    return {"day_type": day_type, "effort": effort, "kcal": kcal, "carbs_g": carb,
            "protein_g": prot, "fat_g": fat, "protein_floor_ok": prot >= PROTEIN_FLOOR_G,
            "deficit_applied_kcal": applied_deficit}


def compare_to_target(actual_kcal: float, actual_c: float, actual_p: float, actual_f: float,
                      tgt: dict) -> dict:
    """Actual intake (from Nori food journal) vs a targets() dict → gaps to surface."""
    return {
        "kcal_gap": round(actual_kcal - tgt["kcal"]),
        "carbs_gap": round(actual_c - tgt["carbs_g"]),
        "protein_gap": round(actual_p - tgt["protein_g"]),
        "fat_gap": round(actual_f - tgt["fat_g"]),
        "protein_below_floor": actual_p < PROTEIN_FLOOR_G,
    }


if __name__ == "__main__":
    # base tables intact
    t = targets("strength")
    assert (t["carbs_g"], t["protein_g"], t["fat_g"]) == (200, 200, 75), t
    # heavy legs adds carbs
    assert targets("strength", "heavy_legs")["carbs_g"] == 235
    assert targets("sport_1h", "tempo")["carbs_g"] == 300
    assert targets("strength", "easy")["carbs_g"] == 150
    # bodyweight scaling up for a bigger athlete raises carbs & kcal
    big = targets("strength", bodyweight_lb=260)
    assert big["carbs_g"] > 200 and big["kcal"] > targets("strength")["kcal"], big
    # protein floor holds when scaling down — and kcal never falls below the macro sum
    small = targets("rest", bodyweight_lb=170)
    assert small["protein_g"] >= PROTEIN_FLOOR_G, small
    assert small["kcal"] >= small["carbs_g"] * 4 + small["protein_g"] * 4 + small["fat_g"] * 9, small
    # deficit trims fat/carbs, never protein
    d = targets("rest", deficit_kcal=500)
    base = targets("rest")
    assert d["protein_g"] == base["protein_g"] and d["kcal"] < base["kcal"], d
    assert d["protein_floor_ok"], d
    # an oversized deficit is capped at what the fat/carb floors can absorb
    huge = targets("rest", deficit_kcal=5000)
    assert huge["deficit_applied_kcal"] < 5000, huge
    assert huge["fat_g"] == 50 and huge["carbs_g"] == 0 and huge["protein_g"] == 200, huge
    assert huge["kcal"] >= huge["carbs_g"] * 4 + huge["protein_g"] * 4 + huge["fat_g"] * 9, huge
    # comparison
    c = compare_to_target(2650, 240, 190, 70, targets("double"))
    assert c["carbs_gap"] == 240 - 260, c
    print("rest w/ 500 deficit:", targets("rest", deficit_kcal=500))
    print("double + standard:", targets("double"))
    print("nutrition self-test OK")
