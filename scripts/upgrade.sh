#!/usr/bin/env bash
# Upgrade claude-coach to the latest release.
#
# Your personal data (wiki.md, state/, memory/, metrics/, charts/, reports/) is
# gitignored and is NEVER touched by this script — only tracked code is updated.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▸ current version: $(cat VERSION 2>/dev/null || echo unknown)"

if [[ -n "$(git status --porcelain -- . ':!wiki.md' ':!state' ':!memory' ':!metrics' ':!charts' ':!reports' 2>/dev/null)" ]]; then
  echo "⚠️  You have local changes to tracked files."
  echo "   Commit or stash them first, then re-run. Your personal data is untracked and safe either way."
  git status --short -- . ':!wiki.md' ':!state' ':!memory' ':!metrics' ':!charts' ':!reports' | head
  exit 1
fi

echo "▸ pulling…"
git pull --ff-only

if [[ -f dashboard/package.json ]]; then
  echo "▸ updating dashboard deps…"
  (cd dashboard && npm install --silent)
fi

echo "▸ verifying python modules…"
python3 - <<'PY'
import importlib, sys
ok = True
for m in ("coachcalc.strength", "coachcalc.nutrition", "coachcalc.pmc",
          "coachcalc.rideeval", "bikeplan.plan", "bikeplan.optimizer"):
    try:
        importlib.import_module(m)
    except Exception as e:
        print(f"  ✗ {m}: {e}"); ok = False
print("  ✓ all modules import" if ok else "  ✗ some modules failed")
sys.exit(0 if ok else 1)
PY

echo "▸ now at version: $(cat VERSION)"
echo
echo "✅ Upgrade complete. See CHANGELOG.md for what changed."
