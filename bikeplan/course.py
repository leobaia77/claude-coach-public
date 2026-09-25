"""
Course model: parse a GPX (or build a synthetic course), resample into fixed-length
segments with smoothed grade, and detect significant climbs.

Kept dependency-free (stdlib xml). GPX is just <trkpt lat lon><ele>.
"""
from __future__ import annotations
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

R_EARTH = 6371000.0  # m


@dataclass
class Segment:
    start_m: float      # cumulative distance at segment start
    length_m: float
    grade: float        # rise/run over the segment (smoothed)
    ele_m: float        # elevation at segment start


@dataclass
class Climb:
    start_m: float
    end_m: float
    length_m: float
    gain_m: float
    avg_grade: float
    name: str = ""


@dataclass
class Course:
    segments: list[Segment]
    total_m: float
    total_gain_m: float
    climbs: list[Climb] = field(default_factory=list)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def _parse_trackpoints(gpx_path: str) -> list[tuple[float, float, float]]:
    """Return list of (cum_dist_m, elevation_m, _) from a GPX file."""
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    ns = {"g": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    def find_all(tag):
        return root.iter("{%s}%s" % (ns["g"], tag)) if ns else root.iter(tag)
    pts = []
    last = None
    cum = 0.0
    for tp in find_all("trkpt"):
        lat = float(tp.attrib["lat"]); lon = float(tp.attrib["lon"])
        ele_el = tp.find("{%s}ele" % ns["g"]) if ns else tp.find("ele")
        ele = float(ele_el.text) if ele_el is not None else 0.0
        if last is not None:
            cum += _haversine(last[0], last[1], lat, lon)
        pts.append((cum, ele, 0.0))
        last = (lat, lon)
    return pts


def _smooth(vals: list[float], window: int) -> list[float]:
    if window <= 1:
        return vals[:]
    out = []
    half = window // 2
    for i in range(len(vals)):
        lo = max(0, i - half); hi = min(len(vals), i + half + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def build_course(points: list[tuple[float, float, float]], seg_len_m: float = 100.0) -> Course:
    """Resample raw (cum_dist, ele) points onto a fixed grid of seg_len_m, smooth
    elevation, compute per-segment grade, and detect climbs."""
    if len(points) < 2:
        raise ValueError("need >=2 points")
    total = points[-1][0]
    n = max(2, int(total // seg_len_m) + 1)
    # resample elevation at each grid node via linear interp
    grid_d = [i * seg_len_m for i in range(n)]
    grid_d[-1] = min(grid_d[-1], total)
    ele = []
    j = 0
    for d in grid_d:
        while j < len(points) - 2 and points[j + 1][0] < d:
            j += 1
        d0, e0, _ = points[j]; d1, e1, _ = points[min(j + 1, len(points) - 1)]
        frac = 0.0 if d1 == d0 else (d - d0) / (d1 - d0)
        ele.append(e0 + frac * (e1 - e0))
    ele = _smooth(ele, 3)  # light smoothing to kill GPS elevation noise
    segs = []
    gain = 0.0
    for i in range(len(grid_d) - 1):
        length = grid_d[i + 1] - grid_d[i]
        if length <= 0:
            continue
        rise = ele[i + 1] - ele[i]
        grade = rise / length
        if rise > 0:
            gain += rise
        segs.append(Segment(start_m=grid_d[i], length_m=length, grade=grade, ele_m=ele[i]))
    climbs = _detect_climbs(segs)
    return Course(segments=segs, total_m=total, total_gain_m=gain, climbs=climbs)


def _detect_climbs(segs: list[Segment]) -> list[Climb]:
    """BBS-style: contiguous run >250 m with avg grade >3%. Allows short dips."""
    climbs = []
    i = 0
    n = len(segs)
    while i < n:
        if segs[i].grade >= 0.03:
            j = i
            dip = 0
            while j < n and (segs[j].grade >= 0.01 or dip < 3):
                if segs[j].grade < 0.01:
                    dip += 1
                else:
                    dip = 0
                j += 1
            k = j
            while k > i and segs[k - 1].grade < 0.01:
                k -= 1
            start = segs[i].start_m
            end = segs[k - 1].start_m + segs[k - 1].length_m
            length = end - start
            gain = sum(s.grade * s.length_m for s in segs[i:k] if s.grade > 0)
            avg = gain / length if length else 0
            if length >= 250 and avg >= 0.03:
                climbs.append(Climb(start, end, length, gain, avg))
            i = j
        else:
            i += 1
    return climbs


def synthetic_rolling_course(total_km: float = 40.0, seg_len_m: float = 100.0) -> Course:
    """A rolling test course: two named climbs + descents + flats, for testing
    without a real GPX. ~40 km, ~600 m gain."""
    pts = []
    d = 0.0
    ele = 100.0
    profile = [  # (length_km, grade)
        (8, 0.0), (3, 0.05), (2, 0.07), (3, -0.06),   # flat, climb1
        (6, 0.0), (2.5, 0.06), (1.5, 0.08), (3, -0.07),  # flat, climb2
        (7, 0.0), (4, -0.01),
    ]
    for length_km, grade in profile:
        steps = int(length_km * 1000 / seg_len_m)
        for _ in range(steps):
            pts.append((d, ele, 0.0))
            d += seg_len_m
            ele += grade * seg_len_m
    pts.append((d, ele, 0.0))
    c = build_course(pts, seg_len_m)
    names = ["Climb 1", "Climb 2"]
    for k, cl in enumerate(c.climbs):
        cl.name = names[k] if k < len(names) else f"Climb {k+1}"
    return c


if __name__ == "__main__":
    c = synthetic_rolling_course()
    print(f"total {c.total_m/1000:.1f} km, gain {c.total_gain_m:.0f} m, "
          f"{len(c.segments)} segs, {len(c.climbs)} climbs")
    for cl in c.climbs:
        print(f"  {cl.name}: {cl.start_m/1000:.1f}-{cl.end_m/1000:.1f} km, "
              f"{cl.length_m:.0f} m @ {cl.avg_grade*100:.1f}%, +{cl.gain_m:.0f} m")
