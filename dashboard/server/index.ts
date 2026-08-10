import express from 'express'
import fs from 'node:fs'
import path from 'node:path'
import {
  REPO_ROOT,
  WIKI_PATH,
  REPORTS_DIR,
  CHARTS_DIR,
  STATE_PATH,
  DIST_DIR,
  DATA_DIR,
  PORT,
  HOST,
  COACH_TOKEN,
} from './env.js'
import { toNodeHandler } from 'better-auth/node'
import { runMigrations } from './db/client.js'
import { cryptoSelfTest } from './lib/crypto.js'
import { auth } from './auth.js'
import { seedBootstrapInvite } from './bootstrap.js'
import { stateRouter } from './routes/state.js'
import { filesRouter, listReports, listCharts } from './routes/files.js'
import { chatRouter } from './routes/chat.js'
import { adminRouter } from './routes/admin.js'
import { meRouter } from './routes/me.js'
import { settingsRouter } from './routes/settings.js'
import { userChatRouter } from './routes/userChat.js'
import { userFilesRouter } from './routes/userFiles.js'
import { userStateRouter } from './routes/userState.js'
import { onboardingRouter } from './routes/onboarding.js'
import { integrationsRouter } from './routes/integrations.js'
import { uploadsRouter } from './routes/uploads.js'

runMigrations()
cryptoSelfTest()
await seedBootstrapInvite()

const app = express()

// Behind Railway's (and Cloudflare's) reverse proxy: trust the first proxy hop
// so req.ip / X-Forwarded-For resolve correctly and Secure cookies are set.
// Without this, session cookies + rate-limit IP buckets misbehave in prod.
app.set('trust proxy', 1)

// better-auth parses its own request bodies — MUST mount before express.json().
app.all('/api/auth/*', toNodeHandler(auth))

app.use(express.json({ limit: '1mb' }))

// Legacy shared-secret gate for the single-user endpoints (state/reports/
// charts/chat). New multi-user routes use per-user session auth instead and
// are exempt here; the legacy routes migrate to sessions in Phase 3.
const SESSION_AUTHED_PREFIXES = ['/me', '/admin', '/settings', '/coach', '/onboarding', '/integrations']
app.use('/api', (req, res, next) => {
  if (!COACH_TOKEN) return next()
  if (SESSION_AUTHED_PREFIXES.some((p) => req.path === p || req.path.startsWith(p + '/'))) return next()
  const bearer = (req.get('authorization') || '').replace(/^Bearer\s+/i, '')
  const tok = req.get('x-coach-token') || bearer || (req.query.token as string | undefined)
  if (tok === COACH_TOKEN) return next()
  res.status(401).json({ error: 'unauthorized' })
})

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    sources: {
      wiki: fs.existsSync(WIKI_PATH),
      reports: fs.existsSync(REPORTS_DIR),
      charts: fs.existsSync(CHARTS_DIR),
      state: fs.existsSync(STATE_PATH),
    },
  })
})

app.use(stateRouter)
app.use(filesRouter)
app.use(chatRouter)
app.use(meRouter)
app.use(adminRouter)
app.use(settingsRouter)
app.use(userStateRouter)
app.use(userFilesRouter)
app.use(userChatRouter)
app.use(onboardingRouter)
app.use(integrationsRouter)
app.use(uploadsRouter)

// Production: serve the built frontend as a single process.
if (fs.existsSync(DIST_DIR)) {
  app.use(express.static(DIST_DIR))
  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/api')) return next()
    res.sendFile(path.join(DIST_DIR, 'index.html'))
  })
}

app.listen(PORT, HOST, () => {
  console.log(`[coach-api] listening on http://${HOST}:${PORT}`)
  console.log(`[coach-api] auth: ${COACH_TOKEN ? 'token REQUIRED ✓' : 'OPEN'}`)
  if (!COACH_TOKEN && HOST === '0.0.0.0')
    console.warn('[coach-api] ⚠️  exposed on LAN with NO COACH_TOKEN — set one in .env')
  console.log(`[coach-api] repo root: ${REPO_ROOT}`)
  console.log(`[coach-api] data dir: ${DATA_DIR}`)
  console.log(`[coach-api] wiki: ${fs.existsSync(WIKI_PATH) ? 'found' : 'MISSING'} · reports: ${listReports().length} · charts: ${listCharts().length}`)
  const authMode = process.env.ANTHROPIC_API_KEY
    ? `API key ✓ (model ${process.env.COACH_MODEL || 'claude-sonnet-4-6'})`
    : process.env.CLAUDE_CODE_OAUTH_TOKEN
      ? 'oauth token ✓'
      : 'NONE — set ANTHROPIC_API_KEY in .env or run: claude setup-token'
  console.log(`[coach-api] chat auth: ${authMode}`)
})
