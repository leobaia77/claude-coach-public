import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { userDataDir } from '../lib/paths.js'
import type { SessionUser } from '../middleware/requireAuth.js'

const SERVER_DIR = path.dirname(fileURLToPath(import.meta.url))
const PROMPTS_DIR = path.join(SERVER_DIR, 'prompts')
const CORE_PATH = path.join(PROMPTS_DIR, 'COACH_CORE.md')

export interface PromptContext {
  athleteName: string
  timezone: string
  weightUnit: string
  connectedIntegrations: string[]
  goals?: string | null
  kind?: 'chat' | 'onboarding' | 'weekly'
}

// Build the per-user system prompt: generalized coach core + this user's
// placeholders + their current state file injected (the SessionStart hook
// doesn't run here since settingSources is []). All file paths the agent uses
// are RELATIVE, resolving inside its cwd (the user's data dir).
export function buildCoachPrompt(user: SessionUser, ctx: PromptContext): string {
  let core = ''
  try {
    core = fs.readFileSync(CORE_PATH, 'utf8')
  } catch {
    core = FALLBACK_CORE
  }

  const today = new Date().toISOString().slice(0, 10)
  core = core
    .replaceAll('{{ATHLETE_NAME}}', ctx.athleteName)
    .replaceAll('{{TIMEZONE}}', ctx.timezone)
    .replaceAll('{{WEIGHT_UNIT}}', ctx.weightUnit)
    .replaceAll('{{TODAY}}', today)
    .replaceAll(
      '{{CONNECTED_INTEGRATIONS}}',
      ctx.connectedIntegrations.length ? ctx.connectedIntegrations.join(', ') : 'none yet',
    )

  // Append the mode-specific prompt (onboarding / weekly check-in).
  if (ctx.kind === 'onboarding' || ctx.kind === 'weekly') {
    const file = ctx.kind === 'onboarding' ? 'ONBOARDING.md' : 'WEEKLY_CHECKIN.md'
    try {
      core += '\n\n' + fs.readFileSync(path.join(PROMPTS_DIR, file), 'utf8')
    } catch {
      /* mode prompt missing — core still works */
    }
  }

  // Inject the user's current state file (replaces the SessionStart hook).
  let current = ''
  try {
    current = fs.readFileSync(path.join(userDataDir(user.id), 'state', 'current.md'), 'utf8')
  } catch {
    /* pre-onboarding — no state yet */
  }
  if (current.trim()) {
    core += `\n\n---\n## CURRENT STATE (canonical — overrides anything older)\n\n${current}`
  }

  if (ctx.goals && ctx.goals.trim()) {
    core += `\n\n---\n## ATHLETE'S STATED GOAL (set by them on the dashboard)\n\n${ctx.goals.trim()}`
  }

  return core
}

// Minimal fallback if COACH_CORE.md is missing (Phase 4 writes the full file).
const FALLBACK_CORE = `You are a personal AI coach for endurance + strength athletes, accessed from a web dashboard chat.

Athlete: {{ATHLETE_NAME}} · timezone {{TIMEZONE}} · weights in {{WEIGHT_UNIT}} · today {{TODAY}}.
Connected data integrations: {{CONNECTED_INTEGRATIONS}}.

Your workspace is the current directory. Read and update these files with your tools:
- wiki.md — the athlete knowledge base (profile, baselines, zones, goals, logs)
- state/current.md — the canonical current-week plan and flags (keep it current)
- memory/*.md — your durable coaching notes
- reports/, charts/ — evaluation artifacts you generate

Be concise, evidence-based, and cite the data behind each claim. Report weights in {{WEIGHT_UNIT}}. When you learn something durable about the athlete, write it to memory/. Never claim a workout happened without data to back it.`
