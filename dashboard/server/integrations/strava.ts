import { saveCreds } from './creds.js'

const AUTH = 'https://www.strava.com/oauth/authorize'
const TOKEN = 'https://www.strava.com/oauth/token'
const API = 'https://www.strava.com/api/v3'

export interface StravaCreds {
  access_token: string
  refresh_token: string
  expires_at: number // unix seconds
  athlete_id?: number
}

export function stravaConfigured(): boolean {
  return !!(process.env.STRAVA_CLIENT_ID && process.env.STRAVA_CLIENT_SECRET)
}

export function stravaAuthUrl(state: string): string {
  const redirect = `${process.env.APP_URL}/api/integrations/strava/callback`
  const p = new URLSearchParams({
    client_id: process.env.STRAVA_CLIENT_ID!,
    redirect_uri: redirect,
    response_type: 'code',
    scope: 'read,activity:read_all',
    state,
    approval_prompt: 'auto',
  })
  return `${AUTH}?${p}`
}

export async function stravaExchangeCode(code: string): Promise<StravaCreds> {
  const res = await fetch(TOKEN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: process.env.STRAVA_CLIENT_ID,
      client_secret: process.env.STRAVA_CLIENT_SECRET,
      code,
      grant_type: 'authorization_code',
    }),
  })
  if (!res.ok) throw new Error(`Strava token exchange → HTTP ${res.status}`)
  const d = (await res.json()) as { access_token: string; refresh_token: string; expires_at: number; athlete?: { id: number } }
  return { access_token: d.access_token, refresh_token: d.refresh_token, expires_at: d.expires_at, athlete_id: d.athlete?.id }
}

// Return a valid access token, refreshing (and re-persisting) if near expiry.
async function freshToken(userId: string, c: StravaCreds): Promise<string> {
  if (c.expires_at - 60 > Math.floor(Date.now() / 1000)) return c.access_token
  const res = await fetch(TOKEN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: process.env.STRAVA_CLIENT_ID,
      client_secret: process.env.STRAVA_CLIENT_SECRET,
      refresh_token: c.refresh_token,
      grant_type: 'refresh_token',
    }),
  })
  if (!res.ok) throw new Error(`Strava refresh → HTTP ${res.status}`)
  const d = (await res.json()) as { access_token: string; refresh_token: string; expires_at: number }
  const updated: StravaCreds = { ...c, access_token: d.access_token, refresh_token: d.refresh_token, expires_at: d.expires_at }
  await saveCreds(userId, 'strava', updated)
  return updated.access_token
}

async function stravaGet(userId: string, c: StravaCreds, path: string): Promise<unknown> {
  const token = await freshToken(userId, c)
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`Strava ${path} → HTTP ${res.status}`)
  return res.json()
}

export const strava = {
  listActivities: (userId: string, c: StravaCreds, afterISO?: string, beforeISO?: string) => {
    const p = new URLSearchParams({ per_page: '30' })
    if (afterISO) p.set('after', String(Math.floor(new Date(afterISO).getTime() / 1000)))
    if (beforeISO) p.set('before', String(Math.floor(new Date(beforeISO).getTime() / 1000)))
    return stravaGet(userId, c, `/athlete/activities?${p}`)
  },
  getActivity: (userId: string, c: StravaCreds, id: number) => stravaGet(userId, c, `/activities/${id}`),
  getStreams: (userId: string, c: StravaCreds, id: number, keys: string) =>
    stravaGet(userId, c, `/activities/${id}/streams?keys=${keys}&key_by_type=true`),
}
