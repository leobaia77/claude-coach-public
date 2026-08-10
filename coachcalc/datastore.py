"""
Local daily-data store — one structured, versioned place for everything the coach pulls
each day, readable locally and exportable to CSV/spreadsheet on request.

Two tidy CSVs under repo `metrics/` (git-tracked, so the Stop hook versions them):
  - metrics/daily.csv    — one row per DATE, wide: biometrics (HRV, resp, sleep, RHR, weight…)
                            + derived daily load/strain columns.
  - metrics/sessions.csv — one row per TRAINING SESSION: date, type, title, tss/np, rpe, SLU.

Design goals: (1) idempotent upserts keyed by date / (date,type,title) so re-pulling a day
overwrites rather than duplicates; (2) union of columns so new metrics extend the schema
without migrations; (3) stdlib-only (csv); (4) `export()` drops a clean CSV anywhere
(Desktop, a given path) for Sheets/Excel.

Coach usage each session: after pulling metrics/workouts, call `upsert_daily(date, {...})`
and `upsert_sessions([...])`. Ask "export my data" → `export("daily"|"sessions", dest)`.
"""
from __future__ import annotations
import csv, os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(_REPO, "metrics")

# canonical column order (unknown columns are appended alphabetically after these)
DAILY_COLS = ["date", "hrv", "sleep_hrv", "resp_rate", "rhr", "sleep_eff", "deep_min",
              "rem_min", "total_sleep_h", "awakenings", "weight_lb",
              "daily_slu", "acute_slu", "chronic_slu", "strain_score", "strain_level",
              "oura_flag", "note"]
SESSION_COLS = ["date", "type", "title", "dur_min", "tss", "np_w", "avg_rpe", "max_rpe",
                "slu", "temp_c", "note"]


def _paths(store_dir):
    store_dir = store_dir or STORE
    os.makedirs(store_dir, exist_ok=True)
    return (os.path.join(store_dir, "daily.csv"),
            os.path.join(store_dir, "sessions.csv"))


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _order(cols, canonical):
    known = [c for c in canonical if c in cols]
    extra = sorted(c for c in cols if c not in canonical)
    return known + extra


def _write(path, rows, canonical):
    cols = set()
    for r in rows:
        cols |= set(r.keys())
    fieldnames = _order(cols, canonical)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def upsert_daily(date: str, values: dict, store_dir: str | None = None):
    """Insert or merge a daily row keyed by `date`. Existing fields are updated;
    unspecified fields are preserved. Returns the merged row."""
    daily, _ = _paths(store_dir)
    rows = _read(daily)
    idx = {r["date"]: r for r in rows}
    row = idx.get(date, {"date": date})
    for k, v in values.items():
        if v is not None and v != "":
            row[k] = v
    idx[date] = row
    rows = [idx[d] for d in sorted(idx)]
    _write(daily, rows, DAILY_COLS)
    return row


def upsert_sessions(sessions: list, store_dir: str | None = None):
    """Insert/merge training sessions, keyed by (date, type, title). Idempotent."""
    _, spath = _paths(store_dir)
    rows = _read(spath)
    key = lambda r: (r.get("date", ""), r.get("type", ""), r.get("title", ""))
    idx = {key(r): r for r in rows}
    for s in sessions:
        k = key(s)
        cur = idx.get(k, {})
        cur.update({kk: vv for kk, vv in s.items() if vv is not None and vv != ""})
        idx[k] = cur
    rows = sorted(idx.values(), key=lambda r: (r.get("date", ""), r.get("type", "")))
    _write(spath, rows, SESSION_COLS)
    return len(rows)


def load_daily(store_dir: str | None = None):
    daily, _ = _paths(store_dir)
    return _read(daily)


def load_sessions(store_dir: str | None = None):
    _, spath = _paths(store_dir)
    return _read(spath)


def export(which: str, dest: str, store_dir: str | None = None):
    """Copy a canonical table to `dest` for spreadsheet use. which: 'daily'|'sessions'.
    dest may be a directory or a .csv path. Returns the written path."""
    daily, spath = _paths(store_dir)
    src = {"daily": daily, "sessions": spath}[which]
    if os.path.isdir(dest):
        dest = os.path.join(dest, f"coach_{which}.csv")
    rows = _read(src)
    _write(dest, rows, DAILY_COLS if which == "daily" else SESSION_COLS)
    return dest


def summary(store_dir: str | None = None):
    d, s = load_daily(store_dir), load_sessions(store_dir)
    span = (f"{d[0]['date']}→{d[-1]['date']}" if d else "—")
    return {"daily_rows": len(d), "session_rows": len(s), "daily_span": span}


if __name__ == "__main__":
    import tempfile
    t = tempfile.mkdtemp()
    upsert_daily("2026-07-24", {"hrv": 36.0, "sleep_eff": 94.3, "note": "pre-ride"}, store_dir=t)
    upsert_daily("2026-07-23", {"hrv": 38.3, "resp_rate": 12.375}, store_dir=t)
    # re-upsert same day merges (no dup, preserves note, updates hrv)
    upsert_daily("2026-07-24", {"hrv": 37.0, "strain_level": "none"}, store_dir=t)
    d = load_daily(t)
    assert len(d) == 2 and d[0]["date"] == "2026-07-23", d          # sorted, deduped
    row = [r for r in d if r["date"] == "2026-07-24"][0]
    assert row["hrv"] == "37.0" and row["note"] == "pre-ride", row  # merged, not clobbered
    upsert_sessions([{"date": "2026-07-24", "type": "ride", "title": "Los Altos",
                      "tss": 185, "slu": 185}], store_dir=t)
    upsert_sessions([{"date": "2026-07-24", "type": "ride", "title": "Los Altos", "np_w": 227}], t)
    s = load_sessions(t)
    assert len(s) == 1 and s[0]["np_w"] == "227" and s[0]["tss"] == "185", s  # merged
    out = export("daily", os.path.join(t, "out"), store_dir=t)
    assert os.path.exists(out)
    print("summary:", summary(t))
    print("export ->", out)
    print("datastore self-test OK")
