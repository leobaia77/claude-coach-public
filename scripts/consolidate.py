#!/usr/bin/env python3
"""Nightly consolidation (the poor-man's gbrain dream cycle).

Deterministic checks, no LLM:
  1. TRIPWIRES — superseded rule nodes carry a `tripwire:` regex; a hit in live
     surfaces means retired guidance has resurfaced (the "No CGM talk" class).
  2. REVIEW-BY — active nodes past their review_by date.
  3. SIZE — state/current.md must stay <= 9,000 B (injection cap), wiki.md <= 95 KB.
  4. FRESHNESS — glucose_raw stale > 36 h (sensor/capture died), sleep_daily > 3 d.
  5. DUPES — duplicate (night,date,time) keys in sleep_intervals.csv.
  6. LEDGER — new files in charts/ and reports/ are auto-appended (self-healing).

Findings -> state/ATTENTION.md (injected at session start); clean run removes it.
"""
import csv, os, re, pathlib, subprocess
from datetime import datetime, timedelta, date
ROOT = pathlib.Path(__file__).resolve().parent.parent
findings = []

# 1+2. rule nodes
LIVE = ["state/current.md", "CLAUDE.md", "scripts", "templates", ".claude"]
for p in sorted((ROOT / "state" / "rules").glob("*.md")):
    s = p.read_text()
    fm = dict(l.split(":", 1) for l in s.split("---")[1].splitlines() if ":" in l)
    fm = {k.strip(): v.strip() for k, v in fm.items()}
    if fm.get("status") != "active" and fm.get("tripwire"):
        r = subprocess.run(["grep", "-rlIE", "--exclude-dir=__pycache__", fm["tripwire"]] + [str(ROOT / x) for x in LIVE],
                           capture_output=True, text=True)
        hits = [h for h in r.stdout.splitlines() if "/state/rules/" not in h and "/state/archive/" not in h
                and "consolidate.py" not in h]
        if hits:
            findings.append(f"TRIPWIRE `{fm['name']}` (retired {fm.get('since','?')}): stale text resurfaced in {', '.join(os.path.relpath(h, ROOT) for h in hits)}")
    if fm.get("status") == "active" and fm.get("review_by"):
        if date.fromisoformat(fm["review_by"]) < date.today():
            findings.append(f"REVIEW OVERDUE: node `{fm['name']}` was due {fm['review_by']} — resolve or extend it")

# 3. sizes
sz = (ROOT / "state" / "current.md").stat().st_size
if sz > 9000: findings.append(f"SIZE: state/current.md is {sz:,} B (> 9,000) — injection at risk, archive something")
wz = (ROOT / "wiki.md").stat().st_size
if wz > 95000: findings.append(f"SIZE: wiki.md is {wz:,} B (> 95 KB) — move content into wiki/entries/ or sections")

# 4. freshness
def last_ts_glucose():
    with open(ROOT / "metrics" / "glucose_raw.csv") as f:
        last = None
        for r in csv.DictReader(f): last = r
    return datetime.fromisoformat(last["timestamp_utc"].replace("Z", "+00:00")) if last else None
# The CGM is deliberately off from 2026-09-23 (see state/rules/cgm-active.md). Staleness is
# expected while it is dark, so only flag it when the node says a sensor should be running.
cgm_dark = "CGM DARK" in (ROOT / "state" / "rules" / "cgm-active.md").read_text()
ts = last_ts_glucose()
if ts and not cgm_dark and (datetime.now(ts.tzinfo) - ts) > timedelta(hours=36):
    findings.append(f"FRESHNESS: last CGM reading {ts:%Y-%m-%d %H:%M}Z (>36 h) — sensor or capture is down")
with open(ROOT / "metrics" / "sleep_daily.csv") as f:
    last_sleep = list(csv.DictReader(f))[-1]["date"]
if (date.today() - date.fromisoformat(last_sleep)).days > 3:
    findings.append(f"FRESHNESS: sleep_daily last row {last_sleep} (>3 d) — pull Oura in-session")

# 5. dupes
seen, dupes = set(), 0
with open(ROOT / "metrics" / "sleep_intervals.csv") as f:
    for r in csv.DictReader(f):
        k = (r["night"], r["local_date"], r["local_time"])
        if k in seen: dupes += 1
        seen.add(k)
if dupes: findings.append(f"DUPES: {dupes} duplicate interval keys in sleep_intervals.csv")

# 6. ledger self-heal
LEDGER = ROOT / "state" / "ledger.csv"
rows = list(csv.reader(open(LEDGER))) if LEDGER.exists() else [["date", "kind", "ref", "subject"]]
known = {r[2] for r in rows[1:]}
added = 0
for d, kind in (("charts", "chart"), ("reports", "report"), ("routes", "route")):
    for p in sorted((ROOT / d).glob("*")):
        if p.suffix in (".png", ".html", ".gpx", ".json") and f"{d}/{p.name}" not in known:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", p.name)
            rows.append([m.group(1) if m else datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),
                         kind, f"{d}/{p.name}", p.stem.replace("_", " ")])
            added += 1
if added:
    rows = [rows[0]] + sorted(rows[1:], key=lambda r: (r[0], r[2]))
    with open(LEDGER, "w", newline="") as f: csv.writer(f).writerows(rows)

ATT = ROOT / "state" / "ATTENTION.md"
if findings:
    ATT.write_text(f"# ⚠️ CONSOLIDATION FINDINGS — {date.today()}\n\n"
                   + "\n".join(f"- {x}" for x in findings)
                   + "\n\nResolve each (fix, or update the node), then re-run scripts/consolidate.py.\n")
    print(f"{len(findings)} finding(s) -> state/ATTENTION.md" + (f" · ledger +{added}" if added else ""))
else:
    if ATT.exists(): ATT.unlink()
    print(f"clean" + (f" · ledger +{added}" if added else ""))
