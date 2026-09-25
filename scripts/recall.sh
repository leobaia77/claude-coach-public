#!/bin/bash
# recall.sh <terms> — "was this already instructed / already generated?"
# Greps every memory surface: rules nodes, state, ledger, wiki entries, wiki, CLAUDE.md, auto-memory.
[ -z "$1" ] && { echo "usage: scripts/recall.sh <search terms>"; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MEM="$HOME/.claude/projects/-Users-leonardoteixeira-Claude-coach/memory"
Q="$*"

# Exact node hit: print the WHOLE node. state/current.md injects priority-1 rules only, and
# even those are cut at <!--more--> — so "recall.sh <name>" is the documented way to get the
# full text back. Returning grep lines here would make the tiering lossy.
NODE="$ROOT/state/rules/$Q.md"
if [ -f "$NODE" ]; then
  echo "── NODE $Q (full) ──"
  sed '/^<!--more-->$/d' "$NODE"
  echo
fi

for area in "RULES+FLAGS:$ROOT/state/rules" "STATE:$ROOT/state/current.md" \
            "LEDGER:$ROOT/state/ledger.csv" "WIKI ENTRIES:$ROOT/wiki/entries" \
            "WIKI:$ROOT/wiki.md" "CLAUDE.md:$ROOT/CLAUDE.md" "AUTO-MEMORY:$MEM"; do
  name="${area%%:*}"; path="${area#*:}"
  hits=$(grep -riIn --include='*.md' --include='*.csv' -E "$Q" "$path" 2>/dev/null | head -8)
  [ -n "$hits" ] && { echo "── $name ──"; echo "$hits" | sed "s|$ROOT/||;s|$MEM/|memory/|"; }
done
