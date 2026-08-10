import { sqliteTable, text, integer, real, uniqueIndex, index } from 'drizzle-orm/sqlite-core'

/* ------------------------------------------------------------------ */
/*  better-auth core tables (shapes match better-auth v1.6 drizzle     */
/*  adapter defaults; `role` + `onboardingStage` are additionalFields) */
/* ------------------------------------------------------------------ */

export const user = sqliteTable('user', {
  id: text('id').primaryKey(),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  emailVerified: integer('email_verified', { mode: 'boolean' }).notNull().default(false),
  image: text('image'),
  role: text('role').notNull().default('user'), // 'admin' | 'user'
  // 'account' -> 'anthropic_key' -> 'integrations' -> 'intake' -> 'done'
  onboardingStage: text('onboarding_stage').notNull().default('account'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
})

export const session = sqliteTable('session', {
  id: text('id').primaryKey(),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  token: text('token').notNull().unique(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
  ipAddress: text('ip_address'),
  userAgent: text('user_agent'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
})

export const account = sqliteTable('account', {
  id: text('id').primaryKey(),
  userId: text('user_id')
    .notNull()
    .references(() => user.id, { onDelete: 'cascade' }),
  accountId: text('account_id').notNull(),
  providerId: text('provider_id').notNull(),
  accessToken: text('access_token'),
  refreshToken: text('refresh_token'),
  idToken: text('id_token'),
  accessTokenExpiresAt: integer('access_token_expires_at', { mode: 'timestamp' }),
  refreshTokenExpiresAt: integer('refresh_token_expires_at', { mode: 'timestamp' }),
  scope: text('scope'),
  password: text('password'), // scrypt hash for email+password provider
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
})

export const verification = sqliteTable('verification', {
  id: text('id').primaryKey(),
  identifier: text('identifier').notNull(),
  value: text('value').notNull(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }).notNull(),
  createdAt: integer('created_at', { mode: 'timestamp' }),
  updatedAt: integer('updated_at', { mode: 'timestamp' }),
})

/* ------------------------------------------------------------------ */
/*  app tables                                                         */
/* ------------------------------------------------------------------ */

export const invites = sqliteTable('invites', {
  id: text('id').primaryKey(), // crypto.randomUUID()
  code: text('code').notNull().unique(), // short human code e.g. 'KX7-Q2M-9DP'
  email: text('email'), // optional lock-to-email
  note: text('note'),
  createdBy: text('created_by').references(() => user.id), // null = system bootstrap invite
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  expiresAt: integer('expires_at', { mode: 'timestamp' }),
  usedBy: text('used_by').references(() => user.id),
  usedAt: integer('used_at', { mode: 'timestamp' }),
})

export const userSettings = sqliteTable('user_settings', {
  userId: text('user_id')
    .primaryKey()
    .references(() => user.id, { onDelete: 'cascade' }),
  encryptedAnthropicKey: text('encrypted_anthropic_key'), // AES-256-GCM blob, null until set
  anthropicKeyLast4: text('anthropic_key_last4'), // display only
  goals: text('goals'), // athlete's headline goal(s), user-editable on the dashboard
  coachModel: text('coach_model').notNull().default('claude-sonnet-4-6'),
  timezone: text('timezone').notNull().default('America/Los_Angeles'),
  weightUnit: text('weight_unit').notNull().default('lb'),
  weeklyAutoCheckin: integer('weekly_auto_checkin', { mode: 'boolean' }).notNull().default(false),
  weeklyEmail: integer('weekly_email', { mode: 'boolean' }).notNull().default(true),
  calendarFeedToken: text('calendar_feed_token').notNull(), // random ≥128-bit, for /calendar.ics?token=
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
})

export const integrations = sqliteTable(
  'integrations',
  {
    id: text('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    provider: text('provider').notNull(), // 'hevy' | 'strava' | 'oura' | 'garmin'
    encryptedCredentials: text('encrypted_credentials').notNull(), // AES-GCM(JSON)
    status: text('status').notNull().default('connected'), // 'connected' | 'error' | 'disconnected'
    lastSyncAt: integer('last_sync_at', { mode: 'timestamp' }),
    lastError: text('last_error'),
    createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
    updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
  },
  (t) => [uniqueIndex('integrations_user_provider').on(t.userId, t.provider)],
)

export const chatSessions = sqliteTable(
  'chat_sessions',
  {
    id: text('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    sdkSessionId: text('sdk_session_id'), // from Agent SDK result msg (resume)
    title: text('title').notNull(), // first user msg, truncated 60 chars
    kind: text('kind').notNull().default('chat'), // 'chat' | 'onboarding' | 'weekly'
    createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
    lastMessageAt: integer('last_message_at', { mode: 'timestamp' }).notNull(),
  },
  (t) => [index('chat_sessions_user').on(t.userId)],
)

export const metricsCache = sqliteTable(
  'metrics_cache',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    userId: text('user_id')
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    date: text('date').notNull(), // 'YYYY-MM-DD' in user's tz
    metric: text('metric').notNull(), // 'hrv'|'sleep_hours'|'weight_lb'|'ride_tss'|...
    value: real('value').notNull(),
    source: text('source').notNull(), // 'oura'|'garmin'|'hevy'|'strava'|'manual'
    createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  },
  (t) => [uniqueIndex('metrics_user_date_metric').on(t.userId, t.date, t.metric, t.source)],
)

export const auditLog = sqliteTable(
  'audit_log',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    userId: text('user_id'), // null for system jobs
    action: text('action').notNull(), // 'login'|'chat.start'|'jail.deny'|'integration.connect'|'key.set'|...
    detail: text('detail'), // JSON string — NEVER secrets
    createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  },
  (t) => [index('audit_user').on(t.userId), index('audit_action').on(t.action)],
)
