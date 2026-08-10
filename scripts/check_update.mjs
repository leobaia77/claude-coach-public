#!/usr/bin/env node
/**
 * Update checker for claude-coach.
 *
 * Compares the local VERSION file against the latest GitHub release and, if a
 * newer one exists, prints what changed and how to upgrade.
 *
 * PRIVACY: this makes ONE unauthenticated GET to api.github.com to read the
 * public release list. It sends no telemetry, no identifiers, and nothing about
 * you, your data, or your training. Nothing leaves your machine. Disable it
 * entirely with COACH_NO_UPDATE_CHECK=1.
 *
 * It is deliberately fail-quiet: any network/parse error exits 0 silently so a
 * flaky connection can never block a coaching session.
 *
 *   node scripts/check_update.mjs           # human-readable, cached 24h
 *   node scripts/check_update.mjs --force   # ignore cache
 *   node scripts/check_update.mjs --json    # machine-readable
 *   node scripts/check_update.mjs --quiet   # print only if an update exists
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const REPO = process.env.COACH_REPO || 'leobaia77/claude-coach-public';
const CACHE = join(ROOT, '.update-check.json');
const CACHE_MS = 24 * 60 * 60 * 1000;

const args = process.argv.slice(2);
const FORCE = args.includes('--force');
const JSON_OUT = args.includes('--json');
const QUIET = args.includes('--quiet');

if (process.env.COACH_NO_UPDATE_CHECK === '1') process.exit(0);

const local = existsSync(join(ROOT, 'VERSION'))
  ? readFileSync(join(ROOT, 'VERSION'), 'utf8').trim()
  : '0.0.0';

/** semver compare: returns 1 if a>b, -1 if a<b, 0 equal. Ignores build metadata. */
function cmp(a, b) {
  const parse = (v) => String(v).replace(/^v/, '').split('+')[0].split('-')[0]
    .split('.').map((n) => parseInt(n, 10) || 0);
  const [x, y] = [parse(a), parse(b)];
  for (let i = 0; i < 3; i++) {
    if ((x[i] || 0) > (y[i] || 0)) return 1;
    if ((x[i] || 0) < (y[i] || 0)) return -1;
  }
  return 0;
}

function readCache() {
  try {
    const c = JSON.parse(readFileSync(CACHE, 'utf8'));
    if (Date.now() - c.checkedAt < CACHE_MS) return c;
  } catch { /* no cache */ }
  return null;
}

async function fetchLatest() {
  const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
    headers: { 'Accept': 'application/vnd.github+json', 'User-Agent': 'claude-coach-update-check' },
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const r = await res.json();
  return { version: (r.tag_name || '').replace(/^v/, ''), notes: r.body || '', url: r.html_url || '' };
}

function render({ version, notes, url }) {
  const lines = String(notes).split('\n')
    .map((l) => l.trim())
    .filter((l) => l.startsWith('-') || l.startsWith('*'))
    .slice(0, 6);
  const bar = '─'.repeat(64);
  let out = `\n\x1b[36m${bar}\x1b[0m\n`;
  out += `\x1b[1m🔔 claude-coach ${version} is available\x1b[0m  (you have ${local})\n`;
  if (lines.length) {
    out += `\n\x1b[1mWhat's new:\x1b[0m\n`;
    for (const l of lines) out += `  ${l.replace(/^[-*]\s*/, '• ')}\n`;
  }
  out += `\n\x1b[1mUpgrade:\x1b[0m  git pull && ./scripts/upgrade.sh\n`;
  if (url) out += `\x1b[2m${url}\x1b[0m\n`;
  out += `\x1b[2mSilence with COACH_NO_UPDATE_CHECK=1\x1b[0m\n`;
  out += `\x1b[36m${bar}\x1b[0m\n`;
  return out;
}

(async () => {
  let latest = FORCE ? null : readCache()?.latest;
  if (!latest) {
    try {
      latest = await fetchLatest();
      mkdirSync(dirname(CACHE), { recursive: true });
      writeFileSync(CACHE, JSON.stringify({ checkedAt: Date.now(), latest }));
    } catch {
      process.exit(0); // fail quiet — never block a session
    }
  }
  const behind = latest.version && cmp(latest.version, local) > 0;
  if (JSON_OUT) {
    console.log(JSON.stringify({ local, latest: latest.version, updateAvailable: !!behind }));
    process.exit(0);
  }
  if (behind) process.stdout.write(render(latest));
  else if (!QUIET) console.log(`claude-coach ${local} — up to date.`);
})();
