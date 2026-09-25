#!/usr/bin/env python3
"""Whole-day CGM trace with meal + workout annotations.

  python3 scripts/plot_day.py --date YYYY-MM-DD
  -> charts/{date}_day_glucose.png

Meals come from metrics/food_log.csv; the workout window is passed on the CLI.
"""
import argparse, csv, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--date", required=True)
ap.add_argument("--workout", default="", help="HH:MM-HH:MM")
ap.add_argument("--title", default="")
a = ap.parse_args()

def mins(t): h, m = t.split(":"); return int(h) * 60 + int(m)

g = []
with open(ROOT / "metrics" / "glucose_raw.csv") as f:
    for r in csv.DictReader(f):
        if r["local_date"] == a.date:
            g.append((mins(r["local_time"]), int(r["mg_dl"])))
g.sort()
if not g:
    raise SystemExit(f"no glucose rows for {a.date}")

meals = {}
fl = ROOT / "metrics" / "food_log.csv"
if fl.exists():
    with open(fl) as f:
        for r in csv.DictReader(f):
            if r["date"] != a.date: continue
            k = (r["meal"], r["time"])
            d = meals.setdefault(k, [0.0, 0.0])
            d[0] += float(r["kcal"]); d[1] += float(r["carbs_g"])

fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor("#0f1115"); ax.set_facecolor("#151922")

xs = [p[0] for p in g]; ys = [p[1] for p in g]
ax.plot(xs, ys, lw=2.6, color="#2dc4a0", zorder=4)
ax.fill_between(xs, 40, ys, color="#2dc4a0", alpha=0.07, zorder=1)

ax.axhline(70, color="#ff3b3b", ls=":", lw=1.8, zorder=2)
ax.axhspan(40, 70, color="#ff3b3b", alpha=0.10, zorder=0)
ax.axhline(140, color="#ffb648", ls=":", lw=1.4, zorder=2)

if a.workout:
    s, e = a.workout.split("-")
    ax.axvspan(mins(s), mins(e), color="#4da3ff", alpha=0.16, zorder=1)
    ax.text((mins(s) + mins(e)) / 2, 158, "WORKOUT", color="#4da3ff",
            fontsize=11, ha="center", fontweight="bold")

for (meal, t), (kcal, carbs) in sorted(meals.items(), key=lambda kv: mins(kv[0][1])):
    x = mins(t)
    ax.axvline(x, color="#8b94a7", ls="--", lw=1.0, alpha=0.55, zorder=2)
    ax.text(x + 3, 150, f"{meal}\n{carbs:.0f}g C", color="#c8cedb", fontsize=8.5,
            va="top", ha="left", linespacing=1.4)

lo = min(ys); lox = xs[ys.index(lo)]
hi = max(ys); hix = xs[ys.index(hi)]
ax.annotate(f"{hi}", (hix, hi), textcoords="offset points", xytext=(0, 10),
            ha="center", color="#ffb648", fontsize=12, fontweight="bold")
ax.annotate(f"{lo}", (lox, lo), textcoords="offset points", xytext=(0, -18),
            ha="center", color="#ff3b3b", fontsize=12, fontweight="bold")

ticks = list(range(0, 24 * 60 + 1, 120))
ax.set_xticks(ticks); ax.set_xticklabels([f"{t//60:02d}:00" for t in ticks])
ax.set_xlim(min(xs) - 15, max(xs) + 15)
# Data-driven floor - a hardcoded 55 clipped the 53 on 8/25, hiding the worst reading
# of the day. Same bug was in plot_sleep.py. Never let the axis crop a hypo.
ax.set_ylim(min(55, min(ys) - 5), max(165, max(ys) + 10))
ax.set_xlabel("Time of day", color="#c8cedb", fontsize=12)
ax.set_ylabel("Glucose (mg/dL)", color="#c8cedb", fontsize=12)
ax.set_title(a.title or f"Glucose — {a.date}", color="#f0f2f6",
             fontsize=15, fontweight="bold", pad=14)
ax.tick_params(colors="#8b94a7")
for sp in ax.spines.values(): sp.set_color("#2a3040")
ax.grid(alpha=0.12, color="#5a6478")

out = ROOT / "charts" / f"{a.date}_day_glucose.png"
plt.tight_layout(); plt.savefig(out, dpi=150, facecolor=fig.get_facecolor())
print(f"✅ {out}")
print(f"   range {lo}-{hi} mg/dL · nadir at {lox//60:02d}:{lox%60:02d} · peak at {hix//60:02d}:{hix%60:02d}")
