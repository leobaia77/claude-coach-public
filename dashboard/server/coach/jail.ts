import path from 'node:path'
import fs from 'node:fs'

// The path jail is layer 3 of 4 in the agent's isolation (layers: cwd,
// disallowedTools, THIS, no additionalDirectories). It denies any file tool
// whose target resolves outside the user's own data directory, and blocks the
// entire shell/network tool class outright.
//
// canUseTool signature is intentionally loose-typed here so it works across
// @anthropic-ai/claude-agent-sdk minor versions; verified against the installed
// .d.ts. Return shape: { behavior: 'allow', updatedInput } | { behavior: 'deny', message }.

type ToolResult =
  | { behavior: 'allow'; updatedInput: Record<string, unknown> }
  | { behavior: 'deny'; message: string }

// File tools and which of their params carry a path.
const FILE_TOOLS: Record<string, string[]> = {
  Read: ['file_path'],
  Write: ['file_path'],
  Edit: ['file_path'],
  MultiEdit: ['file_path'],
  Glob: ['path'],
  Grep: ['path'],
  NotebookEdit: ['notebook_path'],
  NotebookRead: ['notebook_path'],
}

// Never available to web users — the whole shell/network/subagent class.
const BANNED = new Set([
  'Bash',
  'BashOutput',
  'KillShell',
  'KillBash',
  'WebFetch',
  'WebSearch',
  'Task',
  'ExitPlanMode',
])

export function makeJail(userDir: string, audit: (action: string, detail: unknown) => void) {
  // Resolve symlinks once at construction. With Bash banned the agent cannot
  // create new symlinks mid-session, so this snapshot stays valid.
  const root = fs.realpathSync(userDir)

  return async (toolName: string, input: Record<string, unknown>): Promise<ToolResult> => {
    if (BANNED.has(toolName)) {
      audit('jail.deny', { tool: toolName, reason: 'banned' })
      return { behavior: 'deny', message: `${toolName} is not available in the coach workspace.` }
    }

    const pathParams = FILE_TOOLS[toolName]
    if (pathParams) {
      for (const p of pathParams) {
        const raw = input[p]
        if (raw == null) continue // e.g. Grep with no path defaults to cwd (= userDir) — fine
        const resolved = path.resolve(root, String(raw))
        if (resolved !== root && !resolved.startsWith(root + path.sep)) {
          audit('jail.deny', { tool: toolName, param: p, value: String(raw) })
          return { behavior: 'deny', message: 'That path is outside your coach workspace.' }
        }
      }
    }

    return { behavior: 'allow', updatedInput: input }
  }
}
