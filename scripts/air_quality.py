#!/usr/bin/env python3
"""Daily air-quality + wind watch for the Monterey -> Morro Bay (Hwy 1) corridor.

Why this exists: the Timber and Plaskett fires burn EAST of Highway 1, so the route's
air quality is governed by wind DIRECTION more than by fire size. Onshore NW flow keeps
the corridor clean; offshore E/NE flow carries smoke onto it.

Free APIs, no keys: open-meteo air-quality + forecast.
Appends one row per waypoint per run to metrics/air_quality.csv for trend tracking.

  python3 scripts/air_quality.py            # today + forecast
  python3 scripts/air_quality.py --days 5   # longer look-ahead
"""
import argparse, csv, json, pathlib, subprocess, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "metrics" / "air_quality.csv"

# Hwy 1 corridor, north -> south. Fires sit inland (east) of this line.
WAYPOINTS = [
    ("Monterey",      36.600, -121.894),
    ("Carmel",        36.555, -121.923),
    ("Big Sur Vlg",   36.270, -121.808),
    ("Lucia",         36.023, -121.548),
    ("Gorda",         35.907, -121.456),
    ("Ragged Point",  35.777, -121.325),
    ("San Simeon",    35.644, -121.189),
    ("Cambria",       35.564, -121.081),
    ("Cayucos",       35.443, -120.893),
    ("Morro Bay",     35.366, -120.850),
]
RIDE_HOURS = range(8, 17)          # 08:00-16:00 is what he actually breathes

# EPA AQI bands, annotated for PROLONGED HEAVY EXERTION (not sedentary exposure)
def band(aqi):
    if aqi is None:          return "?",  "no data"
    if aqi <= 50:            return "🟢", "good — ride anything"
    if aqi <= 100:           return "🟡", "moderate — fine, but it is not 'clean' at 100"
    if aqi <= 150:           return "🟠", "USG — cut duration/intensity; no 5 h day"
    if aqi <= 200:           return "🔴", "unhealthy — no prolonged heavy exertion"
    return "🟣", "very unhealthy — do not ride outside"

def curl_json(url):
    r = subprocess.run(["curl", "-s", "--max-time", "25", url], capture_output=True, text=True)
    return json.loads(r.stdout)

def wind_label(deg):
    """Wind FROM this bearing. The fires are inland/east, so easterly = smoke onto the route."""
    if deg is None: return "?", ""
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    name = dirs[int((deg + 11.25) % 360 // 22.5)]
    if 20 <= deg <= 110:   return name, "OFFSHORE — carries fire smoke onto the coast ⚠️"
    if 240 <= deg <= 340:  return name, "onshore marine — pushes smoke inland ✅"
    return name, "cross/variable"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    today = dt.date.today().isoformat()
    rows, day_tbl = [], {}

    for name, lat, lon in WAYPOINTS:
        aq = curl_json(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}"
                       f"&longitude={lon}&hourly=pm2_5,us_aqi&forecast_days={a.days}"
                       f"&timezone=America%2FLos_Angeles")
        wx = curl_json(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                       f"&hourly=wind_speed_10m,wind_direction_10m&forecast_days={a.days}"
                       f"&timezone=America%2FLos_Angeles")
        t   = aq["hourly"]["time"]
        aqi = aq["hourly"]["us_aqi"]
        pm  = aq["hourly"]["pm2_5"]
        ws  = wx["hourly"]["wind_speed_10m"]
        wd  = wx["hourly"]["wind_direction_10m"]

        for day_off in range(a.days):
            d = (dt.date.today() + dt.timedelta(days=day_off)).isoformat()
            idx = [i for i, x in enumerate(t) if x.startswith(d) and int(x[11:13]) in RIDE_HOURS]
            if not idx: continue
            av = [aqi[i] for i in idx if aqi[i] is not None]
            pv = [pm[i]  for i in idx if pm[i]  is not None]
            sv = [ws[i]  for i in idx if ws[i]  is not None]
            dv = [wd[i]  for i in idx if wd[i]  is not None]
            if not av: continue
            rec = dict(pulled=today, date=d, place=name,
                       aqi_mean=round(sum(av)/len(av)), aqi_max=round(max(av)),
                       pm25_mean=round(sum(pv)/len(pv), 1) if pv else "",
                       wind_kmh=round(sum(sv)/len(sv)) if sv else "",
                       wind_dir=round(sum(dv)/len(dv)) if dv else "")
            rows.append(rec)
            day_tbl.setdefault(d, []).append(rec)

    new = not OUT.exists()
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new: w.writeheader()
        w.writerows(rows)

    print(f"MONTEREY → MORRO BAY · Hwy 1 · ride-hours (08:00–16:00) AQI\n")
    for d in sorted(day_tbl):
        recs = day_tbl[d]
        worst = max(recs, key=lambda r: r["aqi_max"])
        e, msg = band(worst["aqi_max"])
        print(f"── {d} ──  worst {e} AQI {worst['aqi_max']} @ {worst['place']}  ({msg})")
        for r in recs:
            em, _ = band(r["aqi_max"])
            wn, wmsg = wind_label(r["wind_dir"])
            print(f"   {em} {r['place']:<13} AQI mean {r['aqi_mean']:>3} / max {r['aqi_max']:>3}"
                  f" · PM2.5 {r['pm25_mean']:>5} · wind {r['wind_kmh']:>2} km/h {wn:<3} {wmsg}")
        print()
    print(f"appended {len(rows)} rows → {OUT.relative_to(ROOT)}")
    print("\n⚠️ AQI bands above are read for PROLONGED HEAVY EXERTION. At 80–110 L/min he inhales"
          "\n   roughly 15–20× the resting dose, so AQI 100 on a 5 h ride is NOT AQI 100 sitting still.")

if __name__ == "__main__":
    main()
