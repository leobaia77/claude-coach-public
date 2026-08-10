import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SERVER_DIR = path.dirname(fileURLToPath(import.meta.url))
export const DASHBOARD_DIR = path.resolve(SERVER_DIR, '..')
export const REPO_ROOT = path.resolve(DASHBOARD_DIR, '..')

// Load dashboard/.env (gitignored) — no dependency. Values already present in
// the process environment win (so Railway/launchd env vars override the file).
function loadLocalEnv() {
  try {
    const txt = fs.readFileSync(path.join(DASHBOARD_DIR, '.env'), 'utf8')
    for (const line of txt.split('\n')) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
      if (m && m[1] && !process.env[m[1]]) {
        process.env[m[1]] = m[2].replace(/^["']|["']$/g, '')
      }
    }
  } catch {
    /* no .env — fine */
  }
}
loadLocalEnv()

// Multi-user runtime data root. Locally defaults to <repo>/data (gitignored);
// on Railway set DATA_DIR=/data (persistent volume).
export const DATA_DIR = process.env.DATA_DIR || path.join(REPO_ROOT, 'data')
export const USERS_DIR = path.join(DATA_DIR, 'users')
fs.mkdirSync(USERS_DIR, { recursive: true })

// Single-athlete legacy paths (Leo's terminal-workflow files at the repo root).
// Still used by the current single-user endpoints; per-user routes replace them
// phase by phase.
export const WIKI_PATH = path.join(REPO_ROOT, 'wiki.md')
export const REPORTS_DIR = path.join(REPO_ROOT, 'reports')
export const CHARTS_DIR = path.join(REPO_ROOT, 'charts')
export const STATE_PATH = path.join(DASHBOARD_DIR, 'data', 'coach-state.json')
export const DIST_DIR = path.join(DASHBOARD_DIR, 'dist')

export const PORT = Number(process.env.PORT) || 8787
export const HOST = process.env.HOST || '0.0.0.0'

// Shared-secret gate for the legacy single-user API. Replaced by session auth
// in Phase 1; kept so behavior is unchanged until then.
export const COACH_TOKEN = process.env.COACH_TOKEN
