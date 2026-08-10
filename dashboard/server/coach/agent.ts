import { query } from '@anthropic-ai/claude-agent-sdk'
import path from 'node:path'
import { eq } from 'drizzle-orm'
import { db } from '../db/client.js'
import { userSettings, integrations } from '../db/schema.js'
import { DATA_DIR } from '../env.js'
import { userDataDir } from '../lib/paths.js'
import { decrypt } from '../lib/crypto.js'
import { audit } from '../lib/audit.js'
import { buildCoachPrompt } from './prompt.js'
import { makeJail } from './jail.js'
import { buildUserToolServer } from './tools.js'
import type { Provider } from '../integrations/creds.js'
import type { SessionUser } from '../middleware/requireAuth.js'

export interface CoachEvent {
  type: 'text' | 'tool' | 'done' | 'error'
  text?: string
  name?: string
  sessionId?: string
  cost?: number
  error?: string
}

// Build a minimal environment for the agent subprocess. NEVER spread
// process.env — that would leak MASTER_ENCRYPTION_KEY / BETTER_AUTH_SECRET /
// OAuth secrets into the agent. Only PATH/HOME-class vars + the user's own key.
function safeBaseEnv(): Record<string, string> {
  const keep = ['PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ', 'TMPDIR', 'NODE_ENV']
  const out: Record<string, string> = {}
  for (const k of keep) if (process.env[k]) out[k] = process.env[k] as string
  return out
}

export class NoKeyError extends Error {}

// Run one coach turn for a user, streaming events to `onEvent`. Path-jailed to
// the user's data dir; uses the user's own decrypted Anthropic key.
export async function runCoachQuery(
  user: SessionUser,
  message: string,
  opts: { resume?: string; kind?: 'chat' | 'onboarding' | 'weekly' },
  onEvent: (e: CoachEvent) => void,
): Promise<void> {
  const [settings] = await db
    .select()
    .from(userSettings)
    .where(eq(userSettings.userId, user.id))
    .limit(1)

  if (!settings?.encryptedAnthropicKey) {
    throw new NoKeyError('no anthropic key')
  }
  const apiKey = decrypt(settings.encryptedAnthropicKey)

  const connected = (
    await db
      .select({ provider: integrations.provider })
      .from(integrations)
      .where(eq(integrations.userId, user.id))
  ).map((r) => r.provider)

  const userDir = userDataDir(user.id)
  const systemPrompt = buildCoachPrompt(user, {
    athleteName: user.name,
    timezone: settings.timezone,
    weightUnit: settings.weightUnit,
    connectedIntegrations: connected,
    goals: settings.goals,
    kind: opts.kind,
  })

  const jailAudit = (action: string, detail: unknown) => audit(user.id, action, detail)

  const connectedSet = new Set(connected as Provider[])
  const coachTools = buildUserToolServer(user.id, connectedSet, { onboarding: opts.kind === 'onboarding' })

  audit(user.id, 'chat.start', { kind: opts.kind ?? 'chat', resume: !!opts.resume })

  const q = query({
    prompt: message,
    options: {
      cwd: userDir, // L1: relative paths land inside the user's dir
      systemPrompt,
      settingSources: [], // no CLAUDE.md/hooks/local MCP leakage
      permissionMode: 'default', // NOT bypassPermissions
      // L2: the shell/network/subagent class is never offered
      disallowedTools: ['Bash', 'WebFetch', 'WebSearch', 'Task'],
      allowedTools: ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'TodoWrite', 'mcp__coach'],
      // L3: allow/deny + realpath-prefix path check
      canUseTool: makeJail(userDir, jailAudit) as never,
      // L4: no extra roots
      additionalDirectories: [],
      // In-process coach tools (integrations + plan/dashboard) scoped to this user.
      mcpServers: { coach: coachTools },
      model: settings.coachModel,
      env: {
        ...safeBaseEnv(),
        ANTHROPIC_API_KEY: apiKey,
        // Session transcripts (and resume) persist on the volume across redeploys.
        CLAUDE_CONFIG_DIR: path.join(DATA_DIR, '.claude'),
      },
      ...(opts.resume ? { resume: opts.resume } : {}),
    } as never,
  })

  try {
    for await (const msg of q as AsyncIterable<Record<string, unknown>>) {
      if (msg.type === 'assistant') {
        const inner = msg.message as { content?: Array<{ type: string; text?: string; name?: string }> } | undefined
        for (const b of inner?.content ?? []) {
          if (b.type === 'text' && b.text) onEvent({ type: 'text', text: b.text })
          else if (b.type === 'tool_use' && b.name) onEvent({ type: 'tool', name: b.name })
        }
        if (msg.error) onEvent({ type: 'error', error: String(msg.error) })
      } else if (msg.type === 'result') {
        const r = msg as { session_id?: string; total_cost_usd?: number }
        onEvent({ type: 'done', sessionId: r.session_id, cost: r.total_cost_usd })
      }
    }
  } catch (err) {
    onEvent({ type: 'error', error: err instanceof Error ? err.message : String(err) })
  }
}
