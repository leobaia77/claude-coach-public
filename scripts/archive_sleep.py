#!/usr/bin/env python3
"""Archive Oura sleep intervals into metrics/sleep_intervals.csv.

Oura is a remote connector and cannot be cron-scheduled (Appendix K §2), so the
raw intervals arrive as MCP tool output captured in-session. Feed this either a
saved tool-result JSON ({"result": [...]}) or a compact run-length file.

  python3 scripts/archive_sleep.py --json <tool-result.json>
  python3 scripts/archive_sleep.py --runlength <rle.json>

Run-length format lets a night that is still in the model's context be archived
without a second API round-trip:
  {"night": "2026-08-15",
   "segments": [{"start": "2026-08-14T23:51:59-07:00", "is_nap": false,
                 "runs": [["AWAKE", 5], ["CORE", 1], ...]}]}

`night` follows Oura's 6pm-to-6pm sleep day. Each row's own `local_date` is the
real calendar date of that block, so pre-midnight blocks date to the prior day —
without that, plot_sleep.py's midnight-wraparound handler mis-orders the
hypnogram (fixed 2026-08-13).
"""
import argparse, csv, json, pathlib
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "metrics" / "sleep_intervals.csv"
STATE = {"AWAKE_IN_BED": "AWAKE", "CORE": "CORE", "DEEP": "DEEP", "REM": "REM",
         "ASLEEP_UNSPECIFIED": "CORE"}
BLOCK_MIN = 5


def sleep_night(ts):
    """Oura's sleep day: 6pm the previous calendar day through 6pm this day."""
    return (ts + timedelta(hours=6)).date().isoformat()


def from_json(path):
    rows = []
    for iv in json.load(open(path))["result"]:
        if iv.get("is_nap"):
            continue
        ts = datetime.fromisoformat(iv["interval_starts_at"])
        end = datetime.fromisoformat(iv["interval_ends_at"])
        rows.append((sleep_night(ts), ts, STATE[iv["sleep_state"]],
                     round((end - ts).total_seconds() / 60)))
    return rows


def from_runlength(path):
    spec = json.load(open(path))
    rows = []
    night = None
    for seg in spec["segments"]:
        if seg.get("is_nap"):
            continue
        ts = datetime.fromisoformat(seg["start"])
        if night is None:
            night = sleep_night(ts)
            if night != spec["night"]:
                print(f"⚠️  spec says night {spec['night']} but first segment computes to "
                      f"{night} via the 6pm rule — archiving as {night}")
        for state, n in seg["runs"]:
            for _ in range(n):
                rows.append((night, ts, state, BLOCK_MIN))
                ts += timedelta(minutes=BLOCK_MIN)
    return rows


ap = argparse.ArgumentParser()
ap.add_argument("--json")
ap.add_argument("--runlength")
a = ap.parse_args()
if not (a.json or a.runlength):
    raise SystemExit("need --json or --runlength")

new = (from_json(a.json) if a.json else []) + \
      (from_runlength(a.runlength) if a.runlength else [])

existing = list(csv.reader(open(OUT))) if OUT.exists() else []
if existing:
    header, body = existing[0], existing[1:]
else:
    header, body = ["night", "local_date", "local_time", "state", "minutes", "source"], []
have = {(r[0], r[1], r[2]) for r in body}

added = 0
for night, ts, state, mins in new:
    key = (night, ts.date().isoformat(), ts.strftime("%H:%M"))
    if key in have:
        continue
    body.append([night, key[1], key[2], state, str(mins), "OURA"])
    have.add(key)
    added += 1

body.sort(key=lambda r: (r[0], r[1], r[2]))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(body)

print(f"✅ {OUT}  +{added} rows ({len(body)} total)")
for night in sorted({r[0] for r in body})[-5:]:
    blocks = [r for r in body if r[0] == night]
    tally = {s: sum(int(r[4]) for r in blocks if r[3] == s) for s in ("DEEP", "REM", "CORE", "AWAKE")}
    asleep = tally["DEEP"] + tally["REM"] + tally["CORE"]
    inbed = asleep + tally["AWAKE"]
    print(f"   {night}: {asleep//60}h{asleep%60:02d} asleep / {inbed//60}h{inbed%60:02d} in bed"
          f"  deep {tally['DEEP']}m  rem {tally['REM']}m  core {tally['CORE']}m  awake {tally['AWAKE']}m")
