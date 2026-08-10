// Auth-aware client for the per-user coach API. All requests ride the
// better-auth session cookie (same origin, so cookies attach automatically).

export interface MeResponse {
  user: { id: string; email: string; name: string; role: string; onboardingStage: string }
  settings: {
    coachModel: string
    timezone: string
    weightUnit: string
    weeklyAutoCheckin: boolean
    weeklyEmail: boolean
    hasAnthropicKey: boolean
    anthropicKeyLast4: string | null
    goals: string | null
  } | null
  integrations: Array<{ provider: string; status: string; lastSyncAt: number | null }>
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: 'include', ...init })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.error || detail
    } catch {
      /* non-json */
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export const getMe = () => j<MeResponse>('/api/me')
export const getCoachState = () => j<Record<string, unknown>>('/api/coach/state')
export const getCoachReports = () => j<Array<{ id: string; title: string; date: string; type: string; summary: string; file: string }>>('/api/coach/reports')
export const coachReportUrl = (file: string) => `/api/coach/reports/file/${encodeURIComponent(file)}`

export const setAnthropicKey = (apiKey: string) =>
  j<{ ok: boolean; last4: string }>('/api/settings/anthropic-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiKey }),
  })

export const clearAnthropicKey = () => j('/api/settings/anthropic-key', { method: 'DELETE' })

export const patchSettings = (patch: Record<string, unknown>) =>
  j('/api/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })

export const advanceOnboarding = (stage: string) =>
  j('/api/onboarding/advance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage }),
  })

// Integrations
export const getIntegrations = () =>
  j<{ integrations: Array<{ provider: string; status: string; lastSyncAt: number | null; lastError: string | null }>; available: Record<string, boolean> }>('/api/integrations')
export const connectHevy = (apiKey: string) =>
  j('/api/integrations/hevy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ apiKey }) })
export const disconnectIntegration = (provider: string) =>
  j(`/api/integrations/${provider}`, { method: 'DELETE' })
// Upload a document (PDF/image/csv) into the user's uploads/ folder for the
// coach to process. Sends the raw file with the filename in the query.
export async function uploadDocument(file: File): Promise<{ ok: boolean; file: string; relPath: string }> {
  const res = await fetch(`/api/coach/uploads?name=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body: file,
  })
  if (!res.ok) {
    let d = `HTTP ${res.status}`
    try { d = (await res.json()).error || d } catch { /* */ }
    throw new Error(d)
  }
  return (await res.json()) as { ok: boolean; file: string; relPath: string }
}

export const saveDexa = (body: { date?: string; bodyFatPct?: number; leanMassLb?: number }) =>
  j<{ ok: boolean; saved: number }>('/api/integrations/dexa', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

// Admin
export const getAdminUsers = () => j<Array<Record<string, unknown>>>('/api/admin/users')
export const getAdminInvites = () => j<Array<Record<string, unknown>>>('/api/admin/invites')
export const createInvite = (body: { email?: string; note?: string; expiresInDays?: number }) =>
  j<{ code: string; url: string }>('/api/admin/invites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export interface CoachStreamHandlers {
  onText: (t: string) => void
  onTool?: (name: string) => void
  onDone?: (sessionId?: string) => void
  onError?: (err: string) => void
}

// Stream a coach turn over SSE from the per-user endpoint.
export async function streamCoach(
  message: string,
  sessionId: string | undefined,
  kind: 'chat' | 'onboarding' | 'weekly',
  h: CoachStreamHandlers,
): Promise<void> {
  let res: Response
  try {
    res = await fetch('/api/coach/chat', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, sessionId, kind }),
    })
  } catch (err) {
    h.onError?.(err instanceof Error ? err.message : 'network error')
    return
  }
  if (!res.ok || !res.body) {
    h.onError?.(`HTTP ${res.status}`)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const chunks = buf.split('\n\n')
    buf = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const dataLine = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (!dataLine) continue
      const payload = dataLine.slice(5).trim()
      if (!payload) continue
      let evt: { type: string; text?: string; name?: string; sessionId?: string; error?: string }
      try {
        evt = JSON.parse(payload)
      } catch {
        continue
      }
      if (evt.type === 'text' && evt.text) h.onText(evt.text)
      else if (evt.type === 'tool' && evt.name) h.onTool?.(evt.name)
      else if (evt.type === 'done') h.onDone?.(evt.sessionId)
      else if (evt.type === 'error' && evt.error) h.onError?.(evt.error)
    }
  }
}
