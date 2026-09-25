#!/usr/bin/env python3
"""Breakfast food-order experiment: protein->carb gap vs no gap.

Overlays post-breakfast CGM curves aligned on meal time (t=0 = last reading
before the rise). Days are labelled with the actual protocol used, taken from
what the athlete reported at the time — there is no food log for this window,
so meal composition is self-reported and noted as such on the chart.

  python3 scripts/plot_breakfast_gap.py
  -> charts/breakfast_gap_comparison.png
"""
import csv, json, pathlib
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "metrics" / "glucose_raw.csv"
OUT = ROOT / "charts" / "breakfast_gap_comparison.png"

# Experiment config (dates, meal protocols, annotations) is PERSONAL data and lives
# outside the repo-shippable script, in metrics/breakfast_days.json:
#   {"days": {"YYYY-MM-DD": [t0, label, colour, "gap"|"nogap"], ...},
#    "partial": [...], "highlight": "..."}
CFG = ROOT / "metrics" / "breakfast_days.json"
if not CFG.exists():
    raise SystemExit("no metrics/breakfast_days.json — this chart needs a local experiment config")
_cfg = json.load(open(CFG))
DAYS = {d: tuple(v) for d, v in _cfg["days"].items()}
PARTIAL: set = set(_cfg.get("partial", []))
HIGHLIGHT = _cfg.get("highlight", "")

def load():
    rows = {}
    with open(RAW) as f:
        for r in csv.DictReader(f):
            rows.setdefault(r["local_date"], []).append((r["local_time"], int(r["mg_dl"])))
    for d in rows: rows[d].sort()
    return rows

def mins(hhmm):
    h, m = hhmm.split(":"); return int(h) * 60 + int(m)

data = load()
fig, ax = plt.subplots(figsize=(13, 7.5))
fig.patch.set_facecolor("#0f1115"); ax.set_facecolor("#151922")

summary = []
for date, (t0, label, colour, group) in DAYS.items():
    if date not in data: continue
    z = mins(t0)
    xs, ys = [], []
    for hhmm, v in data[date]:
        dt = mins(hhmm) - z
        if -20 <= dt <= 150:
            xs.append(dt); ys.append(v)
    if not xs: continue
    partial = date in PARTIAL
    ax.plot(xs, ys, lw=3.0, color=colour, alpha=0.95,
            ls="--" if partial else "-",
            label=label, zorder=3, marker="o", ms=3.5, mew=0)
    peak = max(ys); nadir = min(ys[ys.index(peak):]) if ys.index(peak) < len(ys) - 1 else peak
    summary.append((date, group, peak, nadir, peak - nadir, partial))
    # annotate peak
    px = xs[ys.index(peak)]
    ax.annotate(f"{peak}", (px, peak), textcoords="offset points", xytext=(0, 9),
                ha="center", color=colour, fontsize=11, fontweight="bold")
    if not partial and nadir < peak:
        ni = ys.index(peak) + ys[ys.index(peak):].index(nadir)
        ax.annotate(f"{nadir}", (xs[ni], nadir), textcoords="offset points", xytext=(0, -16),
                    ha="center", color=colour, fontsize=11, fontweight="bold")

ax.axhline(70, color="#ff3b3b", ls=":", lw=1.8)
ax.text(148, 71, "70 mg/dL — hypoglycaemia", color="#ff3b3b", fontsize=9, ha="right")
ax.axhspan(40, 70, color="#ff3b3b", alpha=0.08, zorder=0)
ax.axvline(0, color="#5a6478", ls="--", lw=1.2)
ax.text(1.5, 141, "carbs eaten", color="#8b94a7", fontsize=9.5, rotation=90, va="top")

ax.set_xlabel("Minutes from eating the carbohydrate portion", color="#c8cedb", fontsize=12)
ax.set_ylabel("Blood glucose (mg/dL)", color="#c8cedb", fontsize=12)
ax.set_title("Does waiting 10 minutes between protein and carbs change the glucose curve?\n"
             "Same person, same breakfast foods, four consecutive mornings · FreeStyle Libre 3",
             color="#f0f2f6", fontsize=15, fontweight="bold", pad=16)
ax.set_xlim(-20, 152); ax.set_ylim(45, 190)
ax.tick_params(colors="#8b94a7")
for s in ax.spines.values(): s.set_color("#2a3040")
ax.grid(alpha=0.12, color="#5a6478")
leg = ax.legend(loc="upper right", fontsize=9.5, framealpha=0.92,
                facecolor="#1a1f2b", edgecolor="#2a3040", labelcolor="#e0e4ec")

nogap = [s for s in summary if s[1] == "nogap"]
gap = [s for s in summary if s[1] == "gap"]
if nogap and gap:
    txt = (f"NO / 1-MIN GAP   peak {min(s[2] for s in nogap)}–{max(s[2] for s in nogap)}"
           f"  ·  fell to {min(s[3] for s in nogap)}–{max(s[3] for s in nogap)}"
           f"  ·  swing {min(s[4] for s in nogap)}–{max(s[4] for s in nogap)} mg/dL\n"
           f"10-MIN GAP        peak {min(s[2] for s in gap)}–{max(s[2] for s in gap)}"
           f"  ·  fell to {min(s[3] for s in gap)}–{max(s[3] for s in gap)}"
           f"  ·  swing {min(s[4] for s in gap)}–{max(s[4] for s in gap)} mg/dL")
    ax.text(-18, 51, txt, color="#e0e4ec", fontsize=10.5, va="bottom", fontweight="bold",
            family="DejaVu Sans Mono",
            bbox=dict(boxstyle="round,pad=0.6", fc="#1a1f2b", ec="#2a3040"))

# highlight the near-controlled pair: 8/7 vs 8/10 were essentially the same meal
ax.text(-18, 188, HIGHLIGHT,
        color="#f0c674", fontsize=9.5, va="top", ha="left", linespacing=1.5,
        bbox=dict(boxstyle="round,pad=0.45", fc="#221f14", ec="#5c5230"))

fig.text(0.5, 0.015,
         "Self-reported meal composition (no food log for this window). n=1 — one person's response over four consecutive mornings, not a general claim.",
         ha="center", color="#6c7588", fontsize=8.5)
plt.tight_layout(rect=[0, 0.035, 1, 1])
OUT.parent.mkdir(exist_ok=True)
plt.savefig(OUT, dpi=150, facecolor=fig.get_facecolor())
print(f"✅ {OUT}")
print(f"{'date':12}{'group':8}{'peak':>6}{'nadir':>7}{'swing':>7}")
for d, g, p, n, s, pt in summary:
    print(f"{d:12}{g:8}{p:>6}{n:>7}{s:>7}{'  (partial)' if pt else ''}")
