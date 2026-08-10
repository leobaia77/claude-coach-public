import { saveCreds } from './creds.js'

const AUTH = 'https://cloud.ouraring.com/oauth/authorize'
const TOKEN = 'https://api.ouraring.com/oauth/token'
const API = 'https://api.ouraring.com/v2/usercollection'

export interface OuraCreds {
  access_token: string
  refresh_token: string
  expires_at: number // unix seconds
}

export function ouraConfigured(): boolean {
  return !!(process.env.OURA_CLIENT_ID && process.env.OURA_CLIENT_SECRET)
}

export function ouraAuthUrl(state: string): string {
  const redirect = `${process.env.APP_URL}/api/integrations/oura/callback`
  const p = new URLSearchParams({
    client_id: process.env.OURA_CLIENT_ID!,
    redirect_uri: redirect,
    response_type: 'code',
    scope: 'daily heartrate workout personal',
    state,
  })
  return `${AUTH}?${p}`
}

function basicAuth(): string {
  return Buffer.from(`${process.env.OURA_CLIENT_ID}:${process.env.OURA_CLIENT_SECRET}`).toString('base64')
}

export async function ouraExchangeCode(code: string): Promise<OuraCreds> {
  const redirect = `${process.env.APP_URL}/api/integrations/oura/callback`
  const res = await fetch(TOKEN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Authorization: `Basic ${basicAuth()}` },
    body: new URLSearchParams({ grant_type: 'authorization_code', code, redirect_uri: redirect }),
  })
  if (!res.ok) throw new Error(`Oura token exchange → HTTP ${res.status}`)
  const d = (await res.json()) as { access_token: string; refresh_token: string; expires_in: number }
  return { access_token: d.access_token, refresh_token: d.refresh_token, expires_at: Math.floor(Date.now() / 1000) + d.expires_in }
}

async function freshToken(userId: string, c: OuraCreds): Promise<string> {
  if (c.expires_at - 60 > Math.floor(Date.now() / 1000)) return c.access_token
  const res = await fetch(TOKEN, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Authorization: `Basic ${basicAuth()}` },
    body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: c.refresh_token }),
  })
  if (!res.ok) throw new Error(`Oura refresh → HTTP ${res.status}`)
  const d = (await res.json()) as { access_token: string; refresh_token: string; expires_in: number }
  const updated: OuraCreds = { access_token: d.access_token, refresh_token: d.refresh_token, expires_at: Math.floor(Date.now() / 1000) + d.expires_in }
  await saveCreds(userId, 'oura', updated)
  return updated.access_token
}

const COLLECTIONS: Record<string, string> = {
  readiness: 'daily_readiness',
  sleep: 'daily_sleep',
  activity: 'daily_activity',
  heartrate: 'heartrate',
}

export const oura = {
  getDaily: async (userId: string, c: OuraCreds, metric: string, start: string, end: string) => {
    const coll = COLLECTIONS[metric] ?? 'daily_readiness'
    const token = await freshToken(userId, c)
    const p = new URLSearchParams({ start_date: start, end_date: end })
    const res = await fetch(`${API}/${coll}?${p}`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) throw new Error(`Oura ${coll} → HTTP ${res.status}`)
    return res.json()
  },
}
