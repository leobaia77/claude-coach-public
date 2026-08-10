import { betterAuth } from 'better-auth'
import { drizzleAdapter } from 'better-auth/adapters/drizzle'
import { APIError, createAuthMiddleware } from 'better-auth/api'
import { and, eq, isNull } from 'drizzle-orm'
import { db } from './db/client.js'
import * as schema from './db/schema.js'
import { createUserWorkspace } from './lib/paths.js'
import { randomToken } from './lib/crypto.js'
import { audit } from './lib/audit.js'

const APP_URL = process.env.APP_URL || 'http://localhost:8787'
const ADMIN_EMAIL = (process.env.ADMIN_EMAIL || '').toLowerCase()

// Hand-off between the signup `before` hook (which sees the invite code) and the
// user-create `after` hook (which doesn't). Keyed by lowercase email; single
// process, and email is unique in the user table, so this is race-safe.
const pendingInviteByEmail = new Map<string, string>()

export const auth = betterAuth({
  baseURL: APP_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  // Prod is same-origin (Express serves the built frontend). The localhost
  // entries let the split vite dev server (:4280 → api :8787) authenticate.
  trustedOrigins: [APP_URL, 'http://localhost:4280', 'http://localhost:8787'],
  database: drizzleAdapter(db, {
    provider: 'sqlite',
    schema: {
      user: schema.user,
      session: schema.session,
      account: schema.account,
      verification: schema.verification,
    },
  }),
  emailAndPassword: {
    enabled: true,
    minPasswordLength: 10,
  },
  user: {
    additionalFields: {
      role: { type: 'string', defaultValue: 'user', input: false },
      onboardingStage: { type: 'string', defaultValue: 'account', input: false },
    },
  },
  session: {
    expiresIn: 60 * 60 * 24 * 30, // 30 days
    updateAge: 60 * 60 * 24, // refresh expiry daily
  },
  advanced: {
    // Behind Railway's proxy; cookies must still be Secure in prod.
    useSecureCookies: APP_URL.startsWith('https://'),
    // Resolve the real client IP from the proxy's forwarded header so the
    // rate limiter buckets per-client (not one shared bucket). Express's
    // `trust proxy` handles the socket side; this tells better-auth which
    // header to read.
    ipAddress: {
      ipAddressHeaders: ['x-forwarded-for'],
    },
  },
  hooks: {
    // Invite gate: signup requires a valid, unused, unexpired invite code.
    before: createAuthMiddleware(async (ctx) => {
      if (ctx.path !== '/sign-up/email') return
      const body = ctx.body as { email?: string; inviteCode?: string } | undefined
      const code = (body?.inviteCode || '').trim().toUpperCase()
      if (!code) throw new APIError('BAD_REQUEST', { message: 'Invite code required' })
      const [invite] = await db
        .select()
        .from(schema.invites)
        .where(and(eq(schema.invites.code, code), isNull(schema.invites.usedBy)))
        .limit(1)
      if (!invite) throw new APIError('BAD_REQUEST', { message: 'Invalid or already-used invite code' })
      if (invite.expiresAt && invite.expiresAt.getTime() < Date.now())
        throw new APIError('BAD_REQUEST', { message: 'Invite code expired' })
      if (invite.email && invite.email.toLowerCase() !== (body?.email || '').toLowerCase())
        throw new APIError('BAD_REQUEST', { message: 'Invite code is locked to a different email' })
      pendingInviteByEmail.set((body?.email || '').toLowerCase(), invite.id)
    }),
  },
  databaseHooks: {
    user: {
      create: {
        after: async (newUser) => {
          const now = new Date()
          // Mark the exact invite validated in the `before` hook as used.
          const inviteId = pendingInviteByEmail.get(newUser.email.toLowerCase())
          pendingInviteByEmail.delete(newUser.email.toLowerCase())
          if (inviteId) {
            await db
              .update(schema.invites)
              .set({ usedBy: newUser.id, usedAt: now })
              .where(eq(schema.invites.id, inviteId))
          }

          // Admin bootstrap: ADMIN_EMAIL signup becomes admin automatically.
          if (ADMIN_EMAIL && newUser.email.toLowerCase() === ADMIN_EMAIL) {
            await db.update(schema.user).set({ role: 'admin' }).where(eq(schema.user.id, newUser.id))
          }

          // Per-user settings row + coach workspace (wiki from template).
          await db.insert(schema.userSettings).values({
            userId: newUser.id,
            calendarFeedToken: randomToken(24),
            updatedAt: now,
          })
          createUserWorkspace(newUser.id)
          audit(newUser.id, 'user.signup', { email: newUser.email })
        },
      },
    },
  },
})

export type AuthSession = typeof auth.$Infer.Session
