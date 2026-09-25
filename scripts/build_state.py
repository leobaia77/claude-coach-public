#!/usr/bin/env python3
"""Regenerate the FLAGS / TODOS / RULES sections of state/current.md from node files.

Nodes live in state/rules/*.md, one per rule/flag/todo, with frontmatter:
  name: kebab-slug            (must match filename)
  type: rule | flag | todo
  status: active | superseded | resolved | corrected
  since: YYYY-MM-DD
  review_by: YYYY-MM-DD       (optional — consolidate.py nags past it)
  supersedes: other-slug      (optional)
  superseded_by: other-slug   (required when status != active)
  tripwire: <regex>           (optional — consolidate.py greps live files for a
                               superseded node's tripwire; a hit = stale text resurfacing)
Body = the display text (markdown, usually one bullet's worth).

Only status: active nodes render, between the GENERATED markers in state/current.md.
To retire a rule: set status + superseded_by on the node and re-run this script —
never hand-edit the generated sections.
"""
import re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
NODES = ROOT / "state" / "rules"
STATE = ROOT / "state" / "current.md"

def parse(p):
    s = p.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", s, re.S)
    if not m:
        sys.exit(f"{p.name}: no frontmatter")
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    for req in ("name", "type", "status", "since"):
        if req not in fm:
            sys.exit(f"{p.name}: missing '{req}'")
    if fm["name"] != p.stem:
        sys.exit(f"{p.name}: name '{fm['name']}' != filename")
    if fm["status"] != "active" and "superseded_by" not in fm and fm["type"] != "todo":
        sys.exit(f"{p.name}: non-active needs superseded_by")
    return fm, m.group(2).strip()

# Rules at priority >=3 render as a one-line INDEX, not their full body. The injected
# state file has a hard size budget (the SessionStart hook truncates), and a rule the
# model knows exists and can fetch beats a rule that pushed the whole file past the cap.
# Body stays fully greppable via scripts/recall.sh <name>.
INDEX_FROM_PRIORITY = 2


def _headline(body):
    """First bold phrase of a node body — enough to know whether to go fetch it."""
    m = re.search(r"\*\*(.+?)\*\*", body, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip(" .:—-") if m else body.strip()[:70]


def _inline(body, name):
    """Inline only the operative rule. Everything after a `<!--more-->` marker is evidence
    and stays on disk — greppable via recall.sh, but out of the injected byte budget."""
    if "<!--more-->" not in body:
        return body.strip()
    return body.split("<!--more-->")[0].strip() + f" *(evidence: `recall.sh {name}`)*"


def render(nodes, typ):
    live = [(fm, body) for fm, body in nodes if fm["type"] == typ and fm["status"] == "active"]
    live.sort(key=lambda n: n[0].get("priority", "5") + n[0]["since"], reverse=False)
    if typ in ("rule", "flag"):
        full = [n for n in live if n[0].get("priority", "5") < str(INDEX_FROM_PRIORITY)]
        idx = [n for n in live if n[0].get("priority", "5") >= str(INDEX_FROM_PRIORITY)]
        out = "\n".join(_inline(b, fm["name"]) for fm, b in full)
        if idx:
            out += (f"\n\n**Lower-priority {typ}s — indexed only. "
                    "`scripts/recall.sh <name>` for the full text:**\n")
            out += "\n".join(f"- `{fm['name']}` — {_headline(b)}" for fm, b in idx)
        return out + "\n"
    return "\n".join(f"- {body}" for _, body in live)

def main():
    nodes = [parse(p) for p in sorted(NODES.glob("*.md"))]
    s = STATE.read_text()
    for typ, tag in (("flag", "FLAGS"), ("todo", "TODOS"), ("rule", "RULES")):
        start, end = f"<!-- GENERATED:{tag} -->", f"<!-- /GENERATED:{tag} -->"
        if start not in s:
            sys.exit(f"marker {start} missing from state/current.md")
        block = f"{start}\n{render(nodes, typ)}\n{end}"
        s = re.sub(re.escape(start) + r".*?" + re.escape(end), block, s, flags=re.S)
    STATE.write_text(s)
    n_active = sum(1 for fm, _ in nodes if fm["status"] == "active")
    print(f"regenerated from {len(nodes)} nodes ({n_active} active) → {STATE.stat().st_size:,} bytes")

if __name__ == "__main__":
    main()
