#!/usr/bin/env python3
"""Regenerate wiki.md §12: an index of wiki/entries/*.md plus the newest entry inline.

Entries carry frontmatter: date, title, type (ride|sleep|glucose|plan|audit|strength|note).
New coach-log entries are written as files in wiki/entries/ (YYYY-MM-DD-slug.md),
then this script re-renders §12. Never append prose to §12 directly.
"""
import re, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "wiki" / "entries"
WIKI = ROOT / "wiki.md"

def parse(p):
    s = p.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", s, re.S)
    fm = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    return {k.strip(): v.strip() for k, v in fm.items()}, m.group(2).strip(), p.name

def main():
    es = sorted((parse(p) for p in ENTRIES.glob("*.md")), key=lambda e: e[2], reverse=True)
    rows = "\n".join(f"| {fm['date']} | {fm.get('type','note')} | [{fm['title']}](wiki/entries/{name}) |"
                     for fm, _, name in es)
    latest = es[0]
    body = (f"> **{len(es)} entries live in `wiki/entries/` (one file each, frontmatter: date/title/type).**\n"
            f"> Write new entries as files there and re-run `scripts/build_wiki_index.py` — do not append prose here.\n"
            f"> Recall: `scripts/recall.sh <term>` greps entries + rules + ledger + memory.\n\n"
            f"### 📇 Index (newest first)\n| date | type | entry |\n|---|---|---|\n{rows}\n\n"
            f"### ⤵️ Latest entry (inline): {latest[0]['title']}\n\n{latest[1]}\n")
    s = WIKI.read_text()
    i = s.index("## 12. COACH AI NOTES")
    hdr_end = s.index("\n", i) + 1
    WIKI.write_text(s[:hdr_end] + "\n" + body)
    print(f"§12 rebuilt: {len(es)} entries indexed · wiki.md {WIKI.stat().st_size:,} bytes")

if __name__ == "__main__":
    main()
