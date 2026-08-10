import { db } from './db/client.js'
import { user, invites } from './db/schema.js'
import { inviteCode } from './lib/crypto.js'

// First-run bootstrap: with zero users, signup is impossible (invite-gated,
// and invites are admin-created). Seed one system invite and print it, so the
// admin (ADMIN_EMAIL) can create the first account.
export async function seedBootstrapInvite() {
  const [anyUser] = await db.select({ id: user.id }).from(user).limit(1)
  if (anyUser) return
  const [anyInvite] = await db.select({ id: invites.id, code: invites.code }).from(invites).limit(1)
  if (anyInvite) {
    console.log(`[bootstrap] no users yet — use existing invite code: ${anyInvite.code}`)
    return
  }
  const code = inviteCode()
  await db.insert(invites).values({
    id: crypto.randomUUID(),
    code,
    email: process.env.ADMIN_EMAIL || null, // lock to admin if configured
    note: 'system bootstrap invite (first run)',
    createdBy: null,
    createdAt: new Date(),
  })
  console.log(`[bootstrap] first-run invite code: ${code} (locked to ${process.env.ADMIN_EMAIL || 'any email'})`)
}
