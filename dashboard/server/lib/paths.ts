import fs from 'node:fs'
import path from 'node:path'
import { USERS_DIR, REPO_ROOT } from '../env.js'

// Per-user coach workspace. EVERY per-user file access in EVERY route must go
// through these helpers — they are isolation enforcement point #1.

const USER_SUBDIRS = ['state', 'memory', 'reports', 'charts', 'uploads']

export function userDataDir(userId: string): string {
  // userId comes from the session (better-auth UUID) — never from client input.
  // basename() defends against a compromised/malformed id ever containing separators.
  const safe = path.basename(userId)
  return path.join(USERS_DIR, safe)
}

// Create the workspace for a new user, seeding wiki.md from the shared template.
export function createUserWorkspace(userId: string): string {
  const dir = userDataDir(userId)
  for (const sub of USER_SUBDIRS) fs.mkdirSync(path.join(dir, sub), { recursive: true })
  const wiki = path.join(dir, 'wiki.md')
  if (!fs.existsSync(wiki)) {
    const template = path.join(REPO_ROOT, 'templates', 'wiki-template.md')
    try {
      fs.copyFileSync(template, wiki)
    } catch {
      fs.writeFileSync(wiki, '# Athlete Wiki\n\n(To be filled during onboarding.)\n')
    }
  }
  const current = path.join(dir, 'state', 'current.md')
  if (!fs.existsSync(current)) {
    fs.writeFileSync(
      current,
      '# COACH CURRENT STATE\n\nNo committed plan yet — onboarding not complete.\n',
    )
  }
  return dir
}

// Resolve a client-supplied file name inside one of a user's subdirectories,
// with path-traversal protection. Returns null if outside or missing.
export function resolveUserFile(userId: string, subdir: string, rawName: string): string | null {
  const base = path.join(userDataDir(userId), subdir)
  const name = path.basename(rawName)
  const full = path.join(base, name)
  if (!full.startsWith(base + path.sep) && full !== base) return null
  if (!fs.existsSync(full)) return null
  return full
}
